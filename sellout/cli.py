"""Execução da rodada pelo terminal, sem subir o app.

    python -m sellout.cli "sellout geral.xlsx" "Sellout Clássicos.xlsx" -s saida/

Sem `--decisoes`, usa os padrões: todas as filiais do estoque, produção só
com estoque, produtos novos com estoque e códigos duplicados sem divisão
mantidos como estão.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import motor, relatorio


def decisoes_padrao(analise: dict) -> dict:
    return {
        "data_sellout": analise["data_sugerida"],
        "filiais_estoque": analise["filiais_estoque"],
        "producao_exige_estoque": True,
        "novos": [n["codigo"] for n in analise["novos_candidatos"]
                  if n["estoque"] > 0 and n["aba"]],
        "duplicados": {d["chave"]: "manter" for d in analise["duplicados_pendentes"]},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Atualização semanal do sellout")
    p.add_argument("geral", help="planilha sellout geral.xlsx")
    p.add_argument("classicos", help="planilha Sellout Clássicos.xlsx")
    p.add_argument("-s", "--saida", default="saida", help="pasta de destino")
    p.add_argument("--decisoes", help="json com as decisões da rodada")
    p.add_argument("--so-analisar", action="store_true",
                   help="imprime a análise em json e não gera arquivos")
    args = p.parse_args(argv)

    analise = motor.analisar(args.geral, args.classicos)
    if args.so_analisar:
        print(json.dumps(analise, ensure_ascii=False, indent=2, default=str))
        return 0

    decisoes = decisoes_padrao(analise)
    if args.decisoes:
        decisoes.update(json.loads(Path(args.decisoes).read_text()))

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    rel = motor.processar(
        args.geral, args.classicos,
        str(saida / "sellout geral atualizado.xlsx"),
        str(saida / "Sellout Clássicos atualizado.xlsx"),
        decisoes,
    )
    relatorio.gerar(rel, str(saida / "relatorio de conferencia.xlsx"))

    print("Rodada %s" % decisoes["data_sellout"])
    print("  %d linhas atualizadas" % rel["alterados"])
    print("  %d produtos novos" % len(rel["novos_inseridos"]))
    print("  %d linhas divididas por cor" % len(rel["por_cor"]))
    print("  %d fórmulas reajustadas" % len(rel["formulas_ajustadas"]))
    for planilha, abas in rel["nivel"].items():
        for aba, d in abas.items():
            print("  Nível de Estoque %s/%s: %d pçs, R$ %.2f" % (planilha, aba, d["pecas"], d["valor"]))
    print("Arquivos em %s" % saida.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
