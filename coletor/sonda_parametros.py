"""Descobre, por tentativa, os valores que um parâmetro de relatório aceita.

Os métodos de relatório e de cadastro do MN — `MovimentacaoPorGrade`,
`Transferencia_Filiais`, `produtosac/Lista` — exigem `QUEBRA`, `LAYOUT`,
`ORDEM`, `CAMPO` com valor de uma lista que o `$metadata` **não publica**. Não
há `EnumType` nenhum no arquivo inteiro, e não existe método que liste as
opções. Sobra tentar.

    python -m coletor.sonda_parametros produtosac/Lista --parametro CAMPO --sem-datas

O MN só reclama de **um** parâmetro por vez. Quando a reclamação muda de nome,
o valor da vez foi aceito e a barreira andou — a sonda entende isso e continua
sozinha, fixando o que já passou e atacando o parâmetro seguinte, até o método
responder ou acabar a paciência (`--fundo`). No final ela imprime a combinação
inteira, que é o que interessa.

Por que vale a pena: `MovimentacaoPorGrade` é o único método que devolve
`COD_PRODUTO` **e** `COD_COR` do ERP com filtro por evento e por filial. É o
que falta para ler as entradas que não passam pela Elena — o sapato entra na
loja pelo `105 RECEBIMENTO DE COMPRA P.A (LOJAS)`, e `vendas_consulta_completa`
não enxerga evento de entrada.

Nada aqui grava. São chamadas de leitura, uma por valor tentado.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date

from . import mn

# Valores plausíveis por parâmetro. A ordem importa pouco; o que importa é
# cobrir as famílias: vazio, numérico, nome de dimensão, nome de campo.
CANDIDATOS = {
    "QUEBRA": ["", "0", "1", "2", "N", "S", "NENHUMA", "PRODUTO", "FILIAL",
               "DATA", "COR", "EVENTO", "MARCA", "COLECAO", "GRUPO", "TIPO",
               "DIVISAO", "DEPARTAMENTO", "CLIENTE", "FORNECEDOR", "GRADE",
               "TAMANHO", "REFERENCIA", "SUBCOLECAO", "CATEGORIA"],
    "LAYOUT": ["", "0", "1", "2", "PADRAO", "NORMAL", "ANALITICO", "SINTETICO",
               "DETALHADO", "RESUMIDO", "COMPLETO", "SIMPLES"],
    "ORDEM": ["", "0", "1", "2", "PRODUTO", "DATA", "FILIAL", "CODIGO",
              "ALFABETICA", "DESCRICAO", "REFERENCIA", "N", "S", "A", "D"],
    "TIPO": ["", "0", "1", "2", "E", "S", "T", "A", "N", "TODOS"],
    # CAMPO e FILTRO num método de cadastro são o "buscar por" da tela: o campo
    # e o modo de comparação. Numéricos primeiro — foi o que passou no
    # produtosac/Lista (CAMPO=0).
    "CAMPO": ["", "0", "1", "2", "3", "COD_PRODUTO", "CODIGO", "PRODUTO",
              "REFERENCIA", "DESCRICAO", "DESCRICAO1", "NOME", "COLECAO",
              "DESC_COLECAO", "TODOS"],
    "FILTRO": ["", "0", "1", "2", "3", "TODOS", "=", "IGUAL", "CONTEM",
               "CONTENDO", "INICIA", "LIKE", "N", "S"],
}

# Quando a barreira anda para um parâmetro que não está no mapa, é isso que
# sobra tentar. Curto de propósito: a sonda encadeia, e lista longa em
# profundidade vira centenas de chamadas.
GENERICOS = ["", "0", "1", "2", "3", "N", "S", "TODOS", "A"]

RE_PARAM = re.compile(r"parameter (\w+)")


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


def recado(bruto: str) -> str:
    """Tira a mensagem de dentro do JSON de erro do MN.

    O detalhe vem como `HTTP 400 em /caminho: {"error":{"message":{"value":
    "Error in macro #SELECT: ..."}}}`. Ler isso truncado em 90 colunas não
    diz nada; a frase útil está no fim.
    """
    corte = bruto.find("{")
    if corte < 0:
        return bruto
    try:
        erro = json.loads(bruto[corte:])
    except ValueError:
        return bruto[corte:]
    msg = (erro.get("error") or {}).get("message")
    if isinstance(msg, dict):
        msg = msg.get("value")
    return str(msg or bruto)


def tenta(caminho: str, params: dict) -> tuple[bool, str, str, list]:
    """-> (aceitou, parametro_que_barrou, recado, linhas)."""
    try:
        linhas = mn.valores(mn.requisita(caminho, **params))
    except mn.Falha as e:
        msg = recado(str(e))
        if "not found in list" in msg:
            achado = RE_PARAM.search(msg)
            return False, (achado.group(1) if achado else "?"), "recusou", []
        return False, "", msg[:110], []
    return True, "", f"{len(linhas)} linha(s)", linhas


class Orcamento:
    """Teto de chamadas. Sem isso, encadear em três níveis vira milhares."""

    def __init__(self, teto: int):
        self.resta = teto

    def gasta(self) -> bool:
        self.resta -= 1
        return self.resta >= 0


def sonda(caminho, base, parametro, valores, fundo, vistos, orc, nivel=0):
    """Tenta os valores; quando a barreira anda, desce no parâmetro seguinte.

    Devolve (params, linhas) da combinação que o método aceitou, ou None.
    """
    recuo = "  " + "  " * nivel
    print(f"{recuo}{parametro}: {len(valores)} valor(es)")
    for v in valores:
        if not orc.gasta():
            print(f"{recuo}  (teto de chamadas atingido)")
            return None
        params = dict(base)
        params[parametro] = v
        ok, barrou, msg, linhas = tenta(caminho, params)
        andou = barrou and barrou != parametro.upper()
        marca = "OK  " if ok else ("->  " if andou else "    ")
        print(f"{recuo}  {marca}{parametro}={v!r:14} {msg if not barrou else 'recusou ' + barrou}")
        if ok:
            return params, linhas
        if andou and fundo > 0 and barrou not in vistos:
            achou = sonda(caminho, params, barrou,
                          CANDIDATOS.get(barrou.upper(), GENERICOS),
                          fundo - 1, vistos | {parametro.upper()}, orc, nivel + 1)
            if achou:
                return achou
    return None


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Tenta valores para um parametro de relatorio do MN")
    p.add_argument("metodo", help="grupo/Metodo, ex.: saidas/MovimentacaoPorGrade")
    p.add_argument("--parametro", required=True, help="QUEBRA, LAYOUT, ORDEM, CAMPO")
    p.add_argument("--de", type=dia, default=date.today())
    p.add_argument("--ate", type=dia, default=date.today())
    p.add_argument("--extras", default="", help="OUTRO=valor,OUTRO2=valor")
    p.add_argument("--valores", default="",
                   help="lista propria, separada por virgula (substitui a embutida)")
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--sem-datas", action="store_true",
                   help="metodo de cadastro nao aceita DATAI/DATAF")
    p.add_argument("--fundo", type=int, default=4,
                   help="ate quantos parametros encadear (0 = nao encadeia)")
    p.add_argument("--max-chamadas", type=int, default=400)
    args = p.parse_args(argv)

    caminho = f"/api/millenium/{args.metodo.strip('/')}"
    base = {"$top": args.top}
    if not args.sem_datas:
        base["DATAI"] = args.de.isoformat()
        base["DATAF"] = args.ate.isoformat()
    base.update(pares(args.extras))

    valores = ([v.strip() for v in args.valores.split(",")] if args.valores
               else CANDIDATOS.get(args.parametro.upper(), GENERICOS))

    print(f"\n{caminho}")
    print(f"  fixos: {base}")
    print(f"  encadeia ate {args.fundo} parametro(s), teto {args.max_chamadas} chamadas\n")

    achou = sonda(caminho, base, args.parametro.upper(), valores,
                  args.fundo, set(), Orcamento(args.max_chamadas))
    if not achou:
        print("\n  Nenhuma combinacao aceita. Tente --valores com outras opcoes,")
        print("  ou confira na tela do ERP como esse relatorio e chamado.")
        return 1

    params, linhas = achou
    combinacao = {k: v for k, v in params.items() if k != "$top"}
    print(f"\n  ACEITOU: {combinacao}")
    print(f"  {len(linhas)} linha(s)")
    if linhas:
        print("  Campos da primeira linha:")
        for k, val in list(linhas[0].items())[:30]:
            print(f"    {k:22} {str(val)[:46]}")
    else:
        print("  Veio vazio — a combinacao passa, mas o filtro nao achou nada.")
        print("  Tente outro valor para o ultimo parametro, ou alargue o periodo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
