"""A exportação do próprio ERP contra o banco, na mesma semana.

    python -m sellout.db.confere_erp VENDAS_14_20.xlsx --semana 2026-09-20

**Por que isto existe, e por que não é mais uma conferência contra a planilha.**
A planilha não é fonte: é uma consumidora anterior da mesma fonte. Quando ela e
o banco discordam, comparar um com o outro não diz quem está certo — diz apenas
que discordam. A autoridade é o ERP.

A exportação do ERP vem no mesmo grão da tabela `venda` (filial, código, cor,
tamanho, quantidade, devolução com sinal negativo) e é produzida por um caminho
que não é o nosso: relatório do sistema, não a nossa extração pela API. Então
ela responde a pergunta que importa antes de aposentar a planilha:

    a nossa extração é fiel ao ERP naquela semana?

Se for, o que sobra de divergência contra a planilha é história da planilha — e
aí o arquivo pode ser aposentado em vez de reconciliado. Se não for, achamos um
defeito na extração, que é o único dos três lugares onde um defeito ainda
importa.

**A tolerância é zero.** Mesma semana, mesma fonte, mesmo grão: qualquer peça
de diferença é achado, não arredondamento. É o oposto da comparação contra a
planilha, onde uma peça sai de data de corte.

Um detalhe que esta conferência pega de graça: duas cargas da mesma semana
dobram tudo, e o número dobrado continua parecendo plausível. Por isso o
programa conta os snapshots antes de somar e para se houver mais de um.
"""

from __future__ import annotations

import argparse
import pathlib
from collections import defaultdict
from datetime import date

import openpyxl

from ..core.leitura import norm_codigo
from .conexao import conectar

# O cabeçalho da exportação. Achado pelo texto, não pela posição: relatório de
# ERP ganha coluna sem avisar, e foi assim que a coluna "Consignado Real"
# apareceu no meio da planilha.
COLUNAS = {"filial": ("FILIAL",),
           "codigo": ("CÓDIGO", "CODIGO"),
           "codigo_cor": ("CODIGO_COR", "CÓDIGO_COR", "COD_COR"),
           "tamanho": ("TAM", "TAMANHO"),
           "qtd": ("QTDE", "QTD", "QUANTIDADE")}


def nrm(v) -> str:
    return str(v or "").strip().upper()


def mapa_do_export(ws) -> dict:
    """{campo: coluna} pela linha de cabeçalho."""
    m = {}
    for c in range(1, ws.max_column + 1):
        t = nrm(ws.cell(1, c).value)
        for campo, nomes in COLUNAS.items():
            if t in nomes and campo not in m:
                m[campo] = c
    return m


def do_export(caminho: str) -> tuple[dict, list]:
    """{(codigo, codigo_cor, filial): qtd} — os tamanhos somados.

    O tamanho é somado porque a planilha e o sellout são por produto e cor; e
    porque uma troca de tamanho dentro do mesmo produto não muda nada do que
    está sendo medido aqui.
    """
    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb[wb.sheetnames[0]]
    m = mapa_do_export(ws)
    faltando = [c for c in COLUNAS if c not in m and c != "tamanho"]
    if faltando:
        wb.close()
        raise ValueError(f"a exportacao nao tem as colunas {faltando}; "
                         f"cabecalho lido: {[ws.cell(1, c).value for c in range(1, ws.max_column + 1)]}")
    fora, avisos = defaultdict(float), []
    for r in range(2, ws.max_row + 1):
        cod = norm_codigo(ws.cell(r, m["codigo"]).value)
        if not cod:
            continue
        q = ws.cell(r, m["qtd"]).value
        if not isinstance(q, (int, float)):
            avisos.append(f"linha {r}: quantidade nao numerica ({q!r})")
            continue
        chave = (cod, nrm(ws.cell(r, m["codigo_cor"]).value),
                 nrm(ws.cell(r, m["filial"]).value))
        fora[chave] += float(q)
    wb.close()
    return dict(fora), avisos


def snapshots_da_semana(semana: date, origem: str) -> list:
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM snapshot WHERE data = %s AND origem = %s "
                    "ORDER BY id", (semana, origem))
        return [r[0] for r in cur.fetchall()]


def do_banco(snaps) -> dict:
    """{(codigo, codigo_cor, filial): qtd} para os snapshots dados."""
    if not snaps:
        return {}
    fora = defaultdict(float)
    with conectar() as c, c.cursor() as cur:
        cur.execute(
            "SELECT v.codigo, v.codigo_cor, v.filial, sum(v.qtd) "
            "  FROM venda v WHERE v.snapshot_id = ANY(%s) "
            " GROUP BY v.codigo, v.codigo_cor, v.filial", (list(snaps),))
        for cod, cor, fil, q in cur.fetchall():
            fora[(norm_codigo(cod), nrm(cor), nrm(fil))] += float(q)
    return dict(fora)


def compara(export: dict, banco: dict) -> dict:
    """Chave a chave, com tolerância zero.

    Chave que existe de um lado só **não** entra como diferença de número: é
    linha que um dos dois não viu, e somar zero do outro lado misturaria as duas
    coisas — foi o erro que a conferência contra a planilha já tinha corrigido.
    """
    iguais, difere, so_erp, so_banco = [], [], [], []
    for k in sorted(set(export) | set(banco)):
        e, b = export.get(k), banco.get(k)
        if e is None:
            so_banco.append({"chave": k, "qtd": b})
        elif b is None:
            so_erp.append({"chave": k, "qtd": e})
        elif abs(e - b) < 1e-9:
            iguais.append(k)
        else:
            difere.append({"chave": k, "erp": e, "banco": b, "dif": e - b})
    return {"iguais": iguais, "difere": difere,
            "so_erp": so_erp, "so_banco": so_banco,
            "total_erp": sum(export.values()),
            "total_banco": sum(banco.values())}


def por_filial(r: dict) -> dict:
    """{filial: {erp, banco, dif, chaves}} — onde a diferença mora.

    Agrupa as três listas juntas: uma filial que só existe num dos lados é
    exatamente o caso que soma errado em silêncio, e ela tem de aparecer na
    mesma tabela que as outras.
    """
    fora = defaultdict(lambda: {"erp": 0.0, "banco": 0.0, "dif": 0.0, "chaves": 0})
    def soma(filial, e, b):
        d = fora[filial]
        d["erp"] += e
        d["banco"] += b
        d["dif"] += e - b
        if abs(e - b) > 1e-9:
            d["chaves"] += 1
    for x in r["difere"]:
        soma(x["chave"][2], x["erp"], x["banco"])
    for x in r["so_erp"]:
        soma(x["chave"][2], x["qtd"], 0.0)
    for x in r["so_banco"]:
        soma(x["chave"][2], 0.0, x["qtd"])
    return {f: dict(v) for f, v in fora.items()}


def fiel(r: dict) -> bool:
    """A extração reproduz o ERP naquela semana, chave a chave."""
    return not r["difere"] and not r["so_erp"] and not r["so_banco"]


def main(argv=None):
    p = argparse.ArgumentParser(
        description="A exportacao do ERP contra o banco, na mesma semana")
    p.add_argument("export", help="xlsx exportado do ERP (Filial, Codigo, Qtde...)")
    p.add_argument("--semana", type=date.fromisoformat, required=True,
                   help="o domingo que fecha a semana, como esta em snapshot.data")
    p.add_argument("--origem", default="erp", choices=("erp", "upload"),
                   help="erp = carga retroativa; upload = rodada do app")
    p.add_argument("--limite", type=int, default=20)
    args = p.parse_args(argv)

    caminho = pathlib.Path(args.export.strip().strip("<>").strip('"').strip("'"))
    if not caminho.exists():
        print(f"\nNao encontrei o arquivo: {caminho}")
        return 1

    ex, avisos = do_export(str(caminho))
    snaps = snapshots_da_semana(args.semana, args.origem)
    print(f"\nERP x banco — semana de {args.semana}, origem {args.origem}")
    print(f"  exportacao: {len(ex):,} chave(s) produto+cor+filial")
    if avisos:
        print(f"  {len(avisos)} linha(s) ignorada(s) na exportacao:")
        for a in avisos[:5]:
            print(f"    {a}")

    if not snaps:
        print(f"\n  O banco nao tem snapshot de {args.semana} com origem "
              f"'{args.origem}'.")
        print("  Sem isso nao ha o que comparar — confira a data do domingo.")
        return 1
    if len(snaps) > 1:
        # Duas cargas da mesma semana dobram tudo, e o dobro parece plausivel.
        print(f"\n  {len(snaps)} snapshots para a MESMA semana e origem: {snaps}")
        print("  Somar os dois dobraria a venda da semana. Isto e defeito de")
        print("  carga, e precisa ser resolvido antes de conferir qualquer coisa.")
        return 1

    ba = do_banco(snaps)
    r = compara(ex, ba)
    print(f"  banco:      {len(ba):,} chave(s)")
    print(f"\n  total de pecas   ERP {r['total_erp']:>8,.0f}   "
          f"banco {r['total_banco']:>8,.0f}   "
          f"dif {r['total_erp'] - r['total_banco']:>+7,.0f}")
    print(f"\n  iguais na peca          {len(r['iguais']):>6}")
    print(f"  diferem                 {len(r['difere']):>6}")
    print(f"  so na exportacao do ERP {len(r['so_erp']):>6}")
    print(f"  so no banco             {len(r['so_banco']):>6}")

    if fiel(r):
        print("\n  A EXTRACAO REPRODUZ O ERP NESTA SEMANA, chave a chave.")
        print("  Então o que sobra de divergencia contra a planilha e historia da")
        print("  planilha, e o arquivo pode ser aposentado em vez de reconciliado.")
        print("  Uma semana nao prova as 38 — repita nas semanas que tiverem")
        print("  exportacao guardada.")
        return 0

    pf = por_filial(r)
    print("\n  onde a diferenca mora:")
    print(f'    {"filial":14} {"erp":>8} {"banco":>8} {"dif":>7} {"chaves":>7}')
    print("    " + "-" * 50)
    for f, d in sorted(pf.items(), key=lambda kv: -abs(kv[1]["dif"])):
        print(f'    {f[:14]:14} {d["erp"]:>8,.0f} {d["banco"]:>8,.0f} '
              f'{d["dif"]:>+7,.0f} {d["chaves"]:>7}')

    for rotulo, lista in (("diferem", r["difere"]), ("so na exportacao", r["so_erp"]),
                          ("so no banco", r["so_banco"])):
        if not lista:
            continue
        print(f"\n  {rotulo} ({len(lista)}):")
        print(f'    {"codigo":8} {"cor":6} {"filial":14} {"erp":>7} {"banco":>7}')
        print("    " + "-" * 48)
        for x in lista[:args.limite]:
            cod, cor, fil = x["chave"]
            e = x.get("erp", x.get("qtd") if lista is r["so_erp"] else 0.0)
            b = x.get("banco", x.get("qtd") if lista is r["so_banco"] else 0.0)
            print(f'    {cod:8} {cor:6} {fil[:14]:14} {e:>7,.0f} {b:>7,.0f}')
    print("\n  Tolerancia zero: mesma semana, mesma fonte, mesmo grao. Uma peca")
    print("  de diferenca aqui e achado, nao arredondamento.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
