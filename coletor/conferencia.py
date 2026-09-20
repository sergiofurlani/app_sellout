"""Aba de conferência: Estoque inicial da planilha x o que o ERP transferiu.

    python -m coletor.conferencia "sellout geral.xlsx" \\
        --de 2026-01-01 --ate 2026-09-07 --colecoes AW26,SS27

Gera uma cópia da planilha com uma aba nova, **Estoque inicial ERP**, sem
encostar nas abas de trabalho nem no histórico de 237 colunas.

O que compara, por produto:

    Estoque inicial   a fórmula de hoje (`=86-1+44-2`), mantida à mão
    Transferido ERP   soma do evento 106, ELENA ES -> lojas, no período
    Diferença         o tamanho do problema, produto a produto

Código dividido em duas linhas pelo texto em vermelho (D1) é tratado como a
planilha trata: a linha do vermelho fica com as cores citadas, a outra com o
resto. O ERP devolve `cod_cor` e `desc_cor` em cada item, então a divisão é
feita com o mesmo casamento de nomes do resto do projeto.

**O número do ERP só conta a partir de `--de`.** Produto que começou a ser
despachado antes disso aparece com transferência menor do que a verdade, e a
aba marca esse caso em vez de deixar parecer diferença real.
"""

from __future__ import annotations

import argparse
import pathlib
from collections import defaultdict
from datetime import date

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from sellout.core.cores import eh_resto, match, nrm, tokens
from sellout.core.leitura import (COLUNAS_PRODUTOS, blocos_de, colunas_da_fonte,
                                  linhas_de_produto, mapa_colunas, norm_codigo, texto, vermelho)

from . import mn

EVENTO = 106
MATRIZ = ("ELENA ES", "ELENA SP", "ELENATIMES")
LOJAS = {"EGREY JDS", "IGUATEMI"}

ABA = "Estoque inicial ERP"
CABECALHO = [
    "Aba", "Linha", "Código", "Descrição", "Coleção", "Cores (vermelho)",
    "Estoque inicial", "Transferido ERP", "Diferença", "Obs",
]


def dia(t: str) -> date:
    return date.fromisoformat(t)


def _matriz(nome: str) -> bool:
    return any(m in (nome or "").upper() for m in MATRIZ)


def transferencias(de: date, ate: date):
    """(codigo, cod_cor, nome_cor) -> quantidade líquida para as lojas.

    Também devolve a primeira data de cada código, para saber se o período
    pegou a coleção desde o começo.
    """
    saldo = defaultdict(float)
    primeira: dict[str, date] = {}
    docs = mn.documentos_do_periodo(de, ate, (EVENTO,))
    for doc in docs:
        origem = (doc.get("cod_filial") or "").strip()
        destino = (doc.get("cod_cliente") or "").strip()
        if _matriz(origem) and destino.upper() in LOJAS:
            sinal = 1
        elif origem.upper() in LOJAS and _matriz(destino):
            sinal = -1
        else:
            continue                      # loja->loja é realocação; resto, fora
        data = mn.parse_data(doc.get("data_emissao"))
        for item in doc.get("itens") or []:
            q = item.get("quant") or 0
            if q <= 0:
                continue
            codigo = str(item.get("cod_produto") or "").strip()
            chave = (codigo, str(item.get("cod_cor") or "").strip(),
                     str(item.get("desc_cor") or "").strip())
            saldo[chave] += sinal * q
            if data and sinal > 0:
                if codigo not in primeira or data < primeira[codigo]:
                    primeira[codigo] = data
    return saldo, primeira, len(docs)


def _nome_limpo(desc_cor: str) -> str:
    """'0308 - VERMELHO' -> 'VERMELHO'."""
    _codigo, _sep, nome = (desc_cor or "").partition("-")
    return (nome or desc_cor or "").strip()


def le_cadastro(caminho) -> dict[str, str]:
    """codigo -> sigla da coleção, do CSV do cadastro do ERP."""
    import csv as _csv
    if not caminho:
        return {}
    mapa = {}
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for linha in _csv.DictReader(f, delimiter=";"):
            cod = (linha.get("codigo") or "").strip()
            sg = (linha.get("sigla") or "").strip().upper()
            if cod and sg:
                mapa[cod] = sg
    return mapa


def divide(codigo, linhas_do_codigo, saldo, colecao_erp=None, colecoes_das_linhas=None):
    """Reparte o transferido entre as linhas do código, pelo texto em vermelho.

    Devolve {linha: (quantidade, observação)}.
    """
    porcor = {(cc, _nome_limpo(dc)): q
              for (cod, cc, dc), q in saldo.items() if cod == codigo}
    total = sum(porcor.values())
    if len(linhas_do_codigo) == 1:
        return {linhas_do_codigo[0][0]: (total, "")}

    # Código em mais de uma linha SEM vermelho em nenhuma: é o mesmo produto
    # em dois blocos de coleção (o `330043 CALÇA MB NEW` está em AW26 e SS27).
    # O ERP tem um único fluxo de transferências para esse código e não sabe a
    # qual coleção cada peça pertence — a coleção é recorte nosso, não dele.
    # Dividir seria inventar; atribuir tudo à última linha, que é o que a regra
    # do "resto" fazia, faz a outra aparecer zerada como se faltasse peça.
    sem_vermelho = [l for l, c in linhas_do_codigo if not c or eh_resto(c)]
    if len(sem_vermelho) > 1:
        # O cadastro do ERP diz a coleção do produto. Com ela, a linha do bloco
        # certo fica com tudo e a outra é marcada como sobra de bloco antigo —
        # sem cadastro, não há como escolher e o total vai para a primeira.
        certa = None
        if colecao_erp and colecoes_das_linhas:
            certas = [l for l in sem_vermelho
                      if colecoes_das_linhas.get(l) == colecao_erp]
            if len(certas) == 1:
                certa = certas[0]
        if certa is not None:
            return {l: (total if l == certa else 0,
                        "" if l == certa
                        else f"cadastro do ERP diz {colecao_erp}; linha de outro bloco")
                    for l, _c in linhas_do_codigo}
        obs = (f"codigo em {len(linhas_do_codigo)} linhas sem vermelho; "
               f"sem cadastro para desempatar — total do codigo: {total:,.0f}")
        return {l: (total if l == sem_vermelho[0] else 0, obs)
                for l, _c in linhas_do_codigo}

    disponiveis = {nome for _cc, nome in porcor}
    resultado, usadas = {}, set()
    resto_em = None
    for linha, cores in linhas_do_codigo:
        if not cores or eh_resto(cores):
            resto_em = linha
            continue
        alvo, nao_achadas = set(), []
        for t in tokens(cores):
            achado = match(t, disponiveis)
            if achado:
                alvo.update(achado)
            else:
                nao_achadas.append(t)
        usadas |= alvo
        q = sum(v for (_cc, nome), v in porcor.items() if nome in alvo)
        obs = ""
        if nao_achadas:
            obs = "sem transferência para: " + ", ".join(nao_achadas)
        resultado[linha] = (q, obs)

    if resto_em is not None:
        q = sum(v for (_cc, nome), v in porcor.items() if nome not in usadas)
        resultado[resto_em] = (q, "demais cores")
    return resultado


def colecao_dos_produtos(wb) -> dict[str, str]:
    """codigo -> coleção, da aba Produtos.

    Necessário porque o produto lançado nesta semana ainda **não tem linha**
    nas abas de trabalho: quem o insere é a rodada, a partir dessa aba. Sem
    isto, justamente a coleção nova — a que interessa conferir — apareceria
    como "fora das coleções pedidas".
    """
    if "Produtos" not in wb.sheetnames:
        return {}
    ws = wb["Produtos"]
    c = colunas_da_fonte(ws, COLUNAS_PRODUTOS)
    mapa = {}
    for r in range(2, ws.max_row + 1):
        codigo = norm_codigo(ws.cell(r, c["codigo"]).value)
        col = texto(ws.cell(r, c["colecao"]).value)
        if codigo and col:
            mapa[codigo] = str(col).strip().replace(" ", "").upper()
    return mapa


def monta(caminho: str, saida: str, saldo, primeira, colecoes, de: date, ate: date,
          cadastro=None):
    cadastro = cadastro or {}
    wb = openpyxl.load_workbook(caminho, data_only=False, rich_text=True)
    wv = openpyxl.load_workbook(caminho, data_only=True)
    if ABA in wb.sheetnames:
        del wb[ABA]
    ws_out = wb.create_sheet(ABA)

    ws_out["A1"] = "Estoque inicial: planilha x ERP"
    ws_out["A1"].font = Font(bold=True, size=13)
    ws_out["A2"] = (f"Evento 106 (venda entre filiais), ELENA ES → lojas, "
                    f"de {de} a {ate}. Coleções: {', '.join(colecoes)}.")
    ws_out["A3"] = ("O ERP só conta a partir da data inicial: produto despachado "
                    "antes disso aparece menor, e a coluna Obs avisa.")
    for c, titulo in enumerate(CABECALHO, 1):
        cel = ws_out.cell(5, c, titulo)
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor="404040")
        cel.alignment = Alignment(horizontal="center", wrap_text=True)

    r = 6
    total_pl = total_erp = 0.0
    vistos = set()
    for aba in ("Masculino", "Feminino"):
        if aba not in wb.sheetnames:
            continue
        ws, wsv = wb[aba], wv[aba]
        col = mapa_colunas(ws)
        coluna_ei = col.get("J")
        if not coluna_ei:
            continue
        blocos = [b for b in blocos_de(ws) if b.get("colecao") in colecoes]
        if not blocos:
            continue

        # agrupa as linhas por código, para dividir pelo vermelho
        por_codigo = defaultdict(list)
        meta = {}
        for linha, codigo, bloco in linhas_de_produto(ws, blocos):
            if not codigo:
                continue
            cores = vermelho(ws.cell(linha, 3).value)
            por_codigo[codigo].append((linha, cores))
            meta[linha] = (bloco, cores)

        for codigo in sorted(por_codigo):
            colecoes_das_linhas = {l: (meta[l][0].get("colecao") or "").upper()
                                   for l, _c in por_codigo[codigo]}
            reparte = divide(codigo, por_codigo[codigo], saldo,
                             cadastro.get(codigo), colecoes_das_linhas)
            vistos.add(codigo)
            for linha, _cores in por_codigo[codigo]:
                bloco, cores = meta[linha]
                ei = wsv.cell(linha, coluna_ei).value
                ei = float(ei) if isinstance(ei, (int, float)) else None
                erp, obs = reparte.get(linha, (0.0, ""))
                inicio = primeira.get(codigo)
                if inicio and inicio <= de:
                    obs = (obs + "; " if obs else "") + "despacho pode ser anterior ao período"
                ws_out.cell(r, 1, aba)
                ws_out.cell(r, 2, linha)
                ws_out.cell(r, 3, codigo)
                ws_out.cell(r, 4, texto(ws.cell(linha, 3).value))
                ws_out.cell(r, 5, bloco.get("colecao"))
                ws_out.cell(r, 6, cores)
                ws_out.cell(r, 7, ei)
                ws_out.cell(r, 8, erp)
                if ei is not None:
                    ws_out.cell(r, 9, f"=H{r}-G{r}")
                    total_pl += ei
                    total_erp += erp
                ws_out.cell(r, 10, obs)
                r += 1

    # o que o ERP transferiu e não apareceu em nenhuma linha das coleções
    de_produtos = colecao_dos_produtos(wb)
    fora = defaultdict(float)
    for (codigo, _cc, _dc), q in saldo.items():
        if codigo not in vistos and q > 0:
            fora[codigo] += q
    pendentes = {c: q for c, q in fora.items() if de_produtos.get(c) in colecoes}
    outros = {c: q for c, q in fora.items() if c not in pendentes}

    if pendentes:
        r += 2
        cel = ws_out.cell(r, 1, "Da coleção, transferidos, mas ainda sem linha na planilha")
        cel.font = Font(bold=True)
        ws_out.cell(r + 1, 1, "A rodada insere estes a partir da aba Produtos. "
                              "Aqui o Estoque inicial nasce — é a chance de "
                              "nascer certo.")
        r += 2
        for codigo, q in sorted(pendentes.items(), key=lambda x: -x[1]):
            ws_out.cell(r, 3, codigo)
            ws_out.cell(r, 5, de_produtos.get(codigo))
            ws_out.cell(r, 8, q)
            ws_out.cell(r, 10, "sem linha ainda; a aba Produtos diz "
                               + str(de_produtos.get(codigo)))
            r += 1

    if outros:
        r += 2
        ws_out.cell(r, 1, "Transferidos, fora das coleções pedidas").font = Font(bold=True)
        r += 1
        for codigo, q in sorted(outros.items(), key=lambda x: -x[1]):
            ws_out.cell(r, 3, codigo)
            ws_out.cell(r, 5, de_produtos.get(codigo) or "—")
            ws_out.cell(r, 8, q)
            ws_out.cell(r, 10, "coleção " + (de_produtos.get(codigo) or "não encontrada"))
            r += 1

    r += 1
    ws_out.cell(r, 4, "TOTAL").font = Font(bold=True)
    ws_out.cell(r, 7, total_pl).font = Font(bold=True)
    ws_out.cell(r, 8, total_erp).font = Font(bold=True)
    ws_out.cell(r, 9, f"=H{r}-G{r}").font = Font(bold=True)

    for letra, largura in zip("ABCDEFGHIJ", (11, 7, 11, 34, 9, 24, 14, 14, 11, 40)):
        ws_out.column_dimensions[letra].width = largura
    ws_out.freeze_panes = "A6"
    wb.save(saida)
    return {"linhas": r, "total_planilha": total_pl, "total_erp": total_erp,
            "pendentes": len(pendentes), "fora": len(outros),
            "pecas_pendentes": sum(pendentes.values())}


def main(argv=None):
    p = argparse.ArgumentParser(description="Compara o Estoque inicial com o ERP")
    p.add_argument("arquivo")
    p.add_argument("--de", type=dia, required=True)
    p.add_argument("--ate", type=dia, default=date.today(),
                   help="padrao: hoje. Parar antes da data da planilha faz\n                         produto recem-chegado aparecer com zero, e zero\n                         parece divergencia.")
    p.add_argument("--colecoes", default="AW26,SS27")
    p.add_argument("--saida", default=None)
    p.add_argument("--sem-cache", action="store_true")
    p.add_argument("--cadastro", metavar="CSV",
                   help="produtos-erp.csv do coletor.produtos; usa a colecao do "
                        "cadastro para desempatar codigo que esta em dois blocos")
    args = p.parse_args(argv)

    mn.USAR_CACHE = not args.sem_cache
    colecoes = [c.strip().upper() for c in args.colecoes.split(",") if c.strip()]

    # O caminho é conferido ANTES da extração. Ela leva minutos e vai à rede;
    # descobrir no fim que o arquivo não existe joga tudo fora. Os `<>` são
    # tirados porque é o erro que a pessoa comete ao copiar um exemplo com
    # marcador de lugar — e o `.xlsx>` resultante dá um erro do openpyxl que
    # não diz nada sobre a causa.
    caminho = pathlib.Path(args.arquivo.strip().strip("<>").strip('"').strip("'"))
    if not caminho.exists():
        print(f"\nNao encontrei o arquivo: {caminho}")
        if args.arquivo != str(caminho):
            print(f"(li como {caminho} depois de tirar aspas e <>)")
        print("Passe o caminho da planilha, sem < >. Exemplo:")
        print('  python -m coletor.conferencia "C:\\caminho\\sellout geral.xlsx" '
              "--de 2026-01-01 --ate 2026-09-07")
        return 1
    saida = args.saida or str(caminho.with_name(caminho.stem + " - conferencia.xlsx"))

    if args.ate < date.today():
        print(f"\nAviso: --ate e {args.ate}, e hoje e {date.today()}. Produto que "
              "chegou\nna loja depois dessa data aparece com ERP = 0 — o que parece "
              "divergencia\ne nao e. A planilha ja conta essas pecas.")

    print(f"\nPuxando o evento {EVENTO} de {args.de} a {args.ate}...")
    saldo, primeira, docs = transferencias(args.de, args.ate)
    pecas = sum(v for v in saldo.values() if v > 0)
    print(f"  {docs} documento(s), {len(saldo)} combinacao(oes) produto+cor, "
          f"{pecas:,.0f} peca(s)")

    cadastro = le_cadastro(args.cadastro)
    if cadastro:
        print(f"  cadastro do ERP: {len(cadastro)} produto(s) com colecao")
    r = monta(str(caminho), saida, saldo, primeira, colecoes, args.de, args.ate,
              cadastro)
    print(f"\n  {saida}")
    print(f"  planilha {r['total_planilha']:,.0f}  x  ERP {r['total_erp']:,.0f}  "
          f"(diferenca {r['total_erp'] - r['total_planilha']:+,.0f})")
    if r["pendentes"]:
        print(f"  {r['pendentes']} produto(s) da colecao, {r['pecas_pendentes']:,.0f} peca(s), "
              "ainda sem linha na planilha")
    if r["fora"]:
        print(f"  {r['fora']} produto(s) transferidos fora das colecoes pedidas")
    print("\n  A aba nova fica ao final do arquivo. As abas de trabalho e as 237")
    print("  colunas de historico nao foram tocadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
