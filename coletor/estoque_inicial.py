"""Extrai o Estoque inicial das lojas a partir do evento 106.

O que a D13 procurava. A peça entra na loja pela **venda entre filiais** da
Elena, evento interno **106** (`00108`), e sai da loja pelo mesmo evento quando
volta para a matriz.

    python -m coletor.estoque_inicial --de 2026-08-31 --ate 2026-09-07
    python -m coletor.estoque_inicial --de 2026-08-31 --ate 2026-09-07 -s entradas.csv

A direção está em dois campos que não se parecem com filial:

    cod_filial   = quem emite  -> origem
    cod_cliente  = para quem   -> destino

Na venda entre filiais a loja é **cliente** da Elena. Foi o que escondeu o
destino durante toda a investigação: procurávamos `filial_destino`.

Regras (D13):

  ELENA ES -> loja      entra no Estoque inicial daquela loja
  loja -> ELENA ES      sai (devolução para a matriz)
  loja -> loja          realocação: sai de uma, entra na outra, nada de novo
                        no conjunto
  ELENA ES -> cliente   atacado, fora do sellout (evento 108, não 106)

O item traz `cod_produto`, `cod_cor`, `desc_cor` e `tamanho` — os códigos do
ERP, os mesmos que a planilha usa. Não precisa de de-para de cor.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta

from . import mn

# Os eventos que movem peça entre a Elena e as lojas.
#
#   106  VENDAS ENTRE FILIAIS      — o caminho normal, nos dois sentidos
#   207  DEVOLUÇÃO PARA ELENATIMES — criado em setembro/2026 para a loja
#                                    devolver peça que não vendeu
#
# O 207 **não é venda negativa**, embora o export de vendas do ERP o traga
# assim. A peça nunca foi vendida: ela saiu da loja e voltou para a Elena.
# Contá-lo como venda encolheria o numerador e deixaria o denominador
# intacto — erro dos dois lados. Aqui ele abate o Estoque inicial, que é o
# que de fato aconteceu. Decidido pelo negócio em 21/09.
EVENTOS = (106, 207)

MATRIZ = ("ELENA ES", "ELENA SP", "ELENATIMES")
LOJAS = ("EGREY JDS", "IGUATEMI")

# Peça acabada por semana na aba Producao, como ordem de grandeza.
#
# Era um número fixo — 826 — comparado direto com o líquido do período, e
# nasceu numa rodada de **uma semana**. Rodando 9 meses ele acusou "ESTOUROU,
# a leitura esta errada" com 17.000 peças, que é justamente o número certo:
# o alarme comparava 38 semanas de transferência com a produção de uma.
#
# Além da escala, a referência é frouxa por natureza (D13): a produção chega
# inteira na Elena, varejo e atacado juntos, e só parte dela vira transferência
# para loja. Por isso o teto vale por semana, com folga, e serve para pegar
# ordem de grandeza — leitura duplicada, evento errado —, não para auditar.
TETO_POR_SEMANA = 826
FOLGA = 2.0


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def ontem() -> date:
    """O último dia fechado.

    A janela terminava em `hoje`, e hoje é um dia pela metade: a peça que
    chegar às 17h entra na rodada da tarde e não estava na de manhã. O mesmo
    comando, rodado duas vezes no mesmo dia, dava dois Estoques iniciais
    diferentes — e o número que fecha com a planilha é o do dia fechado.
    """
    return date.today() - timedelta(days=1)


def e_matriz(nome: str) -> bool:
    return any(m in nome.upper() for m in MATRIZ)


def e_loja(nome: str) -> bool:
    return nome.strip().upper() in {l.upper() for l in LOJAS}


def classifica(origem: str, destino: str) -> str:
    """Devolve entrada, saida, realocacao ou fora."""
    o, d = origem.strip(), destino.strip()
    if e_matriz(o) and e_loja(d):
        return "entrada"
    if e_loja(o) and e_matriz(d):
        return "saida"
    if e_loja(o) and e_loja(d):
        return "realocacao"
    return "fora"


def coleta(de: date, ate: date):
    """Movimentos do evento 106, um registro por item, já classificados."""
    registros = []
    # Fatia mensal: e o mesmo cache que a conferencia enche, entao rodar os
    # dois sobre o mesmo periodo custa uma extracao, nao duas.
    for doc in mn.documentos_do_periodo(de, ate, EVENTOS):
        origem = str(doc.get("cod_filial") or "").strip()
        destino = str(doc.get("cod_cliente") or "").strip()
        tipo = classifica(origem, destino)
        data = mn.parse_data(doc.get("data_emissao"))
        nota = ""
        if doc.get("nfs"):
            nota = str(doc["nfs"][0].get("numero_nota") or "")
        for item in doc.get("itens") or []:
            q = item.get("quant") or 0
            if q <= 0:
                continue
            registros.append({
                "data": data,
                "tipo": tipo,
                "origem": origem,
                "destino": destino,
                "codigo": str(item.get("cod_produto") or "").strip(),
                "cod_cor": str(item.get("cod_cor") or "").strip(),
                "cor": str(item.get("desc_cor") or "").strip(),
                "tamanho": str(item.get("tamanho") or "").strip(),
                "quant": q,
                "valor": float(item.get("total") or 0),
                "nota": nota,
                "romaneio": doc.get("romaneio"),
            })
    return registros


def sanidade(liquido: float, de: date, ate: date) -> list[str]:
    """As linhas do rodapé: o líquido contra a produção esperada do período.

    Era um trecho solto dentro de `main`, lendo `ate` e `de` que ali se chamam
    `args.ate` e `args.de` — `NameError` no meio de uma rodada de minutos, e
    nenhum teste pegou porque `main` não tinha nenhum. Agora é função, e tem.
    """
    semanas = max((ate - de).days, 1) / 7
    esperado = TETO_POR_SEMANA * semanas
    linhas = [f"  ordem de grandeza: {semanas:.0f} semana(s) x "
              f"{TETO_POR_SEMANA:,.0f} peca(s) de producao"]
    if liquido > esperado * FOLGA:
        linhas[0] += f"  <-- {liquido / esperado:.1f}x A PRODUCAO."
        linhas.append("  Nao e auditoria: e ordem de grandeza. Tanto acima disso")
        linhas.append("  costuma ser leitura duplicada ou evento a mais na lista.")
    else:
        linhas[0] += f"  ({liquido / esperado:.0%} dela)"
    return linhas


def segunda_da_semana(ate: date) -> date:
    """A segunda-feira da semana que termina em `ate`.

    O incremento semanal do Estoque inicial precisa da janela da rodada, não
    da janela inteira da extração — e as duas saem da mesma leitura.
    """
    return ate - timedelta(days=ate.weekday())


def grava_para_app(caminho: str, total, semana) -> int:
    """O CSV que o app lê: uma linha por produto+cor, com as duas janelas."""
    agregado = defaultdict(lambda: [0.0, 0.0])
    for (cod, cod_cor, cor, _loja), q in total.items():
        agregado[(cod, cod_cor, cor)][0] += q
    for (cod, cod_cor, cor, _loja), q in semana.items():
        agregado[(cod, cod_cor, cor)][1] += q

    linhas = [(c, cc, cor, t, s) for (c, cc, cor), (t, s) in sorted(agregado.items())
              if t or s]
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["codigo", "codigo_cor", "cor", "quant", "quant_semana"])
        for cod, cod_cor, cor, t, s in linhas:
            w.writerow([cod, cod_cor, cor, f"{t:g}", f"{s:g}"])
    return len(linhas)


def saldo_por_loja(registros):
    """Quanto cada loja ganhou de estoque, por produto+cor.

    Realocação mexe nas duas pontas e soma zero no conjunto — é o que a D13
    decidiu em 18/09.
    """
    saldo = defaultdict(float)
    for r in registros:
        chave_base = (r["codigo"], r["cod_cor"], r["cor"])
        if r["tipo"] == "entrada":
            saldo[chave_base + (r["destino"],)] += r["quant"]
        elif r["tipo"] == "saida":
            saldo[chave_base + (r["origem"],)] -= r["quant"]
        elif r["tipo"] == "realocacao":
            saldo[chave_base + (r["destino"],)] += r["quant"]
            saldo[chave_base + (r["origem"],)] -= r["quant"]
    return saldo


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Estoque inicial das lojas pela venda entre filiais (106) e pela devolucao para a Elena (207)")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, default=ontem(),
                   help="padrao: ontem, o ultimo dia fechado. Parar antes da\n"
                        "                         data da planilha faz produto recem-chegado\n"
                        "                         aparecer com zero, e zero parece divergencia;\n"
                        "                         incluir hoje traz um dia pela metade.")
    p.add_argument("-s", "--salvar", help="grava o detalhe por item num CSV")
    p.add_argument("--para-app", metavar="ARQUIVO",
                   help="CSV que o app le: codigo;codigo_cor;cor;quant;quant_semana")
    p.add_argument("--semana", type=dia, default=None,
                   help="primeiro dia da janela do incremento semanal.\n"
                        "                         padrao: a segunda-feira de --ate. A coluna\n"
                        "                         quant_semana e o que entra na linha que ja\n"
                        "                         existe; quant e o acumulado, para a nova.")
    p.add_argument("--sem-cache", action="store_true")
    args = p.parse_args(argv)
    if args.semana is None:
        args.semana = max(segunda_da_semana(args.ate), args.de)

    mn.USAR_CACHE = not args.sem_cache
    registros = coleta(args.de, args.ate)
    if not registros:
        print("Nenhum movimento do evento 106 no periodo.")
        return 1

    print(f"\nEventos {', '.join(map(str, EVENTOS))} — Elena x lojas, {args.de} a {args.ate}")
    print(f"{len(registros)} item(ns) em movimento\n")

    por_tipo = defaultdict(lambda: {"itens": 0, "quant": 0.0, "valor": 0.0})
    fluxo = defaultdict(float)
    for r in registros:
        a = por_tipo[r["tipo"]]
        a["itens"] += 1
        a["quant"] += r["quant"]
        a["valor"] += r["valor"]
        fluxo[(r["origem"], r["destino"], r["tipo"])] += r["quant"]

    print(f'  {"tipo":12} {"itens":>6} {"peças":>8} {"valor":>14}')
    print("  " + "-" * 44)
    for tipo in ("entrada", "saida", "realocacao", "fora"):
        a = por_tipo.get(tipo)
        if a:
            print(f'  {tipo:12} {a["itens"]:>6} {a["quant"]:>8,.0f} {a["valor"]:>14,.2f}')

    print(f'\n  {"origem":14} -> {"destino":14} {"peças":>8}  tipo')
    print("  " + "-" * 52)
    for (o, d, t), q in sorted(fluxo.items(), key=lambda x: -x[1]):
        print(f'  {o[:14]:14} -> {d[:14]:14} {q:>8,.0f}  {t}')

    saldo = saldo_por_loja(registros)
    entrou = sum(v for v in saldo.values() if v > 0)
    saiu = -sum(v for v in saldo.values() if v < 0)
    liquido = entrou - saiu

    print(f"\n  {len(saldo)} combinacao(oes) produto+cor+loja")
    print(f"  entrou {entrou:,.0f} · saiu {saiu:,.0f} · liquido {liquido:,.0f} peca(s)")
    for linha in sanidade(liquido, args.de, args.ate):
        print(linha)

    consolidado = defaultdict(float)
    for (cod, cod_cor, cor, _loja), q in saldo.items():
        consolidado[(cod, cod_cor, cor)] += q

    print(f"\n  Estoque inicial por produto+cor ({len(consolidado)} combinacoes), maiores:")
    print(f'    {"codigo":10} {"cor":>5} {"descricao":18} {"peças":>7}')
    print("    " + "-" * 44)
    for (cod, cod_cor, cor), q in sorted(consolidado.items(), key=lambda x: -x[1])[:15]:
        print(f'    {cod:10} {cod_cor:>5} {cor[:18]:18} {q:>7,.0f}')

    if args.para_app:
        # Duas janelas do mesmo evento, porque sao duas perguntas diferentes:
        #
        #   quant         tudo que ja chegou  -> Estoque inicial da linha NOVA
        #   quant_semana  o que chegou agora  -> incremento da linha que JA EXISTE
        #
        # Somar o acumulado de nove meses numa linha existente toda semana
        # dobraria o denominador sozinho. Era o risco desta mudanca, e e por
        # isso que as duas colunas saem juntas, de uma rodada so.
        semana = saldo_por_loja([r for r in registros
                                 if r["data"] and args.semana <= r["data"] <= args.ate])
        n = grava_para_app(args.para_app, saldo, semana)
        print(f"\n  Para o app: {args.para_app}  ({n} linha(s))")
        print(f"    quant        acumulado de {args.de} a {args.ate}")
        print(f"    quant_semana so de {args.semana} a {args.ate}"
              f"  ({sum(semana.values()):,.0f} peca(s))")

    if args.salvar:
        with open(args.salvar, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(registros[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(registros)
        print(f"\n  Detalhe por item em {args.salvar}")

    print("""
  Como conferir: some, por codigo, as pecas acima e compare com o que a
  coluna Estoque inicial da planilha ganhou de uma semana para a outra.
  Se bater, a coluna deixa de ser digitada e passa a ser derivada.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
