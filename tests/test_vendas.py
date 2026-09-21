"""A venda da semana, extraída do ERP."""

from datetime import date, timedelta

import pytest

from coletor import mn, vendas


def docs(monkeypatch, lista):
    """O campo é `_evento`, com underscore: é o carimbo que
    `documentos_do_periodo` põe em cada documento, porque o payload do MN não
    diz de qual evento ele veio. Estes testes usavam `evento` e por isso
    passavam sem provar nada — o código real lia None e tratava tudo como
    venda."""
    lista = [{**d, "_evento": d.pop("evento")} if "evento" in d else d
             for d in lista]
    monkeypatch.setattr(mn, "documentos_do_periodo", lambda de, ate, ev: lista)


def item(**kw):
    base = {"cod_produto": "334128", "cod_cor": "0002", "desc_cor": "PRETO",
            "tamanho": "38", "quant": 1, "total": 699.0}
    base.update(kw)
    return base


def test_devolucao_desconta_da_venda(monkeypatch):
    """A planilha soma venda líquida. Separar aqui para somar depois seria
    trabalho a mais e uma chance a mais de errar o sinal."""
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "IGUATEMI", "itens": [item(quant=3, total=2097.0)]},
        {"evento": 12, "cod_filial": "IGUATEMI", "itens": [item(quant=1)]},
    ])
    saldo, r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    assert r["por_filial"]["IGUATEMI"] == 2
    (chave, valores), = saldo.items()
    assert valores["qtd"] == 2 and valores["valor"] == pytest.approx(1398.0)


def test_ecommerce_vira_site(monkeypatch):
    """O site fatura pelo evento 00003 e a filial tem outro nome. Em 19/09 ele
    sumiu inteiro da extração porque o evento estava fora da lista."""
    docs(monkeypatch, [
        {"evento": 25, "cod_filial": "E. GREY", "itens": [item(quant=2)]},
    ])
    saldo, r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    assert r["por_filial"] == {"SITE": 2}
    assert list(saldo)[0][-1] == "SITE"


def test_atacado_fica_de_fora_mas_aparece_no_resumo(monkeypatch):
    """Silêncio aqui viraria venda de varejo inflada. Sai da conta e aparece
    no relatório, que é diferente de sumir."""
    docs(monkeypatch, [
        {"evento": 108, "cod_filial": "ELENA ES", "itens": [item(quant=50)]},
        {"evento": 30, "cod_filial": "IGUATEMI", "itens": [item(quant=1)]},
    ])
    saldo, r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    assert r["fora"] == {"ELENA ES": 50}
    assert sum(v["qtd"] for v in saldo.values()) == 1


def test_a_chave_separa_cor_e_tamanho(monkeypatch):
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "IGUATEMI",
         "itens": [item(tamanho="38"), item(tamanho="40"),
                   item(cod_cor="0008", desc_cor="AZUL", tamanho="38")]},
    ])
    saldo, _r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    assert len(saldo) == 3


def test_linha_zerada_nao_vai_para_o_csv(tmp_path, monkeypatch):
    """Vendeu uma e devolveu uma: o líquido é zero e a linha não existe."""
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "IGUATEMI", "itens": [item(quant=1)]},
        {"evento": 12, "cod_filial": "IGUATEMI", "itens": [item(quant=1)]},
    ])
    saldo, _r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    assert vendas.grava(saldo, str(tmp_path / "v.csv")) == 0


def test_a_semana_padrao_e_segunda_a_domingo_anterior():
    de, ate = vendas.semana_passada()
    assert de.weekday() == 0 and ate.weekday() == 6
    assert ate - de == timedelta(days=6)
    assert ate < date.today()


def test_o_csv_sai_no_formato_da_aba_vendas(tmp_path, monkeypatch):
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "IGUATEMI", "itens": [item(quant=2, total=1398.0)]},
    ])
    saldo, _r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    destino = tmp_path / "v.csv"
    vendas.grava(saldo, str(destino))
    linhas = destino.read_text(encoding="utf-8-sig").splitlines()
    assert linhas[0].split(";") == ["FILIAL", "CODIGO", "DESCRICAO", "CODIGO COR",
                                    "COR", "TAMANHO", "QTDE", "VALOR"]
    assert linhas[1].startswith("IGUATEMI;334128;;0002;PRETO;38;2;")


def test_devolucao_com_quantidade_negativa_ainda_subtrai(monkeypatch):
    """O ERP manda a devolução como -1. O laço pulava item com quantidade
    <= 0, e com isso a devolução sumia: 398 peças contra 334 do ERP na
    semana de 14 a 20/09, sempre para mais. O sinal é do evento."""
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "IGUATEMI", "itens": [item(quant=3, total=2097.0)]},
        {"evento": 12, "cod_filial": "IGUATEMI", "itens": [item(quant=-1, total=-699.0)]},
    ])
    saldo, r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    (_chave, v), = saldo.items()
    assert v["qtd"] == 2, "3 vendidas menos 1 devolvida"
    assert v["valor"] == pytest.approx(1398.0)
    assert r["itens_negativos"] == {"devolucao varejo": 1}


def test_estorno_dentro_de_evento_de_venda_subtrai(monkeypatch):
    """Quantidade negativa num evento de VENDA é estorno, e subtrai. Tratar
    como venda — que era o efeito do `abs` — deixou seis chaves da Jardins
    com o sinal trocado contra o export do ERP."""
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "EGREY JDS", "itens": [item(quant=3, total=2097.0)]},
        {"evento": 30, "cod_filial": "EGREY JDS", "itens": [item(quant=-1, total=-699.0)]},
    ])
    saldo, _r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    (_chave, v), = saldo.items()
    assert v["qtd"] == 2 and v["valor"] == pytest.approx(1398.0)


def test_devolucao_positiva_da_o_mesmo_resultado(monkeypatch):
    """Devolução lançada como +1 num evento de devolução também subtrai."""
    docs(monkeypatch, [
        {"evento": 30, "cod_filial": "IGUATEMI", "itens": [item(quant=3, total=2097.0)]},
        {"evento": 12, "cod_filial": "IGUATEMI", "itens": [item(quant=1, total=699.0)]},
    ])
    saldo, _r = vendas.coleta(date(2026, 9, 15), date(2026, 9, 21))
    (_chave, v), = saldo.items()
    assert v["qtd"] == 2 and v["valor"] == pytest.approx(1398.0)
