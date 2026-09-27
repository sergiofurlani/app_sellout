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
from .conexao import conectar

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


def nasceu_antes(corte: date) -> set:
    """Códigos com histórico de sellout **anterior** ao corte.

    A planilha acumula venda e estoque inicial desde que o produto entrou na
    aba — 2023, para muitos. O banco começa em 01/01/2026 (D10/D24). Num
    produto assim, falta o mesmo pedaço dos dois lados, e a divergência está
    explicada antes de qualquer investigação.

    Separar isso **com dado** é o que evita chamar de "produto antigo" um
    grupo escolhido a olho. A fonte é `sellout_historico`, que tem a data de
    cada semana por código desde 2022.
    """
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute("SELECT codigo FROM sellout_historico "
                        "GROUP BY codigo HAVING min(data) < %s", (corte,))
            return {r[0] for r in cur.fetchall()}


def do_banco(ate: date) -> dict:
    """{codigo: {...}} — as cores somadas, porque a planilha é por produto."""
    por_codigo = defaultdict(lambda: {"estoque_inicial": 0.0, "vendas": 0.0,
                                      "colecao": "", "venda_desde": None})
    for l in consulta.sellout(ate):
        d = por_codigo[l["codigo"]]
        d["estoque_inicial"] += float(l["estoque_inicial"])
        d["vendas"] += float(l["vendas"])
        d["colecao"] = d["colecao"] or (l["colecao"] or "").upper()
        desde = l.get("venda_desde")
        if desde and (d["venda_desde"] is None or desde < d["venda_desde"]):
            d["venda_desde"] = desde
    return dict(por_codigo)


def compara(planilha: dict, banco: dict, comparaveis, antigos=()) -> dict:
    """Junta os dois lados e separa o que dá para comparar do que não dá.

    `antigos` são os códigos com vida anterior à janela do banco. Eles saem do
    veredito por **dado**, não por aparência: a diferença deles já está
    explicada, e mantê-los afogaria o sinal do que não está.
    """
    alvo = {c.upper() for c in comparaveis}
    antigos = set(antigos)
    linhas, fora, so_planilha, so_banco, anteriores = [], [], [], [], []

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
        item["venda_desde"] = b.get("venda_desde")
        if item["colecao"] not in alvo:
            fora.append(item)
        elif cod in antigos:
            anteriores.append(item)
        else:
            linhas.append(item)

    return {"comparaveis": linhas, "fora_da_janela": fora,
            "vida_anterior": anteriores,
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


def apura(linhas, devolucoes, planilha_desde=None, tolerancia=TOLERANCIA) -> list:
    """Cerca cada divergência de venda com os números vizinhos.

    **Isto não explica nada — testa uma identidade.** A devolução entra em
    `venda` com sinal negativo, e o total do banco já é líquido. Se uma coluna
    conta só a saída, ela fica maior pelo tamanho exato do que voltou:

        vendas_planilha − vendas_banco + devolucao == 0

    `resto` é esse lado esquerdo. Zero em um produto é coincidência; zero nos
    nove do grupo de −3, com a devolução de cada um sendo o seu próprio
    número, não é. E se der diferente de zero, a hipótese morre aqui em vez de
    virar conclusão — foi o que aconteceu com `vida_anterior`, que pegou 5 de
    255.

    Nenhum rótulo de causa: `resto` e as duas datas são o que a apuração tem.
    """
    planilha_desde = planilha_desde or {}
    saida = []
    for l in linhas:
        dev = float(devolucoes.get(l["codigo"], {}).get("pecas", 0.0))
        item = dict(l)
        item["devolucao"] = dev
        item["resto"] = l["dif_vendas"] + dev
        item["fecha_com_devolucao"] = bool(dev) and abs(item["resto"]) <= tolerancia
        item["planilha_desde"] = planilha_desde.get(l["codigo"])
        saida.append(item)
    return saida


def main(argv=None):
    p = argparse.ArgumentParser(description="Banco x planilha, por componente")
    p.add_argument("planilha")
    p.add_argument("--ate", type=date.fromisoformat, required=True,
                   help="a data da coluna viva da planilha, para os dois lados\n"
                        "                         olharem a mesma foto")
    p.add_argument("--colecoes", default=",".join(abertura.RECONSTRUIDAS))
    p.add_argument("--corte", type=date.fromisoformat, default=abertura.DATA_BASE,
                   help="inicio da janela do banco; produto com historico\n"
                        "                         anterior sai do veredito (padrao 2026-01-01)")
    p.add_argument("--com-antigos", action="store_true",
                   help="nao separa quem tem vida anterior ao corte")
    p.add_argument("--tolerancia", type=float, default=TOLERANCIA)
    p.add_argument("--limite", type=int, default=15)
    p.add_argument("--apura", action="store_true",
                   help="cerca cada desvio de venda com a devolucao do periodo\n"
                        "                         e as datas de estreia dos dois lados")
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
    antigos = set() if args.com_antigos else nasceu_antes(args.corte)
    r = compara(pl, ba, args.colecoes.split(","), antigos)
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

    if args.apura:
        divergentes = v["so_vendas"] + v["ambos"]
        if not divergentes:
            print("\n  Nenhum desvio de venda para apurar.")
        else:
            ap = apura(divergentes, consulta.devolucoes(args.ate),
                       consulta.primeira_semana_planilha(), args.tolerancia)
            fecham = [x for x in ap if x["fecha_com_devolucao"]]
            print(f"\n  apuracao — {len(divergentes)} produto(s) com desvio de venda")
            print("  resto = (venda pl - venda bc) + devolucao. Zero significa que o")
            print("  desvio tem o tamanho exato do que voltou no periodo.")
            print(f'\n    {"codigo":8} {"venda pl":>8} {"venda bc":>8} {"dif":>6} '
                  f'{"devol":>6} {"resto":>6}  {"bc desde":10} {"pl desde":10}')
            print("    " + "-" * 76)
            for x in sorted(ap, key=lambda y: (not y["fecha_com_devolucao"],
                                               -abs(y["dif_vendas"])))[:args.limite * 2]:
                print(f'    {x["codigo"]:8} {x["vendas_planilha"]:>8,.0f} '
                      f'{x["vendas_banco"]:>8,.0f} {x["dif_vendas"]:>6,.0f} '
                      f'{x["devolucao"]:>6,.0f} {x["resto"]:>6,.0f}  '
                      f'{str(x["venda_desde"] or "-"):10} '
                      f'{str(x["planilha_desde"] or "-"):10}')
            print(f"\n    resto zero (dentro de {args.tolerancia:g}): "
                  f"{len(fecham)} de {len(divergentes)}")
            if len(fecham) < len(divergentes):
                print("    Nos outros a devolucao NAO da conta do desvio — e esses sao")
                print("    os que ainda nao tem numero que os cerque.")

    if r["so_planilha"] or r["so_banco"]:
        print(f"\n  codigo so na planilha: {len(r['so_planilha'])}   "
              f"so no banco: {len(r['so_banco'])}")
        print("  (diferenca de cadastro, nao de numero — nao entra no veredito)")
    if r.get("vida_anterior"):
        n = len(r["vida_anterior"])
        v2 = veredito(r["vida_anterior"], args.tolerancia)
        print(f"\n  {n} produto(s) com historico ANTERIOR a {args.corte}: fora do")
        print("  veredito. A planilha acumula desde que o produto entrou na aba;")
        print("  o banco comeca no corte. Falta o mesmo pedaco dos dois lados.")
        print(f"  (se entrassem, fechariam {v2['ok']} de {n})")

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
