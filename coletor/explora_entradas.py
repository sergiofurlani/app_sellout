"""Descobre por qual evento a peça entra no estoque das lojas.

A tese (D13): o Estoque inicial é a transferência da ELENA ES para Jardins e
Iguatemi. A lista de eventos de entrada dá cinco candidatos e nenhuma certeza —
só a chamada decide qual carrega o fluxo de verdade.

    python -m coletor.explora_entradas --de 2026-09-01 --ate 2026-09-17

O script chama três métodos para o mesmo período e imprima o que cada um vê:

  1. eventos/Eventos_InfluenciaEstoque    a lista, para ter código e descrição
  2. transferencias/Transferencia_Filiais origem -> destino, por produto
  3. saidas/MovimentacaoPorGrade          COD_PRODUTO + COD_COR + evento

O que procurar na saída:

  - No (2): linhas com ELENA ES na origem e IGUATEMI/EGREY JDS no destino.
    Se aparecerem, a tese está certa e o método serve.
  - No (3): qual DESC_EVENTO acompanha essas peças.
  - Se (2) vier vazio, o fluxo não é registrado como transferência — aí é
    venda com evento próprio, e o caminho é vendas_consulta_completa.

Nada aqui grava nada. É leitura.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date

from . import mn

EVENTOS = "/api/millenium/eventos/Eventos_InfluenciaEstoque"
TRANSFERENCIAS = "/api/millenium/transferencias/Transferencia_Filiais"
POR_GRADE = "/api/millenium/saidas/MovimentacaoPorGrade"

# Lidas na chamada de 18/09. Servem de referência; a lista viva manda.
CANDIDATOS = {
    105: "RECEBIMENTO DE COMPRA P.A (LOJAS)",
    104: "RECEBIMENTO DE COMPRA ELENATIMES ES",
    13: "RECEBIMENTO DE TRANSFERENCIA MATRIZ",
    103: "RECEBIMENTO DE COMPRA P.A",
    115: "RECEBIMENTO ELENATIMES (ATACADO)",
}

LOJAS = ("IGUATEMI", "JDS", "JARDINS")

# A aba Producao do mesmo export (31/08 a 07/09), para comparar.
#
# Cuidado com ela: mistura **peça acabada** (positiva, tamanhos 34-46/M/P) com
# **insumo consumido** (negativa, tamanho U) — tecido em metros, botão,
# etiqueta. São famílias de código diferentes (000076, 000149, 000151 contra
# 239064, 334066), então não colidem com produto; mas somar a coluna inteira dá
# 484 em vez de 826, e o erro passaria por "produção baixa nessa semana".
REFERENCIA_PRODUCAO = {
    "pecas": 826,          # só peça acabada
    "linhas": 181,
    "produtos": 18,
    "produto_cor": 29,
    "insumo": -342,        # o que a coluna traz de negativo, fora da conta
}


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def titulo(texto: str) -> None:
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")


def tenta(rotulo: str, caminho: str, **params):
    """Chama e devolve as linhas. Erro não derruba o script — o resto segue."""
    print(f"\n  GET {caminho}")
    print(f"      {params}")
    try:
        linhas = mn.valores(mn.requisita(caminho, **params))
    except mn.Falha as e:
        print(f"      FALHOU: {e}")
        return []
    print(f"      {len(linhas)} linha(s)")
    return linhas


def lista_eventos():
    titulo("1. Eventos que influenciam estoque")
    linhas = tenta("eventos", EVENTOS)
    if not linhas:
        return
    print(f'\n  {"evento":>7} {"codigo":8} descricao')
    print("  " + "-" * 60)
    for ev in sorted(linhas, key=lambda x: x.get("evento", 0)):
        marca = " <-- candidato" if ev.get("evento") in CANDIDATOS else ""
        print(f'  {ev.get("evento", ""):>7} {str(ev.get("codigo", "")):8} '
              f'{ev.get("descricao", "")}{marca}')


def transferencias(de: date, ate: date):
    titulo("2. Transferencia_Filiais — quem manda para quem")
    linhas = tenta("transferencias", TRANSFERENCIAS,
                   **{"$top": 5000, "DATAI": de.isoformat(), "DATAF": ate.isoformat()})
    if not linhas:
        print("\n  Vazio. Ou nao houve transferencia no periodo, ou o fluxo nao")
        print("  e registrado como transferencia — nesse caso e venda com evento.")
        return

    print("\n  Campos da primeira linha (para conferir o formato de QUANTS):")
    for k, v in list(linhas[0].items())[:30]:
        print(f'    {k:16} {str(v)[:50]}')

    fluxo = defaultdict(lambda: {"linhas": 0, "qtde": 0.0, "produtos": set()})
    for l in linhas:
        origem = (l.get("desc_filialo") or l.get("DESC_FILIALO") or "?").strip()
        destino = (l.get("desc_filiald") or l.get("DESC_FILIALD") or "?").strip()
        f = fluxo[(origem, destino)]
        f["linhas"] += 1
        f["qtde"] += float(l.get("quants_s") or l.get("QUANTS_S") or 0)
        f["produtos"].add(str(l.get("cod_produto") or l.get("COD_PRODUTO") or ""))

    print(f'\n  {"origem":22} -> {"destino":22} {"linhas":>7} {"qtde":>9} {"prod":>6}')
    print("  " + "-" * 76)
    for (o, d), f in sorted(fluxo.items(), key=lambda x: -x[1]["qtde"]):
        alvo = " *" if any(s in d.upper() for s in LOJAS) else ""
        print(f'  {o[:22]:22} -> {d[:22]:22} {f["linhas"]:>7} '
              f'{f["qtde"]:>9,.0f} {len(f["produtos"]):>6}{alvo}')
    print("\n  As linhas com * terminam numa loja: sao candidatas a Estoque inicial.")


def por_grade(de: date, ate: date):
    titulo("3. MovimentacaoPorGrade — COD_PRODUTO + COD_COR + evento")
    linhas = tenta("por grade", POR_GRADE,
                   **{"$top": 5000, "DATAI": de.isoformat(), "DATAF": ate.isoformat()})
    if not linhas:
        print("\n  Vazio ou recusado. Se recusou, o grupo da URL pode nao ser")
        print("  'saidas' — conferir no $metadata o prefixo do ReturnType.")
        return

    print("\n  Campos da primeira linha:")
    for k, v in list(linhas[0].items())[:30]:
        print(f'    {k:16} {str(v)[:50]}')

    ag = defaultdict(lambda: {"linhas": 0, "qtde": 0.0, "cores": set(), "filiais": set()})
    for l in linhas:
        ev = (l.get("desc_evento") or l.get("DESC_EVENTO") or "?").strip()
        a = ag[ev]
        a["linhas"] += 1
        a["qtde"] += float(l.get("qtde") or l.get("QTDE") or 0)
        cor = l.get("cod_cor") or l.get("COD_COR")
        if cor:
            a["cores"].add(str(cor).strip())
        a["filiais"].add((l.get("cod_filial") or l.get("COD_FILIAL") or "?").strip())

    print(f'\n  {"evento":42} {"linhas":>7} {"qtde":>9} {"cores":>6}  filiais')
    print("  " + "-" * 86)
    for ev, a in sorted(ag.items(), key=lambda x: -x[1]["qtde"]):
        print(f'  {ev[:42]:42} {a["linhas"]:>7} {a["qtde"]:>9,.0f} '
              f'{len(a["cores"]):>6}  {",".join(sorted(a["filiais"]))[:30]}')

    com_cor = sum(len(a["cores"]) for a in ag.values())
    print(f"\n  COD_COR preenchido em {com_cor} combinacao(oes) distintas.")
    print("  Se vier vazio, o de-para de cor tem que sair do Detalhado2_Data.")


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Descobre por qual evento a peca entra no estoque das lojas")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, required=True)
    p.add_argument("--pular-eventos", action="store_true")
    args = p.parse_args(argv)

    if not args.pular_eventos:
        lista_eventos()
    transferencias(args.de, args.ate)
    por_grade(args.de, args.ate)

    titulo("O que fazer com isso")
    r = REFERENCIA_PRODUCAO
    print(f"""
  Referencia da aba Producao no mesmo periodo (31/08 a 07/09):

    peca acabada   {r['pecas']} pecas em {r['linhas']} linhas,
                   {r['produtos']} produtos, {r['produto_cor']} produto+cor
    insumo         {r['insumo']} (tecido, botao, etiqueta — FORA da conta)

  A producao chega INTEIRA na Elena, varejo e atacado juntos. Entao a
  transferencia ELENA ES -> lojas tem que ser um PEDACO dessas {r['pecas']}
  pecas, nunca mais que isso. Se der mais, a leitura esta errada.

  O que a saida responde:

  - Se (2) mostrar ELENA ES -> IGUATEMI / EGREY JDS com quantidade, a tese da
    D13 esta certa e o Estoque inicial vira dado derivado.
  - Se (3) trouxer COD_COR preenchido, o saldo de abertura sai por cor direto,
    sem de-para.
  - Se (2) vier vazio e (3) mostrar um evento tipo "VENDA ENTRE FILIAIS", o
    caminho e vendas_consulta_completa com aquele EVENTO — e ele tem que ser
    excluido da agregacao de venda, senao a receita de varejo infla.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
