"""Banco x planilha, componente a componente.

O veredito é o que autoriza aposentar a planilha, então ele é testado sem
banco: as funções que comparam e classificam são puras.
"""

from datetime import date

import pytest

from sellout.db import confere


def lado(inicial, vendas):
    return {"estoque_inicial": float(inicial), "vendas": float(vendas)}


def banco(inicial, vendas, colecao="SS27"):
    return {"estoque_inicial": float(inicial), "vendas": float(vendas),
            "colecao": colecao}


def test_produto_que_fecha_nos_dois_componentes():
    r = confere.compara({"334128": lado(100, 40)},
                        {"334128": banco(100, 40)}, ["SS27"])
    v = confere.veredito(r["comparaveis"])
    assert v["ok"] == 1 and v["total"] == 1


def test_separa_de_que_lado_esta_o_desvio():
    """Se o Estoque inicial bate e a venda não, já se sabe onde olhar. Um
    veredito que só diz 'difere' obriga a refazer a investigação inteira."""
    r = confere.compara(
        {"A": lado(100, 40), "B": lado(100, 40), "C": lado(100, 40)},
        {"A": banco(80, 40), "B": banco(100, 25), "C": banco(70, 20)},
        ["SS27"])
    v = confere.veredito(r["comparaveis"])
    assert [l["codigo"] for l in v["so_inicial"]] == ["A"]
    assert [l["codigo"] for l in v["so_vendas"]] == ["B"]
    assert [l["codigo"] for l in v["ambos"]] == ["C"]


def test_dois_erros_opostos_nao_passam_pelo_percentual():
    """**O motivo de a comparação ser por componente.** 50/200 e 25/100 dão os
    mesmos 25%: pelo percentual final este produto passaria como certo, com os
    dois números errados."""
    r = confere.compara({"334128": lado(200, 50)},
                        {"334128": banco(100, 25)}, ["SS27"])
    (item,) = r["comparaveis"]
    assert item["sellout_planilha"] == item["sellout_banco"] == 0.25
    assert confere.veredito(r["comparaveis"])["ok"] == 0


def test_a_tolerancia_absorve_uma_peca():
    r = confere.compara({"334128": lado(100, 40)},
                        {"334128": banco(101, 39)}, ["SS27"])
    assert confere.veredito(r["comparaveis"], tolerancia=1.0)["ok"] == 1


def test_colecao_antiga_fica_fora_do_veredito():
    """A planilha acumula venda desde 2023; o banco começa em 01/01/2026.
    Comparar ali não mede nada — a planilha ganha sempre, por um motivo
    conhecido. Contar isso como divergência afogaria o sinal de verdade."""
    r = confere.compara({"A": lado(100, 90)}, {"A": banco(100, 10, "AW24")},
                        ["AW26", "SS27"])
    assert r["comparaveis"] == []
    assert [l["codigo"] for l in r["fora_da_janela"]] == ["A"]


def test_codigo_de_um_lado_so_nao_vira_diferenca_de_numero():
    """Chave que existe num lado só é diferença de cadastro. Somar como zero
    do outro lado inventaria um desvio que não é de número."""
    r = confere.compara({"A": lado(10, 5)}, {"B": banco(10, 5)}, ["SS27"])
    assert r["so_planilha"] == ["A"] and r["so_banco"] == ["B"]
    assert r["comparaveis"] == []


def test_as_cores_do_banco_somam_no_codigo(monkeypatch):
    """A planilha tem uma linha por produto; o banco, uma por produto e cor."""
    monkeypatch.setattr(confere.consulta, "sellout", lambda ate: [
        {"codigo": "334128", "codigo_cor": "0002", "colecao": "SS27",
         "estoque_inicial": 60, "vendas": 25},
        {"codigo": "334128", "codigo_cor": "0008", "colecao": "SS27",
         "estoque_inicial": 40, "vendas": 15},
    ])
    b = confere.do_banco(date(2026, 9, 14))
    assert b["334128"]["estoque_inicial"] == 100
    assert b["334128"]["vendas"] == 40


def test_veredito_vazio_nao_divide_por_zero():
    assert confere.veredito([])["pct_ok"] is None


def test_a_colecao_vem_da_planilha_quando_o_banco_nao_sabe():
    """**O defeito de 27/09.** A tabela `produto` só é preenchida pelas rodadas
    de upload, e a carga retroativa não passa por lá — filtrar a coleção pelo
    banco deixou a comparação com zero produtos, tendo 394 códigos de um lado e
    739 do outro. Quem sabe a coleção é o bloco da planilha."""
    planilha = {"334128": {"estoque_inicial": 100.0, "vendas": 40.0,
                           "colecao": "SS27"}}
    r = confere.compara(planilha, {"334128": banco(100, 40, colecao="")},
                        ["SS27"])
    assert len(r["comparaveis"]) == 1
    assert r["fora_da_janela"] == []


def test_a_colecao_do_banco_ainda_serve_de_reserva():
    r = confere.compara({"334128": lado(100, 40)},
                        {"334128": banco(100, 40, "AW26")}, ["AW26"])
    assert len(r["comparaveis"]) == 1
