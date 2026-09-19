"""Descobre qual filial do MN é o Site, comparando com a planilha.

A dúvida: `00044` e `00065` (SHOP ONLINE EGREY) são ambos candidatos. O nome não
decide — o número decide. Este script puxa a venda do período por filial e
compara com o que a aba Vendas da planilha traz para JARDINS, IGUATEMI e SITE.

    python -m coletor.valida_site --de 2026-09-11 --ate 2026-09-17

O período tem que ser **o mesmo do export da planilha**. Quando ele não é
conhecido, `--varrer` puxa um intervalo maior uma única vez e testa todas as
janelas de 7 dias dentro dele, dizendo qual chega mais perto do SITE:

    python -m coletor.valida_site --de 2026-08-15 --ate 2026-09-18 --varrer

Eventos: resolvidos pelo catálogo do MN em `mn.EVENTOS`, que agora inclui o
faturamento de e-commerce (código `00003`). Sem ele o Site não aparece de jeito
nenhum — foi o que aconteceu na primeira rodada, em 19/09.

Agregação, igual à planilha: peça de saída soma, devolução subtrai (pela API ela
vem positiva, marcada em tipo_operacao="E"), e linha com quant = 0 é pedido, não
venda — fica de fora.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta

from . import mn

# O que a aba Vendas trouxe no export de 18/09/2026, para comparar.
# "linhas" conta as linhas cruas da aba, inclusive as de quantidade zero, que o
# script ignora — então compare **peças e valor**, não linhas.
REFERENCIA = {
    "JARDINS": {"linhas": 317, "pecas": 112, "valor": 136585.80, "produtos": 118},
    "IGUATEMI": {"linhas": 293, "pecas": 152, "valor": 183579.10, "produtos": 101},
    "SITE": {"linhas": 45, "pecas": 21, "valor": 25548.44, "produtos": 35},
}

JANELA = 7

# A filial do MN que corresponde a cada coluna da planilha. O Site é o 00044,
# confirmado em 19/09; ELENA ES fica de fora (D12) e nem entra no de-para.
DE_PARA = {
    "EGREY JDS": "JARDINS",
    "IGUATEMI": "IGUATEMI",
    "00044": "SITE",
}


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def novo():
    return {"linhas": 0, "saida": 0, "entrada": 0, "valor": 0.0,
            "produtos": set(), "docs": set()}


def soma(alvo: dict, outro: dict) -> None:
    alvo["linhas"] += outro["linhas"]
    alvo["saida"] += outro["saida"]
    alvo["entrada"] += outro["entrada"]
    alvo["valor"] += outro["valor"]
    alvo["produtos"] |= outro["produtos"]
    alvo["docs"] |= outro["docs"]


def agrega_dia(d: date, eventos, filtro) -> dict:
    """Um dia, agregado por filial. É a unidade que as janelas reaproveitam."""
    ag = defaultdict(novo)
    internos = tuple(ev["interno"] for ev in eventos)
    for doc in mn.documentos_do_dia(d, eventos=internos):
        filial = (doc.get("cod_filial") or "").strip()
        if filtro and filial.upper() not in filtro:
            continue
        a = ag[filial]
        vendeu = False
        for item in doc.get("itens") or []:
            quant = item.get("quant") or 0
            if quant <= 0:                       # linha de pedido, não venda
                continue
            a["linhas"] += 1
            a["produtos"].add(str(item.get("cod_produto") or "").strip())
            valor = float(item.get("total") or 0)
            if (item.get("tipo_operacao") or "").upper() == "E":
                a["entrada"] += quant
                a["valor"] -= valor              # devolução vem POSITIVA
            else:
                a["saida"] += quant
                a["valor"] += valor
                vendeu = True
        if vendeu:
            a["valor"] += float(doc.get("valor_acerto") or 0)
            a["docs"].add(doc.get("cod_operacao"))
    return ag


def mostra_eventos(eventos, avisos) -> None:
    print("\nEventos usados nesta extração:")
    for ev in eventos:
        cod = ev.get("codigo") or "?"
        desc = ev.get("descricao") or ev["rotulo"]
        print(f'  interno {ev["interno"]:>4}  codigo {cod:>6}  {desc}')
    for a in avisos:
        print(f"  AVISO: {a}")


def tabela(ag, nomes) -> None:
    cab = (f'{"cod_filial":12} {"linhas":>7} {"saída":>7} {"devol":>7} '
           f'{"líquido":>8} {"valor":>14} {"prod":>5}  nome')
    print(cab)
    print("-" * len(cab))
    for filial, a in sorted(ag.items(), key=lambda x: -abs(x[1]["saida"])):
        liquido = a["saida"] - a["entrada"]
        print(f'{filial:12} {a["linhas"]:>7} {a["saida"]:>7} {a["entrada"]:>7} '
              f'{liquido:>8} {a["valor"]:>14,.2f} {len(a["produtos"]):>5}  '
              f'{nomes.get(filial, "?")[:38]}')


def distancia(a: dict, ref: dict) -> float:
    """Erro relativo médio de peças e valor. Zero é bate exato."""
    liquido = a["saida"] - a["entrada"]
    e_pecas = abs(liquido - ref["pecas"]) / max(ref["pecas"], 1)
    e_valor = abs(a["valor"] - ref["valor"]) / max(ref["valor"], 1)
    return (e_pecas + e_valor) / 2


def varre(diarios, ordem, tamanhos) -> None:
    """Desliza janelas sobre os dias já puxados, pontuando as TRÊS colunas.

    A primeira versão pontuava só o SITE, e por isso disse que 31/08–04/09 era
    a resposta: o Site bate ali porque não fatura no fim de semana. As lojas
    vendem — e ficaram em 65% da planilha. Quem decide o período é o conjunto.
    """
    print("\nJanelas, ordenadas pelo erro somado das três colunas:\n")
    cab = (f'{"janela":26} {"dias":>4}  {"JARDINS":>8} {"IGUATEMI":>8} '
           f'{"SITE":>8}  {"total":>7}')
    print(cab)
    print("-" * len(cab))

    linhas = []
    for n in tamanhos:
        for i in range(len(ordem) - n + 1):
            fatia = ordem[i:i + n]
            junto = defaultdict(novo)
            for d in fatia:
                for filial, a in diarios[d].items():
                    rot = DE_PARA.get(filial)
                    if rot:
                        soma(junto[rot], a)
            if set(junto) != set(REFERENCIA):
                continue                      # janela sem alguma das três
            erros = {r: distancia(junto[r], REFERENCIA[r]) for r in REFERENCIA}
            total = sum(erros.values()) / len(erros)
            linhas.append((total, fatia[0], fatia[-1], n, erros, dict(junto)))

    if not linhas:
        print("  (nenhuma janela tem as três filiais)")
        return

    linhas.sort(key=lambda x: (x[0], x[1], x[3]))
    for total, ini, fim, n, erros, _ in linhas[:10]:
        janela = f"{ini} a {fim}"
        print(f'{janela:26} {n:>4}  {erros["JARDINS"]:>7.1%} {erros["IGUATEMI"]:>7.1%} '
              f'{erros["SITE"]:>7.1%}  {total:>6.1%}')

    total, ini, fim, n, erros, junto = linhas[0]
    print(f"\nMelhor janela: {ini} a {fim} ({n} dias)\n")
    cab2 = f'{"":10} {"peças API":>10} {"peças pl.":>10} {"valor API":>14} {"valor pl.":>14} {"prod":>10}'
    print(cab2)
    print("-" * len(cab2))
    for rot, ref in REFERENCIA.items():
        a = junto[rot]
        liq = a["saida"] - a["entrada"]
        print(f'{rot:10} {liq:>10} {ref["pecas"]:>10} {a["valor"]:>14,.2f} '
              f'{ref["valor"]:>14,.2f} {len(a["produtos"]):>4} / {ref["produtos"]:<4}')

    print("\nErro abaixo de ~5% nas três colunas fecha a validação da extração.")
    print("Se o SITE bate e as lojas não, o período tem fim de semana de fora:")
    print("o e-commerce fatura em dia útil, a loja vende no sábado.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Compara a venda por filial do MN com a planilha")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, required=True)
    p.add_argument("--filiais", default="",
                   help="lista separada por vírgula; vazio mostra todas as que venderam")
    p.add_argument("--varrer", action="store_true",
                   help="testa todas as janelas dentro do intervalo")
    p.add_argument("--janelas", default="5,6,7,8,9,10",
                   help="tamanhos de janela a testar, em dias")
    p.add_argument("--sem-cache", action="store_true",
                   help="ignora o cache de dias e puxa tudo de novo")
    args = p.parse_args(argv)

    mn.USAR_CACHE = not args.sem_cache
    tamanhos = sorted({int(t) for t in args.janelas.split(",") if t.strip()})

    eventos, avisos = mn.conferir_eventos()
    mostra_eventos(eventos, avisos)
    if not eventos:
        print("\nNenhum evento utilizável. Nada a fazer.")
        return 1

    nomes = {f["cod_filial"].strip(): (f.get("nome") or "").strip() for f in mn.filiais()}
    filtro = {f.strip().upper() for f in args.filiais.split(",") if f.strip()}

    ordem = list(mn.dias(args.de, args.ate))
    if args.varrer and len(ordem) < min(tamanhos):
        print(f"\nIntervalo menor que {min(tamanhos)} dias — nada para varrer.")
        return 1

    cache = "sem cache" if args.sem_cache else f"cache em {mn.CACHE}/"
    print(f"\nPuxando {len(ordem)} dia(s), {len(eventos)} evento(s) por dia ({cache})...")
    diarios = {}
    for d in ordem:
        diarios[d] = agrega_dia(d, eventos, filtro)

    total = defaultdict(novo)
    for d in ordem:
        for filial, a in diarios[d].items():
            soma(total[filial], a)

    print(f"\nPeríodo {args.de} a {args.ate}\n")
    tabela(total, nomes)

    if args.varrer:
        varre(diarios, ordem, tamanhos)
        return 0

    print("\nContra a planilha (export de 18/09) — compare peças e valor:")
    for rotulo, ref in REFERENCIA.items():
        print(f'  {rotulo:9} peças {ref["pecas"]:>4}  valor {ref["valor"]:>12,.2f}  '
              f'produtos {ref["produtos"]:>4}')
    print("\nA filial cujo líquido e valor baterem com SITE é o e-commerce.")
    print("Se nenhuma bater, rode de novo com --varrer num intervalo maior:")
    print("o período do export provavelmente não é este.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
