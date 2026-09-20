"""Descobre, por tentativa, os valores que um parâmetro de relatório aceita.

Os métodos de relatório do MN — `MovimentacaoPorGrade`, `Transferencia_Filiais`,
`EstoqueGerencial` — exigem `QUEBRA`, `LAYOUT` ou `ORDEM` com valor de uma lista
que o `$metadata` **não publica**. Não há `EnumType` nenhum no arquivo inteiro,
e não existe método que liste as opções. Sobra tentar.

    python -m coletor.sonda_parametros saidas/MovimentacaoPorGrade \\
        --parametro QUEBRA --de 2026-09-01 --ate 2026-09-07 \\
        --extras SCRIPTEVENTO=105

Imprime, para cada valor tentado: aceito ou recusado, quantas linhas vieram, e
os campos da primeira. Um valor aceito destrava o método inteiro.

Por que vale a pena: `MovimentacaoPorGrade` é o único método que devolve
`COD_PRODUTO` **e** `COD_COR` do ERP com filtro por evento e por filial. É o que
falta para ler as entradas que não passam pela Elena — o sapato, por exemplo,
entra na loja pelo `105 RECEBIMENTO DE COMPRA P.A (LOJAS)`, e `vendas_consulta_completa`
não enxerga evento de entrada.

Nada aqui grava. São chamadas de leitura, uma por valor tentado.
"""

from __future__ import annotations

import argparse
from datetime import date

from . import mn

# Valores plausíveis para um parâmetro de agrupamento num relatório de estoque.
# A ordem importa pouco; o que importa é cobrir as famílias: sem quebra, por
# dimensão do produto, por filial, por data.
CANDIDATOS = {
    "QUEBRA": ["", "N", "S", "0", "1", "NENHUMA", "NENHUM", "PRODUTO", "FILIAL",
               "DATA", "COR", "EVENTO", "MARCA", "COLECAO", "GRUPO", "TIPO",
               "DIVISAO", "DEPARTAMENTO", "CLIENTE", "FORNECEDOR", "GRADE",
               "TAMANHO", "REFERENCIA", "SUBCOLECAO", "CATEGORIA"],
    "LAYOUT": ["", "0", "1", "2", "PADRAO", "NORMAL", "ANALITICO", "SINTETICO",
               "DETALHADO", "RESUMIDO", "COMPLETO", "SIMPLES"],
    "ORDEM": ["", "0", "1", "PRODUTO", "DATA", "FILIAL", "CODIGO", "ALFABETICA",
              "DESCRICAO"],
    "TIPO": ["", "E", "S", "T", "A", "0", "1", "2", "TODOS"],
    # CAMPO num método de listagem costuma ser o campo pelo qual se busca —
    # então os candidatos são os próprios nomes de campo que o método devolve.
    "CAMPO": ["", "COD_PRODUTO", "CODIGO", "PRODUTO", "PRODUTOAC", "REFERENCIA",
              "DESCRICAO", "DESCRICAO1", "DESC_PRODUTO", "NOME", "COLECAO",
              "DESC_COLECAO", "TODOS", "0", "1"],
    "FILTRO": ["", "TODOS", "=", "IGUAL", "CONTEM", "CONTENDO", "INICIA",
               "INICIADO", "LIKE", "0", "1", "2", "N", "S"],
}


def dia(t: str) -> date:
    return date.fromisoformat(t)


def pares(texto: str) -> dict:
    """--extras SCRIPTEVENTO=105,FILIAL=00044 -> dict."""
    fora = {}
    for pedaco in (texto or "").split(","):
        if "=" in pedaco:
            chave, _, valor = pedaco.partition("=")
            fora[chave.strip()] = valor.strip()
    return fora


def tenta(caminho: str, params: dict) -> tuple[bool, str, list]:
    try:
        linhas = mn.valores(mn.requisita(caminho, **params))
    except mn.Falha as e:
        msg = str(e)
        # a mensagem útil vem dentro do JSON de erro do MN
        if "not found in list" in msg:
            import re
            achado = re.search(r"parameter (\w+)", msg)
            qual = achado.group(1) if achado else "?"
            return False, f"recusou {qual}", []
        return False, msg[:90], []
    return True, f"{len(linhas)} linha(s)", linhas


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Tenta valores para um parametro de relatorio do MN")
    p.add_argument("metodo", help="grupo/Metodo, ex.: saidas/MovimentacaoPorGrade")
    p.add_argument("--parametro", required=True, help="QUEBRA, LAYOUT, ORDEM, TIPO")
    p.add_argument("--de", type=dia, default=date.today())
    p.add_argument("--ate", type=dia, default=date.today())
    p.add_argument("--extras", default="", help="OUTRO=valor,OUTRO2=valor")
    p.add_argument("--valores", default="",
                   help="lista propria, separada por virgula (substitui a embutida)")
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--sem-datas", action="store_true",
                   help="metodo de cadastro nao aceita DATAI/DATAF")
    args = p.parse_args(argv)

    caminho = f"/api/millenium/{args.metodo.strip('/')}"
    base = {"$top": args.top}
    if not args.sem_datas:
        base["DATAI"] = args.de.isoformat()
        base["DATAF"] = args.ate.isoformat()
    base.update(pares(args.extras))

    valores = ([v.strip() for v in args.valores.split(",")] if args.valores
               else CANDIDATOS.get(args.parametro.upper(), [""]))

    print(f"\n{caminho}")
    print(f"  fixos: {base}")
    print(f"  tentando {len(valores)} valor(es) para {args.parametro}\n")

    aceitos = []
    for v in valores:
        params = dict(base)
        params[args.parametro.upper()] = v
        ok, msg, linhas = tenta(caminho, params)
        # "recusou OUTRO" significa que ESTE valor passou e a barreira mudou de
        # parâmetro — é progresso, e a próxima rodada ataca o outro.
        passou = ok or (msg.startswith("recusou")
                        and not msg.endswith(args.parametro.upper()))
        marca = "OK  " if ok else ("->  " if passou else "    ")
        print(f'  {marca}{args.parametro}={v!r:16} {msg}')
        if passou and not ok:
            seguinte = msg.split()[-1]
            print(f"\n  {args.parametro}={v!r} passou. Agora a barreira e {seguinte}:")
            print(f"    python -m coletor.sonda_parametros {args.metodo} "
                  f"--parametro {seguinte} "
                  f"--extras {args.parametro.upper()}={v}"
                  f"{',' + args.extras if args.extras else ''}"
                  f"{' --sem-datas' if args.sem_datas else ''}")
            return 0
        if ok:
            aceitos.append((v, linhas))
            if linhas:
                break          # achou e voltou dado: não precisa testar o resto

    if not aceitos:
        print("\n  Nenhum valor aceito. Tente --valores com outras opcoes, ou")
        print("  confira na tela do ERP como esse relatorio e chamado.")
        return 1

    valor, linhas = aceitos[-1]
    print(f"\n  Aceito: {args.parametro}={valor!r}")
    if linhas:
        print("  Campos da primeira linha:")
        for k, val in list(linhas[0].items())[:30]:
            print(f'    {k:22} {str(val)[:46]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
