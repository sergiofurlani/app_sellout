"""Migrações e conexão.

Os testes que precisam de banco rodam só quando DATABASE_URL existe — assim a
suíte continua verde na máquina de quem não tem Postgres, e roda de verdade no
CI e na Railway.
"""
import pathlib

import pytest

from sellout.db import conexao, migracoes

precisa_banco = pytest.mark.skipif(
    not conexao.disponivel(), reason="sem DATABASE_URL/psycopg")


def test_sem_url_o_app_nao_quebra(monkeypatch):
    for v in conexao.VARIAVEIS:
        monkeypatch.delenv(v, raising=False)
    assert conexao.url() is None
    assert conexao.disponivel() is False
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with conexao.conectar():
            pass


def test_nomes_das_migracoes_seguem_o_padrao():
    achados = migracoes.arquivos()
    assert achados, "nenhuma migracao encontrada"
    numeros = [n for n, _, _ in achados]
    assert numeros == sorted(numeros)
    assert len(set(numeros)) == len(numeros)


def test_arquivo_fora_do_padrao_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(migracoes, "PASTA", tmp_path)
    (tmp_path / "estrutura.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="fora do padrao"):
        migracoes.arquivos()


def test_numero_repetido_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(migracoes, "PASTA", tmp_path)
    (tmp_path / "001_uma.sql").write_text("SELECT 1;")
    (tmp_path / "001_outra.sql").write_text("SELECT 2;")
    with pytest.raises(ValueError, match="repetidos"):
        migracoes.arquivos()


@precisa_banco
def test_aplica_uma_vez_so():
    migracoes.aplicar()
    assert migracoes.aplicar() == []
    assert {m["nome"] for m in migracoes.versao()} >= {"estrutura"}


@precisa_banco
def test_migracao_editada_depois_de_aplicada_vira_aviso(monkeypatch):
    migracoes.aplicar()
    original = migracoes._checksum
    monkeypatch.setattr(migracoes, "_checksum", lambda t: original(t + "mexido"))
    _, avisos = migracoes.pendentes()
    assert any("nao se edita" in a for a in avisos)


@precisa_banco
def test_estrutura_tem_as_tabelas_do_modelo():
    esperadas = {"produto", "cor", "produto_cor", "filial", "snapshot",
                 "estoque", "venda", "producao", "preco",
                 "saldo_abertura", "movimento"}
    migracoes.aplicar()
    with conexao.conectar() as c, c.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public'")
        assert esperadas <= {r[0] for r in cur.fetchall()}


@precisa_banco
def test_movimento_do_erp_nao_entra_duas_vezes():
    import psycopg
    migracoes.aplicar()
    linha = ("2026-09-02", "334066", "1530", "40", "IGUATEMI",
             "transferencia", 3, 106, "teste-dup")
    sql = ("INSERT INTO movimento (data,codigo,codigo_cor,tamanho,filial,"
           "tipo,qtd,evento_mn,documento) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)")
    with conexao.conectar() as c, c.cursor() as cur:
        cur.execute("DELETE FROM movimento WHERE documento = 'teste-dup'")
        cur.execute(sql, linha)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conexao.conectar() as c, c.cursor() as cur:
            cur.execute(sql, linha)


@precisa_banco
def test_tipo_de_movimento_invalido_e_recusado():
    import psycopg
    migracoes.aplicar()
    with pytest.raises(psycopg.errors.CheckViolation):
        with conexao.conectar() as c, c.cursor() as cur:
            cur.execute("INSERT INTO movimento (data,codigo,codigo_cor,tipo,qtd) "
                        "VALUES ('2026-09-02','1','1','sei_la',1)")
