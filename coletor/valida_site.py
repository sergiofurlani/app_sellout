"""Descobre qual filial do MN é o Site, comparando com a planilha.

A dúvida: `00044` e `00065` (SHOP ONLINE EGREY) são ambos candidatos. O nome não
decide — o número decide. Este script puxa a venda do período por filial e
compara com o que a aba Vendas da planilha traz para JARDINS, IGUATEMI e SITE.

    python -m coletor.valida_site --de 2026-09-11 --ate 2026-09-17

O período tem que ser **o mesmo do export da planilha**.

Agregação, igual à planilha: peça de saída soma, devolução subtrai (pela API ela
vem positiva, marcada em tipo_operacao="E"), e linha com quant = 0 é pedido, não
venda — fica de fora.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date

from . import mn

# O que a aba Vendas trouxe no export de 18/09/2026, para comparar.
REFERENCIA = {
    "JARDINS": {"linhas": 317, "pecas": 112, "valor": 136585.80, "produtos": 118},
    "IGUATEMI": {"linhas": 293, "pecas": 152, "valor": 183579.10, "produtos": 101},
    "SITE": {"linhas": 45, "pecas": 21, "valor": 25548.44, "produtos": 35},
}


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def main(argv=None):
    p = argparse.ArgumentParser(description="Compara a venda por filial do MN com a planilha")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, required=True)
    p.add_argument("--filiais", default="",
                   help="lista separada por vírgula; vazio mostra todas as que venderam")
    args = p.parse_args(argv)

    nomes = {f["cod_filial"].strip(): (f.get("nome") or "").strip() for f in mn.filiais()}
    filtro = {f.strip().upper() for f in args.filiais.split(",") if f.strip()}

    ag = defaultdict(lambda: {"linhas": 0, "saida": 0, "entrada": 0,
                              "valor": 0.0, "produtos": set(), "docs": set()})

    for d in mn.dias(args.de, args.ate):
        for doc in mn.documentos_do_dia(d):
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

    print(f"\nPeríodo {args.de} a {args.ate}\n")
    cab = f'{"cod_filial":12} {"linhas":>7} {"saída":>7} {"devol":>7} {"líquido":>8} {"valor":>14} {"prod":>5}  nome'
    print(cab)
    print("-" * len(cab))
    for filial, a in sorted(ag.items(), key=lambda x: -abs(x[1]["saida"])):
        liquido = a["saida"] - a["entrada"]
        print(f'{filial:12} {a["linhas"]:>7} {a["saida"]:>7} {a["entrada"]:>7} '
              f'{liquido:>8} {a["valor"]:>14,.2f} {len(a["produtos"]):>5}  {nomes.get(filial,"?")[:38]}')

    print("\nContra a planilha (export de 18/09):")
    for rotulo, ref in REFERENCIA.items():
        print(f'  {rotulo:9} linhas {ref["linhas"]:>4}  peças {ref["pecas"]:>4}  '
              f'valor {ref["valor"]:>12,.2f}  produtos {ref["produtos"]:>4}')
    print("\nA filial cujo líquido e valor baterem com SITE é o e-commerce.")
    print("Se nenhuma bater, o período provavelmente não é o mesmo do export.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
