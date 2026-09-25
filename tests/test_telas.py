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
        "entradas_erp": {"estado": "ok", "produtos": 690, "pecas_semana": 120},
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


def test_revisao_avisa_quando_o_csv_do_erp_nao_veio(env):
    """**Sem o arquivo, nenhuma linha recebe peça** — e a rodada terminaria
    calada, com o denominador congelado e o sellout subindo sozinho. Desde a
    D18 isso é pior do que recusar, então a tela exige confirmação."""
    a = analise(entradas_erp={"estado": "ausente", "produtos": 0, "pecas_semana": 0})
    html = env.get_template("revisao.html").render(
        request=_Req(), job="x", a=a,
        nomes={"geral": "g.xlsx", "classicos": "c.xlsx"})
    assert "painel alerta" in html
    assert 'name="confirma_sem_entradas"' in html and "required" in html


def test_revisao_avisa_quando_o_csv_e_do_formato_antigo(env):
    """CSV sem `quant_semana`: só produto novo recebe peça. É o caso mais
    traiçoeiro dos três, porque o arquivo existe e parece certo."""
    a = analise(entradas_erp={"estado": "antigo", "produtos": 690, "pecas_semana": 0})
    html = env.get_template("revisao.html").render(
        request=_Req(), job="x", a=a,
        nomes={"geral": "g.xlsx", "classicos": "c.xlsx"})
    assert "formato antigo" in html and "quant_semana" in html


def test_revisao_nao_incomoda_quando_esta_tudo_certo(env):
    """Aviso que aparece sempre deixa de ser lido."""
    html = env.get_template("revisao.html").render(
        request=_Req(), job="x", a=analise(),
        nomes={"geral": "g.xlsx", "classicos": "c.xlsx"})
    assert "painel alerta" not in html
    assert "confirma_sem_entradas" not in html


def test_resultado_diz_quando_nada_cresceu(env):
    html = env.get_template("resultado.html").render(
        request=_Req(), job="x", rel=relatorio(entradas_semana=[]),
        decisoes={"data_sellout": "Sellout 21/09"}, banco=None)
    assert "nao cresceu" in html.replace("ã", "a").replace("ó", "o")


def estado(**extra):
    base = {"conectado": True, "razao": None, "aplicadas": [], "pendentes": [],
            "avisos": []}
    base.update(extra)
    return base


def test_banco_sem_conexao_nao_estoura(env):
    """A tela do banco existe justamente para quando o banco não está de pé:
    se ela mesma depender da conexão, não serve para nada."""
    b = estado(conectado=False, razao="DATABASE_URL nao definida no ambiente")
    html = env.get_template("banco.html").render(request=_Req(), b=b, feitas=None)
    assert "Sem conexão com o banco" in html
    assert "DATABASE_URL" in html


def test_banco_lista_o_que_vai_rodar_antes_de_rodar(env):
    """Botão que aplica migração sem dizer quais é pedir para alguém clicar no
    escuro."""
    b = estado(pendentes=[{"numero": 3, "nome": "movimento",
                           "arquivo": "003_movimento.sql"}])
    html = env.get_template("banco.html").render(request=_Req(), b=b, feitas=None)
    assert "003_movimento.sql" in html
    assert 'action="/banco/migrar"' in html


def test_banco_em_dia_nao_mostra_botao(env):
    html = env.get_template("banco.html").render(
        request=_Req(), b=estado(), feitas=None)
    assert "/banco/migrar" not in html
    assert "Nenhuma" in html


def test_banco_mostra_o_que_acabou_de_aplicar(env):
    html = env.get_template("banco.html").render(
        request=_Req(), b=estado(), feitas=["003_movimento.sql"])
    assert "Aplicado agora" in html and "003_movimento.sql" in html


def test_banco_avisa_migracao_que_mudou_depois_de_aplicada(env):
    """Arquivo já aplicado que muda deixa dois bancos diferentes com o mesmo
    número, e depois nada avisa."""
    b = estado(avisos=["001_estrutura.sql mudou depois de aplicada"])
    html = env.get_template("banco.html").render(request=_Req(), b=b, feitas=None)
    assert "mudou de conteúdo" in html


def test_index_renderiza_sem_a_chave_de_erro(env):
    """`{% if erro %}` estourava aqui com StrictUndefined: em produção o Jinja
    do FastAPI é tolerante e trata ausente como falso, mas depender disso é
    contar com a sorte do modo padrão. `erro is defined and erro` funciona nos
    dois."""
    assert env.get_template("index.html").render(request=_Req())
