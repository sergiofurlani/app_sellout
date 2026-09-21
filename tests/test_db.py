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


# --------------------------------------------------------------- ingestão

from datetime import date  # noqa: E402

from sellout.db import ingestao  # noqa: E402


class FontesFalsas:
    """O mínimo que a ingestão precisa, sem depender de um .xlsx."""
    produtos = [{"codigo": "239064", "descricao": "CALCA", "colecao": "SS27", "divisao": "F"}]
    linhas = {
        "estoque": [
            {"codigo": "239064", "codigo_cor": "0308", "cor": "VERMELHO",
             "tamanho": "38", "filial": "IGUATEMI", "qtd": 3},
            {"codigo": "239064", "codigo_cor": "0308", "cor": "VERMELHO",
             "tamanho": "38", "filial": "IGUATEMI", "qtd": 2},   # repetida de propósito
            {"codigo": "239064", "codigo_cor": "0308", "cor": "VERMELHO",
             "tamanho": "38", "filial": "EGREY JDS", "qtd": 4},
        ],
        "vendas": [
            {"codigo": "239064", "codigo_cor": "0308", "cor": "VERMELHO",
             "tamanho": "38", "filial": "IGUATEMI", "qtd": 1},
        ],
        # sem codigo_cor: tem que sair do de-para montado pelo estoque
        "producao": [
            {"codigo": "239064", "codigo_cor": "", "cor": "VERMELHO", "tamanho": "38", "qtd": 7},
            {"codigo": "239064", "codigo_cor": "", "cor": "COR QUE NAO EXISTE",
             "tamanho": "40", "qtd": 1},
        ],
        "preco": [
            {"codigo": "239064", "codigo_cor": "0308", "tamanho": "38", "preco": 199.9},
        ],
    }


def test_linha_repetida_e_somada_antes_do_insert():
    """A aba pode trazer a mesma combinação duas vezes; sem somar, bate na chave."""
    linhas = FontesFalsas.linhas["estoque"]
    somado = ingestao._somar(linhas, ("codigo", "codigo_cor", "tamanho", "filial"), ("qtd",))
    por_filial = {l[3]: l[4] for l in somado}
    assert por_filial == {"IGUATEMI": 5, "EGREY JDS": 4}


def test_codigo_de_cor_da_producao_vem_do_de_para():
    resolvidas, contagem = ingestao._resolve(FontesFalsas.linhas)
    codigos = [l["codigo_cor"] for l in resolvidas["producao"]]
    assert codigos == ["0308", ""]
    assert contagem["producao_sem_codigo_cor"] == 1


@precisa_banco
def test_grava_snapshot_completo():
    migracoes.aplicar()
    r = ingestao.gravar(FontesFalsas(), date(2026, 9, 7), quem="teste")
    assert r["estoque"] == 2 and r["vendas"] == 1 and r["preco"] == 1
    assert r["cores"] == 1 and r["filiais"] == 2
    with conexao.conectar() as c, c.cursor() as cur:
        cur.execute("SELECT sum(qtd) FROM estoque WHERE snapshot_id=%s", (r["snapshot"],))
        assert cur.fetchone()[0] == 9
        cur.execute("SELECT nome FROM cor WHERE codigo_cor='0308'")
        assert cur.fetchone()[0] == "VERMELHO"


@precisa_banco
def test_dois_snapshots_nao_se_misturam():
    """O ponto da migração: a semana passada não é sobrescrita pela nova."""
    migracoes.aplicar()
    a = ingestao.gravar(FontesFalsas(), date(2026, 9, 7))
    b = ingestao.gravar(FontesFalsas(), date(2026, 9, 14))
    assert a["snapshot"] != b["snapshot"]
    with conexao.conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(DISTINCT snapshot_id) FROM estoque WHERE snapshot_id IN (%s,%s)",
                    (a["snapshot"], b["snapshot"]))
        assert cur.fetchone()[0] == 2


def test_gravar_se_der_nao_levanta_sem_banco(monkeypatch):
    monkeypatch.setattr(ingestao, "disponivel", lambda: False)
    assert ingestao.gravar_se_der(FontesFalsas(), date(2026, 9, 7)) is None


def test_gravar_se_der_devolve_o_erro_em_vez_de_esconder(monkeypatch):
    monkeypatch.setattr(ingestao, "disponivel", lambda: True)
    def explode(*a, **k):
        raise RuntimeError("banco caiu")
    monkeypatch.setattr(ingestao, "gravar", explode)
    r = ingestao.gravar_se_der(FontesFalsas(), date(2026, 9, 7))
    assert "banco caiu" in r["erro"]
