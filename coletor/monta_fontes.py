"""Escreve as abas de origem na planilha, a partir do ERP.

    python -m coletor.vendas --de 2026-09-14 --ate 2026-09-20 -s vendas.csv
    python -m coletor.estoque_inicial --de 2026-09-14 --para-app entradas.csv
    python -m coletor.monta_fontes "sellout geral.xlsx" \\
        --estoque ESTOQUE.xlsx --preco Tabela_preco.xlsx --vendas vendas.csv

É a ponte que tira o export semanal do caminho. As abas **Estoque**, **Vendas**
e **Preco** passam a ser escritas com o que veio do ERP, e a rodada continua
exatamente como é hoje: você sobe a planilha no app, confere e baixa.

**Produção não é escrita.** Ela existia para alimentar o Estoque inicial, e o
Estoque inicial passou a vir da transferência da Elena (D14). A aba é deixada
como está.

**O texto em vermelho é o risco desta operação.** A divisão de um código entre
duas linhas depende dele (D1), e já houve uma rodada que o apagou. Por isso a
planilha é aberta com `rich_text=True`, as abas de trabalho não são tocadas, e
no fim o arquivo novo é **reaberto e conferido**: se o número de trechos em
vermelho mudar, o programa avisa em vez de entregar calado.

Nada é escrito por cima do original — sai um arquivo novo, ` - fontes.xlsx`.
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import openpyxl

from . import fontes_erp, planilha_xml

CABECALHOS = {
    "Estoque": ["FILIAL", "CODIGO", "DESCRICAO", "CODIGO COR", "COR", "TAMANHO",
                "ESTOQUE ATUAL"],
    "Vendas": ["FILIAL", "CODIGO", "DESCRICAO", "CODIGO COR", "COR", "TAMANHO",
               "QTDE", "VALOR"],
    "Preco": ["PRODUTO", "DESCRICAO", "CODIGO COR", "COR", "TAMANHO", "PRECO"],
}


def conta_vermelho(caminho: str) -> int:
    """Quantas linhas das abas de trabalho têm texto em vermelho na descrição.

    É a medida de integridade da D1, e usa a mesma leitura que o app usa —
    `sellout.core.leitura.vermelho` —, não uma cópia parecida. Comparar antes e
    depois é o que impede esta ferramenta de repetir o defeito que já apagou a
    divisão por cor numa rodada.
    """
    from sellout.core.leitura import vermelho

    wb = openpyxl.load_workbook(caminho, rich_text=True)
    total = 0
    for aba in ("Masculino", "Feminino"):
        if aba not in wb.sheetnames:
            continue
        ws = wb[aba]
        for (celula,) in ws.iter_rows(min_col=3, max_col=3):
            if vermelho(celula.value):
                total += 1
    wb.close()
    return total


def le_vendas(caminho: str) -> list[dict]:
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return [
            {"filial": (l.get("FILIAL") or "").strip(),
             "codigo": (l.get("CODIGO") or "").strip(),
             "codigo_cor": (l.get("CODIGO COR") or "").strip(),
             "cor": (l.get("COR") or "").strip(),
             "tamanho": (l.get("TAMANHO") or "").strip(),
             "qtd": float(l.get("QTDE") or 0),
             "valor": float(l.get("VALOR") or 0)}
            for l in csv.DictReader(f, delimiter=";")
            if (l.get("CODIGO") or "").strip()
        ]


def monta(planilha: str, estoque, preco, vendas, saida: str) -> dict:
    """Escreve as três abas de origem sem reabrir a planilha inteira.

    **Salvar pelo openpyxl apagava uma semana de histórico.** Ele não calcula
    fórmula e descarta o resultado que o Excel tinha guardado; o app congela a
    coluna de sellout lendo justamente esse valor, encontrava `None`, e a
    coluna anterior saía em branco na planilha da semana. Aconteceu em 21/09
    com a `Sellout 14/09`.

    Por isso a gravação é feita parte a parte no zip (`planilha_xml`): as abas
    de trabalho não são lidas nem reescritas, e chegam do outro lado com o
    valor guardado, o texto em vermelho da D1 e a formatação intactos.
    """
    dados = {
        "Estoque": [CABECALHOS["Estoque"]] +
        [[e["filial"], e["codigo"], "", e["codigo_cor"], e["cor"],
          e["tamanho"], e["qtd"]] for e in estoque],
        "Vendas": [CABECALHOS["Vendas"]] +
        [[v["filial"], v["codigo"], "", v["codigo_cor"], v["cor"],
          v["tamanho"], v["qtd"], v["valor"]] for v in vendas],
        "Preco": [CABECALHOS["Preco"]] +
        [[p["codigo"], "", p["codigo_cor"], "", p["tamanho"], p["preco"]]
         for p in preco],
    }
    planilha_xml.escreve_abas(planilha, saida, dados)
    return {"estoque": len(estoque), "vendas": len(vendas), "preco": len(preco)}


def conta_formulas_com_valor(caminho: str) -> int:
    """Quantas fórmulas das abas de trabalho têm resultado guardado.

    É a medida que faltava. O texto em vermelho era conferido antes e depois; o
    valor guardado das fórmulas, não — e era ele que sumia. Zero aqui significa
    que o app vai congelar a coluna da semana passada em branco.
    """
    valores = openpyxl.load_workbook(caminho, data_only=True)
    formulas = openpyxl.load_workbook(caminho, data_only=False)
    total = 0
    for aba in ("Masculino", "Feminino"):
        if aba not in valores.sheetnames:
            continue
        wv, wf = valores[aba], formulas[aba]
        for linha in wf.iter_rows(min_row=1, max_row=wf.max_row):
            for celula in linha:
                if isinstance(celula.value, str) and celula.value.startswith("="):
                    if wv.cell(celula.row, celula.column).value is not None:
                        total += 1
    valores.close()
    formulas.close()
    return total


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Escreve as abas de origem na planilha, a partir do ERP")
    p.add_argument("planilha")
    p.add_argument("--estoque", required=True)
    p.add_argument("--preco", required=True)
    p.add_argument("--vendas", required=True, help="CSV do coletor.vendas")
    p.add_argument("--saida", default=None)
    args = p.parse_args(argv)

    caminho = pathlib.Path(args.planilha.strip().strip("<>").strip('"').strip("'"))
    pistas = {"planilha": ("sellout", "geral"), "estoque": ("estoque",),
              "preco": ("preco", "preço", "tabela"), "vendas": ("venda",)}
    for rotulo, alvo in (("planilha", caminho), ("estoque", pathlib.Path(args.estoque)),
                         ("preco", pathlib.Path(args.preco)),
                         ("vendas", pathlib.Path(args.vendas))):
        if alvo.exists():
            continue
        print(f"\nNao encontrei o {rotulo}: {alvo}")
        # Em vez de só reclamar, olha na pasta e sugere. Marcador de exemplo
        # colado literalmente — `caminho\ESTOQUE.xlsx` — foi o erro mais
        # repetido desta empreitada, e a pasta quase sempre tem o arquivo certo.
        vizinhos = sorted(
            p.name for p in pathlib.Path(".").iterdir()
            if p.is_file() and p.suffix.lower() in (".xlsx", ".xls", ".csv")
            and any(t in p.name.lower() for t in pistas[rotulo]))
        if vizinhos:
            print(f"  Nesta pasta tem: {', '.join(vizinhos[:6])}")
            print(f"  Talvez seja:  --{rotulo} \"{vizinhos[0]}\"")
        return 1
    saida = args.saida or str(caminho.with_name(caminho.stem + " - fontes.xlsx"))

    est, r_est, av_est = fontes_erp.le_estoque(args.estoque)
    pre, r_pre, av_pre = fontes_erp.le_preco(args.preco)
    ven = le_vendas(args.vendas)
    for a in av_est + av_pre:
        print(f"  AVISO: {a}")
    if not est or not pre or not ven:
        print("\n  Faltou uma das fontes. Nada foi escrito.")
        return 1

    antes, formulas_antes = conta_vermelho(str(caminho)), conta_formulas_com_valor(str(caminho))
    r = monta(str(caminho), est, pre, ven, saida)
    depois, formulas_depois = conta_vermelho(saida), conta_formulas_com_valor(saida)

    print(f"\n  {saida}")
    print(f"    Estoque  {r['estoque']:>7,} linha(s)   "
          f"{sum(e['qtd'] for e in est):>9,.0f} peca(s)")
    print(f"    Vendas   {r['vendas']:>7,} linha(s)   "
          f"{sum(v['qtd'] for v in ven):>9,.0f} peca(s)   "
          f"R$ {sum(v['valor'] for v in ven):,.2f}")
    print(f"    Preco    {r['preco']:>7,} linha(s)")
    print("    Producao nao foi tocada — o Estoque inicial vem do evento 106 (D14)")

    print(f"\n  texto em vermelho: {antes} antes, {depois} depois", end="")
    if antes != depois:
        print("  <-- MUDOU, NAO USE ESTE ARQUIVO")
        print("\n  A divisao por cor depende desses trechos (D1). Alguma coisa")
        print("  nesta gravacao mexeu neles; conferir antes de seguir.")
        return 1
    print("  (intacto)")

    print(f"  formulas com valor guardado: {formulas_antes:,} antes, "
          f"{formulas_depois:,} depois", end="")
    if formulas_depois < formulas_antes:
        print("  <-- SUMIRAM, NAO USE ESTE ARQUIVO")
        print("\n  E esse valor que o app congela na coluna da semana passada.")
        print("  Sem ele a coluna anterior sai em branco — foi o que aconteceu")
        print("  com a Sellout 14/09 em 21/09.")
        return 1
    print("  (intacto)")
    print("\n  Suba este arquivo no app junto com a Sellout Classicos, como sempre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
