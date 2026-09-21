"""Conexão com o Postgres.

`DATABASE_URL` é o que a Railway injeta quando o serviço é ligado ao Postgres.
Sem ela, `disponivel()` devolve False e o app segue rodando **como antes**, só
por planilha. Isso é de propósito: a versão nova tem que conseguir subir com o
banco fora do ar em vez de virar tela de erro.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

VARIAVEIS = ("DATABASE_URL", "SELLOUT_DATABASE_URL", "POSTGRES_URL")


def url() -> str | None:
    for nome in VARIAVEIS:
        valor = os.environ.get(nome)
        if valor:
            return valor
    return None


def disponivel() -> bool:
    return por_que_nao() is None


def por_que_nao() -> str | None:
    """None quando dá para conectar; senão, a razão em uma frase.

    As duas causas são diferentes e exigem ações diferentes — sem separá-las,
    faltar o psycopg aparecia como "DATABASE_URL não definida", que manda a
    pessoa procurar no lugar errado.
    """
    if url() is None:
        return ("DATABASE_URL nao definida no ambiente (as alternativas aceitas "
                "sao " + ", ".join(VARIAVEIS[1:]) + ")")
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return ("psycopg nao instalado — rode: pip install -r requirements.txt")
    return None


@contextmanager
def conectar(autocommit: bool = False):
    """Abre e fecha a conexão. Erro no meio faz rollback, nunca commit parcial."""
    import psycopg

    endereco = url()
    if endereco is None:
        raise RuntimeError(
            "DATABASE_URL nao definida. Ligue o servico ao Postgres na Railway, "
            "ou rode a versao por planilha (branch main)."
        )
    conexao = psycopg.connect(endereco, autocommit=autocommit)
    try:
        yield conexao
        if not autocommit:
            conexao.commit()
    except Exception:
        if not autocommit:
            conexao.rollback()
        raise
    finally:
        conexao.close()
