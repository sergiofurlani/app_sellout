"""Entradas do ERP: o Estoque inicial do produto novo nasce do que chegou."""
import pytest

from sellout.core.leitura import carrega_entradas_erp


def total(caminho):
    """Só a coluna `quant`. O leitor devolve duas janelas — acumulado e
    semana (D18) —, e estes testes são sobre a primeira."""
    return carrega_entradas_erp(caminho)[0]


def escreve(tmp_path, texto):
    caminho = tmp_path / "entradas.csv"
    caminho.write_text(texto, encoding="utf-8-sig")
    return str(caminho)


def test_le_o_formato_do_coletor(tmp_path):
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n"
                          "334066;0036;0036 - OFF-WHITE;24\n"
                          "334066;0308;0308 - VERMELHO;24\n")
    e = total(c)
    assert e["334066"] == {"OFF WHITE": 24, "VERMELHO": 24}


def test_tira_o_codigo_da_frente_da_cor(tmp_path):
    """O ERP manda '0308 - VERMELHO'; as abas de origem trazem só o nome."""
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n239064;0308;0308 - VERMELHO;42\n")
    assert list(total(c)["239064"]) == ["VERMELHO"]


def test_soma_linhas_do_mesmo_produto_e_cor(tmp_path):
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n"
                          "334066;0036;OFF-WHITE;10\n"
                          "334066;0036;OFF-WHITE;14\n")
    assert total(c)["334066"]["OFF WHITE"] == 24


def test_aceita_virgula_como_separador(tmp_path):
    c = escreve(tmp_path, "codigo,codigo_cor,cor,quant\n334066,0036,OFF-WHITE,24\n")
    assert total(c)["334066"]["OFF WHITE"] == 24


def test_quantidade_zero_ou_vazia_nao_entra(tmp_path):
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n"
                          "334066;0036;OFF-WHITE;0\n"
                          "334044;0003;MARINHO;;\n"
                          "334017;0003;MARINHO;5\n")
    e = total(c)
    assert set(e) == {"334017"}


def test_devolucao_liquida_pode_ser_negativa(tmp_path):
    """A loja pode devolver mais do que recebeu no período extraído."""
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n100009;0001;BRANCO;-1\n")
    assert total(c)["100009"]["BRANCO"] == -1


@pytest.mark.parametrize("cabecalho", ["CODIGO;CODIGO_COR;COR;QUANT",
                                       "Codigo; Codigo_cor; Cor; Quantidade"])
def test_cabecalho_tolerante(tmp_path, cabecalho):
    c = escreve(tmp_path, cabecalho + "\n334066;0036;OFF-WHITE;24\n")
    assert total(c)["334066"]["OFF WHITE"] == 24


def test_as_duas_janelas_saem_separadas(tmp_path):
    """`quant` é o acumulado, `quant_semana` é o da rodada (D18).

    São as duas perguntas que o Estoque inicial faz: quanto já chegou deste
    produto (linha nova) e quanto chegou agora (linha que já existe).
    """
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant;quant_semana\n"
                          "334066;0036;0036 - OFF-WHITE;120;12\n")
    acumulado, semana = carrega_entradas_erp(c)
    assert acumulado["334066"]["OFF WHITE"] == 120
    assert semana["334066"]["OFF WHITE"] == 12


def test_csv_antigo_nao_incrementa_nada(tmp_path):
    """**O risco desta mudança é o lançamento em dobro.**

    Um CSV sem `quant_semana` é o formato velho, que traz só o acumulado de
    meses. Se a coluna ausente virasse `quant`, cada rodada somaria o
    acumulado inteiro ao Estoque inicial de quem já tem linha — o denominador
    dobraria sozinho, e o sellout cairia pela metade sem ninguém entender.

    Ausente vale zero: a rodada deixa de incrementar, que é visível, em vez de
    inflar, que não é.
    """
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant\n334066;0036;OFF-WHITE;120\n")
    acumulado, semana = carrega_entradas_erp(c)
    assert acumulado["334066"]["OFF WHITE"] == 120
    assert semana == {}


def test_produto_que_so_chegou_esta_semana(tmp_path):
    """Acumulado e semana iguais: o produto estreou na janela da rodada."""
    c = escreve(tmp_path, "codigo;codigo_cor;cor;quant;quant_semana\n"
                          "334099;0002;PRETO;24;24\n")
    acumulado, semana = carrega_entradas_erp(c)
    assert acumulado["334099"]["PRETO"] == semana["334099"]["PRETO"] == 24


def _fontes(acumulado, semana):
    from sellout.core.leitura import Fontes
    f = Fontes()
    f.entradas_erp, f.entradas_erp_semana = acumulado, semana
    return f


def test_diagnostico_separa_os_tres_estados():
    """Ausente e antigo levam ao mesmo lugar — Estoque inicial congelado —,
    mas exigem ações diferentes: um é gerar o arquivo, o outro é gerar de
    novo com a versão atual do coletor. Confundir os dois manda a pessoa
    procurar no lugar errado."""
    from sellout.core.motor import diagnostico_entradas
    assert diagnostico_entradas(_fontes({}, {}))["estado"] == "ausente"
    assert diagnostico_entradas(_fontes({"334128": {"PRETO": 120}}, {}))["estado"] == "antigo"
    d = diagnostico_entradas(_fontes({"334128": {"PRETO": 120}},
                                     {"334128": {"PRETO": 12}}))
    assert d["estado"] == "ok" and d["pecas_semana"] == 12
