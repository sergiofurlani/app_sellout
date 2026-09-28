"""A ficha de um produto: as parcelas dos dois lados, sem veredito."""

from datetime import date

import openpyxl

from sellout.db import ficha


def mov(tipo="transferencia", qtd=10, data="2026-03-01", cor="0002"):
    return {"data": date.fromisoformat(data), "codigo_cor": cor, "tipo": tipo,
            "evento": 106, "filial": "EGREY JDS", "qtd": float(qtd),
            "documento": "D1"}


def test_os_tipos_de_movimento_nao_viram_um_total_so():
    """Transferência entra estoque, realocação soma zero no conjunto e saída de
    bazar tira do universo do sellout. Um total único esconde as três."""
    t = ficha.por_tipo([mov("transferencia", 10), mov("transferencia", 5),
                        mov("saida_bazar", -3), mov("realocacao", 2)])
    assert t["transferencia"] == {"qtd": 15.0, "linhas": 2}
    assert t["saida_bazar"]["qtd"] == -3.0
    assert set(t) == {"transferencia", "saida_bazar", "realocacao"}


def test_sem_movimento_nenhum_tipo_e_inventado():
    assert ficha.por_tipo([]) == {}


def linha(inicial, vendas, atual, cor="0002"):
    return {"codigo_cor": cor, "estoque_inicial": float(inicial),
            "vendas": float(vendas), "estoque_atual": float(atual)}


def test_a_sobra_e_o_que_ainda_nao_tem_nome():
    """100 entraram, 60 venderam, 30 estão na loja: 10 estão em algum lugar.
    Consignação mais erro (D21) — e é por isso que ela não acusa sozinha."""
    r = ficha.reconcilia([linha(100, 60, 30)])
    assert r["sobra"] == 10.0
    assert r["sellout"] == 0.6


def test_as_cores_somam_no_produto():
    r = ficha.reconcilia([linha(60, 25, 30, "0002"), linha(40, 15, 20, "0008")])
    assert r["estoque_inicial"] == 100.0 and r["vendas"] == 40.0
    assert r["estoque_atual"] == 50.0 and r["sobra"] == 10.0


def test_sem_denominador_o_sellout_e_ausencia_e_nao_zero():
    """Zero por cento e "não há conta" são coisas diferentes, e a segunda é a
    que precisa de investigação."""
    r = ficha.reconcilia([linha(0, 0, 0)])
    assert r["sellout"] is None


def test_sobra_negativa_aparece_como_esta():
    """Vendeu mais do que entrou: é erro, e arredondar para zero o esconderia."""
    assert ficha.reconcilia([linha(10, 15, 0)])["sobra"] == -5.0


# ------------------------------------------------------ o lado da planilha

def planilha(tmp_path, codigo="334019", com_real=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Feminino"
    cab = ["", "Código", "FEMININO - SS27", "Estoque atual"]
    cab += ["Consignado Real", "Consignado"] if com_real else ["Consignado"]
    cab += ["Vendas Jardins", "Vendas Iguatemi", "Vendas Site", "Vendas Totais",
            "Estoque inicial", "Sellout 21/09"]
    for i, t in enumerate(cab, 1):
        ws.cell(3, i, t)
    vals = ["", codigo, "BLUSA", 12] + ([3, 5] if com_real else [5])
    vals += [8, 19, 15, 42, 58, 0.724]
    for i, v in enumerate(vals, 1):
        ws.cell(4, i, v)
    caminho = tmp_path / "g.xlsx"
    wb.save(caminho)
    return str(caminho)


def test_a_ficha_traz_a_linha_inteira_da_planilha(tmp_path):
    (a,) = ficha.da_planilha(planilha(tmp_path), "334019")
    assert a["aba"] == "Feminino" and a["linha"] == 4
    assert a["J"] == 58 and a["I"] == 42
    assert (a["JARDINS"], a["IGUATEMI"], a["SITE"]) == (8, 19, 15)


def test_as_duas_consignacoes_aparecem_separadas(tmp_path):
    """A medida e a conta lado a lado — a diferença entre elas é o assunto."""
    (a,) = ficha.da_planilha(planilha(tmp_path), "334019")
    assert a["E"] == 3, "Consignado Real"
    assert a["E_CONTA"] == 5, "o resto = J - I - D"


def test_planilha_antiga_so_tem_uma_consignacao(tmp_path):
    (a,) = ficha.da_planilha(planilha(tmp_path, com_real=False), "334019")
    assert a["E"] == a["E_CONTA"] == 5


def test_codigo_ausente_devolve_lista_vazia(tmp_path):
    assert ficha.da_planilha(planilha(tmp_path), "999999") == []


def test_o_codigo_e_normalizado_antes_de_procurar(tmp_path):
    """A planilha guarda código como número em algumas linhas e como texto em
    outras; procurar pelo texto cru acha metade."""
    assert ficha.da_planilha(planilha(tmp_path), " 334019 ")
