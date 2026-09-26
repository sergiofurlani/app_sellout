"""Consignação: remessa que não voltou.

A regra, como o negócio explicou em 26/09: remessa (evento 14) tira a peça da
loja, acerto (19) devolve, e **acerto não é venda** — se a cliente ficou com a
peça, sai uma venda normal, que o `coletor.vendas` já trata. O que interessa
aqui é só a diferença.
"""

from datetime import date

import pytest

from coletor import consignacao, mn


def docs(monkeypatch, lista):
    monkeypatch.setattr(mn, "documentos_do_periodo", lambda de, ate, ev: lista)


def doc(evento, loja="IGUATEMI", quant=1, codigo="334128", cor="0002",
        data="/Date(1789430400000-0180)/"):
    return {"_evento": evento, "cod_filial": loja, "data_emissao": data,
            "itens": [{"cod_produto": codigo, "cod_cor": cor,
                       "desc_cor": "0002 - PRETO", "tamanho": "38",
                       "quant": quant, "total": 100.0 * quant}]}


JANELA = (date(2025, 1, 1), date(2026, 9, 20))


def test_remessa_sem_acerto_fica_em_aberto(monkeypatch):
    docs(monkeypatch, [doc(14, quant=3)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert sum(saldo.values()) == 3


def test_remessa_com_acerto_nao_sobra_nada(monkeypatch):
    """Toda remessa volta como acerto. A peça que voltou não está em lugar
    nenhum a não ser na loja, e o Estoque atual já a enxerga."""
    docs(monkeypatch, [doc(14, quant=3), doc(19, quant=3)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert sum(saldo.values()) == 0


def test_o_saldo_zerado_nao_vai_para_o_csv(tmp_path, monkeypatch):
    docs(monkeypatch, [doc(14, quant=3), doc(19, quant=3)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert consignacao.grava(str(tmp_path / "c.csv"), saldo) == 0


def test_acerto_parcial_deixa_o_resto_fora(monkeypatch):
    """Saiu 3, voltou 1: duas continuam com a cliente."""
    docs(monkeypatch, [doc(14, quant=3), doc(19, quant=1)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert sum(saldo.values()) == 2


def test_quantidade_negativa_no_acerto_nao_dobra_o_sinal(monkeypatch):
    """O ERP pode mandar o acerto como -1. O sinal é do evento, não da
    quantidade — dobrar os dois transformaria devolução em saída, que foi
    exatamente o defeito de 398 contra 334 peças no coletor de vendas."""
    docs(monkeypatch, [doc(14, quant=3), doc(19, quant=-1)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert sum(saldo.values()) == 2


def test_a_cor_separa_as_linhas(monkeypatch):
    docs(monkeypatch, [doc(14, cor="0002"), doc(14, cor="0008")])
    saldo, _r = consignacao.coleta(*JANELA)
    assert len(consignacao.consolida(saldo)) == 2


def test_as_lojas_somam_na_linha_do_produto(monkeypatch):
    """A planilha tem uma linha por produto, não por loja."""
    docs(monkeypatch, [doc(14, loja="IGUATEMI", quant=2),
                       doc(14, loja="EGREY JDS", quant=3)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert len(saldo) == 2, "no detalhe, uma chave por loja"
    (_chave, q), = consignacao.consolida(saldo).items()
    assert q == 5, "no CSV do app, somadas"


def test_consignacao_fora_das_lojas_nao_entra(monkeypatch):
    """A Elena também consigna, e isso não é sellout de varejo."""
    docs(monkeypatch, [doc(14, loja="ELENA ES", quant=50),
                       doc(14, loja="IGUATEMI", quant=2)])
    saldo, r = consignacao.coleta(*JANELA)
    assert sum(saldo.values()) == 2
    assert r["fora_de_loja"] == {"ELENA ES": 50}


def test_venda_nao_entra_aqui(monkeypatch):
    """**Acerto não é venda, e venda não é consignação.** Se um evento de
    venda entrasse nesta conta, a peça vendida apareceria como estando na mão
    da cliente — e o Estoque atual já a tirou da loja. Contaria duas vezes."""
    docs(monkeypatch, [doc(30, quant=9), doc(14, quant=2)])
    saldo, _r = consignacao.coleta(*JANELA)
    assert sum(saldo.values()) == 2


def test_saldo_negativo_entra_no_csv(tmp_path, monkeypatch):
    """Acerto sem remessa: a remessa é anterior à janela. Esconder a linha
    devolveria o total ao mundo dos números que fecham por construção — que é
    justamente o defeito da coluna Consignado de hoje."""
    docs(monkeypatch, [doc(19, quant=2)])
    saldo, _r = consignacao.coleta(*JANELA)
    destino = tmp_path / "c.csv"
    assert consignacao.grava(str(destino), saldo) == 1
    assert destino.read_text(encoding="utf-8-sig").splitlines()[1].endswith(";-2")


def test_o_csv_sai_no_formato_que_o_app_le(tmp_path, monkeypatch):
    docs(monkeypatch, [doc(14, quant=4)])
    saldo, _r = consignacao.coleta(*JANELA)
    destino = tmp_path / "c.csv"
    consignacao.grava(str(destino), saldo)
    linhas = destino.read_text(encoding="utf-8-sig").splitlines()
    assert linhas[0].split(";") == ["codigo", "codigo_cor", "cor", "quant"]
    assert linhas[1] == "334128;0002;0002 - PRETO;4"


def test_main_vai_ate_o_fim(tmp_path, monkeypatch, capsys):
    docs(monkeypatch, [doc(14, quant=3), doc(19, quant=1)])
    destino = tmp_path / "c.csv"
    assert consignacao.main(["--de", "2025-01-01", "--ate", "2026-09-20",
                             "--para-app", str(destino)]) == 0
    saida = capsys.readouterr().out
    assert "em aberto: 2" in saida
    assert destino.exists()


def test_main_sem_movimento_avisa(tmp_path, monkeypatch):
    docs(monkeypatch, [])
    destino = tmp_path / "c.csv"
    assert consignacao.main(["--de", "2025-01-01", "--para-app", str(destino)]) == 1
    assert not destino.exists()


# ---------------------------------------------------------------- no app

def escreve_csv(tmp_path, texto):
    caminho = tmp_path / "consignado.csv"
    caminho.write_text(texto, encoding="utf-8-sig")
    return str(caminho)


def test_o_app_le_o_csv_do_coletor(tmp_path):
    from sellout.core.leitura import carrega_consignado
    c = escreve_csv(tmp_path, "codigo;codigo_cor;cor;quant\n"
                              "334066;0036;0036 - OFF-WHITE;12\n")
    assert carrega_consignado(c)["334066"]["OFF WHITE"] == 12


def test_o_app_aceita_consignado_negativo(tmp_path):
    """Acerto sem remessa na janela. Descartar esconderia o sintoma e
    devolveria o total ao mundo dos números que fecham por construção — o
    defeito que a coluna tinha."""
    from sellout.core.leitura import carrega_consignado
    c = escreve_csv(tmp_path, "codigo;codigo_cor;cor;quant\n100009;0001;BRANCO;-2\n")
    assert carrega_consignado(c)["100009"]["BRANCO"] == -2


def test_sem_o_arquivo_nada_muda(tmp_path):
    """A coluna Consignado continua sendo a fórmula de sempre. Rodada sem o
    CSV não pode ficar pior do que era antes de a consignação existir."""
    from sellout.core.leitura import Fontes
    assert Fontes().consignado == {}
