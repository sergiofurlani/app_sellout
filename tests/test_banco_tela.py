"""A tela do banco responde mesmo com o banco fora do ar.

Ela existe para o momento em que alguma coisa está errada — se depender da
conexão para abrir, não serve justamente quando é necessária.

Aqui as rotas rodam de verdade, com TestClient. As migrações **não** rodam no
deploy de propósito: uma que falhe no pre-deploy derruba o app inteiro, e aí
se perde a mudança de esquema e o serviço no ar de uma vez. Rodam quando
alguém manda, olhando a lista do que vai rodar.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.delenv("SELLOUT_SENHA", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SELLOUT_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    from sellout.web import main
    importlib.reload(main)
    return TestClient(main.app)


def test_a_tela_abre_sem_banco(cliente):
    r = cliente.get("/banco")
    assert r.status_code == 200
    assert "Sem conexão com o banco" in r.text
    assert "DATABASE_URL" in r.text


def test_sem_banco_nao_oferece_o_botao(cliente):
    """Botão que só pode dar erro é pior que botão nenhum."""
    assert "/banco/migrar" not in cliente.get("/banco").text


def test_migrar_sem_banco_responde_em_vez_de_estourar(cliente):
    """Alguém chega em /banco/migrar com o banco fora: tem que sair uma tela
    explicando, não um 500 sem texto."""
    r = cliente.post("/banco/migrar")
    assert r.status_code == 500
    assert "DATABASE_URL" in r.text or "banco" in r.text.lower()


def test_a_rodada_por_planilha_nao_depende_do_banco(cliente):
    """O app inteiro continua de pé sem banco — é a regra desde o começo."""
    assert cliente.get("/").status_code == 200
    assert cliente.get("/saude").json() == {"ok": True}


def test_o_inicio_leva_para_a_tela_do_banco(cliente):
    assert "/banco" in cliente.get("/").text
