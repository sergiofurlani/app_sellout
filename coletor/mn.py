"""Cliente mínimo da API Millennium (MN). Só biblioteca padrão.

Roda **dentro da rede da Egrey** — o MN não responde a IP de nuvem.

Credenciais em variável de ambiente:

    EGREY_API_URL      http://egray.millenniumhosting.com.br:6017
    EGREY_API_USUARIO  int-egray
    EGREY_API_SENHA    a senha (no PowerShell, entre aspas SIMPLES se tiver #)
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = os.environ.get("EGREY_API_URL", "http://egray.millenniumhosting.com.br:6017")
USUARIO = os.environ.get("EGREY_API_USUARIO", "")
SENHA = os.environ.get("EGREY_API_SENHA", "")

VENDAS = "/api/millenium/movimentacao/vendas_consulta_completa"
FILIAIS = "/api/millenium/filiais/Lista_Filiais_SemFiltro"
CATALOGO = "/api/millenium/eventos/ListaEventosPorTipo"
CATALOGO_ENTRADA = "/api/millenium/eventos/Eventos_InfluenciaEstoque"

# Os eventos que o sellout usa, com os DOIS códigos.
#
# O parâmetro EVENTO da API recebe o INTERNO. O código do ERP é o que aparece
# nas telas e o que as pessoas dizem em voz alta. Os dois colidem: interno 12 é
# devolução de varejo, código "12" é recebimento de transferência. Manter os
# dois lado a lado e conferir um contra o outro é o que impede a troca
# silenciosa — ver conferir_eventos().
#
# interno=None significa "ainda não sabemos, resolver pelo catálogo".
EVENTOS = [
    {"rotulo": "venda",                 "interno": 10,   "codigo": "09",    "sinal": +1},
    {"rotulo": "venda cupom fiscal",    "interno": 30,   "codigo": "00027", "sinal": +1},
    {"rotulo": "venda cupom multiplo",  "interno": 204,  "codigo": "00206", "sinal": +1},
    {"rotulo": "devolucao varejo",      "interno": 12,   "codigo": "11",    "sinal": -1},
    {"rotulo": "venda e-commerce",      "interno": 25,   "codigo": "00003", "sinal": +1},
    {"rotulo": "devolucao e-commerce",  "interno": 23,   "codigo": "00002", "sinal": -1},
    {"rotulo": "troca/cupom e-commerce","interno": 27,   "codigo": "00004", "sinal": -1},
]

EVENTOS_VENDA = (10, 30, 204)
EVENTO_DEVOLUCAO = 12
TOP = 5000
TIMEOUT = 180
TENTATIVAS = 3

RE_DATA_MS = re.compile(r"/Date\((-?\d+)")


class Falha(Exception):
    pass


def _auth() -> str:
    if not USUARIO or not SENHA:
        raise Falha("Defina EGREY_API_USUARIO e EGREY_API_SENHA no ambiente.")
    return "Basic " + base64.b64encode(f"{USUARIO}:{SENHA}".encode()).decode()


def requisita(caminho: str, **params) -> dict:
    """GET com retentativa. 4xx não é retentado — é erro de chamada, não de rede."""
    params.setdefault("$format", "json")
    url = f"{BASE}{caminho}?{urllib.parse.urlencode(params)}"
    ultimo = None
    for tentativa in range(1, TENTATIVAS + 1):
        req = urllib.request.Request(url, headers={"Authorization": _auth()})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                texto = r.read().decode("utf-8", errors="replace")
            return json.loads(texto) if texto.strip() else {}
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", errors="replace")[:400]
            if e.code == 401:
                raise Falha(
                    "401. Antes de achar que a senha está errada: se ela tem '#' e "
                    "você usou aspas duplas no PowerShell, o valor foi cortado. "
                    "Se persistir, testar o header WTS-Authorization."
                ) from e
            if 400 <= e.code < 500:
                raise Falha(f"HTTP {e.code} em {caminho}: {detalhe}") from e
            ultimo = f"HTTP {e.code}: {detalhe}"
        except urllib.error.URLError as e:
            ultimo = f"rede: {e.reason} (está na rede da Egrey?)"
        if tentativa < TENTATIVAS:
            time.sleep(2 * tentativa)
    raise Falha(f"falhou em {TENTATIVAS} tentativas: {ultimo}")


def valores(resposta) -> list:
    if isinstance(resposta, dict):
        return resposta.get("value") or []
    return resposta or []


def parse_data(valor):
    """/Date(1757...000-180)/ → date.

    O offset já foi aplicado pelo MN. Reaplicar joga lançamento para o dia
    anterior, e o erro só aparece como "a venda do sábado caiu na sexta".
    """
    if not valor:
        return None
    m = RE_DATA_MS.search(str(valor))
    return datetime.utcfromtimestamp(int(m.group(1)) / 1000).date() if m else None


def filiais() -> list[dict]:
    """De-para das filiais: cod_filial (texto, do ERP) x filial (inteiro, interno)."""
    return valores(requisita(FILIAIS))


def catalogo_eventos() -> list[dict]:
    """Todos os eventos, com interno (`evento`) e do ERP (`codigo`).

    `ListaEventosPorTipo` traz entrada e saída; se ela recusar sem parâmetro,
    cai para `Eventos_InfluenciaEstoque`, que só tem entrada — melhor pouco
    que nada, e o aviso diz o que ficou de fora.
    """
    try:
        linhas = valores(requisita(CATALOGO))
        if linhas:
            return linhas
    except Falha:
        pass
    return valores(requisita(CATALOGO_ENTRADA))


def conferir_eventos(tabela=None) -> tuple[list[dict], list[str]]:
    """Resolve o interno pelo código e confere os que já vinham preenchidos.

    Devolve (eventos_resolvidos, avisos). Um evento que não resolve fica de
    fora com aviso, em vez de virar chamada com número errado.
    """
    tabela = tabela or EVENTOS
    avisos = []
    try:
        catalogo = catalogo_eventos()
    except Falha as e:
        avisos.append(f"catalogo de eventos indisponivel ({e}); usando so os internos fixos")
        catalogo = []

    por_codigo, por_interno = {}, {}
    for ev in catalogo:
        cod = str(ev.get("codigo") or ev.get("CODIGO") or "").strip()
        interno = ev.get("evento", ev.get("EVENTO"))
        desc = (ev.get("descricao") or ev.get("DESCRICAO") or "").strip()
        if cod:
            por_codigo[cod] = (interno, desc)
        if interno is not None:
            por_interno[interno] = (cod, desc)

    resolvidos = []
    for linha in tabela:
        ev = dict(linha)
        rot, interno, cod = ev["rotulo"], ev["interno"], ev["codigo"]

        if cod and cod in por_codigo:
            do_catalogo, desc = por_codigo[cod]
            if interno is None:
                ev["interno"] = do_catalogo
            elif do_catalogo != interno:
                avisos.append(
                    f"{rot}: codigo {cod} aponta para o evento interno {do_catalogo}, "
                    f"mas a tabela diz {interno}. Nao vou adivinhar — confira antes de usar."
                )
                continue
            ev["descricao"] = desc
        elif cod:
            avisos.append(f"{rot}: codigo {cod} nao esta no catalogo lido")

        if ev["interno"] is None:
            avisos.append(f"{rot}: sem evento interno, ficou de fora da extracao")
            continue
        if "descricao" not in ev and ev["interno"] in por_interno:
            ev["codigo"], ev["descricao"] = por_interno[ev["interno"]]
        resolvidos.append(ev)

    return resolvidos, avisos


def documentos_do_dia(dia: date, eventos=EVENTOS_VENDA + (EVENTO_DEVOLUCAO,)) -> list[dict]:
    """Uma chamada por evento. Sem TIPO — com TIPO=S a devolução some."""
    saida = []
    for evento in eventos:
        dados = requisita(
            VENDAS,
            **{
                "$top": TOP,
                "DATAI": dia.isoformat(),
                "DATAF": dia.isoformat(),
                "EVENTO": evento,
                "BVENDEDORES": "true",
            },
        )
        docs = valores(dados)
        if len(docs) >= TOP:
            raise Falha(f"{dia} evento {evento}: bateu o teto de $top, pode estar truncado")
        for doc in docs:
            doc["_evento"] = evento
        saida.extend(docs)
    return saida


def dias(de: date, ate: date):
    atual = de
    while atual <= ate:
        yield atual
        atual += timedelta(days=1)
