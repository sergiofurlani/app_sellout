"""Senha no app.

O app ficou aberto na internet desde o primeiro deploy: qualquer um com a URL
rodava uma rodada e baixava as planilhas de sellout da empresa. Isto fecha isso.

    SELLOUT_SENHA=...        liga a autenticação
    SELLOUT_USUARIO=egrey    opcional, padrão "egrey"

Autenticação HTTP Basic, que o navegador já sabe pedir — sem tela de login para
manter. Sem `SELLOUT_SENHA` definida o app continua aberto, para o
desenvolvimento local não precisar de senha; nesse caso ele grita no log, uma
vez, para ninguém subir em produção sem perceber.

`/saude` fica de fora: é o healthcheck da Railway, que não manda credencial.
"""

from __future__ import annotations

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

LIVRES = {"/saude"}
PREFIXOS_LIVRES = ("/static/",)

log = logging.getLogger("sellout.seguranca")


def _configurada() -> tuple[str, str] | None:
    senha = os.environ.get("SELLOUT_SENHA", "")
    if not senha:
        return None
    return os.environ.get("SELLOUT_USUARIO", "egrey"), senha


def _confere(cabecalho: str, usuario: str, senha: str) -> bool:
    """Compara em tempo constante — comparar com == vaza a senha pelo relógio."""
    import base64
    import binascii

    tipo, _, valor = cabecalho.partition(" ")
    if tipo.lower() != "basic" or not valor:
        return False
    try:
        cru = base64.b64decode(valor, validate=True).decode("utf-8", "replace")
    except (binascii.Error, ValueError):
        return False
    u, sep, s = cru.partition(":")
    if not sep:
        return False
    # os dois hmac.compare_digest sempre rodam: parar no primeiro erro diria
    # a quem tenta se o usuário existe
    ok_u = hmac.compare_digest(u, usuario)
    ok_s = hmac.compare_digest(s, senha)
    return ok_u and ok_s


class Senha(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        credencial = _configurada()
        if credencial is None:
            return await call_next(request)

        caminho = request.url.path
        if caminho in LIVRES or caminho.startswith(PREFIXOS_LIVRES):
            return await call_next(request)

        cabecalho = request.headers.get("authorization", "")
        if _confere(cabecalho, *credencial):
            return await call_next(request)

        return Response(
            "Acesso restrito.",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Sellout E.GREY", charset="UTF-8"'},
        )


def instalar(app) -> None:
    app.add_middleware(Senha)
    if _configurada() is None:
        log.warning(
            "SELLOUT_SENHA nao definida — o app esta ABERTO. "
            "Em producao, defina a variavel."
        )
