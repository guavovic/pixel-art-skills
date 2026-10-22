"""Guia de pixel art: um capítulo curto por assunto, lido só quando o assunto aparece.

    from pixel_atelier.guia import capitulo
    print(capitulo())             # o índice
    print(capitulo("cor"))        # um capítulo

Os capítulos são os `.md` desta pasta; `indice.md` diz qual ler e quais regras do `revisar`
cada um explica.
"""
from __future__ import annotations

from importlib import resources

INDICE = "indice"


def capitulos() -> list[str]:
    """Nomes dos capítulos, sem o índice."""
    return sorted(a.name[:-3] for a in resources.files(__package__).iterdir()
                  if a.name.endswith(".md") and a.name != f"{INDICE}.md")


def capitulo(nome: str | None = None) -> str:
    """Texto do capítulo (sem nome, o índice). Nome desconhecido levanta `KeyError` com a lista."""
    nome = (nome or INDICE).strip().lower().removesuffix(".md")
    if nome != INDICE and nome not in capitulos():
        raise KeyError(f"capítulo {nome!r} não existe; há: {', '.join(capitulos())}")
    return resources.files(__package__).joinpath(f"{nome}.md").read_text(encoding="utf-8")
