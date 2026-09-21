"""Escreve abas de dados num .xlsx sem reescrever o resto do arquivo.

O openpyxl **não calcula fórmula**, e ao salvar ele joga fora o resultado que o
Excel tinha guardado. Isso não aparece em lugar nenhum: o arquivo abre, as
fórmulas estão lá, e o Excel recalcula ao abrir. Quem lê o arquivo por
programa, não.

Foi o que aconteceu em 21/09. O `monta_fontes` abria a planilha com openpyxl,
escrevia as abas de origem e salvava — e com isso apagou o valor guardado da
coluna `Sellout 14/09`. O app congela essa coluna lendo justamente o valor
guardado (`data_only=True`), achou `None`, e entregou a planilha da semana com
a coluna anterior **em branco**. Uma semana de histórico apagada por um efeito
colateral de salvar.

A saída é não deixar o openpyxl encostar no arquivo inteiro. Aqui o .xlsx é
tratado como o zip que ele é: cada parte é copiada byte a byte, e só o XML das
abas de dados é trocado. As abas de trabalho chegam do outro lado idênticas —
com o valor guardado das fórmulas, com o texto em vermelho da D1, com a
formatação. Não há o que se perder, porque nada é reescrito.

Os textos vão como `inlineStr`, e não pela tabela de textos compartilhados do
arquivo: assim as abas novas não dependem de índices que pertencem às outras
abas, que é o que quebraria ao trocar só uma parte.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from xml.sax.saxutils import escape

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def coluna(n: int) -> str:
    """1 -> A, 27 -> AA."""
    letras = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def caminhos_das_abas(zf: zipfile.ZipFile) -> dict[str, str]:
    """{nome da aba: caminho da parte dentro do zip}."""
    wb = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")

    alvo = {m.group(1): m.group(2) for m in re.finditer(
        r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', rels)}
    # O atributo pode vir em qualquer ordem; a segunda passada pega o inverso.
    for m in re.finditer(r'<Relationship[^>]*Target="([^"]+)"[^>]*Id="([^"]+)"', rels):
        alvo.setdefault(m.group(2), m.group(1))

    abas = {}
    for m in re.finditer(r"<sheet\s([^>]*?)/?>", wb):
        atrib = m.group(1)
        nome = re.search(r'name="([^"]*)"', atrib)
        rid = re.search(r'r:id="([^"]*)"', atrib) or re.search(r'id="([^"]*)"', atrib)
        if not nome or not rid or rid.group(1) not in alvo:
            continue
        destino = alvo[rid.group(1)].lstrip("/")
        if not destino.startswith("xl/"):
            destino = "xl/" + destino
        abas[_desescapa(nome.group(1))] = destino
    return abas


def _desescapa(t: str) -> str:
    return (t.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))


def _celula(ref: str, valor) -> str:
    if valor is None or valor == "":
        return ""
    if isinstance(valor, bool):                       # antes de int: bool é int
        return f'<c r="{ref}" t="b"><v>{int(valor)}</v></c>'
    if isinstance(valor, (int, float)):
        return f'<c r="{ref}"><v>{valor!r}</v></c>'
    texto = escape(str(valor))
    return (f'<c r="{ref}" t="inlineStr"><is>'
            f'<t xml:space="preserve">{texto}</t></is></c>')


def xml_da_aba(linhas) -> bytes:
    """O XML inteiro de uma aba de dados, do zero."""
    partes = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{NS}" xmlns:r="{NS_R}">',
    ]
    largura = max((len(l) for l in linhas), default=0)
    if linhas and largura:
        partes.append(f'<dimension ref="A1:{coluna(largura)}{len(linhas)}"/>')
    partes.append("<sheetData>")
    for i, linha in enumerate(linhas, 1):
        celulas = "".join(_celula(f"{coluna(j)}{i}", v) for j, v in enumerate(linha, 1))
        if celulas:
            partes.append(f'<row r="{i}">{celulas}</row>')
    partes.append("</sheetData></worksheet>")
    return "".join(partes).encode("utf-8")


def escreve_abas(origem: str, destino: str, dados: dict[str, list[list]]) -> dict:
    """Copia `origem` para `destino` trocando só o conteúdo das abas de `dados`.

    `dados` é {nome da aba: [linha, linha, ...]}, cabeçalho incluído. Toda outra
    parte do arquivo — abas de trabalho, estilos, fórmulas e os valores que o
    Excel guardou — é copiada sem ser lida.
    """
    with zipfile.ZipFile(origem) as zf:
        abas = caminhos_das_abas(zf)
        faltando = [a for a in dados if a not in abas]
        if faltando:
            raise ValueError("a planilha nao tem as abas: " + ", ".join(faltando))
        troca = {abas[aba]: xml_da_aba(linhas) for aba, linhas in dados.items()}

        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as saida:
            for item in zf.infolist():
                if item.filename in troca:
                    saida.writestr(item.filename, troca[item.filename])
                else:
                    # `item` inteiro, não só o nome: preserva data e modo.
                    saida.writestr(item, zf.read(item.filename))
    return {aba: len(linhas) for aba, linhas in dados.items()}


def copia(origem: str, destino: str) -> None:
    shutil.copyfile(origem, destino)
