"""Motor da atualização semanal do sellout.

Duas etapas:

* `analisar`  — lê as planilhas e devolve o que precisa de decisão humana
                (filiais do estoque, códigos duplicados que o vermelho não
                resolve, produtos novos candidatos).
* `processar` — aplica as decisões e grava as planilhas atualizadas.
"""

from __future__ import annotations

import copy
import datetime as dt
from collections import defaultdict

import openpyxl

from . import divisao
from .cores import nrm
from .leitura import (
    ABAS_TRABALHO,
    blocos_de,
    carrega_fontes,
    linhas_de_produto,
    mapa_colunas,
    norm_codigo,
    texto,
    vermelho,
)

FMT_PECAS = '#,##0 "peças"'
MARCAS_COLUNA_A = {
    "ambos": "SIM",
    "estoque": "ESTOQUE",
    "vendas": "VENDAS",
    "producao": "PRODUÇÃO",
    "manter": "MANTER",
    "pendente": "REVISAR",
}


def rotulo_sellout(data: dt.date | None = None) -> str:
    data = data or dt.date.today()
    return "Sellout %02d/%02d" % (data.day, data.month)


def chave(rotulo, aba, codigo) -> str:
    return "%s|%s|%s" % (rotulo, aba, codigo)


class Planilha:
    """Uma planilha de trabalho aberta nas três leituras que precisamos."""

    def __init__(self, caminho, rotulo):
        self.caminho = caminho
        self.rotulo = rotulo
        self.rich = openpyxl.load_workbook(caminho, rich_text=True)
        self.valores = openpyxl.load_workbook(caminho, data_only=True)
        self.formulas = openpyxl.load_workbook(caminho, data_only=False)

    def codigos(self) -> set:
        achados = set()
        for aba in ABAS_TRABALHO:
            ws = self.valores[aba]
            for r in range(4, ws.max_row + 1):
                b = ws.cell(r, 2).value
                if b not in (None, "Código"):
                    achados.add(norm_codigo(b))
        return achados


# --------------------------------------------------------------------------- #
# Etapa 1 — análise
# --------------------------------------------------------------------------- #

def analisar(caminho_geral, caminho_classicos) -> dict:
    fontes = carrega_fontes(caminho_geral)
    planilhas = [Planilha(caminho_geral, "Geral"), Planilha(caminho_classicos, "Clássicos")]

    existentes = set()
    for p in planilhas:
        existentes |= p.codigos()

    pendentes, resolvidos = [], []
    for p in planilhas:
        for aba in ABAS_TRABALHO:
            ws = p.rich[aba]
            blocos = blocos_de(ws)
            linhas = linhas_de_produto(ws, blocos)
            vermelhos = {r: vermelho(ws.cell(r, 3).value) for r, _c, _b in linhas}
            descricoes = {r: texto(ws.cell(r, 3).value) for r, _c, _b in linhas}
            for cod, rs in divisao.agrupar_por_codigo(linhas).items():
                atribuicao, _sobra, motivo = divisao.resolver(cod, rs, vermelhos, fontes)
                if motivo is None and len(rs) == 1:
                    continue
                item = {
                    "chave": chave(p.rotulo, aba, cod),
                    "planilha": p.rotulo,
                    "aba": aba,
                    "codigo": cod,
                    "estoque": sum(fontes.estoque.get(cod, {}).values()),
                    "vendas": sum(sum(d.values()) for d in fontes.vendas.get(cod, {}).values()),
                    "cores": sorted(fontes.cores_do_codigo(cod)),
                    "linhas": [
                        {"idx": i, "linha": r, "descricao": descricoes[r],
                         "vermelho": vermelhos[r],
                         "cores": sorted(atribuicao[r]) if isinstance(atribuicao.get(r), set) else []}
                        for i, r in enumerate(rs)
                    ],
                }
                if motivo:
                    item["motivo"] = motivo
                    pendentes.append(item)
                else:
                    resolvidos.append(item)

    novos = []
    for prod in fontes.produtos:
        cod = prod["codigo"]
        if not cod or cod in existentes:
            continue
        estoque = sum(fontes.estoque.get(cod, {}).values())
        vendas = sum(sum(d.values()) for d in fontes.vendas.get(cod, {}).values())
        producao = sum(fontes.producao.get(cod, {}).values())
        if not (estoque or vendas or producao):
            continue
        divisao_txt = prod["divisao"] or ""
        novos.append({
            "codigo": cod,
            "descricao": prod["descricao"],
            "colecao": prod["colecao"],
            "aba": "Masculino" if "MASCULINO" in divisao_txt.upper() else
                   ("Feminino" if "FEMININO" in divisao_txt.upper() else None),
            "estoque": estoque,
            "vendas": vendas,
            "producao": producao,
        })
    novos.sort(key=lambda x: (x["aba"] or "zz", x["codigo"]))

    producao_sem_destino = [
        {"codigo": c, "qtde": sum(d.values())}
        for c, d in sorted(fontes.producao.items())
        if c not in existentes and c not in {n["codigo"] for n in novos}
    ]

    return {
        "filiais_estoque": fontes.filiais_estoque,
        "filiais_vendas": fontes.filiais_vendas,
        "duplicados_pendentes": pendentes,
        "duplicados_resolvidos": resolvidos,
        "novos_candidatos": novos,
        "producao_sem_destino": producao_sem_destino,
        "data_sugerida": rotulo_sellout(),
    }


# --------------------------------------------------------------------------- #
# Etapa 2 — processamento
# --------------------------------------------------------------------------- #

def processar(caminho_geral, caminho_classicos, saida_geral, saida_classicos, decisoes) -> dict:
    filiais = decisoes.get("filiais_estoque") or None
    fontes = carrega_fontes(caminho_geral, filiais_estoque=filiais)
    rotulo_data = decisoes.get("data_sellout") or rotulo_sellout()
    exige_estoque_prod = decisoes.get("producao_exige_estoque", True)
    aprovados = set(decisoes.get("novos") or [])
    escolhas = decisoes.get("duplicados") or {}

    rel = {
        "alterados": 0, "novos_inseridos": [], "por_cor": [], "producao": [],
        "producao_nao_aplicada": [], "mantidos": [], "pendentes": [],
        "nao_encontrados": [], "sem_cores": [], "cores_sem_destino": [], "sem_preco": [],
        "formulas_ajustadas": [], "nivel": {},
    }

    planilhas = [
        (Planilha(caminho_geral, "Geral"), saida_geral),
        (Planilha(caminho_classicos, "Clássicos"), saida_classicos),
    ]
    existentes = set()
    for p, _ in planilhas:
        existentes |= p.codigos()

    # Produtos novos aprovados, agrupados por (planilha destino, aba, coleção).
    novos_por_aba = defaultdict(list)
    for prod in fontes.produtos:
        cod = prod["codigo"]
        if not cod or cod in existentes or cod not in aprovados:
            continue
        div = (prod["divisao"] or "").upper()
        aba = "Masculino" if "MASCULINO" in div else ("Feminino" if "FEMININO" in div else None)
        if aba is None:
            continue
        novos_por_aba[(aba, nrm(prod["colecao"]))].append(
            {"codigo": cod, "descricao": prod["descricao"]}
        )
    for lista in novos_por_aba.values():
        lista.sort(key=lambda x: x["codigo"])

    usados_producao = set()
    for planilha, saida in planilhas:
        _processar_planilha(planilha, fontes, rotulo_data, exige_estoque_prod,
                            escolhas, novos_por_aba, usados_producao, rel)
        planilha.formulas.save(saida)

    rel["producao_sem_destino"] = [
        {"codigo": c, "qtde": sum(d.values())}
        for c, d in sorted(fontes.producao.items())
        if c not in usados_producao and c not in {
            x["codigo"] for x in rel["producao_nao_aplicada"]
        }
    ]
    return rel


def _processar_planilha(p, fontes, rotulo_data, exige_estoque_prod,
                        escolhas, novos_por_aba, usados_producao, rel):
    nivel = {}
    for aba in ABAS_TRABALHO:
        ws = p.formulas[aba]
        ws_rich = p.rich[aba]
        ws_val = p.valores[aba]
        cols = mapa_colunas(ws)
        col_sellout, col_inicial, col_atual = cols["K"], cols["J"], cols["D"]
        col_total = cols["I"]
        filiais_cols = {k: cols[k] for k in ("JARDINS", "IGUATEMI", "SITE") if k in cols}
        max_orig = ws.max_row
        blocos = blocos_de(ws)

        # Modelos das fórmulas que só referenciam a própria linha.
        modelo = _modelos_de_formula(ws, blocos[0]["ini"], col_sellout)

        cache_sellout = {r: ws_val.cell(r, col_sellout).value for r in range(1, max_orig + 1)}
        cache_vermelho = {r: vermelho(ws_rich.cell(r, 3).value) for r in range(1, max_orig + 1)}
        cache_desc = {r: texto(ws_rich.cell(r, 3).value) for r in range(1, max_orig + 1)}

        # ---- inserir produtos novos ao final do bloco da coleção ----
        deslocamento = {r: r for r in range(1, max_orig + 1)}
        linhas_novas = {}
        for bloco in sorted(blocos, key=lambda b: -b["sub"]):
            itens = novos_por_aba.get((aba, nrm(bloco["colecao"])), [])
            if not itens or p.rotulo != "Geral":
                continue
            pos, n, base = bloco["sub"], len(itens), bloco["ini"]
            ws.insert_rows(pos, n)
            for r in range(1, max_orig + 1):
                if deslocamento[r] >= pos:
                    deslocamento[r] += n
            for i, item in enumerate(itens):
                r = pos + i
                for c in range(1, ws.max_column + 1):
                    ws.cell(r, c)._style = copy.copy(ws.cell(base, c)._style)
                ws.cell(r, 2).value = item["codigo"]
                ws.cell(r, 3).value = item["descricao"]
                linhas_novas[r] = item["codigo"]
                rel["novos_inseridos"].append({
                    "planilha": p.rotulo, "aba": aba, "linha": r,
                    "codigo": item["codigo"], "descricao": item["descricao"],
                    "bloco": bloco["titulo"],
                })
        original = {novo: velho for velho, novo in deslocamento.items()}

        blocos = blocos_de(ws)
        linhas = linhas_de_produto(ws, blocos)
        for r, _cod, _b in linhas:
            for c, tpl in modelo.items():
                ws.cell(r, c).value = tpl.format(r=r)

        # ---- resolver a divisão por cor ----
        vermelhos = {r: cache_vermelho.get(original.get(r), "") for r, _c, _b in linhas}
        destino = {}
        for cod, rs in divisao.agrupar_por_codigo(linhas).items():
            escolha = escolhas.get(chave(p.rotulo, aba, cod))
            atribuicao, sobra, motivo = divisao.resolver(cod, rs, vermelhos, fontes, escolha)
            for r in rs:
                destino[r] = atribuicao[r]
            desc = lambda r: cache_desc.get(original.get(r)) or ws.cell(r, 3).value
            if atribuicao[rs[0]] == divisao.MANTER:
                for r in rs:
                    rel["mantidos"].append({"planilha": p.rotulo, "aba": aba, "linha": r,
                                            "codigo": cod, "descricao": desc(r)})
            elif atribuicao[rs[0]] == divisao.PENDENTE:
                for r in rs:
                    rel["pendentes"].append({"planilha": p.rotulo, "aba": aba, "linha": r,
                                             "codigo": cod, "descricao": desc(r), "motivo": motivo})
            elif len(rs) > 1 or vermelhos.get(rs[0]):
                for r in rs:
                    rel["por_cor"].append({
                        "planilha": p.rotulo, "aba": aba, "linha": r, "codigo": cod,
                        "descricao": desc(r), "vermelho": vermelhos.get(r, ""),
                        "cores": sorted(atribuicao[r]) if isinstance(atribuicao[r], set) else [],
                    })
                if sobra:
                    rel["cores_sem_destino"].append({
                        "planilha": p.rotulo, "aba": aba, "codigo": cod, "cores": sorted(sobra),
                        "estoque": sum(fontes.estoque[cod][c] for c in sobra),
                        "vendas": sum(sum(fontes.vendas[cod][c].values()) for c in sobra),
                    })

        # ---- rotação da coluna de sellout ----
        max_atual = ws.max_row
        estilos = {r: copy.copy(ws.cell(r, col_sellout)._style) for r in range(1, max_atual + 1)}
        ws.insert_cols(col_sellout + 1)
        for r in range(1, max_atual + 1):
            nova = ws.cell(r, col_sellout + 1)
            nova._style = estilos[r]
            atual = ws.cell(r, col_sellout).value
            if isinstance(atual, str) and atual.startswith("Sellout"):
                nova.value = atual
                ws.cell(r, col_sellout).value = rotulo_data
            else:
                nova.value = cache_sellout.get(original.get(r))

        # ---- estoque, vendas, produção e coluna A ----
        codigos_da_aba = set()
        for r, cod, _b in linhas:
            d = destino.get(r)
            cores_est = fontes.estoque.get(cod, {})
            cores_ven = fontes.vendas.get(cod, {})
            cores_pro = fontes.producao.get(cod, {})
            codigos_da_aba.add(cod)
            if d in (divisao.MANTER, divisao.PENDENTE):
                ws.cell(r, 1).value = MARCAS_COLUNA_A["manter" if d == divisao.MANTER else "pendente"]
                continue
            filtro = fontes.cores_do_codigo(cod) if d is None else d
            qtd_est = sum(cores_est.get(c, 0) for c in filtro)
            tem_est = any(c in cores_est for c in filtro)
            tem_ven = any(c in cores_ven for c in filtro)
            qtd_prod = sum(cores_pro.get(c, 0) for c in filtro)

            vendas_por_col = defaultdict(int)
            for c in filtro:
                for filial, q in cores_ven.get(c, {}).items():
                    if filial in filiais_cols:
                        vendas_por_col[filiais_cols[filial]] += q
            qtd_ven = sum(vendas_por_col.values())

            if tem_est and tem_ven:
                ws.cell(r, 1).value = MARCAS_COLUNA_A["ambos"]
            elif tem_est:
                ws.cell(r, 1).value = MARCAS_COLUNA_A["estoque"]
            elif tem_ven:
                ws.cell(r, 1).value = MARCAS_COLUNA_A["vendas"]
            elif qtd_prod:
                ws.cell(r, 1).value = MARCAS_COLUNA_A["producao"]
            elif isinstance(d, set):
                # Linha de um código dividido que não ficou com nenhuma cor:
                # o estoque foi todo para a linha irmã. Zera o Estoque atual
                # para não contar duas vezes no subtotal do bloco; as vendas
                # são acumuladas de semanas anteriores e ficam como estão.
                ws.cell(r, 1).value = None
                ws.cell(r, col_atual).value = 0
                rel["sem_cores"].append({
                    "planilha": p.rotulo, "aba": aba, "linha": r, "codigo": cod,
                    "descricao": cache_desc.get(original.get(r)) or ws.cell(r, 3).value})
                rel["alterados"] += 1
                continue
            else:
                ws.cell(r, 1).value = None
                rel["nao_encontrados"].append({
                    "planilha": p.rotulo, "aba": aba, "linha": r, "codigo": cod,
                    "descricao": cache_desc.get(original.get(r)) or ws.cell(r, 3).value})
                continue

            if r in linhas_novas:
                ws.cell(r, col_atual).value = qtd_est
                for col in filiais_cols.values():
                    ws.cell(r, col).value = vendas_por_col.get(col, 0)
                ws.cell(r, col_inicial).value = max(qtd_prod, qtd_est + qtd_ven)
                if qtd_prod:
                    usados_producao.add(cod)
                    rel["producao"].append({
                        "planilha": p.rotulo, "aba": aba, "linha": r, "codigo": cod,
                        "descricao": ws.cell(r, 3).value, "qtde": qtd_prod,
                        "obs": "linha nova — já no Estoque inicial"})
                rel["alterados"] += 1
                continue

            if tem_est:
                ws.cell(r, col_atual).value = qtd_est
            for col, q in vendas_por_col.items():
                anterior = ws.cell(r, col).value
                ws.cell(r, col).value = (anterior + q) if isinstance(anterior, (int, float)) else q

            if qtd_prod and exige_estoque_prod and qtd_est <= 0:
                rel["producao_nao_aplicada"].append({
                    "planilha": p.rotulo, "aba": aba, "linha": r, "codigo": cod,
                    "descricao": cache_desc.get(original.get(r)), "qtde": qtd_prod,
                    "motivo": "linha sem estoque atual"})
                qtd_prod = 0
            if qtd_prod:
                anterior = ws.cell(r, col_inicial).value
                sufixo = ("+%d" % qtd_prod) if qtd_prod > 0 else ("%d" % qtd_prod)
                if isinstance(anterior, str) and anterior.startswith("="):
                    ws.cell(r, col_inicial).value = anterior + sufixo
                elif isinstance(anterior, (int, float)) and anterior:
                    ws.cell(r, col_inicial).value = "=%s%s" % (anterior, sufixo)
                else:
                    ws.cell(r, col_inicial).value = qtd_prod
                usados_producao.add(cod)
                rel["producao"].append({
                    "planilha": p.rotulo, "aba": aba, "linha": r, "codigo": cod,
                    "descricao": cache_desc.get(original.get(r)), "qtde": qtd_prod,
                    "obs": "somada ao Estoque inicial"})
            rel["alterados"] += 1

        _ajustar_somatorias(ws, p.rotulo, aba, col_atual, col_sellout, col_total, col_inicial, rel)
        nivel[aba] = _nivel_de_estoque(ws, p.rotulo, aba, col_atual, codigos_da_aba, fontes, rel)

    _totais_cruzados(p, nivel)
    rel["nivel"][p.rotulo] = {a: {"valor": v[1], "pecas": v[2]} for a, v in nivel.items()}


def _modelos_de_formula(ws, linha_base, col_sellout) -> dict:
    """Guarda o formato das fórmulas que só olham a própria linha."""
    import re
    modelos = {}
    for c in range(1, col_sellout + 1):
        v = ws.cell(linha_base, c).value
        if isinstance(v, str) and v.startswith("=") and re.search(r"[A-Z]%d\b" % linha_base, v):
            modelos[c] = re.sub(r"([A-Z]{1,2})%d\b" % linha_base, r"\1{r}", v)
    return modelos


def _ajustar_somatorias(ws, rotulo, aba, col_atual, col_sellout, col_total, col_inicial, rel):
    letra = openpyxl.utils.get_column_letter
    blocos = blocos_de(ws)
    for b in blocos:
        for c in range(col_atual, col_sellout + 1):
            antes = ws.cell(b["sub"], c).value
            if isinstance(antes, str) and antes.startswith("=SUM("):
                depois = "=SUM(%s%d:%s%d)" % (letra(c), b["ini"], letra(c), b["fim"])
                if antes != depois:
                    rel["formulas_ajustadas"].append({
                        "planilha": rotulo, "aba": aba, "linha": b["sub"],
                        "tipo": "subtotal de bloco", "antes": antes, "depois": depois})
                ws.cell(b["sub"], c).value = depois
            elif isinstance(antes, str) and antes.startswith("=") and c == col_sellout:
                ws.cell(b["sub"], c).value = "=IFERROR(%s%d/%s%d,0)" % (
                    letra(col_total), b["sub"], letra(col_inicial), b["sub"])

    linha_total = None
    for r in range(4, ws.max_row + 1):
        valor = ws.cell(r, col_atual).value
        if (isinstance(ws.cell(r, 3).value, str) and nrm(ws.cell(r, 3).value) == "TOTAL"
                and isinstance(valor, str) and "+" in valor
                and "SUM" not in valor and "!" not in valor):
            linha_total = r
            break
    if linha_total is None:
        return
    subtotais = [b["sub"] for b in blocos]
    for c in range(col_atual, col_sellout + 1):
        if c == col_sellout:
            ws.cell(linha_total, c).value = "=IFERROR(%s%d/%s%d,0)" % (
                letra(col_total), linha_total, letra(col_inicial), linha_total)
            continue
        antes = ws.cell(linha_total, c).value
        if isinstance(antes, str) and antes.startswith("="):
            depois = "=" + "+".join("%s%d" % (letra(c), s) for s in subtotais)
            if antes != depois:
                rel["formulas_ajustadas"].append({
                    "planilha": rotulo, "aba": aba, "linha": linha_total,
                    "tipo": "total geral", "antes": antes, "depois": depois})
            ws.cell(linha_total, c).value = depois


def _nivel_de_estoque(ws, rotulo, aba, col_atual, codigos, fontes, rel):
    valor = pecas = 0
    for cod, _cor, codcor, tam, qtd in fontes.linhas_estoque:
        if cod not in codigos or not qtd:
            continue
        pecas += qtd
        unitario, origem = fontes.preco_de(cod, codcor, tam)
        if origem != "exato":
            rel["sem_preco"].append({"planilha": rotulo, "aba": aba, "codigo": cod,
                                     "cor": codcor, "tamanho": tam, "qtde": qtd,
                                     "preco_usado": unitario, "origem": origem})
        if unitario:
            valor += qtd * unitario

    linha = None
    for r in range(4, ws.max_row + 1):
        if isinstance(ws.cell(r, 3).value, str) and nrm(ws.cell(r, 3).value) == "NIVEL DE ESTOQUE":
            linha = r
    if linha is None:
        return None
    letra = openpyxl.utils.get_column_letter(col_atual)
    ws.cell(linha, col_atual).value = valor
    ws.cell(linha + 1, col_atual).value = pecas
    ws.cell(linha + 1, col_atual).number_format = FMT_PECAS
    ws.cell(linha + 2, col_atual).value = "=IFERROR(%s%d/%s%d,0)" % (letra, linha, letra, linha + 1)
    return (linha, valor, pecas, col_atual)


def _totais_cruzados(p, nivel):
    """As linhas de Total somam a aba irmã; refaz as referências."""
    for aba in ABAS_TRABALHO:
        atual, outra = nivel.get(aba), nivel.get("Feminino" if aba == "Masculino" else "Masculino")
        if not atual or not outra:
            continue
        linha, _v, _p, col = atual
        letra = openpyxl.utils.get_column_letter(col)
        nome_outra = "Feminino" if aba == "Masculino" else "Masculino"
        ws = p.formulas[aba]
        ws.cell(linha + 4, col).value = "=%s%d+%s!%s%d" % (letra, linha, nome_outra, letra, outra[0])
        ws.cell(linha + 5, col).value = "=%s%d+%s!%s%d" % (letra, linha + 1, nome_outra, letra, outra[0] + 1)
        ws.cell(linha + 5, col).number_format = FMT_PECAS
        ws.cell(linha + 6, col).value = "=IFERROR(%s%d/%s%d,0)" % (letra, linha + 4, letra, linha + 5)
