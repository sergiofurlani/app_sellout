"""As telas renderizam com o relatório que o motor produz hoje.

Os templates não tinham teste nenhum, e template quebra em produção, não no
`pytest`: um `{{ rel.producao }}` que deixou de existir só aparece quando
alguém termina uma rodada de minutos e recebe uma tela de erro no lugar do
resultado. Aqui eles são renderizados com `StrictUndefined`, que transforma
campo ausente em falha de teste — que é exatamente o que se quer ao tirar
chaves do relatório, como a D18 fez com a produção.
"""

import jinja2
import pytest

TEMPLATES = "sellout/web/templates"


@pytest.fixture
def env():
    return jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES),
                              undefined=jinja2.StrictUndefined)


class _Req:
    url = type("U", (), {"path": "/"})()


def relatorio(**extra):
    """O `rel` no formato que `motor.processar` devolve."""
    base = {
        "alterados": 3, "novos_inseridos": [], "por_cor": [], "mantidos": [],
        "pendentes": [], "estoque_inicial_novos": [], "entradas_semana": [],
        "nao_encontrados": [], "sem_cores": [], "cores_sem_destino": [],
        "sem_preco": [], "formulas_ajustadas": [], "avisos": [],
        "valores_ignorados": [],
        "nivel": {"Geral": {"Feminino": {"pecas": 10, "valor": 100.0}}},
    }
    base.update(extra)
    return base


def analise(**extra):
    base = {
        "filiais_estoque": ["EGREY JDS"], "filiais_vendas": ["IGUATEMI"],
        "duplicados_pendentes": [], "duplicados_resolvidos": [],
        "novos_candidatos": [], "avisos": [], "colunas_usadas": {},
        "valores_ignorados": [], "total_valores_ignorados": 0,
        "data_sugerida": "Sellout 21/09",
    }
    base.update(extra)
    return base


def test_resultado_renderiza(env):
    html = env.get_template("resultado.html").render(
        request=_Req(), job="x", rel=relatorio(),
        decisoes={"data_sellout": "Sellout 21/09"}, banco=None)
    assert "Sellout 21/09" in html


def test_resultado_mostra_a_entrada_do_erp_no_lugar_da_producao(env):
    """A linha do resumo mudou de dono na D18."""
    rel = relatorio(entradas_semana=[
        {"planilha": "Geral", "aba": "Feminino", "linha": 4, "codigo": "334128",
         "descricao": "BLUSA", "qtde": 12, "obs": "transferencia da semana"}])
    html = env.get_template("resultado.html").render(
        request=_Req(), job="x", rel=rel,
        decisoes={"data_sellout": "Sellout 21/09"}, banco=None)
    assert "entradas do ERP no Estoque inicial" in html
    assert "produção" not in html.lower()


def test_revisao_renderiza(env):
    html = env.get_template("revisao.html").render(
        request=_Req(), job="x", a=analise(),
        nomes={"geral": "g.xlsx", "classicos": "c.xlsx"})
    assert "Sellout 21/09" in html


def test_revisao_do_produto_novo_mostra_a_entrada_do_erp(env):
    """O candidato a produto novo era listado com a produção. Produto que só
    existe na aba Producao ainda não chegou na loja — o que interessa agora é
    o que a Elena transferiu."""
    a = analise(novos_candidatos=[
        {"codigo": "334099", "descricao": "VESTIDO", "colecao": "SS27",
         "aba": "Feminino", "estoque": 5, "vendas": 1, "entrada": 24}])
    html = env.get_template("revisao.html").render(
        request=_Req(), job="x", a=a,
        nomes={"geral": "g.xlsx", "classicos": "c.xlsx"})
    assert "entrada ERP" in html and "24" in html


def test_a_regra_da_producao_saiu_da_tela(env):
    """A D5 não existe mais: não há o que perguntar ao usuário sobre produção."""
    html = env.get_template("revisao.html").render(
        request=_Req(), job="x", a=analise(),
        nomes={"geral": "g.xlsx", "classicos": "c.xlsx"})
    assert "producao_exige_estoque" not in html
