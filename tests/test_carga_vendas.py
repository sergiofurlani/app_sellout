"""Carga retroativa das vendas.

O que decide o resultado sem tocar no banco — o recorte das semanas e o papel
da filial — é testado aqui. A gravação em si só roda com `DATABASE_URL`.
"""

from datetime import date

import pytest

from sellout.db import carga_vendas, conexao

precisa_banco = pytest.mark.skipif(
    not conexao.disponivel(), reason="sem DATABASE_URL/psycopg")


def test_a_semana_e_sempre_segunda_a_domingo():
    js = carga_vendas.semanas(date(2026, 1, 5), date(2026, 1, 18))
    assert js == [(date(2026, 1, 5), date(2026, 1, 11)),
                  (date(2026, 1, 12), date(2026, 1, 18))]


def test_recua_ate_a_segunda_quando_a_data_cai_no_meio():
    """01/01/2026 é uma quinta. Começar ali daria uma semana de quatro dias —
    um número menor que ninguém questionaria, porque a linha existe."""
    js = carga_vendas.semanas(date(2026, 1, 1), date(2026, 1, 11))
    assert js[0] == (date(2025, 12, 29), date(2026, 1, 4))


def test_cobre_o_intervalo_inteiro():
    js = carga_vendas.semanas(date(2026, 1, 1), date(2026, 9, 20))
    assert js[0][0] <= date(2026, 1, 1)
    assert js[-1][1] >= date(2026, 9, 20)
    # segunda a domingo sao 6 dias de diferenca, nao 7
    assert all((b - a).days == 6 for a, b in js)
    assert all(a.weekday() == 0 and b.weekday() == 6 for a, b in js)


def test_um_dia_ainda_da_uma_semana():
    assert len(carga_vendas.semanas(date(2026, 9, 20), date(2026, 9, 20))) == 1


def test_o_papel_da_filial_decide_se_a_venda_aparece():
    """A consulta do sellout só soma papel 'loja' ou 'ecommerce'. Filial sem
    papel cai em 'fora' e some da conta — calada. Uma venda que entra no banco
    e não aparece na consulta é pior do que uma venda que não entrou."""
    assert carga_vendas.PAPEL["EGREY JDS"] == "loja"
    assert carga_vendas.PAPEL["IGUATEMI"] == "loja"
    assert carga_vendas.PAPEL["SITE"] == "ecommerce"


def test_a_matriz_nao_tem_papel_de_venda():
    """O que a Elena 'vende' para a loja é transferência, e já está no
    denominador. Contar como venda infla o numerador com movimento interno."""
    assert "ELENA ES" not in carga_vendas.PAPEL
    assert "ELENA SP" not in carga_vendas.PAPEL


def test_apagar_sem_datas_nao_toca_no_banco():
    """Guarda contra um --refazer num intervalo vazio virar DELETE sem WHERE."""
    assert carga_vendas.apaga([]) == 0


@precisa_banco
def test_ja_carregadas_devolve_datas():
    datas = carga_vendas.ja_carregadas(date(2026, 1, 1), date(2026, 12, 31))
    assert isinstance(datas, set)
    assert all(isinstance(d, date) for d in datas)
