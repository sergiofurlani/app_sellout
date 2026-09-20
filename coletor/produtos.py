"""Cadastro de produtos do MN: coleção, subcoleção, tipo, grupo, marca.

    python -m coletor.produtos --salvar produtos-erp.csv

A coleção **é campo do cadastro**, não invenção da planilha: o `334128` é
coleção VERÃO, subcoleção 2027. Os blocos `SS27` e `AW26` das abas de trabalho
são a mesma informação escrita de outro jeito.

Isso resolve duas coisas:

1. **Código em dois blocos.** `330043` aparece em AW26 e SS27 na planilha; o
   cadastro diz qual é a coleção de verdade, então a transferência do ERP tem
   onde pousar em vez de virar ambiguidade.
2. **Os filtros da tela nova.** Tipo, grupo, departamento, marca e divisão vêm
   do mesmo lugar, de graça.

`produtosac/Lista` devolve 29 campos por produto e aceita filtro por coleção.
É o método mais enxuto que traz `COD_PRODUTO` com `DESC_COLECAO` e
`DESC_SUBCOLECAO` juntos.

A sigla (`SS27`, `AW26`) é montada aqui: estação pela coleção, ano pelos dois
últimos dígitos da subcoleção. O mapa está em `ESTACAO` e é o único ponto onde
o vocabulário do ERP encontra o da planilha.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter

from . import mn

LISTA = "/api/millenium/produtosac/Lista"

# Coleção do ERP -> sigla da planilha. VERÃO é a estação de venda, e a planilha
# usa a convenção do setor: SS (spring/summer) e AW (autumn/winter).
ESTACAO = {
    "VERAO": "SS", "VERÃO": "SS", "SS": "SS", "PRIMAVERA": "SS",
    "INVERNO": "AW", "AW": "AW", "OUTONO": "AW",
}

CAMPOS = ["codigo", "colecao", "subcolecao", "sigla", "referencia", "descricao",
          "tipo", "grupo", "departamento", "marca", "divisao", "categoria",
          "status", "grade", "fornecedor", "cadastro"]


def campo(d: dict, *nomes):
    for n in nomes:
        for chave in (n, n.lower(), n.upper()):
            if chave in d:
                return d[chave]
    return None


def sigla(colecao: str, subcolecao: str) -> str:
    """VERÃO + 2027 -> SS27. Devolve vazio quando não dá para montar."""
    est = ESTACAO.get((colecao or "").strip().upper())
    ano = re.search(r"(\d{2})\s*$", (subcolecao or "").strip())
    if not est or not ano:
        return ""
    return f"{est}{ano.group(1)}"


def carrega(filtro_colecao: str | None = None) -> list[dict]:
    params = {"$top": 20000}
    if filtro_colecao:
        params["COLECAO"] = filtro_colecao
    linhas = mn.valores(mn.requisita(LISTA, **params))
    saida = []
    for l in linhas:
        codigo = str(campo(l, "cod_produto") or "").strip()
        if not codigo:
            continue
        col = str(campo(l, "desc_colecao") or "").strip()
        sub = str(campo(l, "desc_subcolecao") or "").strip()
        saida.append({
            "codigo": codigo,
            "colecao": col,
            "subcolecao": sub,
            "sigla": sigla(col, sub),
            "referencia": str(campo(l, "referencia") or "").strip(),
            "descricao": str(campo(l, "desc_produto", "descricao1") or "").strip(),
            "tipo": str(campo(l, "desc_tipo") or "").strip(),
            "grupo": str(campo(l, "desc_grupo") or "").strip(),
            "departamento": str(campo(l, "desc_departamento") or "").strip(),
            "marca": str(campo(l, "desc_marca") or "").strip(),
            "divisao": str(campo(l, "desc_divisao") or "").strip(),
            "categoria": str(campo(l, "desc_categoria") or "").strip(),
            "status": str(campo(l, "desc_status") or "").strip(),
            "grade": str(campo(l, "desc_grade") or "").strip(),
            "fornecedor": str(campo(l, "desc_fornecedor") or "").strip(),
            "cadastro": str(mn.parse_data(campo(l, "data_cadastro")) or ""),
        })
    return saida


def por_codigo(produtos: list[dict]) -> dict[str, str]:
    """codigo -> sigla da coleção, para quem só quer o de-para."""
    return {p["codigo"]: p["sigla"] for p in produtos if p["sigla"]}


def main(argv=None):
    p = argparse.ArgumentParser(description="Cadastro de produtos do MN")
    p.add_argument("--salvar", metavar="ARQUIVO", help="grava tudo num CSV")
    p.add_argument("--colecao", help="filtra por uma coleção do ERP")
    p.add_argument("--codigos", default="",
                   help="mostra so estes codigos, separados por virgula")
    args = p.parse_args(argv)

    try:
        produtos = carrega(args.colecao)
    except mn.Falha as e:
        print(f"\nFALHOU: {e}")
        print("Se recusou por parametro, tente --colecao com um valor do ERP.")
        return 1

    print(f"\n{len(produtos)} produto(s) no cadastro")

    pares = Counter((p["colecao"], p["subcolecao"], p["sigla"]) for p in produtos)
    print(f"\n{'coleção':16} {'subcoleção':14} {'sigla':6} {'produtos':>9}")
    print("-" * 50)
    for (col, sub, sg), n in sorted(pares.items(), key=lambda x: -x[1])[:25]:
        marca = "" if sg else "   <-- sem sigla"
        print(f"{col[:16]:16} {sub[:14]:14} {sg:6} {n:>9}{marca}")

    sem = [p for p in produtos if not p["sigla"]]
    if sem:
        print(f"\n{len(sem)} produto(s) sem sigla montada. Se a coleção deles "
              "entra no\nsellout, acrescente o nome em ESTACAO, em coletor/produtos.py.")

    if args.codigos:
        print("\ncódigos pedidos:")
        procurados = {c.strip() for c in args.codigos.split(",") if c.strip()}
        achados = {p["codigo"] for p in produtos}
        for p in produtos:
            if p["codigo"] in procurados:
                print(f'  {p["codigo"]:9} {p["sigla"]:6} {p["colecao"]:12} '
                      f'{p["subcolecao"]:10} {p["tipo"][:18]:18} {p["descricao"][:30]}')
        for c in sorted(procurados - achados):
            print(f"  {c:9} NAO ESTA NO CADASTRO")

    if args.salvar:
        with open(args.salvar, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
            w.writeheader()
            w.writerows(produtos)
        print(f"\n  {args.salvar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
