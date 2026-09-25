from sellout.core.leitura import ColunaAusente, colunas_da_fonte, num
import openpyxl
import pytest


def test_num_aceita_numero_texto_e_vazio():
    assert num(12) == 12
    assert num("12") == 12
    assert num("1,5") == 1.5
    assert num("1.234,56") == 1234.56
    assert num(None) == 0
    assert num("") == 0
    assert num("-") == 0
    assert num("n/d") is None       # sinaliza célula não numérica


def _aba(cabecalhos):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(cabecalhos)
    return ws


def test_colunas_pelo_cabecalho_mesmo_fora_de_ordem():
    ws = _aba(["ESTOQUE ATUAL", "Cor", "Código", "CODIGO cor", "tamanho"])
    spec = [("codigo", ["CODIGO"], 2, True), ("cor", ["COR"], 5, True),
            ("qtde", ["ESTOQUE ATUAL"], 7, True)]
    achadas = colunas_da_fonte(ws, spec)
    assert achadas == {"codigo": 3, "cor": 2, "qtde": 1}


def test_coluna_obrigatoria_ausente_avisa_qual():
    ws = _aba(["Alguma coisa"])
    spec = [("qtde", ["ESTOQUE ATUAL"], 90, True)]
    with pytest.raises(ColunaAusente, match="ESTOQUE ATUAL"):
        colunas_da_fonte(ws, spec)
