from sellout.core.cores import eh_resto, match, nrm, tokens


def test_nrm_tira_acento_e_pontuacao():
    assert nrm("BORDÔ") == "BORDO"
    assert nrm("VERDE CL.") == "VERDE CL"
    assert nrm("  Off-White ") == "OFF WHITE"


def test_tokens_separa_por_virgula_e_e():
    assert tokens("PRETO, OFF E BEGE") == ["PRETO", "OFF", "BEGE"]
    assert tokens("ROXO, AZUL BIC, VERDE CL") == ["ROXO", "AZUL BIC", "VERDE CL"]
    assert tokens("AZUL E BLUSH") == ["AZUL", "BLUSH"]
    assert tokens("") == []


def test_match_resolve_abreviacao_e_genero():
    cores = {"OFF WHITE", "PRETO", "BEGE", "VERDE CL", "AMARELO"}
    assert match("OFF", cores) == ["OFF WHITE"]
    assert match("VERDE CL", cores) == ["VERDE CL"]
    assert match("AMARELA", cores) == ["AMARELO"]
    assert match("ROSA", cores) == []


def test_match_prefere_exato_sobre_prefixo():
    assert match("VERDE", {"VERDE", "VERDE MILITAR"}) == ["VERDE"]


def test_demais_cores():
    assert eh_resto("DEMAIS CORES")
    assert not eh_resto("MARINHO")
