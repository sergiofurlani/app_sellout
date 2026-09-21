"""Entradas do ERP: o Estoque inicial do produto novo nasce do que chegou."""
import pytest

from sellout.core.leitura import carrega_entradas_erp


def escreve(tmp_path, texto):
    caminho = tmp_path / "entradas.csv"
    caminho.write_text(texto, encoding="utf-8-sig")
    return str(caminho)


def test_le_o_formato_do_coletor(tmp_path):
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n"
                          "334066;0036;0036 - OFF-WHITE;24\n"
                          "334066;0308;0308 - VERMELHO;24\n")
    e = carrega_entradas_erp(c)
    assert e["334066"] == {"OFF WHITE": 24, "VERMELHO": 24}


def test_tira_o_codigo_da_frente_da_cor(tmp_path):
    """O ERP manda '0308 - VERMELHO'; as abas de origem trazem só o nome."""
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n239064;0308;0308 - VERMELHO;42\n")
    assert list(carrega_entradas_erp(c)["239064"]) == ["VERMELHO"]


def test_soma_linhas_do_mesmo_produto_e_cor(tmp_path):
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n"
                          "334066;0036;OFF-WHITE;10\n"
                          "334066;0036;OFF-WHITE;14\n")
    assert carrega_entradas_erp(c)["334066"]["OFF WHITE"] == 24


def test_aceita_virgula_como_separador(tmp_path):
    c = escreve(tmp_path, "codigo,codigo_cor,cor,quant\n334066,0036,OFF-WHITE,24\n")
    assert carrega_entradas_erp(c)["334066"]["OFF WHITE"] == 24


def test_quantidade_zero_ou_vazia_nao_entra(tmp_path):
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n"
                          "334066;0036;OFF-WHITE;0\n"
                          "334044;0003;MARINHO;;\n"
                          "334017;0003;MARINHO;5\n")
    e = carrega_entradas_erp(c)
    assert set(e) == {"334017"}


def test_devolucao_liquida_pode_ser_negativa(tmp_path):
    """A loja pode devolver mais do que recebeu no período extraído."""
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n100009;0001;BRANCO;-1\n")
    assert carrega_entradas_erp(c)["100009"]["BRANCO"] == -1


@pytest.mark.parametrize("cabecalho", ["CODIGO;CODIGO_COR;COR;QUANT",
                                       "Codigo; Codigo_cor; Cor; Quantidade"])
def test_cabecalho_tolerante(tmp_path, cabecalho):
    c = escreve(tmp_path, cabecalho + "\n334066;0036;OFF-WHITE;24\n")
    assert carrega_entradas_erp(c)["334066"]["OFF WHITE"] == 24
