"""Descobre por qual evento a peça entra no estoque das lojas.

A tese (D13): o Estoque inicial é a transferência da ELENA ES para Jardins e
Iguatemi. Falta saber por qual evento ela é registrada.

    python -m coletor.explora_entradas --de 2026-08-31 --ate 2026-09-07

Três passos, todos por métodos já provados nesta base:

  1. `eventos/ListaEventosPorTipo` — o catálogo **completo**, entrada e saída,
     com os dois códigos. É o que responde "quais eventos existem".
  2. Escolhe os candidatos pela descrição (transferência, filial, Elena) e
     pelos recebimentos de produto acabado.
  3. Sonda cada candidato com `movimentacao/vendas_consulta_completa`, o mesmo
     método da extração de vendas, que devolve os itens com produto e cor.

Por que não `Transferencia_Filiais` nem `MovimentacaoPorGrade`: os dois existem
e o caminho da URL está certo — o servidor chegou a executar a macro — mas são
**relatórios**, e exigem valor válido em `LAYOUT` e `QUEBRA`, de uma lista que o
`$metadata` não publica. Ficam para depois, se a sondagem não bastar.

Nada aqui grava nada. É leitura.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import date

from . import mn

LISTA_POR_EVENTO = "/api/millenium/movimentacao/Lista_Por_Evento"

# Eventos de entrada que já pareciam candidatos na primeira leitura.
CANDIDATOS_FIXOS = {105, 104, 13, 103, 115}

# Descrições que cheiram a movimentação entre filiais, dos dois lados.
PADRAO = re.compile(r"TRANSFER|FILIA|ELENA|ELENATIMES|REMESSA|ENVIO|MATRIZ", re.I)

LOJAS = ("IGUATEMI", "JDS", "JARDINS")
ORIGENS = ("ELENA", "ELENATIMES")

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
    print(f"\n{'=' * 72}\n{texto}\n{'=' * 72}")


def campo(d: dict, *nomes):
    """A API alterna maiúscula e minúscula conforme o método. Aceita os dois."""
    for n in nomes:
        for chave in (n, n.lower(), n.upper()):
            if chave in d:
                return d[chave]
    return None


def catalogo() -> list[dict]:
    titulo("1. Catálogo de eventos — ListaEventosPorTipo")
    try:
        linhas = mn.catalogo_eventos()
    except mn.Falha as e:
        print(f"  FALHOU: {e}")
        return []

    print(f"  {len(linhas)} evento(s)\n")
    print(f'  {"evento":>7} {"codigo":8} {"E":1} {"S":1}  descricao')
    print("  " + "-" * 66)
    for ev in sorted(linhas, key=lambda x: campo(x, "evento") or 0):
        interno = campo(ev, "evento")
        cod = str(campo(ev, "codigo") or "")
        desc = str(campo(ev, "descricao") or "")
        e = "E" if campo(ev, "tipo_entrada") else " "
        s = "S" if campo(ev, "tipo_saida") else " "
        marca = ""
        if PADRAO.search(desc):
            marca = "  <-- entre filiais?"
        elif interno in CANDIDATOS_FIXOS:
            marca = "  <-- candidato"
        print(f'  {interno:>7} {cod:8} {e:1} {s:1}  {desc}{marca}')
    return linhas


def escolhe(linhas, manual) -> list[tuple[int, str]]:
    if manual:
        pedidos = {int(t) for t in manual.split(",") if t.strip()}
        return [(campo(e, "evento"), str(campo(e, "descricao") or ""))
                for e in linhas if campo(e, "evento") in pedidos] or \
               [(n, "(fora do catalogo)") for n in sorted(pedidos)]

    escolhidos = {}
    for ev in linhas:
        interno = campo(ev, "evento")
        desc = str(campo(ev, "descricao") or "")
        if interno is None:
            continue
        if PADRAO.search(desc) or interno in CANDIDATOS_FIXOS:
            escolhidos[interno] = desc
    return sorted(escolhidos.items())


def sonda(candidatos, de: date, ate: date):
    titulo("2. Sondagem — vendas_consulta_completa por evento")
    if not candidatos:
        print("  Nenhum candidato. Use --eventos para forcar.")
        return

    print(f"  {len(candidatos)} evento(s) x {(ate - de).days + 1} dia(s)\n")
    ag = defaultdict(lambda: {"docs": 0, "itens": 0, "qtde": 0.0,
                              "produtos": set(), "destinos": set()})
    exemplo = None

    for interno, desc in candidatos:
        try:
            docs = mn.documentos_do_periodo(de, ate, (interno,))
        except mn.Falha as e:
            print(f"  evento {interno}: FALHOU ({e})")
            continue
        for doc in docs:
            if exemplo is None:
                exemplo = doc
            filial = str(campo(doc, "cod_filial") or "?").strip()
            a = ag[(interno, desc, filial)]
            a["docs"] += 1
            destino = campo(doc, "filial_destino", "cod_filial_destino",
                            "desc_filial_destino")
            if destino:
                a["destinos"].add(str(destino).strip())
            for item in doc.get("itens") or []:
                q = item.get("quant") or 0
                if q <= 0:
                    continue
                a["itens"] += 1
                a["qtde"] += q
                a["produtos"].add(str(item.get("cod_produto") or "").strip())

    if not ag:
        print("  Nenhum documento em nenhum candidato.")
        print("  A movimentacao nao passa por vendas_consulta_completa:")
        print("  o caminho passa a ser Lista_Por_Evento ou os relatorios.")
        return

    print(f'  {"evento":>6} {"filial":12} {"docs":>5} {"itens":>6} {"qtde":>8} '
          f'{"prod":>5}  descricao')
    print("  " + "-" * 82)
    for (interno, desc, filial), a in sorted(ag.items(), key=lambda x: -x[1]["qtde"]):
        alvo = " *" if any(s in filial.upper() for s in LOJAS) else ""
        print(f'  {interno:>6} {filial:12} {a["docs"]:>5} {a["itens"]:>6} '
              f'{a["qtde"]:>8,.0f} {len(a["produtos"]):>5}  {desc[:28]}{alvo}')
        if a["destinos"]:
            print(f'         destinos: {", ".join(sorted(a["destinos"]))[:60]}')

    if exemplo:
        print("\n  Campos de um documento (para achar a filial de destino):")
        for k, v in list(exemplo.items())[:28]:
            if k == "itens":
                v = f"[{len(exemplo['itens'])} itens]"
            print(f'    {k:22} {str(v)[:44]}')


def por_evento(candidatos, de: date, ate: date):
    """Plano B: Lista_Por_Evento traz FILIAL_DESTINO no documento."""
    titulo("3. Lista_Por_Evento — documento com filial de destino")
    for interno, desc in candidatos[:6]:
        try:
            linhas = mn.valores(mn.requisita(
                LISTA_POR_EVENTO,
                **{"$top": 2000, "EVENTO": interno,
                   "DATAI": de.isoformat(), "DATAF": ate.isoformat()}))
        except mn.Falha as e:
            print(f"  evento {interno:>4} ({desc[:30]}): {str(e)[:110]}")
            continue
        if not linhas:
            print(f"  evento {interno:>4} ({desc[:30]}): vazio")
            continue
        print(f"\n  evento {interno} — {desc}: {len(linhas)} documento(s)")
        fluxo = defaultdict(lambda: {"docs": 0, "valor": 0.0})
        for l in linhas:
            o = str(campo(l, "filial") or "?").strip()
            d = str(campo(l, "filial_destino") or "").strip() or "—"
            f = fluxo[(o, d)]
            f["docs"] += 1
            f["valor"] += float(campo(l, "valor_final") or 0)
        for (o, d), f in sorted(fluxo.items(), key=lambda x: -x[1]["valor"]):
            print(f'    {o:14} -> {d:14} {f["docs"]:>5} doc  R$ {f["valor"]:>12,.2f}')


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Descobre por qual evento a peca entra no estoque das lojas")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, required=True)
    p.add_argument("--eventos", default="",
                   help="internos separados por virgula; vazio escolhe pela descricao")
    p.add_argument("--so-catalogo", action="store_true")
    p.add_argument("--sem-cache", action="store_true")
    args = p.parse_args(argv)

    mn.USAR_CACHE = not args.sem_cache

    linhas = catalogo()
    if args.so_catalogo:
        return 0

    candidatos = escolhe(linhas, args.eventos)
    print(f"\nCandidatos: {', '.join(str(c[0]) for c in candidatos) or '(nenhum)'}")

    sonda(candidatos, args.de, args.ate)
    por_evento(candidatos, args.de, args.ate)

    r = REFERENCIA_PRODUCAO
    titulo("O que fazer com isso")
    print(f"""
  Referencia da aba Producao no mesmo periodo (31/08 a 07/09):

    peca acabada   {r['pecas']} pecas em {r['linhas']} linhas,
                   {r['produtos']} produtos, {r['produto_cor']} produto+cor
    insumo         {r['insumo']} (tecido, botao, etiqueta — FORA da conta)

  A producao chega INTEIRA na Elena, varejo e atacado juntos. Entao a
  transferencia ELENA ES -> lojas tem que ser um PEDACO dessas {r['pecas']}
  pecas, nunca mais que isso. Se der mais, a leitura esta errada.

  Procure na secao 2 ou 3 um evento que mova peca de ELENA ES para
  IGUATEMI ou EGREY JDS (marcado com *). O interno dele vai para a
  tabela mn.EVENTOS como entrada de estoque — e precisa ficar FORA da
  agregacao de venda, senao a receita de varejo infla.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
