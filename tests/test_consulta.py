"""O sellout calculado no banco.

As partes que decidem o número — a razão, os totais do conjunto, o tratamento
do denominador zero — são funções puras e são testadas aqui sem banco. A
consulta em si só roda quando há `DATABASE_URL`.
"""

from datetime import date

import pytest

from sellout.db import consulta, conexao

precisa_banco = pytest.mark.skipif(
    not conexao.disponivel(), reason="sem DATABASE_URL/psycopg")


def linha(**kw):
    base = {"codigo": "334128", "codigo_cor": "0002", "cor": "PRETO",
            "descricao": "BLUSA", "colecao": "SS27", "linha": "",
            "estoque_inicial": 100, "vendas": 40, "estoque_atual": 55,
            "venda_desde": date(2026, 9, 14)}
    base.update(kw)
    return consulta.enriquece(base)


def test_a_razao_e_vendas_sobre_estoque_inicial():
    assert consulta.percentual(40, 100) == 0.4


def test_denominador_zero_nao_e_zero_por_cento():
    """Zero por cento é um número e ninguém questiona; ausência de conta tem
    que aparecer como ausência. Com 0%, a média do bloco cairia sem nenhum
    produto ter ido mal."""
    assert consulta.percentual(0, 0) is None
    assert consulta.percentual(5, 0) is None


def test_a_sobra_e_a_conferencia():
    """Estoque inicial − vendas − estoque atual. É consignação mais erro — a
    mesma conta que a coluna Consignado fazia, agora com as duas pontas
    medidas (D21)."""
    assert linha(estoque_inicial=100, vendas=40, estoque_atual=55)["sobra"] == 5


def test_o_sellout_do_conjunto_e_a_razao_dos_totais():
    """**Média de percentuais dá peso igual a um produto de 3 peças e a um de
    300.** Um produto pequeno com 100% puxaria o bloco inteiro para cima."""
    linhas = [linha(estoque_inicial=300, vendas=30),
              linha(codigo="999999", estoque_inicial=3, vendas=3)]
    r = consulta.resumo(linhas)
    assert r["sellout"] == pytest.approx(33 / 303)
    media_ingenua = (30 / 300 + 3 / 3) / 2
    assert r["sellout"] < media_ingenua / 2, "a média ingênua daria 55%"


def test_o_resumo_conta_quem_ficou_sem_denominador():
    linhas = [linha(), linha(codigo="999999", estoque_inicial=0, vendas=0)]
    assert consulta.resumo(linhas)["sem_denominador"] == 1


def test_o_resumo_devolve_a_venda_mais_antiga():
    """É o que denuncia numerador incompleto: o denominador alcança janeiro, e
    se a venda mais antiga do banco é de setembro, o sellout subestima."""
    linhas = [linha(venda_desde=date(2026, 9, 14)),
              linha(codigo="999999", venda_desde=date(2026, 9, 7))]
    assert consulta.resumo(linhas)["venda_desde"] == date(2026, 9, 7)


def test_conjunto_vazio_nao_divide_por_zero():
    r = consulta.resumo([])
    assert r["sellout"] is None and r["produtos"] == 0


def test_venda_maior_que_o_inicial_passa_de_cem_por_cento():
    """Não é erro de conta: é sinal de que o Estoque inicial está incompleto.
    Truncar em 100% esconderia exatamente o que precisa ser visto."""
    assert linha(estoque_inicial=10, vendas=14)["sellout"] == 1.4


@precisa_banco
def test_a_consulta_roda_no_banco():
    linhas = consulta.sellout(date.today())
    assert isinstance(linhas, list)
    for l in linhas[:5]:
        assert {"codigo", "codigo_cor", "estoque_inicial", "vendas",
                "sellout", "sobra"} <= set(l)


@precisa_banco
def test_o_filtro_de_colecao_nao_inventa_linha():
    todas = consulta.sellout(date.today())
    ss27 = consulta.sellout(date.today(), colecao="SS27")
    assert len(ss27) <= len(todas)
    assert all((l["colecao"] or "").upper() == "SS27" for l in ss27)
