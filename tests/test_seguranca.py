"""A senha do app: o que passa, o que não passa."""
import base64
import importlib

import pytest
from fastapi.testclient import TestClient


def sobe(monkeypatch, senha=None, usuario=None):
    monkeypatch.delenv("SELLOUT_SENHA", raising=False)
    monkeypatch.delenv("SELLOUT_USUARIO", raising=False)
    if senha:
        monkeypatch.setenv("SELLOUT_SENHA", senha)
    if usuario:
        monkeypatch.setenv("SELLOUT_USUARIO", usuario)
    from sellout.web import main
    importlib.reload(main)
    return TestClient(main.app)


def cab(usuario, senha):
    return {"Authorization": "Basic " + base64.b64encode(f"{usuario}:{senha}".encode()).decode()}


def test_sem_senha_configurada_fica_aberto(monkeypatch):
    assert sobe(monkeypatch).get("/").status_code == 200


def test_com_senha_exige_credencial(monkeypatch):
    r = sobe(monkeypatch, senha="abc").get("/")
    assert r.status_code == 401
    assert "Basic" in r.headers["www-authenticate"]


def test_credencial_certa_entra(monkeypatch):
    c = sobe(monkeypatch, senha="abc")
    assert c.get("/", headers=cab("egrey", "abc")).status_code == 200


def test_senha_errada_nao_entra(monkeypatch):
    c = sobe(monkeypatch, senha="abc")
    assert c.get("/", headers=cab("egrey", "abd")).status_code == 401
    assert c.get("/", headers=cab("outro", "abc")).status_code == 401


def test_usuario_configuravel(monkeypatch):
    c = sobe(monkeypatch, senha="abc", usuario="sergio")
    assert c.get("/", headers=cab("sergio", "abc")).status_code == 200
    assert c.get("/", headers=cab("egrey", "abc")).status_code == 401


def test_saude_fica_livre(monkeypatch):
    """O healthcheck da Railway nao manda credencial — se fechar, o deploy cai."""
    assert sobe(monkeypatch, senha="abc").get("/saude").status_code == 200


def test_cabecalho_malformado_nao_derruba(monkeypatch):
    c = sobe(monkeypatch, senha="abc")
    for ruim in ("", "Basic", "Basic !!!!", "Bearer abc", "Basic " + base64.b64encode(b"semdoispontos").decode()):
        assert c.get("/", headers={"Authorization": ruim}).status_code == 401
