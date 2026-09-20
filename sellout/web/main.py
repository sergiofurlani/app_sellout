"""App web da atualização semanal do sellout."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import seguranca
from ..core import motor, relatorio
from ..core.leitura import carrega_fontes
from .. import db
from ..core.leitura import ColunaAusente, abas_faltando

BASE = Path(__file__).parent
TRABALHO = Path(os.environ.get("SELLOUT_WORKDIR", "/tmp/sellout-jobs"))
VALIDADE_HORAS = float(os.environ.get("SELLOUT_TTL_HORAS", "6"))
TAMANHO_MAX_MB = float(os.environ.get("SELLOUT_MAX_MB", "60"))

app = FastAPI(title="Sellout semanal")
seguranca.instalar(app)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

ARQUIVOS = {
    "geral": "sellout geral atualizado.xlsx",
    "classicos": "Sellout Clássicos atualizado.xlsx",
    "relatorio": "relatorio de conferencia.xlsx",
}


def _limpar_antigos():
    if not TRABALHO.exists():
        return
    limite = time.time() - VALIDADE_HORAS * 3600
    for pasta in TRABALHO.iterdir():
        try:
            if pasta.is_dir() and pasta.stat().st_mtime < limite:
                shutil.rmtree(pasta, ignore_errors=True)
        except OSError:
            pass


def _pasta(job: str) -> Path:
    if not job or "/" in job or ".." in job:
        raise HTTPException(400, "Identificador inválido.")
    pasta = TRABALHO / job
    if not pasta.is_dir():
        raise HTTPException(404, "Esta sessão expirou. Envie as planilhas novamente.")
    return pasta


async def _gravar(arquivo: UploadFile, destino: Path):
    limite = TAMANHO_MAX_MB * 1024 * 1024
    total = 0
    with destino.open("wb") as saida:
        while pedaco := await arquivo.read(1024 * 1024):
            total += len(pedaco)
            if total > limite:
                raise HTTPException(413, "Arquivo maior que %d MB." % TAMANHO_MAX_MB)
            saida.write(pedaco)


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    _limpar_antigos()
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/saude")
def saude():
    return {"ok": True}


@app.post("/analisar", response_class=HTMLResponse)
async def analisar(request: Request, geral: UploadFile, classicos: UploadFile,
                   entradas_erp: UploadFile | None = None):
    _limpar_antigos()
    job = uuid.uuid4().hex
    pasta = TRABALHO / job
    pasta.mkdir(parents=True, exist_ok=True)

    caminho_geral = pasta / "geral.xlsx"
    caminho_clas = pasta / "classicos.xlsx"
    await _gravar(geral, caminho_geral)
    await _gravar(classicos, caminho_clas)

    # Opcional: o CSV que o coletor gera com as transferências da ELENA ES.
    # O MN só responde dentro da rede da Egrey, então este arquivo é a única
    # ponte — sem ele a rodada segue pela regra antiga (D6).
    caminho_erp = None
    if entradas_erp is not None and entradas_erp.filename:
        caminho_erp = pasta / "entradas-erp.csv"
        await _gravar(entradas_erp, caminho_erp)

    faltando = abas_faltando(caminho_geral)
    if faltando:
        return templates.TemplateResponse(
            request, "index.html",
            {"erro": "A planilha geral está sem as abas: %s." % ", ".join(faltando)},
            status_code=400)

    try:
        analise = motor.analisar(str(caminho_geral), str(caminho_clas),
                                 entradas_erp=str(caminho_erp) if caminho_erp else None)
    except ColunaAusente as e:
        return templates.TemplateResponse(
            request, "index.html", {"erro": str(e)}, status_code=400)
    except KeyError as e:
        return templates.TemplateResponse(
            request, "index.html",
            {"erro": "Não encontrei a aba %s. Confira se os arquivos foram trocados de lugar." % e},
            status_code=400)
    except Exception as e:  # o erro precisa chegar na tela, não só no log
        logging.exception("falha ao analisar as planilhas")
        return templates.TemplateResponse(
            request, "index.html",
            {"erro": "Não consegui ler as planilhas: %s: %s" % (type(e).__name__, e)},
            status_code=400)

    (pasta / "analise.json").write_text(json.dumps(analise, ensure_ascii=False, default=str))
    return templates.TemplateResponse(request, "revisao.html", {
        "job": job, "a": analise,
        "nomes": {"geral": geral.filename, "classicos": classicos.filename},
    })


@app.post("/processar", response_class=HTMLResponse)
async def processar(request: Request, job: str = Form(...), data_sellout: str = Form(...),
                    producao_exige_estoque: str = Form("nao")):
    pasta = _pasta(job)
    form = await request.form()

    decisoes = {
        "data_sellout": data_sellout.strip() or motor.rotulo_sellout(),
        "filiais_estoque": form.getlist("filial"),
        "producao_exige_estoque": producao_exige_estoque == "sim",
        "novos": form.getlist("novo"),
        "duplicados": {
            k[len("dup:"):]: v for k, v in form.items()
            if k.startswith("dup:") and v
        },
        "colunas": {
            k[len("col:"):]: v for k, v in form.items()
            if k.startswith("col:") and v
        },
    }
    (pasta / "decisoes.json").write_text(json.dumps(decisoes, ensure_ascii=False))

    try:
        rel = motor.processar(
            str(pasta / "geral.xlsx"), str(pasta / "classicos.xlsx"),
            str(pasta / ARQUIVOS["geral"]), str(pasta / ARQUIVOS["classicos"]),
            decisoes,
            entradas_erp=str(pasta / "entradas-erp.csv")
            if (pasta / "entradas-erp.csv").exists() else None,
        )
    except Exception as e:
        logging.exception("falha ao processar a rodada")
        return templates.TemplateResponse(
            request, "index.html",
            {"erro": "Falhou ao gerar as planilhas: %s: %s" % (type(e).__name__, e)},
            status_code=500)
    relatorio.gerar(rel, str(pasta / ARQUIVOS["relatorio"]))
    (pasta / "relatorio.json").write_text(json.dumps(rel, ensure_ascii=False, default=str))

    # Gravação no banco, em paralelo. A planilha já está pronta a esta altura:
    # nada aqui pode impedi-la de ser baixada. Por isso vem DEPOIS, e por isso
    # gravar_se_der engole o erro em vez de propagar.
    banco = None
    if db.disponivel():
        try:
            fontes = carrega_fontes(
                str(pasta / "geral.xlsx"),
                filiais_estoque=decisoes.get("filiais") or None,
                colunas_forcadas=decisoes.get("colunas") or None,
            )
            banco = db.gravar_se_der(
                fontes, date.today(), origem="upload",
                observacao=decisoes.get("data_sellout"))
        except Exception as e:                     # noqa: BLE001
            logging.exception("falha ao gravar o snapshot")
            banco = {"erro": "%s: %s" % (type(e).__name__, e)}
        if banco and banco.get("erro"):
            logging.error("snapshot nao gravado: %s", banco["erro"])

    return templates.TemplateResponse(request, "resultado.html", {
        "job": job, "rel": rel, "decisoes": decisoes, "banco": banco,
    })


@app.get("/baixar/{job}/{qual}")
def baixar(job: str, qual: str):
    pasta = _pasta(job)
    if qual not in ARQUIVOS:
        raise HTTPException(404, "Arquivo desconhecido.")
    caminho = pasta / ARQUIVOS[qual]
    if not caminho.exists():
        raise HTTPException(404, "Arquivo ainda não foi gerado.")
    return FileResponse(
        caminho, filename=ARQUIVOS[qual],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
