"""Migrações versionadas.

Arquivos `NNN_nome.sql` em `migracoes/`, aplicados **em ordem numérica**, cada
um dentro da sua transação, e registrados em `schema_migracao`. Rodar de novo
não repete o que já passou.

Por que à mão em vez de Alembic: o esquema aqui é pequeno e nasce de um
documento (`docs/arquitetura.md`), não de modelos ORM. Um diretório de SQL que
qualquer pessoa lê com `cat` vale mais, neste projeto, que uma ferramenta a
mais para instalar na máquina de quem for manter isto depois.

**Migração nunca é editada depois de aplicada** — vira uma nova. Um arquivo
já rodado que muda de conteúdo deixa dois bancos diferentes com o mesmo número,
e nada avisa. Por isso o checksum é guardado e conferido.

    python -m sellout.db.migracoes          aplica o que falta
    python -m sellout.db.migracoes --ver    só mostra o estado
"""

from __future__ import annotations

import hashlib
import pathlib
import re

from .conexao import conectar

PASTA = pathlib.Path(__file__).parent / "migracoes"
PADRAO = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")

CONTROLE = """
CREATE TABLE IF NOT EXISTS schema_migracao (
    numero      integer PRIMARY KEY,
    nome        text NOT NULL,
    checksum    text NOT NULL,
    aplicada_em timestamptz NOT NULL DEFAULT now()
)
"""


def _checksum(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def arquivos() -> list[tuple[int, str, pathlib.Path]]:
    achados = []
    for caminho in sorted(PASTA.glob("*.sql")):
        m = PADRAO.match(caminho.name)
        if not m:
            raise ValueError(
                f"{caminho.name}: nome fora do padrao NNN_nome.sql. "
                "A ordem de aplicacao depende do numero."
            )
        achados.append((int(m.group(1)), m.group(2), caminho))
    numeros = [n for n, _, _ in achados]
    if len(set(numeros)) != len(numeros):
        raise ValueError(f"numeros repetidos em migracoes/: {numeros}")
    return achados


def versao() -> list[dict]:
    """O que o banco diz que já aplicou."""
    with conectar() as c:
        with c.cursor() as cur:
            cur.execute(CONTROLE)
        with c.cursor() as cur:
            cur.execute("SELECT numero, nome, checksum, aplicada_em "
                        "FROM schema_migracao ORDER BY numero")
            return [{"numero": n, "nome": nm, "checksum": ck, "aplicada_em": q}
                    for n, nm, ck, q in cur.fetchall()]


def pendentes() -> tuple[list, list[str]]:
    """(a aplicar, avisos). Aviso aqui é arquivo que mudou depois de aplicado."""
    aplicadas = {m["numero"]: m for m in versao()}
    falta, avisos = [], []
    for numero, nome, caminho in arquivos():
        texto = caminho.read_text(encoding="utf-8")
        ck = _checksum(texto)
        ja = aplicadas.get(numero)
        if ja is None:
            falta.append((numero, nome, caminho, texto, ck))
        elif ja["checksum"] != ck:
            avisos.append(
                f"{caminho.name} mudou depois de aplicada "
                f"({ja['checksum']} -> {ck}). Migracao aplicada nao se edita: "
                "crie a proxima."
            )
    return falta, avisos


def aplicar(seco: bool = False) -> list[str]:
    falta, avisos = pendentes()
    feitas = []
    for numero, nome, caminho, texto, ck in falta:
        if seco:
            feitas.append(f"(nao aplicada) {caminho.name}")
            continue
        # uma transação por migração: falhou no meio, nada daquele arquivo fica
        with conectar() as c:
            with c.cursor() as cur:
                cur.execute(texto)
                cur.execute(
                    "INSERT INTO schema_migracao (numero, nome, checksum) "
                    "VALUES (%s, %s, %s)", (numero, nome, ck))
        feitas.append(caminho.name)
    return feitas + [f"AVISO: {a}" for a in avisos]


def main(argv=None):
    import argparse

    p = argparse.ArgumentParser(description="Migracoes do banco do sellout")
    p.add_argument("--ver", action="store_true", help="so mostra o estado")
    args = p.parse_args(argv)

    if args.ver:
        for m in versao():
            print(f"  {m['numero']:>3} {m['nome']:24} {m['checksum']}  {m['aplicada_em']}")
        falta, avisos = pendentes()
        for numero, nome, caminho, _, _ in falta:
            print(f"  {numero:>3} {nome:24} PENDENTE")
        for a in avisos:
            print(f"  AVISO: {a}")
        return 0

    for linha in aplicar() or ["nada a aplicar"]:
        print(f"  {linha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
