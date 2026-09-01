"""Normalização e casamento de nomes de cor.

O nome da cor aparece escrito de formas diferentes em cada aba:
"BORDÔ" na descrição, "BORDO" no estoque, "OFF" abreviando "OFF-WHITE",
"AMARELA" onde o cadastro diz "AMARELO". Este módulo reduz tudo a uma
forma comparável e resolve essas variações.
"""

from __future__ import annotations

import re
import unicodedata

# Separadores usados quando o texto em vermelho lista mais de uma cor.
_SEPARADORES = re.compile(r"[,/+;]| E |\be\b")
_NAO_ALFANUM = re.compile(r"[^A-Z0-9 ]")
_ESPACOS = re.compile(r"\s+")

# Palavra-chave que significa "todas as cores que sobraram".
MARCADOR_RESTO = "DEMAIS"


def sem_acento(texto) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )


def nrm(texto) -> str:
    """Forma canônica: sem acento, maiúscula, sem pontuação, espaço simples."""
    if texto is None:
        return ""
    t = _NAO_ALFANUM.sub(" ", sem_acento(texto).upper().strip())
    return _ESPACOS.sub(" ", t).strip()


def tokens(vermelho: str) -> list[str]:
    """Quebra o texto em vermelho na lista de cores que ele cita."""
    if not vermelho:
        return []
    partes = _SEPARADORES.split(sem_acento(vermelho).upper())
    return [nrm(p) for p in partes if nrm(p)]


def match(token: str, cores) -> list[str]:
    """Cores disponíveis que o token representa.

    Tenta, nesta ordem: igualdade, prefixo (OFF -> OFF WHITE),
    continência (VERDE CL -> VERDE CL.) e variação de gênero
    (AMARELA -> AMARELO).
    """
    exato = [c for c in cores if c == token]
    if exato:
        return exato
    prefixo = [c for c in cores if c.startswith(token)]
    if prefixo:
        return prefixo
    contido = [c for c in cores if token in c or c in token]
    if contido:
        return contido
    if len(token) > 3:
        base = token[:-1]
        genero = [c for c in cores if len(c) > 3 and c[:-1] == base]
        if genero:
            return genero
    return []


def eh_resto(vermelho: str) -> bool:
    return MARCADOR_RESTO in nrm(vermelho)
