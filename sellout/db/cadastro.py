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
    """{codigo: linha comercial} pelos blocos das abas de trabalho.

    Só interessa o bloco que **não** vira sigla: HOME, GLORIA KALIL, PIMA,
    CASHMERE, COURO. Um bloco AW26 não é linha comercial — é coleção, e essa
    vem do ERP.
    """
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=False, data_only=True)
    linhas = {}
    for aba in ABAS_TRABALHO:
        if aba not in wb.sheetnames:
            continue
        ws = wb[aba]
        for b in blocos_de(ws):
            titulo = (b["titulo"] or "")
            _pre, _sep, nome = titulo.partition("-")
            nome = (nome or titulo).strip().upper()
            if not nome or b["colecao"]:
                continue          # bloco de coleção: quem manda é o ERP
            for r in range(b["ini"], b["fim"] + 1):
                cod = norm_codigo(ws.cell(r, 2).value)
                if cod:
                    linhas[cod] = nome
    wb.close()
    return linhas


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


def grava_linhas(linhas: dict) -> int:
    """Só a linha comercial, e só de quem já existe na tabela.

    Produto que não está no cadastro do ERP não nasce aqui: linha comercial é
    atributo nosso sobre um produto do ERP, não um produto novo.
    """
    with conectar() as c:
        with c.cursor() as cur:
            n = 0
            for cod, nome in linhas.items():
                cur.execute("UPDATE produto SET linha = %s, alterado_em = now() "
                            "WHERE codigo = %s", (nome, cod))
                n += cur.rowcount
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description="Semeia colecao e linha comercial")
    p.add_argument("--cadastro", help="produtos-erp.csv do coletor.produtos")
    p.add_argument("--planilha", help="sellout geral.xlsx, para a linha comercial")
    p.add_argument("--aplicar", action="store_true")
    args = p.parse_args(argv)

    if not args.cadastro and not args.planilha:
        print("\nPasse --cadastro, --planilha, ou os dois.")
        return 1
    razao = por_que_nao()
    if razao:
        print(f"\nSem banco: {razao}")
        return 1

    if args.cadastro:
        caminho = pathlib.Path(args.cadastro)
        if not caminho.exists():
            print(f"\nNao encontrei: {caminho}")
            return 1
        produtos, sem_sigla = do_cadastro(str(caminho))
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
        linhas = da_planilha(str(caminho))
        print(f"\nLinha comercial: {len(linhas):,} produto(s)")
        for nome, n in Counter(linhas.values()).most_common():
            print(f"    {nome[:20]:20} {n:>5}")
        if args.aplicar:
            n = grava_linhas(linhas)
            print(f"\n  {n:,} produto(s) atualizado(s)")
            if n < len(linhas):
                print(f"  {len(linhas) - n} nao estavam na tabela produto — rode")
                print("  o --cadastro primeiro; linha comercial nao cria produto.")

    if not args.aplicar:
        print("\n  Nada foi gravado. Rode de novo com --aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
