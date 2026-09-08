from sellout.core import divisao


class FontesFake:
    def __init__(self, cores):
        self._cores = set(cores)

    def cores_do_codigo(self, _codigo):
        return set(self._cores)


def test_vermelho_divide_e_linha_sem_vermelho_leva_o_resto():
    fontes = FontesFake({"FENDI", "PRETO", "MARINHO", "BEGE"})
    atribuicao, sobra, motivo = divisao.resolver(
        "330043", [28, 52], {28: "FENDI", 52: ""}, fontes)
    assert motivo is None and sobra == set()
    assert atribuicao[28] == {"FENDI"}
    assert atribuicao[52] == {"PRETO", "MARINHO", "BEGE"}


def test_demais_cores_recebe_o_complemento():
    fontes = FontesFake({"MARINHO", "PRETO", "BORDO"})
    atribuicao, _s, motivo = divisao.resolver(
        "323003", [234, 235], {234: "MARINHO", 235: "DEMAIS CORES"}, fontes)
    assert motivo is None
    assert atribuicao[234] == {"MARINHO"}
    assert atribuicao[235] == {"PRETO", "BORDO"}


def test_cor_inexistente_vira_pendencia():
    fontes = FontesFake({"PRETO", "BEGE"})
    atribuicao, _s, motivo = divisao.resolver(
        "212006", [115, 116], {115: "", 116: "CORES SS25"}, fontes)
    assert motivo and "CORES SS25" in motivo
    assert all(v == divisao.PENDENTE for v in atribuicao.values())


def test_duas_linhas_sem_vermelho_viram_pendencia():
    fontes = FontesFake({"ROXO", "PRETO"})
    _a, _s, motivo = divisao.resolver("330011", [51, 154], {51: "", 154: ""}, fontes)
    assert motivo and "sem texto em vermelho" in motivo


def test_decisao_manter():
    fontes = FontesFake({"ROXO"})
    atribuicao, _s, motivo = divisao.resolver(
        "330011", [51, 154], {51: "", 154: ""}, fontes, "manter")
    assert motivo is None
    assert atribuicao == {51: divisao.MANTER, 154: divisao.MANTER}


def test_decisao_por_indice_nao_depende_do_numero_da_linha():
    fontes = FontesFake({"ROXO", "PRETO"})
    atribuicao, _s, _m = divisao.resolver(
        "330011", [59, 162], {59: "", 162: ""}, fontes, "idx:0")
    assert atribuicao[59] == {"ROXO", "PRETO"}
    assert atribuicao[162] == set()


def test_linha_unica_sem_vermelho_leva_tudo():
    fontes = FontesFake({"PRETO"})
    atribuicao, _s, motivo = divisao.resolver("999", [10], {10: ""}, fontes)
    assert motivo is None and atribuicao[10] is None
