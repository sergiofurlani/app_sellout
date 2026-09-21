"""Monta a página da evolução do sellout a partir do histórico.

    python -m sellout.db.evolucao -s evolucao.html                  # do banco
    python -m sellout.db.evolucao -s evolucao.html --da-planilha "sellout geral.xlsx"

É o primeiro relatório que **não existe na planilha**: a curva de cada coleção
ao longo das semanas, e as coleções sobrepostas na mesma idade. Com 237 colunas
lado a lado ninguém enxerga isso; com uma coluna de data, é uma consulta.

A mediana, e não a média, porque um produto que esgotou cedo ou entrou ontem
não pode decidir a curva da coleção inteira.

O HTML é um molde (`docs/evolucao.template.html`) com um `__DADOS__` no meio.
Os números entram como JSON e a página não busca nada — abre offline, de
qualquer lugar.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
from collections import defaultdict
from datetime import date

from .conexao import conectar, por_que_nao

MOLDE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "evolucao.template.html"


def do_banco(planilha: str = "geral") -> list[tuple[date, str, float]]:
    with conectar() as c, c.cursor() as cur:
        cur.execute(
            "SELECT data, upper(coalesce(colecao, '')), percentual "
            "FROM sellout_historico "
            "WHERE planilha = %s AND percentual IS NOT NULL AND coalesce(colecao,'') <> '' "
            "ORDER BY data", (planilha,))
        return [(d, c_, float(p) * 100) for d, c_, p in cur.fetchall()]


def da_planilha(caminho: str, planilha: str = "geral"):
    from .historico import ler
    registros, _resumo, _avisos = ler(caminho, planilha)
    return [(r["data"], (r["colecao"] or "").upper(), float(r["percentual"]) * 100)
            for r in registros
            if r["percentual"] is not None and (r["colecao"] or "").strip()]


def series(linhas):
    """-> {calendario: {colecao: [{d, m, n}]}, idade: {colecao: [{s, m, n, d}]}}"""
    por = defaultdict(list)
    for data, colecao, pct in linhas:
        por[(data, colecao)].append(pct)
    datas = sorted({d for d, _ in por})
    colecoes = sorted({c for _, c in por})
    calendario = {
        c: [{"d": d.isoformat(), "m": round(statistics.median(por[(d, c)]), 1),
             "n": len(por[(d, c)])}
            for d in datas if (d, c) in por]
        for c in colecoes
    }
    idade = {}
    for c, s in calendario.items():
        zero = date.fromisoformat(s[0]["d"])
        idade[c] = [{"s": round((date.fromisoformat(p["d"]) - zero).days / 7),
                     "m": p["m"], "n": p["n"], "d": p["d"]} for p in s]
    return {"calendario": calendario, "idade": idade}


def monta(dados: dict) -> str:
    molde = MOLDE.read_text(encoding="utf-8")
    if "__DADOS__" not in molde:
        raise ValueError(f"{MOLDE} nao tem o marcador __DADOS__")
    return molde.replace("__DADOS__", json.dumps(dados, separators=(",", ":")))


def main(argv=None):
    p = argparse.ArgumentParser(description="Pagina da evolucao do sellout")
    p.add_argument("-s", "--salvar", default="evolucao.html")
    p.add_argument("--planilha", choices=("geral", "classicos"), default="geral")
    p.add_argument("--da-planilha", metavar="XLSX",
                   help="le do arquivo em vez do banco (nao precisa de DATABASE_URL)")
    args = p.parse_args(argv)

    if args.da_planilha:
        linhas = da_planilha(args.da_planilha, args.planilha)
    else:
        motivo = por_que_nao()
        if motivo:
            print(f"\nNao consegui ler o banco: {motivo}")
            print("Use --da-planilha \"sellout geral.xlsx\" para gerar mesmo assim.")
            return 1
        linhas = do_banco(args.planilha)

    if not linhas:
        print("\nNenhum registro com coleção. Nada a desenhar.")
        return 1

    dados = series(linhas)
    pathlib.Path(args.salvar).write_text(monta(dados), encoding="utf-8")

    print(f"\n  {args.salvar}")
    for c, s in sorted(dados["calendario"].items()):
        print(f"  {c:6} {len(s):>3} semanas   {s[0]['d']} -> {s[-1]['d']}   "
              f"mediana hoje {s[-1]['m']:>5.1f}%  ({s[-1]['n']} produtos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
