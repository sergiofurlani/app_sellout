"""Carrega no banco os movimentos de entrada que o coletor extraiu do ERP.

    python -m coletor.estoque_inicial --de 2026-01-01 -s movimentos.csv
    python -m sellout.db.movimentos movimentos.csv --aplicar

O CSV é o detalhe por item do evento 106 — uma linha por produto, cor e
tamanho, com data, origem, destino e romaneio. Aqui ele vira linha da tabela
`movimento`, que é o que permite o Estoque inicial ser **derivado** em vez de
digitado (D13).

O `tipo` do CSV diz a direção; o `tipo` do banco diz o motivo:

    entrada      ELENA ES -> loja        -> transferencia   (+)
    saida        loja -> ELENA ES        -> devolucao       (-)
    realocacao   loja -> loja            -> realocacao      (soma zero)

Realocação entra com as **duas** pontas, positiva no destino e negativa na
origem. No consolidado ela some, como manda a D13 — mas por filial ela existe,
e a tela nova vai precisar dela.

**Repetir a carga é seguro.** O índice `movimento_unico_erp` casa documento,
evento, produto, cor, tamanho e filial; linha repetida é ignorada em vez de
duplicar o estoque. Isso importa porque a extração vai ser refeita toda semana
com janelas que se sobrepõem.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date

from .conexao import conectar, por_que_nao

EVENTO = 106

# direção do coletor -> (tipo no banco, de qual coluna sai a filial, sinal)
DIRECAO = {
    "entrada": (("transferencia", "destino", +1),),
    "saida": (("devolucao", "origem", -1),),
    "realocacao": (("realocacao", "destino", +1), ("realocacao", "origem", -1)),
}


def dia(t: str) -> date:
    return date.fromisoformat(t)


def _data(texto: str):
    """O CSV sai do `str()` de um date; aceita também ISO com hora."""
    t = (texto or "").strip()
    if not t:
        return None
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        return None


def ler(caminho: str) -> tuple[list[dict], dict, list[str]]:
    """CSV do coletor -> linhas prontas para a tabela movimento."""
    linhas, avisos = [], []
    resumo = Counter()
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for n, r in enumerate(csv.DictReader(f, delimiter=";"), start=2):
            direcao = (r.get("tipo") or "").strip().lower()
            if direcao not in DIRECAO:
                resumo["fora do sellout"] += 1
                continue
            data = _data(r.get("data"))
            codigo = (r.get("codigo") or "").strip()
            if not data or not codigo:
                avisos.append(f"linha {n}: sem data ou sem codigo — pulada")
                continue
            try:
                quant = float(r.get("quant") or 0)
            except ValueError:
                avisos.append(f"linha {n}: quantidade ilegivel {r.get('quant')!r}")
                continue
            if quant <= 0:
                continue
            documento = (r.get("romaneio") or r.get("nota") or "").strip() or None
            for tipo, coluna, sinal in DIRECAO[direcao]:
                filial = (r.get(coluna) or "").strip()
                linhas.append({
                    "data": data,
                    "codigo": codigo,
                    "codigo_cor": (r.get("cod_cor") or "").strip(),
                    "tamanho": (r.get("tamanho") or "").strip() or None,
                    "filial": filial or None,
                    "tipo": tipo,
                    "qtd": sinal * quant,
                    "evento_mn": EVENTO,
                    "documento": documento,
                    "observacao": None,
                })
                resumo[tipo] += 1
                resumo[f"pecas {tipo}"] += sinal * quant
    return linhas, dict(resumo), avisos


def gravar(linhas: list[dict]) -> tuple[int, int]:
    """Devolve (inseridas, ignoradas por já existirem)."""
    if not linhas:
        return 0, 0
    sql = ("INSERT INTO movimento (data, codigo, codigo_cor, tamanho, filial, "
           "  tipo, qtd, evento_mn, documento, observacao) "
           "VALUES (%(data)s, %(codigo)s, %(codigo_cor)s, %(tamanho)s, %(filial)s, "
           "  %(tipo)s, %(qtd)s, %(evento_mn)s, %(documento)s, %(observacao)s) "
           "ON CONFLICT DO NOTHING")
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM movimento")
        antes = cur.fetchone()[0]
        cur.executemany(sql, linhas)
        cur.execute("SELECT count(*) FROM movimento")
        depois = cur.fetchone()[0]
    inseridas = depois - antes
    return inseridas, len(linhas) - inseridas


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Carrega os movimentos do evento 106 no banco")
    p.add_argument("arquivo", help="CSV do coletor.estoque_inicial -s")
    p.add_argument("--aplicar", action="store_true",
                   help="sem isto, so mostra o que faria")
    args = p.parse_args(argv)

    linhas, resumo, avisos = ler(args.arquivo)
    print(f"\n{args.arquivo}")
    for k, v in sorted(resumo.items()):
        print(f"  {k:24} {v:,.0f}")
    for a in avisos[:10]:
        print(f"  AVISO: {a}")
    if len(avisos) > 10:
        print(f"  ... e mais {len(avisos) - 10} aviso(s)")
    if not linhas:
        print("\n  Nada para gravar.")
        return 1

    datas = [l["data"] for l in linhas]
    print(f"\n  {len(linhas):,} linha(s), de {min(datas)} a {max(datas)}")

    if not args.aplicar:
        print("\n  Ensaio. Repita com --aplicar para gravar.")
        return 0

    motivo = por_que_nao()
    if motivo:
        print(f"\n  Nao gravei: {motivo}")
        return 1
    inseridas, ja_existiam = gravar(linhas)
    print(f"\n  inseridas: {inseridas:,}   ja existiam: {ja_existiam:,}")
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(*), min(data), max(data), sum(qtd) FROM movimento")
        n, de, ate, total = cur.fetchone()
        print(f"  no banco: {n:,} movimento(s), de {de} a {ate}, saldo {total:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
