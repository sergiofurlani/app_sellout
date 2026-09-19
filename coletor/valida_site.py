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


def varre(diarios, ordem, nomes) -> None:
    """Desliza janelas de 7 dias sobre os dias já puxados."""
    ref = REFERENCIA["SITE"]
    print(f"\nJanelas de {JANELA} dias, ordenadas pela distância do SITE "
          f"({ref['pecas']} peças / R$ {ref['valor']:,.2f}):\n")
    cab = (f'{"janela":25} {"filial":12} {"líquido":>8} {"valor":>14} '
           f'{"prod":>5} {"erro":>7}  nome')
    print(cab)
    print("-" * len(cab))

    linhas = []
    for i in range(len(ordem) - JANELA + 1):
        fatia = ordem[i:i + JANELA]
        junto = defaultdict(novo)
        for d in fatia:
            for filial, a in diarios[d].items():
                soma(junto[filial], a)
        for filial, a in junto.items():
            if a["saida"] == 0 and a["entrada"] == 0:
                continue
            linhas.append((distancia(a, ref), fatia[0], fatia[-1], filial, a))

    for erro, ini, fim, filial, a in sorted(linhas, key=lambda x: (x[0], x[1]))[:12]:
        liquido = a["saida"] - a["entrada"]
        # str() antes do :12 — formatar um date com largura devolve "12"
        janela = f"{ini} a {fim}"
        print(f'{janela:25} {filial:12} {liquido:>8} {a["valor"]:>14,.2f} '
              f'{len(a["produtos"]):>5} {erro:>6.1%}  {nomes.get(filial,"")[:20]}')

    print("\nA linha de erro mais baixo diz, ao mesmo tempo, qual filial é o")
    print("Site e qual período a planilha cobre. Erro acima de ~5% nas 12")
    print("primeiras significa que o Site nao esta nesses eventos, ou que o")
    print("periodo verdadeiro esta fora do intervalo varrido.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Compara a venda por filial do MN com a planilha")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, required=True)
    p.add_argument("--filiais", default="",
                   help="lista separada por vírgula; vazio mostra todas as que venderam")
    p.add_argument("--varrer", action="store_true",
                   help="testa todas as janelas de 7 dias dentro do intervalo")
    args = p.parse_args(argv)

    eventos, avisos = mn.conferir_eventos()
    mostra_eventos(eventos, avisos)
    if not eventos:
        print("\nNenhum evento utilizável. Nada a fazer.")
        return 1

    nomes = {f["cod_filial"].strip(): (f.get("nome") or "").strip() for f in mn.filiais()}
    filtro = {f.strip().upper() for f in args.filiais.split(",") if f.strip()}

    ordem = list(mn.dias(args.de, args.ate))
    if args.varrer and len(ordem) < JANELA:
        print(f"\nIntervalo menor que {JANELA} dias — nada para varrer.")
        return 1

    print(f"\nPuxando {len(ordem)} dia(s), {len(eventos)} evento(s) por dia...")
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
        varre(diarios, ordem, nomes)
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
