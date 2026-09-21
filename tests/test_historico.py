"""A carga do histórico das colunas de sellout."""
import datetime

import pytest

from sellout.db import historico


class Celula:
    def __init__(self, value): self.value = value


class AbaFalsa:
    """Só o suficiente para colunas_de_data: a linha 3 com as datas."""
    def __init__(self, datas):
        self.datas = datas
        self.max_column = len(datas)

    def cell(self, linha, coluna):
        assert linha == 3
        return Celula(self.datas[coluna - 1])


def d(texto):
    return datetime.date.fromisoformat(texto)


def test_le_as_datas_em_ordem():
    aba = AbaFalsa([d("2026-08-23"), d("2026-08-17"), d("2026-08-09")])
    colunas, avisos = historico.colunas_de_data(aba)
    assert [x[1] for x in colunas] == [d("2026-08-23"), d("2026-08-17"), d("2026-08-09")]
    assert avisos == []


def test_ignora_cabecalho_que_nao_e_data():
    """A coluna atual tem rótulo de texto e as antigas perderam o cabeçalho."""
    aba = AbaFalsa(["Sellout 31/08", d("2026-08-23"), None, d("2026-08-17")])
    colunas, _ = historico.colunas_de_data(aba)
    assert [c for c, _ in colunas] == [2, 4]


def test_corrige_o_ano_digitado_errado():
    """Em janeiro, alguém digita o ano novo numa coluna de dezembro."""
    aba = AbaFalsa([d("2026-01-11"), d("2026-01-04"), d("2026-12-15"), d("2025-12-07")])
    colunas, avisos = historico.colunas_de_data(aba)
    assert [x[1] for x in colunas][2] == d("2025-12-15")
    assert len(colunas) == 4
    assert "corrigida para 2025-12-15" in avisos[0]


def test_data_sem_conserto_e_descartada():
    """Tirar um ano tem que fechar a ordem; se não fecha, a semana sai."""
    aba = AbaFalsa([d("2026-08-23"), d("2030-01-01"), d("2026-08-09")])
    colunas, avisos = historico.colunas_de_data(aba)
    assert len(colunas) == 2
    assert "descartada" in avisos[0]


def test_uma_data_so_sempre_passa():
    colunas, avisos = historico.colunas_de_data(AbaFalsa([d("2026-08-23")]))
    assert len(colunas) == 1 and avisos == []


@pytest.mark.parametrize("bruto, esperado", [
    (0.2063, 0.2063),
    (1, 1),
    ("-", None),
    ("", None),
    ("#DIV/0!", None),
    (None, None),
    ("0,35", 0.35),
    (20.63, 0.2063),        # digitado como percentual inteiro
    ("texto", None),
])
def test_percentual(bruto, esperado):
    achado = historico.percentual(bruto)
    if esperado is None:
        assert achado is None
    else:
        assert achado == pytest.approx(esperado)


def test_zero_e_um_valor_de_verdade():
    """Produto que não vendeu tem sellout 0 — diferente de não ter dado."""
    assert historico.percentual(0) == 0
    assert historico.percentual(0) is not None
