"""Peças que saíram em consignação e ainda não voltaram.

    python -m coletor.consignacao --de 2025-01-01 --para-app consignado.csv

É a coluna **Consignado** da planilha, que até hoje nunca foi medida: ela é a
fórmula `= Estoque inicial − Vendas totais − Estoque atual`, ou seja, **o
resto**. Tudo que não fecha nas outras três colunas se acomoda ali, tenha ido
para a mão de um cliente ou não. A prova de que é lata de lixo são as 10 linhas
com Consignado **negativo** na planilha de 14/09: não existe menos dezesseis
peças na mão de um cliente.

Os dois eventos, como o negócio explicou em 26/09:

    14  (código 13)  REMESSA DE CONSIGNAÇÃO   a peça sai da loja
    19  (código 14)  ACERTO DE CONSIGNAÇÃO    a peça volta

**Acerto não é venda.** Toda remessa retorna como acerto; se a cliente ficou
com a peça, sai uma venda normal, pelos eventos que o `coletor.vendas` já
trata. Por isso a consignação não encosta no numerador do sellout — ela só
explica onde a peça está enquanto não está na loja.

O que interessa é a diferença: **remessa sem acerto**. Isso é posição, não
fluxo — uma peça que saiu em março e não voltou continua fora hoje. Por isso
`--de` tem que alcançar a consignação mais antiga ainda aberta, e não a semana
da rodada. Uma janela curta aqui não dá erro: devolve um número menor, que
parece plausível.

**Como conferir:** o ERP tem o relatório de consignação com a coluna
`A Acertar`. O total daqui tem que bater com o de lá. Em 21/09 ele dizia 637
peças, contra 949 da coluna Consignado da planilha — a diferença de 312 é o
erro acumulado que o resto vinha escondendo.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta

from . import mn

# Os dois lados do mesmo movimento. O sinal é o que a peça faz com o estoque
# da loja: a remessa tira, o acerto devolve.
EVENTOS = {
    14: {"rotulo": "remessa de consignacao", "sinal": +1},
    19: {"rotulo": "acerto de consignacao", "sinal": -1},
}

LOJAS = ("EGREY JDS", "IGUATEMI")


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def ontem() -> date:
    return date.today() - timedelta(days=1)


def e_loja(nome: str) -> bool:
    return (nome or "").strip().upper() in {l.upper() for l in LOJAS}


def coleta(de: date, ate: date):
    """(codigo, cod_cor, cor, loja) -> peças ainda fora, e um resumo.

    Remessa soma, acerto subtrai. O saldo por chave é quanto daquela peça, por
    cor e por loja, saiu e não voltou.
    """
    saldo = defaultdict(float)
    por_evento = defaultdict(float)
    fora_de_loja = defaultdict(float)
    primeira: dict[tuple, date] = {}

    for doc in mn.documentos_do_periodo(de, ate, tuple(EVENTOS)):
        # `_evento` com underscore: é o carimbo que `documentos_do_periodo`
        # põe em cada documento. O payload do MN não traz o campo, e ler
        # `evento` devolve None em todos — foi o erro que inverteu o sinal da
        # devolução no coletor de vendas.
        regra = EVENTOS.get(doc.get("_evento"))
        if regra is None:
            continue
        loja = (doc.get("cod_filial") or "").strip().upper()
        data = mn.parse_data(doc.get("data_emissao"))
        for item in doc.get("itens") or []:
            q = item.get("quant") or 0
            if not q:
                continue
            q = abs(q) * regra["sinal"]
            if not e_loja(loja):
                fora_de_loja[loja] += q
                continue
            chave = (str(item.get("cod_produto") or "").strip(),
                     str(item.get("cod_cor") or "").strip(),
                     str(item.get("desc_cor") or "").strip(),
                     loja)
            saldo[chave] += q
            por_evento[regra["rotulo"]] += abs(q)
            if data and regra["sinal"] > 0:
                if chave not in primeira or data < primeira[chave]:
                    primeira[chave] = data

    return saldo, {"por_evento": dict(por_evento),
                   "fora_de_loja": dict(fora_de_loja),
                   "primeira": primeira}


def consolida(saldo) -> dict:
    """Junta as lojas: a planilha tem uma linha por produto, não por loja."""
    junto = defaultdict(float)
    for (cod, cod_cor, cor, _loja), q in saldo.items():
        junto[(cod, cod_cor, cor)] += q
    return junto


def grava(caminho: str, saldo) -> int:
    """CSV no formato que o app lê: codigo;codigo_cor;cor;quant.

    Saldo zero fica de fora — peça que saiu e voltou não é consignação aberta,
    é história. Saldo **negativo** entra, de propósito: significa acerto sem
    remessa no período, e esconder isso devolveria o total ao mundo dos
    números que fecham por construção.
    """
    linhas = [(c, cc, cor, q) for (c, cc, cor), q in sorted(consolida(saldo).items())
              if q]
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["codigo", "codigo_cor", "cor", "quant"])
        for c, cc, cor, q in linhas:
            w.writerow([c, cc, cor, f"{q:g}"])
    return len(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Consignacao em aberto: remessa (14) sem acerto (19)")
    p.add_argument("--de", type=dia, required=True,
                   help="tem que alcancar a consignacao mais antiga ainda\n"
                        "                         aberta. Janela curta nao da erro: devolve um\n"
                        "                         numero menor, que parece plausivel.")
    p.add_argument("--ate", type=dia, default=ontem())
    p.add_argument("--para-app", metavar="ARQUIVO",
                   help="CSV agregado: codigo;codigo_cor;cor;quant")
    p.add_argument("--sem-cache", action="store_true")
    args = p.parse_args(argv)

    mn.USAR_CACHE = not args.sem_cache
    print(f"\nConsignacao — eventos 14 (remessa) e 19 (acerto), "
          f"{args.de} a {args.ate}")
    saldo, r = coleta(args.de, args.ate)
    if not saldo:
        print("\n  Nenhum movimento de consignacao no periodo. Confira as datas —")
        print("  e lembre que o MN so responde de dentro da rede da Egrey.")
        return 1

    print("\n  movimento:")
    for rotulo, q in sorted(r["por_evento"].items(), key=lambda x: -x[1]):
        print(f"    {rotulo:26} {q:>8,.0f}")

    junto = consolida(saldo)
    aberto = sum(junto.values())
    negativas = {k: v for k, v in junto.items() if v < 0}

    por_loja = defaultdict(float)
    for (_c, _cc, _cor, loja), q in saldo.items():
        por_loja[loja] += q
    print("\n  em aberto por loja:")
    for loja, q in sorted(por_loja.items(), key=lambda x: -x[1]):
        print(f"    {loja:14} {q:>8,.0f}")

    print(f"\n  {len(junto)} combinacao(oes) produto+cor")
    print(f"  em aberto: {aberto:,.0f} peca(s)")

    if negativas:
        print(f"\n  {len(negativas)} combinacao(oes) com saldo NEGATIVO "
              f"({sum(negativas.values()):,.0f} pecas)")
        print("  Acerto sem remessa na janela: quase sempre a remessa e anterior")
        print(f"  a {args.de}. Recue o --de e rode de novo.")

    if r["fora_de_loja"]:
        print("\n  fora das lojas do sellout:")
        for f, q in sorted(r["fora_de_loja"].items(), key=lambda x: -abs(x[1]))[:6]:
            print(f"    {f[:14] or '(sem filial)':14} {q:>8,.0f}")

    if args.para_app:
        n = grava(args.para_app, saldo)
        print(f"\n  Para o app: {args.para_app}  ({n} linha(s))")

    print("\n  Confira contra o relatorio de consignacao do ERP, coluna")
    print("  'A Acertar'. Os dois medem a mesma coisa e tem que bater. Se o")
    print("  numero daqui for MENOR, o --de provavelmente nao alcanca as")
    print("  remessas mais antigas ainda abertas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
