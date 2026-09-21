"""Congela o saldo de abertura — o que existia antes de o ERP passar a contar.

    python -m sellout.db.abertura "sellout geral.xlsx" --cadastro produtos-erp.csv
    python -m sellout.db.abertura "sellout geral.xlsx" --cadastro produtos-erp.csv --aplicar

A D10 dizia congelar o Estoque inicial inteiro numa data-base. **Decidido em
21/09: congelar menos do que isso.**

A coluna Estoque inicial da planilha é por *linha de produto*; o banco trabalha
por produto **e cor**. Repartir o número da linha entre as cores seria
estimativa nossa virando número guardado — o tipo de coisa que ninguém
consegue desfazer seis meses depois.

Então o corte é por data, não por rateio:

  **AW26 e SS27 não são congeladas.** São reconstruídas pelos movimentos do
  evento 106 desde 01/01/2026, que têm cor e tamanho de verdade. A conferência
  de 21/09 sustenta: AW26 bate em 97% das linhas dentro de ±10 peças, e no SS27
  quando planilha e ERP discordam quem costuma estar certo é o ERP — a planilha
  guardou produção, não chegada (D14).

  **O resto é congelado por produto, sem cor** (`codigo_cor` vazio). São
  coleções antigas em liquidação: o número total ainda importa para o
  percentual, a divisão por cor já não decide nada, e inventá-la não ajudaria
  ninguém.

Quem quiser conferir depois sabe de onde veio cada número: a coluna `origem`
diz `planilha`, e o que não está na tabela é porque veio do ERP.

Nada é gravado sem `--aplicar`.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
from collections import Counter
from datetime import date

import openpyxl

from ..core.leitura import ABAS_TRABALHO, blocos_de, linhas_de_produto, mapa_colunas, texto
from .conexao import conectar, por_que_nao

# Coleções reconstruídas pelo ERP em vez de congeladas.
RECONSTRUIDAS = ("AW26", "SS27")
DATA_BASE = date(2026, 1, 1)


def dia(t: str) -> date:
    return date.fromisoformat(t)


def le_siglas(caminho) -> dict[str, str]:
    """codigo -> sigla, do CSV do cadastro do ERP (coletor.produtos)."""
    if not caminho:
        return {}
    mapa = {}
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            cod = (linha.get("codigo") or "").strip()
            sg = (linha.get("sigla") or "").strip().upper()
            if cod and sg:
                mapa[cod] = sg
    return mapa


def ler(caminho: str, siglas=None, reconstruidas=RECONSTRUIDAS):
    """-> (linhas a congelar, resumo, avisos).

    A coleção vem do bloco da planilha; o cadastro do ERP só entra como
    desempate quando o código aparece em mais de um bloco — que é exatamente o
    caso em que a planilha não sabe responder sozinha (D11).
    """
    siglas = siglas or {}
    reconstruidas = {c.upper() for c in reconstruidas}
    wb = openpyxl.load_workbook(caminho, data_only=True)

    # Primeiro passo: onde cada código aparece. Código em dois blocos não pode
    # ser somado como se fosse um só.
    ocorrencias: dict[str, list] = {}
    for aba in ABAS_TRABALHO:
        if aba not in wb.sheetnames:
            continue
        ws = wb[aba]
        coluna = mapa_colunas(ws).get("J")
        if not coluna:
            continue
        for bloco in blocos_de(ws):
            colecao = (bloco.get("colecao") or "").upper()
            for linha, codigo, _b in linhas_de_produto(ws, [bloco]):
                if not codigo:
                    continue
                valor = ws.cell(linha, coluna).value
                if not isinstance(valor, (int, float)):
                    continue
                ocorrencias.setdefault(codigo, []).append(
                    {"aba": aba, "linha": linha, "colecao": colecao,
                     "descricao": texto(ws.cell(linha, 3).value), "qtd": float(valor)})

    saida, avisos = [], []
    resumo = Counter()
    for codigo, lista in sorted(ocorrencias.items()):
        colecoes = {o["colecao"] for o in lista}
        # Reconstruída: some do saldo de abertura. Se o código está em dois
        # blocos e um deles é reconstruído, congelar a outra metade criaria
        # estoque do nada quando o ERP somasse a sua parte.
        if colecoes & reconstruidas:
            resumo["produtos reconstruidos pelo ERP"] += 1
            resumo["pecas reconstruidas"] += sum(o["qtd"] for o in lista)
            if colecoes - reconstruidas:
                sigla = siglas.get(codigo, "")
                avisos.append(
                    f"{codigo}: em {', '.join(sorted(colecoes))} — fica inteiro "
                    f"com o ERP" + (f" (cadastro diz {sigla})" if sigla else ""))
            continue
        total = sum(o["qtd"] for o in lista)
        if total == 0:
            resumo["zerados, nao congelados"] += 1
            continue
        saida.append({
            "codigo": codigo,
            "codigo_cor": "",
            "qtd": total,
            "colecao": sorted(colecoes)[0] if colecoes else "",
            "linhas": len(lista),
            "descricao": lista[0]["descricao"],
        })
        resumo["produtos congelados"] += 1
        resumo["pecas congeladas"] += total
        if len(lista) > 1:
            avisos.append(f"{codigo}: somado de {len(lista)} linhas "
                          f"({', '.join(sorted(colecoes))})")
    return saida, dict(resumo), avisos


def gravar(linhas, data_base: date) -> int:
    sql = ("INSERT INTO saldo_abertura (codigo, codigo_cor, data_base, qtd, origem) "
           "VALUES (%(codigo)s, %(codigo_cor)s, %(data_base)s, %(qtd)s, 'planilha') "
           "ON CONFLICT (codigo, codigo_cor, data_base) DO UPDATE SET "
           "  qtd = EXCLUDED.qtd, origem = EXCLUDED.origem")
    registros = [dict(l, data_base=data_base) for l in linhas]
    with conectar() as c, c.cursor() as cur:
        cur.executemany(sql, registros)
    return len(registros)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Congela o saldo de abertura a partir da planilha (D10)")
    p.add_argument("arquivo")
    p.add_argument("--cadastro", metavar="CSV", help="produtos-erp.csv, para desempate")
    p.add_argument("--data-base", type=dia, default=DATA_BASE)
    p.add_argument("--reconstruidas", default=",".join(RECONSTRUIDAS),
                   help="colecoes que vem do ERP em vez de congeladas")
    p.add_argument("--aplicar", action="store_true", help="sem isto, so mostra")
    args = p.parse_args(argv)

    caminho = pathlib.Path(args.arquivo.strip().strip("<>").strip('"').strip("'"))
    if not caminho.exists():
        print(f"\nNao encontrei o arquivo: {caminho}")
        return 1

    recon = [c.strip().upper() for c in args.reconstruidas.split(",") if c.strip()]
    linhas, resumo, avisos = ler(str(caminho), le_siglas(args.cadastro), recon)

    print(f"\n{caminho.name}   data-base {args.data_base}")
    print(f"  reconstruidas pelo ERP: {', '.join(recon)}")
    for k, v in sorted(resumo.items()):
        print(f"  {k:32} {v:,.0f}")
    for a in avisos[:12]:
        print(f"  AVISO: {a}")
    if len(avisos) > 12:
        print(f"  ... e mais {len(avisos) - 12} aviso(s)")

    if not linhas:
        print("\n  Nada a congelar.")
        return 1

    print(f"\n  maiores saldos a congelar:")
    for l in sorted(linhas, key=lambda x: -x["qtd"])[:10]:
        print(f'    {l["codigo"]:9} {l["colecao"][:6]:6} {l["qtd"]:>7,.0f}  '
              f'{l["descricao"][:34]}')

    if not args.aplicar:
        print("\n  Ensaio. Repita com --aplicar para gravar.")
        return 0

    motivo = por_que_nao()
    if motivo:
        print(f"\n  Nao gravei: {motivo}")
        return 1
    print(f"\n  gravados: {gravar(linhas, args.data_base)}")
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(*), sum(qtd) FROM saldo_abertura WHERE data_base = %s",
                    (args.data_base,))
        n, total = cur.fetchone()
        print(f"  no banco: {n} produto(s), {total:,.0f} peca(s) em {args.data_base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
