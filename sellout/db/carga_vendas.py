"""Carga retroativa das vendas, semana a semana, direto do ERP.

    python -m sellout.db.carga_vendas --de 2026-01-01 --ate 2026-09-20
    python -m sellout.db.carga_vendas --de 2026-01-01 --ate 2026-09-20 --aplicar

Fecha o buraco que a D23 deixou exposto: o denominador do sellout alcança
janeiro, o numerador só existia a partir de setembro, quando as rodadas
passaram a gravar snapshot. A venda sempre esteve no ERP — ninguém tinha ido
buscar.

Cada semana vira um `snapshot` com `origem='erp'`, datado no **domingo** que a
fecha, e as linhas de `venda` daquela semana. O recorte é o mesmo da rodada:
segunda a domingo.

**Repetir é seguro.** Semana que já tem snapshot `erp` é pulada, e o programa
diz quantas pulou. `--refazer` apaga e regrava só as semanas do intervalo —
nunca as de `origem='upload'`, que são as rodadas de verdade e não se
reconstroem.

**Nada é gravado sem `--aplicar`.** Sem a flag, mostra o que faria.

---

**O papel da filial decide se a venda existe.** A consulta do sellout só soma
quem tem `papel` em ('loja', 'ecommerce'); filial sem papel cai em 'fora' e
some da conta — calada. Por isso esta carga cadastra a filial com o papel
antes de gravar a venda, e imprime o que cadastrou. Uma venda que entra no
banco e não aparece na consulta é pior do que uma venda que não entrou.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from coletor import vendas as coletor_vendas
from .conexao import conectar, por_que_nao

# D12: quem vende para o consumidor final. A matriz não entra — o que ela
# "vende" para a loja é transferência, e já está no denominador.
PAPEL = {
    "EGREY JDS": "loja",
    "IGUATEMI": "loja",
    "SITE": "ecommerce",
}


def dia(t: str) -> date:
    return date.fromisoformat(t)


def semanas(de: date, ate: date) -> list[tuple[date, date]]:
    """Segunda a domingo, cobrindo o intervalo inteiro.

    Começa na segunda da semana de `de`, mesmo que `de` caia no meio dela: uma
    semana pela metade daria um número menor que ninguém questionaria.
    """
    inicio = de - timedelta(days=de.weekday())
    saida = []
    while inicio <= ate:
        fim = inicio + timedelta(days=6)
        saida.append((inicio, fim))
        inicio = fim + timedelta(days=1)
    return saida


def ja_carregadas(de: date, ate: date) -> set[date]:
    """Domingos que já têm snapshot do ERP no intervalo."""
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute("SELECT data FROM snapshot WHERE origem = 'erp' "
                        "AND data BETWEEN %s AND %s", (de, ate))
            return {r[0] for r in cur.fetchall()}


def apaga(datas) -> int:
    """Remove snapshots do ERP — e só do ERP.

    `origem='upload'` é rodada de verdade, com decisões de quem rodou dentro.
    Apagar uma por engano não se desfaz, então o filtro está no SQL e não na
    chamada.
    """
    if not datas:
        return 0
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM snapshot WHERE origem = 'erp' "
                        "AND data = ANY(%s)", (list(datas),))
            return cur.rowcount


def grava_semana(fim: date, saldo) -> dict:
    """Um snapshot e as vendas da semana. Devolve o que foi gravado."""
    filiais = {f for (_c, _cc, _cor, _t, f) in saldo}
    with conectar() as c:
        with c.cursor() as cur:
            for f in sorted(filiais):
                cur.execute(
                    "INSERT INTO filial (codigo, nome, papel) VALUES (%s, %s, %s) "
                    "ON CONFLICT (codigo) DO UPDATE SET papel = "
                    "  CASE WHEN filial.papel = 'fora' THEN excluded.papel "
                    "       ELSE filial.papel END",
                    (f, f, PAPEL.get(f, "fora")))
            cur.execute(
                "INSERT INTO snapshot (data, origem, quem, observacao) "
                "VALUES (%s, 'erp', %s, %s) RETURNING id",
                (fim, "carga_vendas", "carga retroativa do ERP"))
            snap = cur.fetchone()[0]
            linhas = 0
            for (cod, cod_cor, _cor, tam, fil), v in saldo.items():
                if not v["qtd"]:
                    continue
                cur.execute(
                    "INSERT INTO venda (snapshot_id, codigo, codigo_cor, "
                    "tamanho, filial, qtd, valor) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (snap, cod, cod_cor, tam, fil, v["qtd"], v["valor"]))
                linhas += 1
    return {"snapshot": snap, "linhas": linhas,
            "pecas": sum(v["qtd"] for v in saldo.values())}


def main(argv=None):
    p = argparse.ArgumentParser(description="Carga retroativa das vendas do ERP")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, default=date.today() - timedelta(days=1))
    p.add_argument("--aplicar", action="store_true", help="sem isto, so mostra")
    p.add_argument("--refazer", action="store_true",
                   help="apaga e regrava as semanas do intervalo (so origem=erp)")
    p.add_argument("--sem-cache", action="store_true")
    args = p.parse_args(argv)

    razao = por_que_nao()
    if razao:
        print(f"\nSem banco: {razao}")
        return 1

    coletor_vendas.mn.USAR_CACHE = not args.sem_cache
    janelas = semanas(args.de, args.ate)
    print(f"\nCarga retroativa de vendas — {len(janelas)} semana(s), "
          f"{janelas[0][0]} a {janelas[-1][1]}")

    existentes = ja_carregadas(janelas[0][1], janelas[-1][1])
    if args.refazer and existentes:
        if args.aplicar:
            n = apaga(existentes)
            print(f"  {n} snapshot(s) do ERP apagado(s) para regravar")
        else:
            print(f"  (--refazer apagaria {len(existentes)} snapshot(s) do ERP)")
        existentes = set()

    total_pecas = total_linhas = 0
    pulou = 0
    for de, fim in janelas:
        if fim in existentes:
            pulou += 1
            continue
        saldo, r = coletor_vendas.coleta(de, fim)
        pecas = sum(v["qtd"] for v in saldo.values())
        if not saldo:
            print(f"  {de} a {fim}   sem movimento")
            continue
        if args.aplicar:
            g = grava_semana(fim, saldo)
            total_linhas += g["linhas"]
            print(f"  {de} a {fim}   {g['linhas']:>5} linha(s)  "
                  f"{pecas:>6,.0f} peca(s)")
        else:
            print(f"  {de} a {fim}   {len(saldo):>5} linha(s)  "
                  f"{pecas:>6,.0f} peca(s)   (nao gravado)")
        total_pecas += pecas

    print(f"\n  {total_pecas:,.0f} peca(s) no periodo")
    if pulou:
        print(f"  {pulou} semana(s) ja carregada(s), puladas. Use --refazer "
              f"para regravar.")
    if not args.aplicar:
        print("\n  Nada foi gravado. Rode de novo com --aplicar.")
        return 0

    print(f"  {total_linhas:,} linha(s) de venda gravada(s)")
    print("\n  Confira agora com:")
    print(f"    python -m sellout.db.consulta --ate {args.ate}")
    print("  A venda mais antiga do banco tem que ter recuado para janeiro —")
    print("  e so entao o sellout daqui pode ser comparado com a planilha.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
