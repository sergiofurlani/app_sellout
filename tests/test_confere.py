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


def test_vida_anterior_sai_do_veredito():
    """**Separado por dado, não por aparência.** Produto que já vendia antes de
    2026 tem o mesmo pedaço faltando dos dois lados — a divergência dele está
    explicada antes de qualquer investigação, e mantê-lo no veredito afogaria
    o sinal do que não está."""
    r = confere.compara({"A": lado(100, 40), "B": lado(300, 250)},
                        {"A": banco(100, 40), "B": banco(120, 100)},
                        ["SS27"], antigos={"B"})
    assert [l["codigo"] for l in r["comparaveis"]] == ["A"]
    assert [l["codigo"] for l in r["vida_anterior"]] == ["B"]
    assert confere.veredito(r["comparaveis"])["pct_ok"] == 1.0


def test_sem_lista_de_antigos_nada_muda():
    r = confere.compara({"A": lado(100, 40)}, {"A": banco(100, 40)}, ["SS27"])
    assert len(r["comparaveis"]) == 1 and r["vida_anterior"] == []


# ------------------------------------------------------- apuracao do desvio

def divergente(codigo="332004", pl=42, bc=39, desde=date(2026, 4, 5)):
    return {"codigo": codigo, "vendas_planilha": float(pl),
            "vendas_banco": float(bc), "dif_vendas": float(pl - bc),
            "venda_desde": desde}


def test_o_resto_zera_quando_a_devolucao_tem_o_tamanho_do_desvio():
    """A identidade que se testa: o banco guarda venda líquida, então uma
    coluna que conte só a saída fica maior pelo exato tamanho do que voltou."""
    (x,) = confere.apura([divergente()], {"332004": {"pecas": -3.0, "linhas": 3}})
    assert x["resto"] == 0.0
    assert x["fecha_com_devolucao"]


def test_sem_devolucao_no_periodo_o_desvio_fica_sem_numero_que_o_cerque():
    """**O teste que mata a hipótese.** Produto com desvio e devolução zero não
    pode ser atribuído a devolução — e `fecha_com_devolucao` falso é o que
    impede o relatório de contá-lo como resolvido."""
    (x,) = confere.apura([divergente()], {})
    assert x["resto"] == 3.0
    assert not x["fecha_com_devolucao"]


def test_devolucao_do_tamanho_errado_nao_fecha():
    (x,) = confere.apura([divergente()], {"332004": {"pecas": -1.0, "linhas": 1}})
    assert x["resto"] == 2.0 and not x["fecha_com_devolucao"]


def test_desvio_para_o_outro_lado_nao_e_fechado_por_devolucao():
    """330010: o banco é que tem mais (venda pl 20, bc 48). Devolução só pode
    inflar a planilha em relação ao banco; somá-la aqui afastaria o resto do
    zero, e é isso que tem de acontecer."""
    (x,) = confere.apura([divergente("330010", 20, 48, date(2026, 1, 4))],
                         {"330010": {"pecas": -2.0, "linhas": 2}})
    assert x["resto"] == -30.0 and not x["fecha_com_devolucao"]


def test_devolucao_zero_nunca_fecha_nem_com_desvio_zero():
    """Sem devolução não há o que fechar: `resto` zero com `devolucao` zero é
    produto que já batia, não hipótese confirmada."""
    (x,) = confere.apura([divergente(pl=39)], {})
    assert x["resto"] == 0.0 and not x["fecha_com_devolucao"]


def test_a_apuracao_traz_as_datas_de_estreia_dos_dois_lados():
    """Serve para separar 'falta venda no banco' de 'a planilha conta desde
    outra data' — as duas dão o mesmo desvio no acumulado."""
    (x,) = confere.apura([divergente()], {},
                         {"332004": date(2026, 3, 1)})
    assert x["venda_desde"] == date(2026, 4, 5)
    assert x["planilha_desde"] == date(2026, 3, 1)


def test_a_apuracao_nao_mexe_nas_linhas_da_comparacao():
    linha = divergente()
    confere.apura([linha], {"332004": {"pecas": -3.0, "linhas": 3}})
    assert "resto" not in linha


def test_antigo_fora_da_colecao_alvo_continua_fora_da_janela():
    """As duas exclusões não se confundem: coleção antiga é recorte, vida
    anterior é janela de dado."""
    r = confere.compara({"A": lado(10, 5)}, {"A": banco(10, 5, "AW24")},
                        ["SS27"], antigos={"A"})
    assert [l["codigo"] for l in r["fora_da_janela"]] == ["A"]
    assert r["vida_anterior"] == []


# ------------------------------------- localizar o desvio no tempo (330010)

def semanas(*pares):
    return [(date.fromisoformat(d), float(q), 0.0) for d, q in pares]


def test_acha_a_semana_a_partir_da_qual_o_banco_soma_o_numero_da_planilha():
    """**O caso 330010.** O banco tem 46 desde janeiro; a planilha diz 20. Somando
    de 2026-03-29 para cá dá 19 — dentro da tolerância. O desvio não está
    espalhado: está inteiro nas semanas de janeiro e fevereiro."""
    s = semanas(("2026-01-11", 27), ("2026-03-29", 1), ("2026-05-31", 1),
                ("2026-08-02", 17))
    assert confere.desde_quando(s, 20.0) == date(2026, 3, 29)


def test_alvo_maior_que_tudo_que_o_banco_tem_nao_vira_data():
    """**O caso 332004.** A planilha diz 42 e o banco tem 40 no total: não existe
    semana que resolva isso, e devolver a primeira data faria parecer que
    existe."""
    assert confere.desde_quando(semanas(("2026-04-05", 40)), 42.0) is None


def test_serie_vazia_nao_casa():
    assert confere.desde_quando([], 20.0) is None


def test_casa_na_semana_mais_recente_possivel():
    """Varre de trás para frente: entre duas semanas que dão a mesma soma, a
    mais recente é a afirmação menor — inclui menos dado no que se explica."""
    s = semanas(("2026-01-04", 5), ("2026-02-01", 0), ("2026-03-01", 10))
    assert confere.desde_quando(s, 10.0) == date(2026, 3, 1)


def test_o_numero_da_planilha_entre_liquido_e_bruto_e_apontado():
    """40 líquido, 49 bruto, planilha 42: ela conta parte do que voltou. É outra
    conta que o líquido puro não alcança, e some se ninguém a mede."""
    (x,) = confere.apura([divergente(pl=42, bc=40)],
                         {"332004": {"pecas": -9.0, "linhas": 6}})
    assert x["vendas_bruto"] == 49.0
    assert x["entre_liquido_e_bruto"]
    assert not x["fecha_com_devolucao"], "-9 nao e o tamanho do desvio de +2"


def test_planilha_fora_da_faixa_liquido_bruto():
    (x,) = confere.apura([divergente("330010", 20, 46)],
                         {"330010": {"pecas": -12.0, "linhas": 8}})
    assert x["vendas_bruto"] == 58.0
    assert not x["entre_liquido_e_bruto"]


def test_a_apuracao_usa_a_serie_do_proprio_codigo():
    s = {"330010": semanas(("2026-01-11", 27), ("2026-03-29", 19))}
    (x,) = confere.apura([divergente("330010", 20, 46)], {}, None, s)
    assert x["casa_desde"] == date(2026, 3, 29)


def test_sem_serie_a_apuracao_nao_inventa_semana():
    (x,) = confere.apura([divergente()], {})
    assert x["casa_desde"] is None


# --------------------------------- a planilha e o banco na mesma foto (27/09)

def test_a_janela_casa_quando_a_planilha_roda_depois_do_domingo():
    """As semanas do banco fecham no domingo; a planilha e rodada na segunda."""
    assert confere.janela_casa(date(2026, 9, 21), date(2026, 9, 20))


def test_uma_semana_de_diferenca_nao_casa():
    """**O meu erro de 27/09.** Comparei a planilha de 21/09 com o banco cortado
    em 14/09 e li o resultado como divergência de dado. Sete dias é uma semana
    de venda a mais em um dos lados, em todos os produtos de uma vez."""
    assert not confere.janela_casa(date(2026, 9, 21), date(2026, 9, 14))


def test_o_mesmo_dia_casa():
    assert confere.janela_casa(date(2026, 9, 14), date(2026, 9, 14))


def test_corte_depois_da_planilha_nao_casa():
    """Banco à frente é o mesmo defeito ao contrário — e é o que aconteceria ao
    rodar `--ate` de hoje contra um arquivo da semana passada."""
    assert not confere.janela_casa(date(2026, 9, 14), date(2026, 9, 20))


def test_sem_data_no_cabecalho_nao_se_afirma_que_casa():
    """Não achar a data é não saber. Devolver True aqui deixaria passar
    justamente o arquivo cujo cabeçalho mudou de formato."""
    assert not confere.janela_casa(None, date(2026, 9, 20))


def test_seis_dias_e_o_limite():
    assert confere.janela_casa(date(2026, 9, 26), date(2026, 9, 20))
    assert not confere.janela_casa(date(2026, 9, 27), date(2026, 9, 20))


# --------------------------------- abrir o desvio por loja (o desvio de +3)

def test_o_desvio_concentrado_numa_loja_aparece_nela_sozinha():
    """**O que 18 produtos com desvio de exatamente +3 pedem.** Um desvio no
    total não tem lugar; o mesmo desvio inteiro numa das três lojas tem."""
    r = confere.por_loja(
        ["332004"],
        {"332004": {"EGREY JDS": 8.0, "IGUATEMI": 19.0, "SITE": 15.0}},
        {"332004": {"EGREY JDS": 8.0, "IGUATEMI": 16.0, "SITE": 15.0}})
    assert r["resumo"]["IGUATEMI"]["dif"] == 3.0
    assert r["resumo"]["IGUATEMI"]["produtos"] == 1
    assert r["resumo"]["EGREY JDS"]["dif"] == 0.0
    assert r["resumo"]["SITE"]["produtos"] == 0


def test_filial_que_so_existe_no_banco_nao_e_ignorada():
    """Uma filial mapeada como `fora`, ou de nome novo, explicaria desvio
    constante — e não está em nenhuma coluna do arquivo. Somar só as três lojas
    conhecidas a esconderia."""
    r = confere.por_loja(
        ["A"], {"A": {"EGREY JDS": 10.0}},
        {"A": {"EGREY JDS": 10.0, "OUTLET": 3.0}})
    assert "OUTLET" in r["resumo"]
    assert r["resumo"]["OUTLET"]["dif"] == -3.0


def test_as_tres_lojas_aparecem_mesmo_sem_venda():
    """Zero medido é diferente de loja ausente do relatório."""
    r = confere.por_loja(["A"], {}, {})
    assert set(r["resumo"]) == {"EGREY JDS", "IGUATEMI", "SITE"}
    assert r["resumo"]["SITE"] == {"planilha": 0.0, "banco": 0.0, "dif": 0.0,
                                  "produtos": 0}


def test_desvio_espalhado_nas_tres_nao_se_concentra():
    r = confere.por_loja(
        ["A"], {"A": {"EGREY JDS": 11.0, "IGUATEMI": 11.0, "SITE": 11.0}},
        {"A": {"EGREY JDS": 8.0, "IGUATEMI": 8.0, "SITE": 8.0}})
    difs = {f: d["dif"] for f, d in r["resumo"].items()}
    assert difs == {"EGREY JDS": 3.0, "IGUATEMI": 3.0, "SITE": 3.0}


def test_a_tolerancia_vale_por_loja():
    r = confere.por_loja(["A"], {"A": {"SITE": 11.0}}, {"A": {"SITE": 10.0}})
    assert r["resumo"]["SITE"]["dif"] == 1.0
    assert r["resumo"]["SITE"]["produtos"] == 0, "uma peca nao conta"
