"""Tudo o que os dois lados têm sobre **um** produto.

    python -m sellout.db.ficha 334019 --ate 2026-09-20 \\
        --planilha "...\\Sellout\\sellout geral 2109.xlsx"

**Por que produto a produto, e não mais uma lista.** O estoque inicial das
últimas planilhas não é confiável, principalmente em SS27 — quem mantém o
arquivo sabe disso. Então uma corrida que classifica 250 produtos como "fecha"
ou "não fecha" pelo estoque inicial está medindo, em parte, um número que o
próprio dono não garante. A lista já deu o que tinha para dar; o que resta é
olhar caso a caso, e para isso é preciso ver as parcelas, não o veredito.

A ficha mostra as parcelas dos dois lados e fecha a conta que as liga:

    abertura + movimentos = estoque inicial
    estoque inicial − vendas − estoque atual = sobra

A sobra é consignação mais erro (D21). Ela não é acusação: é o que ainda não
tem nome. Com a consignação medida ao lado, o que sobrar dela é erro de
verdade — e é o número que decide se um produto precisa de ajuste.

Nada aqui é veredito. São as parcelas, com a origem de cada uma, para a
conversa de negócio acontecer em cima de número e não de impressão.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date

from ..core.leitura import ABAS_TRABALHO, mapa_colunas, norm_codigo
from . import consulta
from .conexao import conectar

SQL_MOVIMENTOS = """
SELECT data, codigo_cor, tipo, evento_mn, coalesce(filial, ''), qtd,
       coalesce(documento, '')
  FROM movimento
 WHERE codigo = %(codigo)s AND data <= %(ate)s
 ORDER BY data, id
"""

SQL_ABERTURA = """
SELECT codigo_cor, sum(qtd), min(data_base)
  FROM saldo_abertura
 WHERE codigo = %(codigo)s AND data_base <= %(ate)s
 GROUP BY codigo_cor ORDER BY codigo_cor
"""


def movimentos(codigo: str, ate: date) -> list[dict]:
    with conectar() as c, c.cursor() as cur:
        cur.execute(SQL_MOVIMENTOS, {"codigo": codigo.strip(), "ate": ate})
        return [{"data": d, "codigo_cor": cc, "tipo": t, "evento": e,
                 "filial": f, "qtd": float(q), "documento": doc}
                for d, cc, t, e, f, q, doc in cur.fetchall()]


def abertura(codigo: str, ate: date) -> list[dict]:
    with conectar() as c, c.cursor() as cur:
        cur.execute(SQL_ABERTURA, {"codigo": codigo.strip(), "ate": ate})
        return [{"codigo_cor": cc, "qtd": float(q), "desde": d}
                for cc, q, d in cur.fetchall()]


def por_tipo(movs) -> dict:
    """{tipo: {qtd, linhas}} — o que cada espécie de movimento somou.

    Separado por tipo porque as espécies não são comparáveis: transferência
    entra estoque, realocação soma zero no conjunto (tem as duas pontas) e
    saída de bazar tira do universo do sellout (D12). Um total único esconderia
    as três dentro de um número só.
    """
    fora = defaultdict(lambda: {"qtd": 0.0, "linhas": 0})
    for m in movs:
        d = fora[m["tipo"]]
        d["qtd"] += m["qtd"]
        d["linhas"] += 1
    return {t: dict(v) for t, v in fora.items()}


def da_planilha(caminho: str, codigo: str) -> list[dict]:
    """As células daquele produto, coluna a coluna, como estão no arquivo.

    Uma linha por ocorrência: um código pode aparecer em mais de uma aba, e
    pode estar dividido em duas linhas pelo texto em vermelho (D1).
    """
    import openpyxl
    alvo = norm_codigo(codigo)
    wb = openpyxl.load_workbook(caminho, data_only=True)
    achados = []
    for nome in ABAS_TRABALHO:
        if nome not in wb.sheetnames:
            continue
        ws = wb[nome]
        cols = mapa_colunas(ws)
        for r in range(4, ws.max_row + 1):
            if norm_codigo(ws.cell(r, 2).value) != alvo:
                continue
            achados.append({
                "aba": nome, "linha": r,
                "descricao": ws.cell(r, 3).value,
                **{k: ws.cell(r, c).value for k, c in cols.items()},
            })
    wb.close()
    return achados


def reconcilia(linhas) -> dict:
    """Soma as cores e fecha as duas contas do banco."""
    ei = sum(float(l["estoque_inicial"]) for l in linhas)
    ve = sum(float(l["vendas"]) for l in linhas)
    at = sum(float(l["estoque_atual"]) for l in linhas)
    return {"estoque_inicial": ei, "vendas": ve, "estoque_atual": at,
            "sobra": ei - ve - at,
            "sellout": consulta.percentual(ve, ei)}


ROTULO = {"D": "Estoque atual", "E": "Consignado (medido)",
          "E_CONTA": "Consignado (conta)", "JARDINS": "Vendas Jardins",
          "IGUATEMI": "Vendas Iguatemi", "SITE": "Vendas Site",
          "I": "Vendas totais", "J": "Estoque inicial", "K": "Sellout"}
ORDEM = ("J", "I", "JARDINS", "IGUATEMI", "SITE", "D", "E", "E_CONTA", "K")


def main(argv=None):
    p = argparse.ArgumentParser(description="Um produto, os dois lados")
    p.add_argument("codigo")
    p.add_argument("--ate", type=date.fromisoformat, default=date.today())
    p.add_argument("--planilha", help="xlsx para mostrar o lado da planilha")
    p.add_argument("--limite", type=int, default=25)
    args = p.parse_args(argv)
    cod = norm_codigo(args.codigo)

    linhas = consulta.sellout(args.ate, codigo=cod)
    print(f"\n{'=' * 70}\nProduto {cod}   —   ate {args.ate}\n{'=' * 70}")
    if not linhas:
        print("\nO banco nao tem nada deste codigo: nem abertura, nem movimento,")
        print("nem venda. Isso e ausencia de cadastro/extracao, nao estoque zero.")
    else:
        desc = next((l["descricao"] for l in linhas if l["descricao"]), "")
        col = next((l["colecao"] for l in linhas if l["colecao"]), "")
        print(f"  {desc}   colecao {col or '(sem colecao no cadastro)'}")

        print("\n-- BANCO, por cor " + "-" * 51)
        print(f'  {"cor":6} {"nome":16} {"inicial":>8} {"vendas":>7} '
              f'{"atual":>7} {"sobra":>7} {"sellout":>8}')
        print("  " + "-" * 62)
        for l in linhas:
            s = f'{l["sellout"]:>8.1%}' if l["sellout"] is not None else f'{"—":>8}'
            print(f'  {l["codigo_cor"]:6} {(l["cor"] or "")[:16]:16} '
                  f'{float(l["estoque_inicial"]):>8,.0f} {float(l["vendas"]):>7,.0f} '
                  f'{float(l["estoque_atual"]):>7,.0f} {l["sobra"]:>7,.0f} {s}')
        r = reconcilia(linhas)
        s = f'{r["sellout"]:.1%}' if r["sellout"] is not None else "—"
        print("  " + "-" * 62)
        print(f'  {"TOTAL":23} {r["estoque_inicial"]:>8,.0f} {r["vendas"]:>7,.0f} '
              f'{r["estoque_atual"]:>7,.0f} {r["sobra"]:>7,.0f} {s:>8}')
        print(f"\n  estoque inicial − vendas − estoque atual = {r['sobra']:,.0f}")
        print("  Essa sobra e consignacao mais erro. Ela nao acusa nada sozinha:")
        print("  com a consignacao medida do lado, o que restar e que e erro.")

        # De onde vem o denominador: abertura e movimentos, separados.
        ab = abertura(cod, args.ate)
        movs = movimentos(cod, args.ate)
        total_ab = sum(x["qtd"] for x in ab)
        tipos = por_tipo(movs)
        print("\n-- DE ONDE VEM O ESTOQUE INICIAL " + "-" * 36)
        print(f'  abertura{"":22} {total_ab:>8,.0f}'
              + (f'   (desde {min(x["desde"] for x in ab)})' if ab else ""))
        for t, d in sorted(tipos.items(), key=lambda kv: -abs(kv[1]["qtd"])):
            print(f'  {t:30} {d["qtd"]:>8,.0f}   ({d["linhas"]} linha(s))')
        print("  " + "-" * 40)
        print(f'  {"soma":30} {total_ab + sum(d["qtd"] for d in tipos.values()):>8,.0f}')
        if not ab:
            print("\n  SEM SALDO DE ABERTURA. O denominador comeca do zero e so cresce")
            print("  pelos movimentos — produto que ja existia em 01/01 aparece menor")
            print("  do que e, e o sellout dele, maior.")

        pf = consulta.vendas_por_filial([cod], args.ate).get(cod, {})
        if pf:
            print("\n-- VENDAS POR LOJA, no banco " + "-" * 40)
            for f, q in sorted(pf.items(), key=lambda kv: -abs(kv[1])):
                print(f"  {f:20} {q:>8,.0f}")

        if movs:
            print(f"\n-- MOVIMENTOS ({len(movs)}) " + "-" * 50)
            print(f'  {"data":12} {"cor":6} {"tipo":15} {"ev":>4} {"filial":12} '
                  f'{"qtd":>7}  documento')
            print("  " + "-" * 70)
            for m in movs[:args.limite]:
                print(f'  {str(m["data"]):12} {m["codigo_cor"]:6} {m["tipo"][:15]:15} '
                      f'{m["evento"] or "":>4} {m["filial"][:12]:12} '
                      f'{m["qtd"]:>7,.0f}  {m["documento"][:18]}')
            if len(movs) > args.limite:
                print(f"  ... {len(movs) - args.limite} movimento(s) a mais")

    if args.planilha:
        achados = da_planilha(args.planilha, cod)
        print("\n-- PLANILHA " + "-" * 57)
        if not achados:
            print("  Este codigo nao esta nas abas de trabalho do arquivo.")
        for a in achados:
            print(f'  {a["aba"]} linha {a["linha"]}: {a.get("descricao") or ""}')
            for k in ORDEM:
                if k not in a:
                    continue
                v = a[k]
                if isinstance(v, float) and k == "K":
                    v = f"{v:.1%}"
                elif isinstance(v, (int, float)):
                    v = f"{v:,.0f}"
                print(f'    {ROTULO.get(k, k):22} {str(v if v is not None else "—"):>10}')
        print("\n  O estoque inicial das ultimas planilhas nao e garantido,")
        print("  principalmente em SS27 — leia essa linha sabendo disso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
