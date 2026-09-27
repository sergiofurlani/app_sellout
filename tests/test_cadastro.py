"""Semeadura das dimensões: coleção do ERP, linha comercial da planilha."""

import pytest

from sellout.db import cadastro, conexao

precisa_banco = pytest.mark.skipif(
    not conexao.disponivel(), reason="sem DATABASE_URL/psycopg")

CABECALHO = ("codigo;interno;colecao;subcolecao;sigla;referencia;descricao;"
             "tipo;grupo;departamento;marca;divisao;categoria;status;grade;"
             "fornecedor;cadastro\n")


def csv_de(tmp_path, *linhas):
    caminho = tmp_path / "produtos-erp.csv"
    caminho.write_text(CABECALHO + "".join(linhas), encoding="utf-8-sig")
    return str(caminho)


def linha(codigo="334128", colecao="VERÃO", sub="2027", sigla="SS27",
          descricao="BLUSA", divisao="FEMININO"):
    return (f"{codigo};1;{colecao};{sub};{sigla};ref;{descricao};"
            f"tipo;grupo;dep;marca;{divisao};cat;ativo;grade;forn;2026-01-01\n")


def test_a_colecao_gravada_e_a_sigla():
    """SS27, não VERÃO/2027. É assim que o negócio fala e é o que os blocos da
    planilha usam; guardar a forma crua obrigaria cada leitor a remontar a
    sigla, e a regra ficaria repetida em cada consulta."""
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        c = csv_de(pathlib.Path(d), linha())
        produtos, _ = cadastro.do_cadastro(c)
    assert produtos[0]["colecao"] == "SS27"


def test_perene_vira_colecao_dos_classicos(tmp_path):
    """PERENE não tem estação e por isso não gera sigla — mas é o universo dos
    Clássicos e precisa de nome no banco (D11)."""
    c = csv_de(tmp_path, linha(colecao="PERENE", sub="", sigla=""))
    produtos, _ = cadastro.do_cadastro(c)
    assert produtos[0]["colecao"] == "PERENE"


def test_colecao_fora_do_mapa_fica_sem_sigla_e_e_reportada(tmp_path):
    """Produto sem agrupamento some de qualquer recorte por coleção. Deixar
    isso calado é o mesmo defeito que travou a comparação em 27/09."""
    c = csv_de(tmp_path, linha(colecao="INDEFINIDO", sub="", sigla=""))
    produtos, motivos = cadastro.do_cadastro(c)
    assert produtos[0]["colecao"] == ""
    assert motivos == {"INDEFINIDO": 1}


def test_o_ano_vem_da_subcolecao(tmp_path):
    c = csv_de(tmp_path, linha(codigo="219054", colecao="INVERNO",
                               sub="2026", sigla="AW26"))
    produtos, _ = cadastro.do_cadastro(c)
    assert produtos[0]["colecao"] == "AW26"


def test_le_os_campos_que_a_tabela_produto_tem(tmp_path):
    c = csv_de(tmp_path, linha())
    (p,), _ = cadastro.do_cadastro(c)
    assert set(p) == {"codigo", "colecao", "descricao", "divisao",
                      "departamento", "grupo", "marca", "grade"}


def test_codigo_vazio_nao_entra(tmp_path):
    c = csv_de(tmp_path, linha(codigo=""), linha())
    produtos, _ = cadastro.do_cadastro(c)
    assert len(produtos) == 1


@precisa_banco
def test_gravar_cadastro_e_idempotente(tmp_path):
    c = csv_de(tmp_path, linha(codigo="999999"))
    produtos, _ = cadastro.do_cadastro(c)
    assert cadastro.grava_cadastro(produtos) == 1
    assert cadastro.grava_cadastro(produtos) == 1
