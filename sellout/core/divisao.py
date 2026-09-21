"""Divisão de um código entre duas linhas pela cor escrita em vermelho.

Quando o mesmo código aparece em duas linhas, o trecho em vermelho ao final
da descrição diz de quais cores aquela linha trata; a linha sem vermelho fica
com as cores restantes. "DEMAIS CORES" também significa o restante.
"""

from __future__ import annotations

from collections import defaultdict

from .cores import eh_resto, match, tokens

MANTER = "MANTER"       # não alterar a linha (decisão do usuário)
PENDENTE = "PENDENTE"   # divisão não identificada


def resolver(codigo, linhas_do_codigo, vermelhos, fontes, decisao=None):
    """Devolve (atribuicao, sobra, pendencia).

    `atribuicao` mapeia linha -> conjunto de cores, MANTER ou PENDENTE.
    `sobra` são cores que existem no estoque/vendas e não couberam em
    nenhuma linha. `pendencia` descreve por que não deu para dividir.
    """
    disponiveis = fontes.cores_do_codigo(codigo)
    linhas = list(linhas_do_codigo)

    if decisao == "manter":
        return {r: MANTER for r in linhas}, set(), None

    # "idx:N" concentra tudo na N-ésima linha do código. Guardamos a posição, e
    # não o número da linha, porque produtos novos inseridos acima deslocam a
    # planilha entre a tela de revisão e o processamento.
    if isinstance(decisao, str) and decisao.startswith("idx:"):
        try:
            escolhida = linhas[int(decisao[4:])]
        except (ValueError, IndexError):
            escolhida = None
        if escolhida is not None:
            return {r: (disponiveis if r == escolhida else set()) for r in linhas}, set(), None

    # Linha única sem vermelho leva tudo.
    if len(linhas) == 1 and not vermelhos.get(linhas[0]):
        return {linhas[0]: None}, set(), None

    atribuicao = {}
    tokens_sem_match = []
    cores_sem_saldo = []
    for r in linhas:
        v = vermelhos.get(r, "")
        if not v:
            continue
        if eh_resto(v):
            atribuicao[r] = "__RESTO__"
            continue
        selecionadas = []
        for t in tokens(v):
            achadas = match(t, disponiveis)
            if not achadas:
                # Cor conhecida do cadastro que zerou o estoque nesta semana
                # contribui zero e a linha segue valendo. Só texto que não é
                # cor de verdade ("CORES SS25") trava a divisão.
                if fontes.eh_cor_conhecida(t):
                    cores_sem_saldo.append(t)
                else:
                    tokens_sem_match.append(t)
            selecionadas += achadas
        atribuicao[r] = set(selecionadas)

    usadas = set()
    for r, s in atribuicao.items():
        if s != "__RESTO__":
            usadas |= s

    for r, s in atribuicao.items():
        if s == "__RESTO__":
            atribuicao[r] = disponiveis - usadas

    sem_vermelho = [r for r in linhas if not vermelhos.get(r)]
    if len(sem_vermelho) == 1:
        atribuicao[sem_vermelho[0]] = disponiveis - usadas

    if tokens_sem_match:
        motivo = "cor citada em vermelho não existe no estoque: " + ", ".join(sorted(set(tokens_sem_match)))
        return {r: PENDENTE for r in linhas}, set(), motivo
    if len(sem_vermelho) > 1:
        motivo = "as %d linhas estão sem texto em vermelho" % len(sem_vermelho)
        return {r: PENDENTE for r in linhas}, set(), motivo
    if len(atribuicao) != len(linhas):
        return {r: PENDENTE for r in linhas}, set(), "divisão incompleta entre as linhas"

    cobertas = set()
    for s in atribuicao.values():
        cobertas |= s
    return atribuicao, disponiveis - cobertas, None


def agrupar_por_codigo(linhas):
    por_codigo = defaultdict(list)
    for r, cod, _bloco in linhas:
        por_codigo[cod].append(r)
    return por_codigo
