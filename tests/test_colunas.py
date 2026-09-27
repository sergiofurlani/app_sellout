"""As colunas das abas de trabalho, achadas pelo cabeçalho.

Pela letra não dá: a aba Feminino dos Clássicos tem uma "Curadobia" a mais, e
"sellout geral 2109.xlsx" ganhou uma "Consignado Real". Cada coluna nova
desloca todas à direita dela.
"""

import openpyxl
import pytest

from sellout.core.leitura import mapa_colunas


def aba(*cabecalhos):
    wb = openpyxl.Workbook()
    ws = wb.active
    for i, t in enumerate(cabecalhos, 1):
        ws.cell(3, i, t)
    return ws


GERAL_2109 = ("", "Código", "FEMININO - SS27", "Estoque atual", "Consignado Real",
              "Consignado", "Vendas Jardins", "Vendas Iguatemi", "Vendas Site",
              "Vendas Totais", "Estoque inicial", "Sellout 21/09")

GERAL_1409 = ("", "Código", "FEMININO - SS27", "Estoque atual", "Consignado",
              "Vendas Jardins", "Vendas Iguatemi", "Vendas Site",
              "Vendas Totais", "Estoque inicial", "Sellout 14/09")


def test_a_coluna_nova_nao_desloca_as_outras():
    m = mapa_colunas(aba(*GERAL_2109))
    assert (m["D"], m["I"], m["J"], m["K"]) == (4, 10, 11, 12)
    assert (m["JARDINS"], m["IGUATEMI"], m["SITE"]) == (7, 8, 9)


def test_a_consignacao_medida_e_a_conta_sao_colunas_diferentes():
    """**O defeito que eu tinha deixado aberto.** A regra era "qualquer cabeçalho
    que comece com CONSIGNA", ficando com o último — acertava pela ordem das
    colunas, não por regra. "Consignado Real" é a medida (remessa 14 − acerto
    19); "Consignado" é o resto `= J − I − D`, a conta que fecha sempre."""
    m = mapa_colunas(aba(*GERAL_2109))
    assert m["E"] == 5, "a consignacao do sellout e a medida"
    assert m["E_CONTA"] == 6


def test_planilha_so_com_a_coluna_antiga_continua_funcionando():
    """Os arquivos anteriores a 21/09 têm só "Consignado". Exigir a medida
    quebraria a releitura de qualquer histórico."""
    m = mapa_colunas(aba(*GERAL_1409))
    assert m["E"] == m["E_CONTA"] == 5


def test_a_medida_ganha_mesmo_vindo_depois_da_conta():
    """A ordem das colunas no arquivo não pode decidir isto."""
    m = mapa_colunas(aba("", "Código", "d", "Estoque atual", "Consignado",
                         "Consignado Real", "Vendas Totais", "Estoque inicial",
                         "Sellout 21/09"))
    assert m["E"] == 6 and m["E_CONTA"] == 5


def test_sem_coluna_de_consignacao_nenhuma_chave_e_inventada():
    m = mapa_colunas(aba("", "Código", "d", "Estoque atual", "Vendas Totais",
                         "Estoque inicial", "Sellout 21/09"))
    assert "E" not in m and "E_CONTA" not in m


def test_a_coluna_curadobia_dos_classicos():
    m = mapa_colunas(aba("", "Código", "FEMININO - PERENE", "Curadobia",
                         "Estoque atual", "Consignado", "Vendas Totais",
                         "Estoque inicial", "Sellout 21/09"))
    assert (m["D"], m["E"], m["I"], m["J"], m["K"]) == (5, 6, 7, 8, 9)
