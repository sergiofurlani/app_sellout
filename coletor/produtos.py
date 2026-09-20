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
    "ALTO INVERNO": "AW", "ALTO VERAO": "SS", "ALTO VERÃO": "SS",
}

# Coleções que não são estação: não ganham sigla e não deveriam ganhar.
#
# Categorização é o que está no cadastro — coleção, subcoleção, tipo, grupo.
# A descrição do produto não categoriza nada: "CAMISA CLÁSSICA" no nome não
# faz o produto ser da linha Clássicos, e ler o nome para deduzir categoria
# é como errar duas vezes e acertar por acaso na terceira.
SEM_ESTACAO = {"ATEMPORAL", "PERENE", "INDEF - INDEFINIDO", "INDEFINIDO", "INDEF"}

# A planilha Sellout Clássicos é a coleção PERENE do cadastro — só ela.
# ATEMPORAL também não é estação, e também não é Clássicos.
COLECAO_CLASSICOS = "PERENE"

CAMPOS = ["codigo", "interno", "colecao", "subcolecao", "sigla", "referencia", "descricao",
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


# Parâmetros obrigatórios que o `$metadata` não publica e o método exige.
# Descobertos pela sonda: `CAMPO=0, ORDEM=0`. `ORDEM` é booleano do lado do
# MN — mandar texto devolve "Could not convert variant of type (String) into
# type (Boolean)", que parece erro de parâmetro e não é.
OBRIGATORIOS = {"CAMPO": "0", "ORDEM": "0"}

# O MN prefixa quase toda descrição de cadastro com o código: "0002 - VERÃO",
# "0000000021 - 2011", "01 - BONDUKI...". O prefixo é numérico; o código de
# produto antigo é alfanumérico ("EYV013 - VESTIDO"), então descrição de
# produto não passa por aqui.
RE_PREFIXO = re.compile(r"^\s*\d+\s*-\s*")


def limpa(valor) -> str:
    return RE_PREFIXO.sub("", str(valor or "").strip())


def carrega(filtro_colecao: str | None = None, extras: dict | None = None,
            teto: int = 20000) -> list[dict]:
    params = {"$top": teto}
    params.update(OBRIGATORIOS)
    params.update(extras or {})
    if filtro_colecao:
        params["COLECAO"] = filtro_colecao
    linhas = mn.valores(mn.requisita(LISTA, **params))
    saida = []
    for l in linhas:
        codigo = str(campo(l, "cod_produto") or "").strip()
        if not codigo:
            continue
        col = limpa(campo(l, "desc_colecao"))
        sub = limpa(campo(l, "desc_subcolecao"))
        saida.append({
            "codigo": codigo,
            "interno": str(campo(l, "produtoac", "produto") or "").strip(),
            "colecao": col,
            "subcolecao": sub,
            "sigla": sigla(col, sub),
            "referencia": str(campo(l, "referencia") or "").strip(),
            "descricao": str(campo(l, "desc_produto", "descricao1") or "").strip(),
            "tipo": limpa(campo(l, "desc_tipo")),
            "grupo": limpa(campo(l, "desc_grupo")),
            "departamento": limpa(campo(l, "desc_departamento")),
            "marca": limpa(campo(l, "desc_marca")),
            "divisao": limpa(campo(l, "desc_divisao")),
            "categoria": limpa(campo(l, "desc_categoria")),
            "status": limpa(campo(l, "desc_status")),
            "grade": limpa(campo(l, "desc_grade")),
            "fornecedor": limpa(campo(l, "desc_fornecedor")),
            "cadastro": str(mn.parse_data(campo(l, "data_cadastro")) or ""),
        })
    return saida


def motivo(p: dict) -> str:
    """Por que este produto ficou sem sigla. Separa o que é para arrumar do
    que é assim mesmo — 'atemporal' nunca vai virar SS27."""
    col = (p["colecao"] or "").upper()
    if not col:
        return "sem coleção no cadastro"
    if col in SEM_ESTACAO or col.startswith("INDEF"):
        return "coleção não é estação (atemporal, perene, indefinido)"
    if col not in ESTACAO:
        return "coleção fora do mapa ESTACAO"
    return "coleção conhecida, mas a subcoleção não tem ano"


def por_codigo(produtos: list[dict]) -> dict[str, str]:
    """codigo -> sigla da coleção, para quem só quer o de-para."""
    return {p["codigo"]: p["sigla"] for p in produtos if p["sigla"]}


def main(argv=None):
    p = argparse.ArgumentParser(description="Cadastro de produtos do MN")
    p.add_argument("--salvar", metavar="ARQUIVO", help="grava tudo num CSV")
    p.add_argument("--colecao", help="filtra por uma coleção do ERP")
    p.add_argument("--codigos", default="",
                   help="mostra so estes codigos, separados por virgula")
    p.add_argument("--extras", default="",
                   help="acrescenta ou troca parametro do metodo, ex.: CAMPO=1")
    p.add_argument("--limite", type=int, default=20000, help="teto de $top")
    p.add_argument("--classicos", action="store_true",
                   help=f"lista a colecao {COLECAO_CLASSICOS} — o universo da "
                        "planilha Sellout Classicos")
    args = p.parse_args(argv)

    extras = {}
    for pedaco in args.extras.split(","):
        if "=" in pedaco:
            chave, _, valor = pedaco.partition("=")
            extras[chave.strip()] = valor.strip()

    try:
        produtos = carrega(args.colecao, extras, args.limite)
    except mn.Falha as e:
        print(f"\nFALHOU: {e}")
        print("Se recusou por parametro, rode a sonda e repasse o que ela achar:")
        print("  python -m coletor.sonda_parametros produtosac/Lista "
              "--parametro CAMPO --sem-datas")
        print("  python -m coletor.produtos --extras CAMPO=0,ORDEM=1")
        return 1

    print(f"\n{len(produtos)} produto(s) no cadastro")
    if len(produtos) >= args.limite:
        print(f"  ATENCAO: bateu no teto de {args.limite}. Veio cortado — "
              "suba --limite ou filtre com --colecao.")

    pares = Counter((p["colecao"], p["subcolecao"], p["sigla"]) for p in produtos)
    print(f"\n{'coleção':16} {'subcoleção':14} {'sigla':6} {'produtos':>9}")
    print("-" * 50)
    for (col, sub, sg), n in sorted(pares.items(), key=lambda x: -x[1])[:25]:
        marca = "" if sg else "   <-- sem sigla"
        print(f"{col[:16]:16} {sub[:14]:14} {sg:6} {n:>9}{marca}")

    sem = [p for p in produtos if not p["sigla"]]
    if sem:
        print(f"\n{len(sem)} produto(s) sem sigla. Por quê:")
        motivos = Counter(motivo(p) for p in sem)
        for m, n in motivos.most_common():
            print(f"  {n:>6}  {m}")
        desconhecidas = sorted({p["colecao"] for p in sem
                                if motivo(p).startswith("coleção fora")})
        if desconhecidas:
            print("\n  Acrescente em ESTACAO (coletor/produtos.py) as que "
                  "entram no sellout:")
            print("    " + ", ".join(desconhecidas[:15]))

    if args.classicos:
        perenes = [p for p in produtos
                   if (p["colecao"] or "").upper() == COLECAO_CLASSICOS]
        print(f"\nSellout Clássicos = coleção {COLECAO_CLASSICOS}: "
              f"{len(perenes)} produto(s)")
        for p in sorted(perenes, key=lambda x: x["codigo"]):
            print(f'  {p["codigo"]:9} {p["tipo"][:16]:16} {p["grupo"][:16]:16} '
                  f'{p["descricao"][:36]}')

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
