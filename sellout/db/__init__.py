"""Banco de dados. Só existe na versão nova — ver docs/roteiro.md, Etapa 1."""

from .conexao import conectar, disponivel, url        # noqa: F401
from .migracoes import aplicar, pendentes, versao      # noqa: F401
