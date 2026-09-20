"""Grava uma rodada no banco, sem mexer no que a planilha faz.

Roda **em paralelo** com a geração do Excel: a rodada semanal continua saindo
igual, e o banco vai acumulando o retrato de cada semana. Enquanto as duas
saídas existirem, dá para comparar uma com a outra — que é o único jeito
honesto de ganhar confiança na nova antes de aposentar a velha.

Se o banco estiver fora do ar, a gravação falha e **a rodada segue**. A
planilha não pode depender do Postgres estar em pé.

O que entra é o que o arquivo disse, linha a linha, sem filtro de filial: qual
filial conta é decisão de consulta, e é diferente por fonte (D12). Guardar já
filtrado seria repetir na origem o erro que a migração existe para resolver.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from .conexao import conectar, disponivel

FONTES = ("estoque", "vendas", "producao", "preco")


def _de_para_cor(linhas: dict) -> dict[str, str]:
    """nome da cor -> código, montado do que veio no arquivo.

    A aba Estoque traz nome **e** código na mesma linha; a Producao só traz o
    nome. Este de-para é o que permite gravar a produção no mesmo grão das
    outras fontes.
    """
    mapa: dict[str, str] = {}
    for linha in linhas.get("estoque", ()):
        nome = (linha.get("cor") or "").strip().upper()
        codigo = (linha.get("codigo_cor") or "").strip()
        if nome and codigo:
            mapa.setdefault(nome, codigo)
    return mapa


def _nomes_de_cor(linhas: dict) -> dict[str, str]:
    """código -> nome, para a tabela de dimensão."""
    nomes: dict[str, str] = {}
    for fonte in ("estoque", "vendas"):
        for linha in linhas.get(fonte, ()):
            codigo = (linha.get("codigo_cor") or "").strip()
            nome = (linha.get("cor") or "").strip()
            if codigo and nome:
                nomes.setdefault(codigo, nome)
    return nomes


def _resolve(linhas: dict) -> tuple[dict, dict]:
    """Completa o código de cor da produção. Devolve (linhas, contagem)."""
    mapa = _de_para_cor(linhas)
    resolvidas = {f: list(linhas.get(f, ())) for f in FONTES}
    sem_codigo = 0
    for linha in resolvidas["producao"]:
        if linha.get("codigo_cor"):
            continue
        nome = (linha.get("cor") or "").strip().upper()
        achado = mapa.get(nome, "")
        linha["codigo_cor"] = achado
        if not achado:
            sem_codigo += 1
    return resolvidas, {"producao_sem_codigo_cor": sem_codigo}


def _somar(linhas: list, chaves: tuple[str, ...], campos: tuple[str, ...]) -> list[tuple]:
    """Agrupa pela chave primária da tabela.

    A aba pode trazer a mesma combinação em mais de uma linha (grade quebrada,
    lançamento em dois momentos). Sem somar antes, o INSERT bate na chave e a
    rodada inteira cai por um detalhe de formatação da origem.
    """
    somado = defaultdict(lambda: [0.0] * len(campos))
    for linha in linhas:
        chave = tuple((linha.get(k) or "") for k in chaves)
        for i, campo in enumerate(campos):
            somado[chave][i] += float(linha.get(campo) or 0)
    return [chave + tuple(valores) for chave, valores in somado.items()]


def gravar(fontes, data: date, origem: str = "upload",
           quem: str | None = None, observacao: str | None = None) -> dict:
    """Grava um snapshot. Devolve o resumo do que entrou."""
    linhas, contagem = _resolve(getattr(fontes, "linhas", {}) or {})

    produtos = {p["codigo"]: p for p in getattr(fontes, "produtos", []) if p.get("codigo")}
    cores = _nomes_de_cor(linhas)
    filiais = {(l.get("filial") or "").strip()
               for f in ("estoque", "vendas") for l in linhas[f]}
    filiais.discard("")

    estoque = _somar(linhas["estoque"], ("codigo", "codigo_cor", "tamanho", "filial"), ("qtd",))
    vendas = _somar(linhas["vendas"], ("codigo", "codigo_cor", "tamanho", "filial"), ("qtd",))
    producao = _somar(linhas["producao"], ("codigo", "codigo_cor", "tamanho"), ("qtd",))
    preco = _somar(linhas["preco"], ("codigo", "codigo_cor", "tamanho"), ("preco",))

    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO snapshot (data, origem, quem, observacao) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (data, origem, quem, observacao))
            snap = cur.fetchone()[0]

            # dimensões: o cadastro muda devagar e fora do snapshot
            for codigo, p in produtos.items():
                cur.execute(
                    "INSERT INTO produto (codigo, descricao, colecao, divisao) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (codigo) DO UPDATE SET "
                    "  descricao = COALESCE(EXCLUDED.descricao, produto.descricao),"
                    "  colecao   = COALESCE(EXCLUDED.colecao, produto.colecao),"
                    "  divisao   = COALESCE(EXCLUDED.divisao, produto.divisao),"
                    "  alterado_em = now()",
                    (codigo, p.get("descricao"), p.get("colecao"), p.get("divisao")))
            for codigo, nome in cores.items():
                cur.execute(
                    "INSERT INTO cor (codigo_cor, nome) VALUES (%s, %s) "
                    "ON CONFLICT (codigo_cor) DO NOTHING", (codigo, nome))
            for codigo in sorted(filiais):
                cur.execute(
                    "INSERT INTO filial (codigo, nome) VALUES (%s, %s) "
                    "ON CONFLICT (codigo) DO NOTHING", (codigo, codigo))

            cur.executemany(
                "INSERT INTO estoque (snapshot_id, codigo, codigo_cor, tamanho, filial, qtd) "
                "VALUES (%s, %s, %s, %s, %s, %s)", [(snap,) + l for l in estoque])
            cur.executemany(
                "INSERT INTO venda (snapshot_id, codigo, codigo_cor, tamanho, filial, qtd) "
                "VALUES (%s, %s, %s, %s, %s, %s)", [(snap,) + l for l in vendas])
            cur.executemany(
                "INSERT INTO producao (snapshot_id, codigo, codigo_cor, tamanho, qtd) "
                "VALUES (%s, %s, %s, %s, %s)", [(snap,) + l for l in producao])
            cur.executemany(
                "INSERT INTO preco (snapshot_id, codigo, codigo_cor, tamanho, preco) "
                "VALUES (%s, %s, %s, %s, %s)", [(snap,) + l for l in preco])

    return {
        "snapshot": snap,
        "data": data,
        "produtos": len(produtos),
        "cores": len(cores),
        "filiais": len(filiais),
        "estoque": len(estoque),
        "vendas": len(vendas),
        "producao": len(producao),
        "preco": len(preco),
        **contagem,
    }


def gravar_se_der(fontes, data: date, **kw) -> dict | None:
    """Grava e engole o erro.

    É o que a rodada chama. Banco fora do ar não pode derrubar a geração da
    planilha — mas o erro volta no resultado para aparecer na tela, senão a
    gravação silenciosamente para de acontecer e ninguém nota.
    """
    if not disponivel():
        return None
    try:
        return gravar(fontes, data, **kw)
    except Exception as e:                      # noqa: BLE001 — proposital
        return {"erro": f"{type(e).__name__}: {e}"}
