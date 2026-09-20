"""Extrai o Estoque inicial das lojas a partir do evento 106.

O que a D13 procurava. A peça entra na loja pela **venda entre filiais** da
Elena, evento interno **106** (`00108`), e sai da loja pelo mesmo evento quando
volta para a matriz.

    python -m coletor.estoque_inicial --de 2026-08-31 --ate 2026-09-07
    python -m coletor.estoque_inicial --de 2026-08-31 --ate 2026-09-07 -s entradas.csv

A direção está em dois campos que não se parecem com filial:

    cod_filial   = quem emite  -> origem
    cod_cliente  = para quem   -> destino

Na venda entre filiais a loja é **cliente** da Elena. Foi o que escondeu o
destino durante toda a investigação: procurávamos `filial_destino`.

Regras (D13):

  ELENA ES -> loja      entra no Estoque inicial daquela loja
  loja -> ELENA ES      sai (devolução para a matriz)
  loja -> loja          realocação: sai de uma, entra na outra, nada de novo
                        no conjunto
  ELENA ES -> cliente   atacado, fora do sellout (evento 108, não 106)

O item traz `cod_produto`, `cod_cor`, `desc_cor` e `tamanho` — os códigos do
ERP, os mesmos que a planilha usa. Não precisa de de-para de cor.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date

from . import mn

EVENTO = 106

MATRIZ = ("ELENA ES", "ELENA SP", "ELENATIMES")
LOJAS = ("EGREY JDS", "IGUATEMI")

# Peça acabada da aba Producao no mesmo período, como teto de sanidade.
TETO_PRODUCAO = 826


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def e_matriz(nome: str) -> bool:
    return any(m in nome.upper() for m in MATRIZ)


def e_loja(nome: str) -> bool:
    return nome.strip().upper() in {l.upper() for l in LOJAS}


def classifica(origem: str, destino: str) -> str:
    """Devolve entrada, saida, realocacao ou fora."""
    o, d = origem.strip(), destino.strip()
    if e_matriz(o) and e_loja(d):
        return "entrada"
    if e_loja(o) and e_matriz(d):
        return "saida"
    if e_loja(o) and e_loja(d):
        return "realocacao"
    return "fora"


def coleta(de: date, ate: date):
    """Movimentos do evento 106, um registro por item, já classificados."""
    registros = []
    for d in mn.dias(de, ate):
        for doc in mn.documentos_do_dia(d, eventos=(EVENTO,)):
            origem = str(doc.get("cod_filial") or "").strip()
            destino = str(doc.get("cod_cliente") or "").strip()
            tipo = classifica(origem, destino)
            data = mn.parse_data(doc.get("data_emissao"))
            nota = ""
            if doc.get("nfs"):
                nota = str(doc["nfs"][0].get("numero_nota") or "")
            for item in doc.get("itens") or []:
                q = item.get("quant") or 0
                if q <= 0:
                    continue
                registros.append({
                    "data": data,
                    "tipo": tipo,
                    "origem": origem,
                    "destino": destino,
                    "codigo": str(item.get("cod_produto") or "").strip(),
                    "cod_cor": str(item.get("cod_cor") or "").strip(),
                    "cor": str(item.get("desc_cor") or "").strip(),
                    "tamanho": str(item.get("tamanho") or "").strip(),
                    "quant": q,
                    "valor": float(item.get("total") or 0),
                    "nota": nota,
                    "romaneio": doc.get("romaneio"),
                })
    return registros


def saldo_por_loja(registros):
    """Quanto cada loja ganhou de estoque, por produto+cor.

    Realocação mexe nas duas pontas e soma zero no conjunto — é o que a D13
    decidiu em 18/09.
    """
    saldo = defaultdict(float)
    for r in registros:
        chave_base = (r["codigo"], r["cod_cor"], r["cor"])
        if r["tipo"] == "entrada":
            saldo[chave_base + (r["destino"],)] += r["quant"]
        elif r["tipo"] == "saida":
            saldo[chave_base + (r["origem"],)] -= r["quant"]
        elif r["tipo"] == "realocacao":
            saldo[chave_base + (r["destino"],)] += r["quant"]
            saldo[chave_base + (r["origem"],)] -= r["quant"]
    return saldo


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Estoque inicial das lojas pela venda entre filiais (evento 106)")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, required=True)
    p.add_argument("-s", "--salvar", help="grava o detalhe por item num CSV")
    p.add_argument("--sem-cache", action="store_true")
    args = p.parse_args(argv)

    mn.USAR_CACHE = not args.sem_cache
    registros = coleta(args.de, args.ate)
    if not registros:
        print("Nenhum movimento do evento 106 no periodo.")
        return 1

    print(f"\nEvento {EVENTO} — venda entre filiais, {args.de} a {args.ate}")
    print(f"{len(registros)} item(ns) em movimento\n")

    por_tipo = defaultdict(lambda: {"itens": 0, "quant": 0.0, "valor": 0.0})
    fluxo = defaultdict(float)
    for r in registros:
        a = por_tipo[r["tipo"]]
        a["itens"] += 1
        a["quant"] += r["quant"]
        a["valor"] += r["valor"]
        fluxo[(r["origem"], r["destino"], r["tipo"])] += r["quant"]

    print(f'  {"tipo":12} {"itens":>6} {"peças":>8} {"valor":>14}')
    print("  " + "-" * 44)
    for tipo in ("entrada", "saida", "realocacao", "fora"):
        a = por_tipo.get(tipo)
        if a:
            print(f'  {tipo:12} {a["itens"]:>6} {a["quant"]:>8,.0f} {a["valor"]:>14,.2f}')

    print(f'\n  {"origem":14} -> {"destino":14} {"peças":>8}  tipo')
    print("  " + "-" * 52)
    for (o, d, t), q in sorted(fluxo.items(), key=lambda x: -x[1]):
        print(f'  {o[:14]:14} -> {d[:14]:14} {q:>8,.0f}  {t}')

    saldo = saldo_por_loja(registros)
    entrou = sum(v for v in saldo.values() if v > 0)
    saiu = -sum(v for v in saldo.values() if v < 0)
    liquido = entrou - saiu

    print(f"\n  {len(saldo)} combinacao(oes) produto+cor+loja")
    print(f"  entrou {entrou:,.0f} · saiu {saiu:,.0f} · liquido {liquido:,.0f} peca(s)")
    print(f"  teto da producao no periodo: {TETO_PRODUCAO:,.0f} pecas", end="")
    if liquido > TETO_PRODUCAO:
        print("  <-- ESTOUROU. A leitura esta errada.")
    else:
        print(f"  ({liquido / TETO_PRODUCAO:.0%} dele)")

    consolidado = defaultdict(float)
    for (cod, cod_cor, cor, _loja), q in saldo.items():
        consolidado[(cod, cod_cor, cor)] += q

    print(f"\n  Estoque inicial por produto+cor ({len(consolidado)} combinacoes), maiores:")
    print(f'    {"codigo":10} {"cor":>5} {"descricao":18} {"peças":>7}')
    print("    " + "-" * 44)
    for (cod, cod_cor, cor), q in sorted(consolidado.items(), key=lambda x: -x[1])[:15]:
        print(f'    {cod:10} {cod_cor:>5} {cor[:18]:18} {q:>7,.0f}')

    if args.salvar:
        with open(args.salvar, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(registros[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(registros)
        print(f"\n  Detalhe por item em {args.salvar}")

    print("""
  Como conferir: some, por codigo, as pecas acima e compare com o que a
  coluna Estoque inicial da planilha ganhou de uma semana para a outra.
  Se bater, a coluna deixa de ser digitada e passa a ser derivada.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
