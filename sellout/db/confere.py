"""Banco contra planilha, componente a componente.

    python -m sellout.db.confere "sellout geral.xlsx" --ate 2026-09-14

É a prova que autoriza aposentar o arquivo. Não basta o percentual final bater:
dois números errados em direções opostas dão a razão certa, e foi assim que a
extração de vendas quase passou com o sinal trocado em seis chaves.

Por isso a comparação é **por componente**:

    Estoque inicial   planilha (coluna J) x banco (abertura + movimentos)
    Vendas            planilha (coluna I) x banco (snapshots)
    Sellout           o quociente dos dois, em cada lado

Se o Estoque inicial bate e a Venda não, já se sabe de que lado olhar. Se os
dois batem, o percentual bate por construção — e aí é resultado, não
coincidência.

---

**O que é comparável, e o que não é.** A coluna Vendas totais da planilha
acumula desde que o produto entrou na aba, o que para coleção antiga é 2023.
O banco começa em 01/01/2026 (D10/D24). Comparar os dois em produto velho não
mede nada: a planilha vai ganhar sempre, e por um motivo conhecido.

Então o corte é o mesmo da abertura (`abertura.RECONSTRUIDAS`): **AW26 e SS27**
são comparáveis, porque a vida inteira delas está dentro da janela do banco. O
resto aparece separado, rotulado, e não entra no veredito.

Produto que a planilha tem e o banco não — e o contrário — é listado, nunca
somado: chave que existe de um lado só é diferença de cadastro, não de número,
e misturar as duas coisas esconde as duas.
"""

from __future__ import annotations

import argparse
import pathlib
import re
from collections import defaultdict
from datetime import date

import openpyxl

from ..core.leitura import (ABAS_TRABALHO, blocos_de, mapa_colunas,
                            norm_codigo)
from . import abertura, consulta

RE_CODIGO = re.compile(r"^\d{5,6}$")
# Diferença que não vale discussão: uma peça a mais ou a menos num produto sai
# de arredondamento de data de corte, não de regra errada.
TOLERANCIA = 1.0


def da_planilha(caminho: str) -> dict:
    """{codigo: {estoque_inicial, vendas, sellout}} das abas de trabalho.

    Lê o valor **guardado** das fórmulas (`data_only`), que é o que o Excel
    calculou. Um arquivo que nunca passou pelo Excel não tem esses valores —
    é o defeito da D17 — e aqui isso aparece como planilha vazia, não como
    zero.
    """
    wb = openpyxl.load_workbook(caminho, data_only=True)
    por_codigo = defaultdict(lambda: {"estoque_inicial": 0.0, "vendas": 0.0,
                                      "linhas": 0, "colecao": ""})
    sem_valor = 0
    for aba in ABAS_TRABALHO:
        if aba not in wb.sheetnames:
            continue
        ws = wb[aba]
        cols = mapa_colunas(ws)
        # **A coleção vem do bloco da planilha, não do banco.** A tabela
        # `produto` só é preenchida pelas rodadas de upload, e a carga
        # retroativa (D24) não passa por lá: filtrar pelo banco deixava a
        # comparação com zero produtos, que foi o que aconteceu em 27/09.
        # Quem sabe a coleção hoje é o nome do bloco — e o cadastro do ERP,
        # que ainda não foi semeado no banco.
        de_linha = {}
        for b in blocos_de(ws):
            for r in range(b["ini"], b["fim"] + 1):
                de_linha[r] = (b["colecao"] or "").upper()
        for r in range(4, ws.max_row + 1):
            cod = norm_codigo(ws.cell(r, 2).value)
            if not cod or not RE_CODIGO.match(cod):
                continue
            j = ws.cell(r, cols["J"]).value
            i = ws.cell(r, cols["I"]).value
            if not isinstance(j, (int, float)) or not isinstance(i, (int, float)):
                sem_valor += 1
                continue
            d = por_codigo[cod]
            d["estoque_inicial"] += float(j)
            d["vendas"] += float(i)
            d["linhas"] += 1
            d["colecao"] = d["colecao"] or de_linha.get(r, "")
    wb.close()
    return {c: dict(v) for c, v in por_codigo.items()}, sem_valor


def do_banco(ate: date) -> dict:
    """{codigo: {...}} — as cores somadas, porque a planilha é por produto."""
    por_codigo = defaultdict(lambda: {"estoque_inicial": 0.0, "vendas": 0.0,
                                      "colecao": ""})
    for l in consulta.sellout(ate):
        d = por_codigo[l["codigo"]]
        d["estoque_inicial"] += float(l["estoque_inicial"])
        d["vendas"] += float(l["vendas"])
        d["colecao"] = d["colecao"] or (l["colecao"] or "").upper()
    return dict(por_codigo)


def compara(planilha: dict, banco: dict, comparaveis) -> dict:
    """Junta os dois lados e separa o que dá para comparar do que não dá."""
    alvo = {c.upper() for c in comparaveis}
    linhas, fora, so_planilha, so_banco = [], [], [], []

    for cod in sorted(set(planilha) | set(banco)):
        p, b = planilha.get(cod), banco.get(cod)
        if p is None:
            so_banco.append(cod)
            continue
        if b is None:
            so_planilha.append(cod)
            continue
        item = {
            "codigo": cod,
            "colecao": p.get("colecao") or b["colecao"],
            "colecao_banco": b["colecao"],
            "inicial_planilha": p["estoque_inicial"],
            "inicial_banco": b["estoque_inicial"],
            "vendas_planilha": p["vendas"],
            "vendas_banco": b["vendas"],
        }
        item["dif_inicial"] = item["inicial_planilha"] - item["inicial_banco"]
        item["dif_vendas"] = item["vendas_planilha"] - item["vendas_banco"]
        item["sellout_planilha"] = consulta.percentual(p["vendas"], p["estoque_inicial"])
        item["sellout_banco"] = consulta.percentual(b["vendas"], b["estoque_inicial"])
        (linhas if item["colecao"] in alvo else fora).append(item)

    return {"comparaveis": linhas, "fora_da_janela": fora,
            "so_planilha": so_planilha, "so_banco": so_banco}


def veredito(linhas, tolerancia=TOLERANCIA) -> dict:
    """Quantos produtos fecham nos dois componentes, e o tamanho do desvio."""
    ok = [l for l in linhas
          if abs(l["dif_inicial"]) <= tolerancia and abs(l["dif_vendas"]) <= tolerancia]
    so_inicial = [l for l in linhas if abs(l["dif_inicial"]) > tolerancia
                  and abs(l["dif_vendas"]) <= tolerancia]
    so_vendas = [l for l in linhas if abs(l["dif_vendas"]) > tolerancia
                 and abs(l["dif_inicial"]) <= tolerancia]
    ambos = [l for l in linhas if abs(l["dif_inicial"]) > tolerancia
             and abs(l["dif_vendas"]) > tolerancia]
    return {"total": len(linhas), "ok": len(ok),
            "so_inicial": so_inicial, "so_vendas": so_vendas, "ambos": ambos,
            "pct_ok": (len(ok) / len(linhas)) if linhas else None}


def main(argv=None):
    p = argparse.ArgumentParser(description="Banco x planilha, por componente")
    p.add_argument("planilha")
    p.add_argument("--ate", type=date.fromisoformat, required=True,
                   help="a data da coluna viva da planilha, para os dois lados\n"
                        "                         olharem a mesma foto")
    p.add_argument("--colecoes", default=",".join(abertura.RECONSTRUIDAS))
    p.add_argument("--tolerancia", type=float, default=TOLERANCIA)
    p.add_argument("--limite", type=int, default=15)
    args = p.parse_args(argv)

    caminho = pathlib.Path(args.planilha.strip().strip("<>").strip('"').strip("'"))
    if not caminho.exists():
        print(f"\nNao encontrei o arquivo: {caminho}")
        return 1

    pl, sem_valor = da_planilha(str(caminho))
    if not pl:
        print("\nA planilha nao tem valor guardado nas formulas.")
        print("Abra no Excel e salve uma vez — ou use um arquivo que veio de la.")
        return 1
    ba = do_banco(args.ate)
    r = compara(pl, ba, args.colecoes.split(","))
    v = veredito(r["comparaveis"], args.tolerancia)

    print(f"\nBanco x planilha ate {args.ate}  —  colecoes {args.colecoes}")
    print(f"  planilha: {len(pl):,} codigo(s)   banco: {len(ba):,} codigo(s)")
    if sem_valor:
        print(f"  {sem_valor} linha(s) da planilha sem valor guardado, fora da conta")

    if not v["total"]:
        # Um "nao deu" que nao diz por que obriga a pessoa a abrir o codigo.
        # Foi o que esta mensagem fez em 27/09: 394 codigos de um lado, 739 do
        # outro, e nenhuma pista de que o filtro de colecao era o culpado.
        from collections import Counter
        na_planilha = Counter((x.get("colecao") or "(vazio)") for x in pl.values())
        no_banco = Counter((x.get("colecao") or "(vazio)") for x in ba.values())
        print("\n  Nenhum produto comparavel — o filtro de colecao nao casou.")
        print(f"\n  colecoes pedidas: {args.colecoes}")
        print("\n  na planilha:")
        for c, n in na_planilha.most_common(12):
            print(f"    {c:12} {n:>5}")
        print("\n  no banco (tabela produto):")
        for c, n in no_banco.most_common(12):
            print(f"    {c:12} {n:>5}")
        if no_banco.get("(vazio)", 0) == len(ba):
            print("\n  A tabela `produto` esta sem colecao em TODOS os codigos.")
            print("  Ela so e preenchida pelas rodadas de upload; a carga")
            print("  retroativa nao passa por la. Semeie do cadastro do ERP")
            print("  (produtos-erp.csv, do coletor.produtos) — a colecao e campo")
            print("  do cadastro desde a revisao da D11.")
        return 1

    print(f"\n  {v['total']} produto(s) comparavel(is), tolerancia de "
          f"{args.tolerancia:g} peca(s)")
    print(f"    fecham nos dois componentes  {v['ok']:>5}  ({v['pct_ok']:.0%})")
    print(f"    so o Estoque inicial difere  {len(v['so_inicial']):>5}")
    print(f"    so a Venda difere            {len(v['so_vendas']):>5}")
    print(f"    os dois diferem              {len(v['ambos']):>5}")

    for rotulo, grupo, campo in (("Estoque inicial", v["so_inicial"], "dif_inicial"),
                                 ("Venda", v["so_vendas"], "dif_vendas"),
                                 ("os dois", v["ambos"], "dif_inicial")):
        if not grupo:
            continue
        print(f"\n  maiores desvios — {rotulo}:")
        print(f'    {"codigo":8} {"col":6} {"inicial pl":>10} {"inicial bc":>10} '
              f'{"venda pl":>9} {"venda bc":>9}')
        print("    " + "-" * 60)
        for l in sorted(grupo, key=lambda x: -abs(x[campo]))[:args.limite]:
            print(f'    {l["codigo"]:8} {l["colecao"][:6]:6} '
                  f'{l["inicial_planilha"]:>10,.0f} {l["inicial_banco"]:>10,.0f} '
                  f'{l["vendas_planilha"]:>9,.0f} {l["vendas_banco"]:>9,.0f}')

    if r["so_planilha"] or r["so_banco"]:
        print(f"\n  codigo so na planilha: {len(r['so_planilha'])}   "
              f"so no banco: {len(r['so_banco'])}")
        print("  (diferenca de cadastro, nao de numero — nao entra no veredito)")
    if r["fora_da_janela"]:
        print(f"\n  {len(r['fora_da_janela'])} produto(s) de colecao anterior a "
              f"2026: fora da comparacao.")
        print("  A planilha acumula venda desde 2023; o banco comeca em 01/01/2026.")
        print("  Comparar os dois ali nao mede nada — a planilha ganha sempre.")

    print("\n  O percentual so vale quando os DOIS componentes fecham. Dois")
    print("  numeros errados em direcoes opostas dao a razao certa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
