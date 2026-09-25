"""O coletor do Estoque inicial: janela, sanidade e o caminho inteiro do main.

Este arquivo nasceu de um `NameError` em produção. O rodapé de sanidade lia
`ate` e `de` dentro de `main`, onde os nomes são `args.ate` e `args.de`; a
rodada de 9 meses foi até o fim — minutos de extração — e estourou na hora de
imprimir. Os 81 testes que existiam passavam, porque nenhum deles chamava
`main`. Agora um chama.
"""

from datetime import date, timedelta

import pytest

from coletor import estoque_inicial as ei
from coletor import mn


def test_a_janela_padrao_termina_ontem():
    """Hoje é um dia pela metade: a peça que chega às 17h não estava na rodada
    da manhã, e o mesmo comando devolveria dois Estoques iniciais no mesmo dia."""
    assert ei.ontem() == date.today() - timedelta(days=1)
    assert ei.ontem() < date.today()


def test_o_teto_acompanha_o_tamanho_da_janela():
    """826 peças era a produção de UMA semana, comparada com o líquido de nove
    meses: a rodada certa de 17.000 peças era acusada de errada."""
    de, ate = date(2026, 1, 1), date(2026, 9, 20)
    linha = ei.sanidade(17000, de, ate)[0]
    assert "A PRODUCAO" not in linha
    assert "55% dela" in linha


def test_o_teto_ainda_acusa_o_absurdo():
    """Afrouxar não pode virar desligar: o dobro da produção continua gritando."""
    de, ate = date(2026, 9, 14), date(2026, 9, 20)
    linhas = ei.sanidade(9000, de, ate)
    assert "A PRODUCAO" in linhas[0]
    assert len(linhas) == 3


def test_janela_de_um_dia_nao_divide_por_zero():
    d = date(2026, 9, 20)
    assert ei.sanidade(100, d, d)


def _doc(origem, destino, quant=10, codigo="334128"):
    return {"cod_filial": origem, "cod_cliente": destino,
            "data_emissao": "/Date(1789430400000ms)/".replace("ms", "-0180"),
            "itens": [{"cod_produto": codigo, "cod_cor": "0002",
                       "desc_cor": "0002 - PRETO", "tamanho": "38",
                       "quant": quant, "total": 100.0 * quant}]}


def test_main_vai_ate_o_fim_e_grava(tmp_path, monkeypatch, capsys):
    """O teste que faltava. Roda o caminho inteiro — resumo, rodapé de sanidade
    e CSV —, que é exatamente onde o NameError estava esperando."""
    monkeypatch.setattr(mn, "documentos_do_periodo", lambda de, ate, ev: [
        _doc("ELENA ES", "EGREY JDS", 10),
        _doc("EGREY JDS", "ELENA ES", 4),
    ])
    destino = tmp_path / "entradas.csv"
    codigo = ei.main(["--de", "2026-09-01", "--ate", "2026-09-20",
                      "--para-app", str(destino)])
    assert codigo == 0
    saida = capsys.readouterr().out
    assert "ordem de grandeza" in saida
    linhas = destino.read_text(encoding="utf-8-sig").splitlines()
    assert linhas[1].endswith(";6;6"), "acumulado e semana: tudo caiu na mesma janela"


def test_main_sem_movimento_avisa_em_vez_de_gravar(tmp_path, monkeypatch):
    monkeypatch.setattr(mn, "documentos_do_periodo", lambda de, ate, ev: [])
    destino = tmp_path / "entradas.csv"
    assert ei.main(["--de", "2026-09-01", "--para-app", str(destino)]) == 1
    assert not destino.exists()


def test_o_207_sai_do_estoque_como_qualquer_devolucao(monkeypatch):
    """A decisão do negócio em 21/09: a peça devolvida para a Elena abate o
    Estoque inicial, não a Venda. A direção já classificava loja -> Elena como
    saída, então o 207 não precisou de tratamento próprio — este teste é o que
    garante que continue assim."""
    assert 207 in ei.EVENTOS
    monkeypatch.setattr(mn, "documentos_do_periodo", lambda de, ate, ev: [
        {**_doc("ELENA ES", "EGREY JDS", 10), "_evento": 106},
        {**_doc("EGREY JDS", "ELENA ES", 3), "_evento": 207},
    ])
    saldo = ei.saldo_por_loja(ei.coleta(date(2026, 9, 1), date(2026, 9, 20)))
    assert sum(saldo.values()) == 7


def test_a_janela_da_semana_e_um_recorte_da_extracao():
    """A segunda-feira sai do fim da janela, não de hoje: rodar a extração na
    quarta não pode mudar o que conta como 'esta semana'."""
    assert ei.segunda_da_semana(date(2026, 9, 20)) == date(2026, 9, 14)
    assert ei.segunda_da_semana(date(2026, 9, 14)) == date(2026, 9, 14)


def test_o_acumulado_e_a_semana_sao_numeros_diferentes(tmp_path):
    """Nove meses de transferência e a semana da rodada, no mesmo arquivo.

    Se os dois fossem o mesmo número, somar na linha existente toda semana
    dobraria o Estoque inicial — o defeito que esta separação existe para
    impedir.
    """
    total = {("334128", "0002", "PRETO", "EGREY JDS"): 120.0}
    semana = {("334128", "0002", "PRETO", "EGREY JDS"): 12.0}
    destino = tmp_path / "e.csv"
    assert ei.grava_para_app(str(destino), total, semana) == 1
    linha = destino.read_text(encoding="utf-8-sig").splitlines()[1]
    assert linha.endswith(";120;12")


def test_produto_sem_movimento_na_semana_sai_com_zero(tmp_path):
    """Ele continua no arquivo por causa do acumulado — a linha nova precisa
    dele —, mas não incrementa nada em quem já tem linha."""
    total = {("334128", "0002", "PRETO", "EGREY JDS"): 120.0}
    destino = tmp_path / "e.csv"
    ei.grava_para_app(str(destino), total, {})
    assert destino.read_text(encoding="utf-8-sig").splitlines()[1].endswith(";120;0")
