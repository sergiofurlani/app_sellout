"""Semeia as dimensões do produto no banco: coleção e linha comercial.

    python -m sellout.db.cadastro --cadastro produtos-erp.csv
    python -m sellout.db.cadastro --cadastro produtos-erp.csv --aplicar
    python -m sellout.db.cadastro --planilha "sellout geral.xlsx" --aplicar

O cano que faltava. O `coletor/produtos.py` já monta a sigla desde a revisão da
D11 — VERÃO + 2027 = SS27, INVERNO = AW, e `PERENE` são os Clássicos —, mas
nada levava isso para a tabela `produto`. O resultado apareceu em 27/09: a
comparação banco x planilha achou 394 códigos de um lado e 739 do outro e
**nenhum comparável**, porque a coleção estava vazia em todos.

São duas dimensões, de duas fontes diferentes, e por isso duas cargas:

    --cadastro   coleção, descrição, divisão, grupo, marca, grade  (do ERP)
    --planilha   linha comercial: HOME, GLORIA KALIL, PIMA...      (nossa)

A linha comercial não existe como campo no ERP — é o nome do bloco das abas de
trabalho (D11). Enquanto ela viver só na planilha, o banco não sabe agrupar por
ela, e a planilha continua indispensável por esse motivo sozinho.

**A coleção é do produto, não da venda.** Produto antigo pode vender no inverno
seguinte; o sellout dele continua na coleção dele. Por isso isto é dimensão,
gravada uma vez e corrigida quando o cadastro muda — nunca derivada da data do
movimento.

Nada é gravado sem `--aplicar`.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
from collections import Counter

from ..core.leitura import ABAS_TRABALHO, blocos_de, norm_codigo
from .conexao import conectar, por_que_nao

# Coleções da planilha que são linha comercial, não estação: o bloco diz
# "FEMININO - HOME" e isso não é coleção nenhuma (D11).
COLECAO_CLASSICOS = "PERENE"

# Onde o negócio decidiu manter a classificação da planilha contra o que o
# cadastro do ERP diz. Fica em arquivo versionado, com motivo e data, porque
# ajuste de dimensão sem rastro é o tipo de coisa que ninguém explica seis
# meses depois — e porque a lista precisa **encolher**: quando o cadastro for
# corrigido, a exceção vira redundante e o programa avisa que pode sair.
EXCECOES = pathlib.Path(__file__).resolve().parents[2] / "docs" / "colecao-excecoes.csv"


def le_excecoes(caminho=None) -> dict:
    """{codigo: colecao} decidida pelo negócio. Ausente devolve vazio."""
    caminho = pathlib.Path(caminho or EXCECOES)
    if not caminho.exists():
        return {}
    fora = {}
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            cod = norm_codigo(linha.get("codigo"))
            col = (linha.get("colecao") or "").strip().upper()
            if cod and col:
                fora[cod] = col
    return fora


def aplica_excecoes(produtos, excecoes) -> tuple[list, list]:
    """Sobrepõe a coleção do ERP onde o negócio decidiu.

    Devolve também o que **mudou de fato**: exceção que hoje diz o mesmo que o
    cadastro já não é exceção, é linha morta na lista, e some sozinha da
    próxima vez que alguém olhar.
    """
    aplicadas = []
    for p in produtos:
        escolhida = excecoes.get(p["codigo"])
        if not escolhida:
            continue
        if escolhida != p["colecao"]:
            aplicadas.append({"codigo": p["codigo"], "erp": p["colecao"],
                              "decidida": escolhida})
            p["colecao"] = escolhida
    redundantes = [c for c, col in excecoes.items()
                   if any(p["codigo"] == c and p["colecao"] == col
                          for p in produtos)
                   and not any(a["codigo"] == c for a in aplicadas)]
    return aplicadas, redundantes


def do_cadastro(caminho: str) -> tuple[list[dict], dict]:
    """Lê o produtos-erp.csv. A coleção gravada é a **sigla** (SS27, AW26).

    É assim que o negócio fala e é o que a planilha usa nos blocos. Guardar
    VERÃO/2027 obrigaria todo leitor a remontar a sigla, e a regra ficaria
    repetida em cada lugar que consulta.
    """
    produtos, motivos = [], Counter()
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            cod = norm_codigo(linha.get("codigo"))
            if not cod:
                continue
            sigla = (linha.get("sigla") or "").strip().upper()
            bruta = (linha.get("colecao") or "").strip().upper()
            if not sigla and bruta == COLECAO_CLASSICOS:
                sigla = COLECAO_CLASSICOS
            if not sigla:
                motivos[bruta or "(sem colecao)"] += 1
            produtos.append({
                "codigo": cod,
                "colecao": sigla,
                "descricao": (linha.get("descricao") or "").strip(),
                "divisao": (linha.get("divisao") or "").strip(),
                "departamento": (linha.get("departamento") or "").strip(),
                "grupo": (linha.get("grupo") or "").strip(),
                "marca": (linha.get("marca") or "").strip(),
                "grade": (linha.get("grade") or "").strip(),
            })
    return produtos, dict(motivos)


def da_planilha(caminho: str) -> dict:
    """{codigo: {bloco, aba, colecao, linha}} — onde o produto está **hoje**.

    Registra **todos** os blocos, não só os de linha comercial. Uma primeira
    versão guardava só HOME/PIMA/CASHMERE e descartava AW26 e SS27, por supor
    que a coleção era assunto exclusivo do ERP. Mas é justamente a
    classificação atual da planilha que permite **auditar** o cadastro
    enquanto ele está sendo arrumado: sem ela não há contra o quê comparar.

    O bloco vira uma coisa ou outra conforme o nome:

        AW26, SS27, ...   coleção — comparável com o que o ERP diz
        HOME, PIMA, ...   linha comercial — não existe no ERP (D11)
    """
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=False, data_only=True)
    onde = {}
    for aba in ABAS_TRABALHO:
        if aba not in wb.sheetnames:
            continue
        ws = wb[aba]
        for b in blocos_de(ws):
            titulo = (b["titulo"] or "")
            _pre, _sep, nome = titulo.partition("-")
            nome = (nome or titulo).strip().upper()
            if not nome:
                continue
            sigla = (b["colecao"] or "").upper()
            for r in range(b["ini"], b["fim"] + 1):
                cod = norm_codigo(ws.cell(r, 2).value)
                if cod:
                    onde[cod] = {"bloco": nome, "aba": aba,
                                 "colecao": sigla,
                                 "linha": "" if sigla else nome}
    wb.close()
    return onde


def divergencias(onde: dict, cadastro: dict) -> dict:
    """Onde a planilha e o cadastro do ERP discordam da coleção.

    É a lista de trabalho para arrumar o cadastro. Enquanto ela não zerar, o
    ERP ainda não pode ser a única fonte — e trocar antes disso seria mudar de
    referência sem saber o tamanho da diferença.
    """
    iguais, difere, so_planilha, sem_colecao_erp = [], [], [], []
    for cod, d in sorted(onde.items()):
        if not d["colecao"]:
            continue                       # bloco de linha comercial, não compara
        erp = cadastro.get(cod)
        if erp is None:
            so_planilha.append({"codigo": cod, "planilha": d["colecao"]})
        elif not erp:
            sem_colecao_erp.append({"codigo": cod, "planilha": d["colecao"]})
        elif erp == d["colecao"]:
            iguais.append(cod)
        else:
            difere.append({"codigo": cod, "planilha": d["colecao"], "erp": erp})
    return {"iguais": iguais, "difere": difere, "so_planilha": so_planilha,
            "sem_colecao_erp": sem_colecao_erp}


def grava_cadastro(produtos) -> int:
    """Upsert. Campo vazio não apaga o que já está lá."""
    with conectar() as c:
        with c.cursor() as cur:
            for p in produtos:
                cur.execute(
                    "INSERT INTO produto (codigo, descricao, divisao, "
                    "  departamento, grupo, marca, grade, colecao) "
                    "VALUES (%(codigo)s,%(descricao)s,%(divisao)s,"
                    "  %(departamento)s,%(grupo)s,%(marca)s,%(grade)s,%(colecao)s) "
                    "ON CONFLICT (codigo) DO UPDATE SET "
                    "  descricao    = coalesce(nullif(excluded.descricao, ''), produto.descricao),"
                    "  divisao      = coalesce(nullif(excluded.divisao, ''), produto.divisao),"
                    "  departamento = coalesce(nullif(excluded.departamento, ''), produto.departamento),"
                    "  grupo        = coalesce(nullif(excluded.grupo, ''), produto.grupo),"
                    "  marca        = coalesce(nullif(excluded.marca, ''), produto.marca),"
                    "  grade        = coalesce(nullif(excluded.grade, ''), produto.grade),"
                    "  colecao      = coalesce(nullif(excluded.colecao, ''), produto.colecao),"
                    "  alterado_em  = now()", p)
    return len(produtos)


def grava_planilha(onde: dict, quando=None) -> int:
    """Grava a classificação atual da planilha: bloco e linha comercial.

    Só de quem já existe na tabela. Produto que não está no cadastro do ERP
    não nasce aqui: isto é atributo **sobre** um produto do ERP, não um
    produto novo — e criar um registro só com o bloco esconderia justamente o
    produto que falta no cadastro.

    **A coleção não é escrita por aqui.** Ela vem do ERP; o bloco fica ao lado,
    como registro do que era, para a auditoria.
    """
    from datetime import date as _date
    quando = quando or _date.today()
    with conectar() as c:
        with c.cursor() as cur:
            n = 0
            for cod, d in onde.items():
                cur.execute(
                    "UPDATE produto SET bloco_planilha = %s, bloco_em = %s, "
                    "  linha = coalesce(nullif(%s, ''), linha), "
                    "  alterado_em = now() WHERE codigo = %s",
                    (d["bloco"], quando, d["linha"], cod))
                n += cur.rowcount
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description="Semeia colecao e linha comercial")
    p.add_argument("--cadastro", help="produtos-erp.csv do coletor.produtos")
    p.add_argument("--planilha", help="sellout geral.xlsx, para a linha comercial")
    p.add_argument("--excecoes", default=None,
                   help=f"padrao: {EXCECOES.name} em docs/")
    p.add_argument("--aplicar", action="store_true")
    args = p.parse_args(argv)

    if not args.cadastro and not args.planilha:
        print("\nPasse --cadastro, --planilha, ou os dois.")
        return 1
    razao = por_que_nao()
    if razao:
        print(f"\nSem banco: {razao}")
        return 1

    produtos = []
    if args.cadastro:
        caminho = pathlib.Path(args.cadastro)
        if not caminho.exists():
            print(f"\nNao encontrei: {caminho}")
            return 1
        produtos, sem_sigla = do_cadastro(str(caminho))

        excecoes = le_excecoes(args.excecoes)
        if excecoes:
            aplicadas, redundantes = aplica_excecoes(produtos, excecoes)
            print(f"\nExcecoes de colecao: {len(excecoes)} no arquivo, "
                  f"{len(aplicadas)} mudaram a colecao do ERP")
            for a in aplicadas[:25]:
                print(f"    {a['codigo']:9} {a['erp'] or '(vazia)':8} -> {a['decidida']}")
            if redundantes:
                print(f"\n  {len(redundantes)} exceção(oes) ja concordam com o "
                      f"cadastro e podem sair do arquivo:")
                print("    " + ", ".join(sorted(redundantes)))
            nao_achadas = [c for c in excecoes
                           if not any(p["codigo"] == c for p in produtos)]
            if nao_achadas:
                print(f"\n  {len(nao_achadas)} exceção(oes) de codigo que nao esta "
                      f"no cadastro: {', '.join(sorted(nao_achadas))}")

        com = sum(1 for x in produtos if x["colecao"])
        print(f"\nCadastro: {len(produtos):,} produto(s), {com:,} com colecao")
        por_col = Counter(x["colecao"] for x in produtos if x["colecao"])
        for col, n in por_col.most_common(12):
            print(f"    {col:10} {n:>5}")
        if sem_sigla:
            print(f"\n  {len(produtos) - com:,} sem sigla, por colecao de origem:")
            for motivo, n in sorted(sem_sigla.items(), key=lambda x: -x[1])[:8]:
                print(f"    {motivo[:28]:28} {n:>5}")
            print("  Coleção fora do mapa ESTACAO vira produto sem agrupamento —")
            print("  acrescente em coletor/produtos.py se alguma delas importar.")
        if args.aplicar:
            print(f"\n  {grava_cadastro(produtos):,} produto(s) gravado(s)")

    if args.planilha:
        caminho = pathlib.Path(args.planilha)
        if not caminho.exists():
            print(f"\nNao encontrei: {caminho}")
            return 1
        onde = da_planilha(str(caminho))
        print(f"\nClassificacao atual da planilha: {len(onde):,} produto(s)")
        for nome, n in Counter(d["bloco"] for d in onde.values()).most_common(20):
            print(f"    {nome[:22]:22} {n:>5}")

        # A auditoria do cadastro: onde os dois discordam.
        do_erp = {p["codigo"]: p["colecao"] for p in (produtos or [])}
        if do_erp:
            d = divergencias(onde, do_erp)
            print(f"\n  Planilha x cadastro do ERP, so os blocos de colecao:")
            print(f"    iguais                      {len(d['iguais']):>5}")
            print(f"    colecao diferente           {len(d['difere']):>5}")
            print(f"    sem colecao no cadastro     {len(d['sem_colecao_erp']):>5}")
            print(f"    nao estao no cadastro       {len(d['so_planilha']):>5}")
            if d["difere"]:
                print("\n    codigo    planilha   cadastro")
                for x in d["difere"][:25]:
                    print(f"    {x['codigo']:9} {x['planilha']:10} {x['erp']}")
                if len(d["difere"]) > 25:
                    print(f"    ... e mais {len(d['difere']) - 25}")
            if d["difere"] or d["sem_colecao_erp"] or d["so_planilha"]:
                print("\n  Esta e a lista de trabalho para arrumar o cadastro.")
                print("  Enquanto ela nao zerar, o ERP ainda nao pode ser a unica")
                print("  fonte — trocar antes seria mudar de referencia sem saber")
                print("  o tamanho da diferenca.")
        else:
            print("\n  (rode junto com --cadastro para comparar com o ERP)")

        if args.aplicar:
            n = grava_planilha(onde)
            print(f"\n  {n:,} produto(s) com o bloco registrado")
            if n < len(onde):
                print(f"  {len(onde) - n} nao estavam na tabela produto — rode")
                print("  o --cadastro primeiro; o bloco nao cria produto.")

    if not args.aplicar:
        print("\n  Nada foi gravado. Rode de novo com --aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
