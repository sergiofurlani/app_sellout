"""O sellout calculado no banco, sem planilha nenhuma.

    python -m sellout.db.consulta --ate 2026-09-20 --colecao SS27

É a peça que faltava para a planilha deixar de ser necessária. Até aqui o
banco guardava tudo e ninguém lia de volta: o número continuava nascendo da
fórmula `K = I/J` das abas de trabalho.

A conta, que é a mesma da planilha, feita com o que está gravado:

    Estoque inicial = saldo de abertura + movimentos até a data
    Vendas          = tudo que as lojas e o site venderam até a data
    Sellout         = Vendas / Estoque inicial

**É razão acumulada, não taxa da semana.** A coluna da planilha sempre foi
assim: quanto de tudo que chegou já foi vendido. Uma peça que chegou em março e
vendeu em agosto conta nos dois lados, e o percentual sobe ao longo da vida do
produto — não é o ritmo de uma semana.

O que cada parcela significa está na D13 e na D18: entra na loja pela
transferência da Elena, sai por venda. `realocacao` soma zero no conjunto
porque tem as duas pontas; `saida_bazar` sai do universo do sellout (D12).

---

**O limite que este módulo NÃO resolve, e que precisa ser dito:** o banco só
tem venda a partir de setembro/2026, quando as rodadas passaram a gravar
snapshot. O denominador alcança janeiro — o saldo de abertura e os movimentos
do evento 106 estão lá —, mas o numerador não.

Então, hoje, o sellout daqui **subestima** qualquer produto que vendeu antes de
setembro. Não é defeito da conta: é dado que ainda não foi carregado. O
`coletor.vendas` extrai qualquer período do ERP; carregar semana a semana desde
01/01 fecha o buraco, e só então este número pode ser comparado com a coluna da
planilha de igual para igual.

Por isso a função devolve `desde`, a data da venda mais antiga que ela achou, e
o programa avisa quando essa data é posterior ao começo do denominador. Número
que parece plausível e está incompleto é o defeito que mais custou caro nesta
empreitada.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date

from .conexao import conectar

# Papéis que vendem para o consumidor final (D12). A matriz não entra: o que
# ela "vende" para a loja é transferência, e já está no denominador.
PAPEIS_VENDA = ("loja", "ecommerce")

SQL = """
WITH abertura AS (
    SELECT codigo, codigo_cor, sum(qtd) AS qtd
      FROM saldo_abertura
     WHERE data_base <= %(ate)s
     GROUP BY codigo, codigo_cor
), movimentos AS (
    SELECT codigo, codigo_cor, sum(qtd) AS qtd
      FROM movimento
     WHERE data <= %(ate)s
     GROUP BY codigo, codigo_cor
), vendas AS (
    SELECT v.codigo, v.codigo_cor, sum(v.qtd) AS qtd,
           min(s.data) AS desde
      FROM venda v
      JOIN snapshot s ON s.id = v.snapshot_id
      LEFT JOIN filial f ON f.codigo = v.filial
     WHERE s.data <= %(ate)s
       AND coalesce(f.papel, 'fora') = ANY(%(papeis)s)
     GROUP BY v.codigo, v.codigo_cor
), ultimo AS (
    SELECT id FROM snapshot
     WHERE data <= %(ate)s AND origem = 'upload'
     ORDER BY data DESC, id DESC LIMIT 1
), atual AS (
    SELECT codigo, codigo_cor, sum(qtd) AS qtd
      FROM estoque
     WHERE snapshot_id = (SELECT id FROM ultimo)
     GROUP BY codigo, codigo_cor
), chaves AS (
    SELECT codigo, codigo_cor FROM abertura
    UNION SELECT codigo, codigo_cor FROM movimentos
    UNION SELECT codigo, codigo_cor FROM vendas
)
SELECT k.codigo,
       k.codigo_cor,
       coalesce(c.nome, '')                              AS cor,
       coalesce(p.descricao, '')                         AS descricao,
       coalesce(p.colecao, '')                           AS colecao,
       coalesce(p.linha, '')                             AS linha,
       coalesce(a.qtd, 0) + coalesce(m.qtd, 0)           AS estoque_inicial,
       coalesce(v.qtd, 0)                                AS vendas,
       coalesce(e.qtd, 0)                                AS estoque_atual,
       v.desde                                           AS venda_desde
  FROM chaves k
  LEFT JOIN abertura     a ON (a.codigo, a.codigo_cor) = (k.codigo, k.codigo_cor)
  LEFT JOIN movimentos   m ON (m.codigo, m.codigo_cor) = (k.codigo, k.codigo_cor)
  LEFT JOIN vendas       v ON (v.codigo, v.codigo_cor) = (k.codigo, k.codigo_cor)
  LEFT JOIN atual        e ON (e.codigo, e.codigo_cor) = (k.codigo, k.codigo_cor)
  LEFT JOIN produto      p ON p.codigo = k.codigo
  LEFT JOIN cor          c ON c.codigo_cor = k.codigo_cor
 ORDER BY k.codigo, k.codigo_cor
"""


def foto_de_estoque(ate: date):
    """A última rodada de upload até a data — a foto de onde sai `estoque_atual`.

    **Existe porque zero e ausência não são a mesma coisa.** `estoque_atual`
    vem do último snapshot de origem `upload`; não havendo nenhum na janela, a
    coluna inteira sai zerada, em silêncio, e a `sobra` engole o estoque todo
    como se fosse consignação ou erro. Foi o que a ficha do 330043 mostrou em
    28/09: sobra de 120 peças num produto que a planilha dizia ter 146 na loja.

    Devolve None quando não há foto — e aí quem for usar a sobra tem de saber
    disso antes de olhar o número.
    """
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT id, data, quem FROM snapshot "
                    " WHERE data <= %s AND origem = 'upload' "
                    " ORDER BY data DESC, id DESC LIMIT 1", (ate,))
        r = cur.fetchone()
        return {"id": r[0], "data": r[1], "quem": r[2] or ""} if r else None


def percentual(vendas, estoque_inicial):
    """Vendas sobre Estoque inicial — ou None quando não há denominador.

    Zero no denominador não é zero por cento: é ausência de conta. Devolver 0
    faria a média do bloco cair sem nenhum produto ter ido mal, e é o tipo de
    zero que ninguém questiona porque parece um número.
    """
    if not estoque_inicial:
        return None
    return float(vendas) / float(estoque_inicial)


def enriquece(linha: dict) -> dict:
    """Acrescenta sellout e a diferença de estoque, que é a conferência."""
    linha["sellout"] = percentual(linha["vendas"], linha["estoque_inicial"])
    # O que deveria estar na loja, contra o que o ERP diz que está. A sobra é
    # consignação mais erro — a mesma conta que a coluna Consignado fazia, mas
    # agora com as duas pontas medidas (D21).
    linha["sobra"] = (float(linha["estoque_inicial"]) - float(linha["vendas"])
                      - float(linha["estoque_atual"]))
    return linha


def sellout(ate: date, colecao=None, linha=None, codigo=None) -> list[dict]:
    """Uma linha por produto e cor, com o sellout acumulado até `ate`."""
    campos = ("codigo", "codigo_cor", "cor", "descricao", "colecao", "linha",
              "estoque_inicial", "vendas", "estoque_atual", "venda_desde")
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(SQL, {"ate": ate, "papeis": list(PAPEIS_VENDA)})
            linhas = [enriquece(dict(zip(campos, r))) for r in cur.fetchall()]

    if colecao:
        alvo = colecao.strip().upper()
        linhas = [l for l in linhas if (l["colecao"] or "").upper() == alvo]
    if linha:
        alvo = linha.strip().upper()
        linhas = [l for l in linhas if (l["linha"] or "").upper() == alvo]
    if codigo:
        linhas = [l for l in linhas if l["codigo"] == codigo.strip()]
    return linhas


SQL_SEMANAL = """
SELECT s.data, s.origem, coalesce(f.papel, 'fora') AS papel,
       sum(v.qtd) AS qtd,
       sum(CASE WHEN v.qtd < 0 THEN v.qtd ELSE 0 END) AS devolucao
  FROM venda v
  JOIN snapshot s ON s.id = v.snapshot_id
  LEFT JOIN filial f ON f.codigo = v.filial
 WHERE v.codigo = %(codigo)s
   AND (%(ate)s::date IS NULL OR s.data <= %(ate)s::date)
 GROUP BY s.data, s.origem, coalesce(f.papel, 'fora')
 ORDER BY s.data
"""


def serie_semanal(codigo: str, ate: date | None = None) -> list[dict]:
    """A venda de um produto, semana a semana, como está no banco.

    É a ferramenta de apuração: total que não bate pode ser uma semana
    faltando, uma semana em dobro ou uma filial no papel errado — e as três
    parecem iguais quando se olha só o acumulado.

    Por isso vem separado por `origem` (a carga retroativa do ERP e as rodadas
    de upload) e por `papel` da filial: venda que caiu em `fora` não entra no
    sellout, e some sem avisar.

    **`ate` existe porque série e comparação têm de olhar a mesma janela.** A
    primeira versão trazia tudo, e a série de 332004 chegou com a semana de
    20/09 dentro enquanto a comparação parava em 14/09: a conta que se faz em
    cima disso erra por uma semana e parece certa.

    `devolucao` é a parte negativa da mesma célula. O `sum` líquido esconde
    uma devolução compensada por uma venda na mesma semana e filial — e
    devolução foi justamente o que sobrou sem explicação em 27/09.
    """
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(SQL_SEMANAL, {"codigo": codigo.strip(), "ate": ate})
            return [{"data": d, "origem": o, "papel": p, "qtd": float(q),
                     "devolucao": float(v)}
                    for d, o, p, q, v in cur.fetchall()]


SQL_DEVOLUCOES = """
SELECT v.codigo, sum(v.qtd) AS pecas, count(*) AS linhas
  FROM venda v
  JOIN snapshot s ON s.id = v.snapshot_id
  LEFT JOIN filial f ON f.codigo = v.filial
 WHERE v.qtd < 0
   AND s.data <= %(ate)s
   AND coalesce(f.papel, 'fora') = ANY(%(papeis)s)
 GROUP BY v.codigo
"""


def devolucoes(ate: date) -> dict:
    """{codigo: {pecas, linhas}} — o que voltou, por código, até a data.

    Fica separado do total porque o número gravado em `venda` já é líquido: a
    devolução está lá dentro, subtraída, e não aparece em nenhuma soma. Quem
    compara com uma coluna que talvez conte só a saída não tem como ver isso.
    """
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(SQL_DEVOLUCOES, {"ate": ate, "papeis": list(PAPEIS_VENDA)})
            return {cod: {"pecas": float(p), "linhas": int(n)}
                    for cod, p, n in cur.fetchall()}


SQL_SEMANAL_MUITOS = """
SELECT v.codigo, s.data, sum(v.qtd) AS qtd,
       sum(CASE WHEN v.qtd < 0 THEN v.qtd ELSE 0 END) AS devolucao
  FROM venda v
  JOIN snapshot s ON s.id = v.snapshot_id
  LEFT JOIN filial f ON f.codigo = v.filial
 WHERE s.data <= %(ate)s
   AND coalesce(f.papel, 'fora') = ANY(%(papeis)s)
   AND v.codigo = ANY(%(codigos)s)
 GROUP BY v.codigo, s.data
 ORDER BY v.codigo, s.data
"""


def series_semanais(codigos, ate: date) -> dict:
    """{codigo: [(data, qtd, devolucao)]} — a série de muitos produtos de uma vez.

    Uma consulta por produto seriam centenas de viagens até a Railway, o mesmo
    defeito que tornou a gravação do cadastro lenta.
    """
    if not codigos:
        return {}
    fora = defaultdict(list)
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(SQL_SEMANAL_MUITOS, {"ate": ate, "codigos": list(codigos),
                                             "papeis": list(PAPEIS_VENDA)})
            for cod, d, q, v in cur.fetchall():
                fora[cod].append((d, float(q), float(v)))
    return dict(fora)


SQL_POR_FILIAL = """
SELECT v.codigo, v.filial, coalesce(f.papel, 'fora') AS papel, sum(v.qtd) AS qtd
  FROM venda v
  JOIN snapshot s ON s.id = v.snapshot_id
  LEFT JOIN filial f ON f.codigo = v.filial
 WHERE s.data <= %(ate)s
   AND v.codigo = ANY(%(codigos)s)
 GROUP BY v.codigo, v.filial, coalesce(f.papel, 'fora')
"""


def vendas_por_filial(codigos, ate: date) -> dict:
    """{codigo: {filial: qtd}} — sem filtrar papel, de propósito.

    O filtro de papel é o que faz uma filial desaparecer do sellout sem avisar.
    Se existe um quarto lugar vendendo e ele está mapeado como `fora`, é aqui
    que aparece — e não apareceria numa consulta que já o exclui.
    """
    if not codigos:
        return {}
    fora = defaultdict(dict)
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(SQL_POR_FILIAL, {"ate": ate, "codigos": list(codigos)})
            for cod, fil, _papel, q in cur.fetchall():
                fora[cod][fil] = fora[cod].get(fil, 0.0) + float(q)
    return dict(fora)


SQL_HISTORICO_CODIGO = """
SELECT data, cores, percentual
  FROM sellout_historico
 WHERE codigo = %(codigo)s
   AND (%(ate)s::date IS NULL OR data <= %(ate)s::date)
 ORDER BY data, cores
"""


def serie_planilha(codigo: str, ate: date | None = None) -> list[dict]:
    """O mesmo produto, semana a semana, **como a planilha registrou**.

    É o outro lado da apuração. Dessas colunas só sobrou o percentual (D-do
    `002_historico.sql`): vendas e estoque inicial de cada semana não foram
    guardados. Não dá para conferir peça a peça, mas dá para ver em que semana
    a planilha começou a contar o produto — e é exatamente isso que separa
    "falta venda no banco" de "a planilha conta desde outra data".
    """
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(SQL_HISTORICO_CODIGO, {"codigo": codigo.strip(), "ate": ate})
            return [{"data": d, "cores": cs, "percentual": float(p)}
                    for d, cs, p in cur.fetchall()]


def primeira_semana_planilha() -> dict:
    """{codigo: primeira data com percentual na planilha}."""
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute("SELECT codigo, min(data) FROM sellout_historico "
                        "GROUP BY codigo")
            return {cod: d for cod, d in cur.fetchall()}


def resumo(linhas) -> dict:
    """Totais do conjunto. O percentual é da soma, não média das linhas.

    Média de percentuais dá peso igual a um produto de 3 peças e a um de 300.
    O sellout de um conjunto é a razão dos totais, sempre.
    """
    ei = sum(float(l["estoque_inicial"]) for l in linhas)
    ve = sum(float(l["vendas"]) for l in linhas)
    at = sum(float(l["estoque_atual"]) for l in linhas)
    datas = [l["venda_desde"] for l in linhas if l["venda_desde"]]
    return {"produtos": len({l["codigo"] for l in linhas}),
            "combinacoes": len(linhas),
            "estoque_inicial": ei, "vendas": ve, "estoque_atual": at,
            "sellout": percentual(ve, ei),
            "sobra": ei - ve - at,
            "venda_desde": min(datas) if datas else None,
            "sem_denominador": sum(1 for l in linhas if l["sellout"] is None)}


def main(argv=None):
    p = argparse.ArgumentParser(description="Sellout calculado no banco")
    p.add_argument("--ate", type=date.fromisoformat, default=date.today())
    p.add_argument("--colecao")
    p.add_argument("--linha", help="linha comercial: HOME, PIMA, CASHMERE...")
    p.add_argument("--codigo")
    p.add_argument("--semanal", action="store_true",
                   help="com --codigo: a serie semanal daquele produto")
    p.add_argument("--limite", type=int, default=20)
    args = p.parse_args(argv)

    if args.codigo and args.semanal:
        serie = serie_semanal(args.codigo, args.ate)
        if not serie:
            print(f"\nSem venda no banco para o codigo {args.codigo} ate {args.ate}.")
            return 1
        print(f"\nVenda semana a semana — {args.codigo}  (ate {args.ate})\n")
        print(f"  {'data':12} {'origem':8} {'papel':11} {'qtd':>6} {'devol':>7}")
        print("  " + "-" * 48)
        for x in serie:
            marca = f"{x['devolucao']:,.0f}" if x["devolucao"] else ""
            print(f"  {str(x['data']):12} {x['origem']:8} {x['papel']:11} "
                  f"{x['qtd']:>6,.0f} {marca:>7}")
        no_sellout = sum(x["qtd"] for x in serie if x["papel"] in PAPEIS_VENDA)
        de_fora = sum(x["qtd"] for x in serie if x["papel"] not in PAPEIS_VENDA)
        dev = sum(x["devolucao"] for x in serie if x["papel"] in PAPEIS_VENDA)
        print(f"\n  no sellout {no_sellout:,.0f}" +
              (f"   fora (papel errado?) {de_fora:,.0f}" if de_fora else ""))
        datas = sorted({x["data"] for x in serie})
        print(f"  {len(datas)} semana(s), de {datas[0]} a {datas[-1]}")
        if dev:
            print(f"\n  devolucao dentro desse numero: {dev:,.0f} peca(s).")
            print(f"  A saida bruta foi {no_sellout - dev:,.0f}; o banco guarda o")
            print("  liquido. Coluna que conte so a saida fica maior por isso.")

        hist = serie_planilha(args.codigo, args.ate)
        print(f"\n  A planilha, no historico dela (so o percentual foi guardado):")
        if not hist:
            print("    nenhuma semana — este codigo nao tem historico de planilha.")
        else:
            for x in hist[:6]:
                print(f"    {str(x['data']):12} {x['cores'] or '-':8} "
                      f"{x['percentual']:>7.1%}")
            if len(hist) > 6:
                print(f"    ... {len(hist) - 6} semana(s) a mais, ate {hist[-1]['data']}")
            print(f"    primeira semana na planilha: {hist[0]['data']}"
                  f"   no banco: {datas[0]}")
        return 0

    linhas = sellout(args.ate, args.colecao, args.linha, args.codigo)
    if not linhas:
        print("\nNada no banco para esse recorte.")
        return 1

    r = resumo(linhas)
    print(f"\nSellout ate {args.ate}"
          + (f" — colecao {args.colecao}" if args.colecao else "")
          + (f" — linha {args.linha}" if args.linha else ""))
    print(f"\n  {r['produtos']:,} produto(s), {r['combinacoes']:,} combinacao(oes) produto+cor")
    print(f"  estoque inicial {r['estoque_inicial']:>10,.0f}")
    print(f"  vendas          {r['vendas']:>10,.0f}")
    print(f"  estoque atual   {r['estoque_atual']:>10,.0f}")
    print(f"  sobra           {r['sobra']:>10,.0f}   (consignacao + erro)")
    print(f"  SELLOUT         {r['sellout']:>10.1%}" if r["sellout"] is not None
          else "  SELLOUT              — sem denominador")

    if r["sem_denominador"]:
        print(f"\n  {r['sem_denominador']} combinacao(oes) sem estoque inicial: ficam")
        print("  sem percentual, em vez de aparecer como 0%.")

    # O aviso que impede este numero de ser lido como completo.
    if r["venda_desde"]:
        print(f"\n  A venda mais antiga no banco e de {r['venda_desde']}.")
        print("  O denominador alcanca janeiro; o numerador, nao. Enquanto isso")
        print("  durar, este sellout SUBESTIMA quem vendeu antes dessa data —")
        print("  e nao da para compara-lo com a coluna da planilha.")
        print("  Carregue as semanas anteriores com o coletor.vendas.")

    piores = sorted((l for l in linhas if l["sellout"] is not None),
                    key=lambda x: x["sellout"])[:args.limite]
    print(f"\n  menores sellout ({len(piores)}):")
    print(f'    {"codigo":8} {"cor":16} {"inicial":>8} {"vendas":>7} {"sellout":>8}')
    print("    " + "-" * 52)
    for l in piores:
        print(f'    {l["codigo"]:8} {l["cor"][:16]:16} '
              f'{float(l["estoque_inicial"]):>8,.0f} {float(l["vendas"]):>7,.0f} '
              f'{l["sellout"]:>8.1%}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
