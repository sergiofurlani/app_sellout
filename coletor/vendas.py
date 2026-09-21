"""Extrai a venda da semana do ERP, por produto, cor, tamanho e loja.

    python -m coletor.vendas --de 2026-09-15 --ate 2026-09-21 -s vendas.csv

É a fonte que estava provada e não estava ligada. O `valida_site` **compara**
a venda do MN com a planilha — e fechou no centavo em IGUATEMI. Só que ninguém
tinha escrito o módulo que **extrai**, então a aba Vendas continuava vindo do
export semanal, sendo que o número já era conhecido.

Devolução entra com sinal negativo, junto: a planilha soma venda líquida, e
separar aqui só para somar depois seria trabalho e uma chance a mais de errar.

**Filtrar por evento é filtrar por canal sem perceber.** Foi o que aconteceu em
19/09: a extração olhava só os eventos 10, 30, 204 e 12, e o e-commerce, que
fatura pelo `00003`, simplesmente não existia no resultado. Nada acusa — some
venda em silêncio. Por isso a lista vem inteira de `mn.EVENTOS`, com o sinal de
cada um, e quem mexer nela precisa saber disso.

Incluir evento de venda a mais é seguro porque a agregação é **por filial**: um
faturamento de atacado lançado na ELENA ES não aparece em IGUATEMI. O perigoso
é deixar de fora.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta

from . import mn

# Só as lojas e o site entram no sellout. ELENA ES e ELENA SP são atacado e
# produção; o Bazar tem vida própria (D12 e D13).
LOJAS = {"EGREY JDS", "IGUATEMI"}
SITE = {"E. GREY", "EGREY", "00044"}


def dia(t: str) -> date:
    return date.fromisoformat(t)


def semana_passada() -> tuple[date, date]:
    """Segunda a domingo da semana anterior — o recorte da rodada."""
    hoje = date.today()
    fim = hoje - timedelta(days=hoje.weekday() + 1)
    return fim - timedelta(days=6), fim


def _normaliza(nome: str) -> str:
    n = (nome or "").strip().upper()
    if n in SITE:
        return "SITE"
    return n


def coleta(de: date, ate: date, sem_cache: bool = False):
    """(codigo, codigo_cor, cor, tamanho, filial) -> quantidade líquida.

    Devolve também o valor, para conferir contra a planilha em dinheiro, que é
    o que pegou o erro da coluna Estampa em 08/09.
    """
    mn.USAR_CACHE = not sem_cache
    eventos = {e["interno"]: e for e in mn.EVENTOS if e.get("interno") is not None}
    docs = mn.documentos_do_periodo(de, ate, tuple(eventos))

    saldo = defaultdict(lambda: {"qtd": 0.0, "valor": 0.0})
    resumo_neg = defaultdict(int)
    por_filial = defaultdict(float)
    por_evento = defaultdict(float)
    fora = defaultdict(float)
    for doc in docs:
        # `documentos_do_periodo` consulta um evento por vez e carimba cada
        # documento com `_evento` — o payload do MN não traz esse campo. Ler
        # `evento` devolvia None em todos, e aí `sinal` virava +1 para tudo:
        # a devolução somava em vez de subtrair, e o total deu 398 contra os
        # 334 do ERP. O `_` faz diferença.
        interno = doc.get("_evento", doc.get("evento"))
        regra = eventos.get(interno)
        sinal = regra["sinal"] if regra else 1
        filial = _normaliza(doc.get("cod_filial"))
        if filial not in LOJAS and filial != "SITE":
            for item in doc.get("itens") or []:
                fora[filial] += (item.get("quant") or 0)
            continue
        for item in doc.get("itens") or []:
            bruta = item.get("quant") or 0
            if bruta == 0:
                continue
            # **Quantidade negativa manda; o sinal do evento só decide quando
            # ela é positiva.** As quatro combinações, conferidas contra o
            # export do ERP da semana de 14 a 20/09:
            #
            #   evento de venda,     quant +1  ->  +1
            #   evento de venda,     quant -1  ->  -1   (estorno lançado ali)
            #   evento de devolução, quant +1  ->  -1
            #   evento de devolução, quant -1  ->  -1   (não dobra o sinal)
            #
            # Usar `abs` e multiplicar pelo evento, que foi a tentativa
            # anterior, transformava o segundo caso em +1 e deixava seis
            # chaves da Jardins com o sinal trocado.
            if bruta < 0:
                resumo_neg[regra["rotulo"] if regra else str(interno)] += 1
                q, sinal_item = -bruta, -1
            else:
                q, sinal_item = bruta, sinal
            chave = (str(item.get("cod_produto") or "").strip(),
                     str(item.get("cod_cor") or "").strip(),
                     str(item.get("desc_cor") or "").strip(),
                     str(item.get("tamanho") or "").strip(),
                     filial)
            saldo[chave]["qtd"] += sinal_item * q
            saldo[chave]["valor"] += sinal_item * abs(float(item.get("total") or 0))
            por_filial[filial] += sinal_item * q
            por_evento[regra["rotulo"] if regra else f"evento {interno}"] += sinal_item * q
    return saldo, {"documentos": len(docs), "por_filial": dict(por_filial),
                   "por_evento": dict(por_evento), "fora": dict(fora),
                   "itens_negativos": dict(resumo_neg)}


def grava(saldo, caminho: str) -> int:
    """CSV no formato da aba Vendas, cabeçalho e tudo."""
    linhas = [(c, cc, cor, tam, fil, v["qtd"], v["valor"])
              for (c, cc, cor, tam, fil), v in sorted(saldo.items())
              if abs(v["qtd"]) > 0]
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["FILIAL", "CODIGO", "DESCRICAO", "CODIGO COR", "COR",
                    "TAMANHO", "QTDE", "VALOR"])
        for c, cc, cor, tam, fil, q, valor in linhas:
            w.writerow([fil, c, "", cc, cor, tam, f"{q:g}", f"{valor:.2f}"])
    return len(linhas)


def main(argv=None):
    de_padrao, ate_padrao = semana_passada()
    p = argparse.ArgumentParser(description="Venda da semana, do ERP")
    p.add_argument("--de", type=dia, default=de_padrao)
    p.add_argument("--ate", type=dia, default=ate_padrao)
    p.add_argument("-s", "--salvar", default="vendas.csv")
    p.add_argument("--sem-cache", action="store_true")
    args = p.parse_args(argv)

    print(f"\nVenda de {args.de} a {args.ate}")
    saldo, r = coleta(args.de, args.ate, args.sem_cache)
    print(f"  {r['documentos']} documento(s), {len(saldo)} combinacao(oes)")

    if not saldo:
        print("\n  Nada no periodo. Confira as datas — e lembre que o ERP so")
        print("  responde de dentro da rede da Egrey.")
        return 1

    print("\n  por loja:")
    for f, q in sorted(r["por_filial"].items(), key=lambda x: -x[1]):
        print(f"    {f:12} {q:>8,.0f}")
    print("\n  por evento:")
    for e, q in sorted(r["por_evento"].items(), key=lambda x: -abs(x[1])):
        print(f"    {e:26} {q:>8,.0f}")
    if r["itens_negativos"]:
        print("\n  itens que ja vieram com quantidade negativa:")
        for e, n in sorted(r["itens_negativos"].items(), key=lambda x: -x[1]):
            print(f"    {e:26} {n:>6}")
        print("    (o sinal usado e o do evento, nao o da quantidade)")
    if r["fora"]:
        print("\n  fora do sellout (atacado, producao, bazar):")
        for f, q in sorted(r["fora"].items(), key=lambda x: -x[1])[:6]:
            print(f"    {f:12} {q:>8,.0f}")

    n = grava(saldo, args.salvar)
    print(f"\n  {args.salvar}  ({n} linha(s))")
    print("\n  Confira contra a planilha da semana: a soma por loja tem que")
    print("  bater. Se faltar venda, o suspeito e evento de canal que ficou")
    print("  fora da lista mn.EVENTOS — foi assim que o site sumiu em 19/09.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
