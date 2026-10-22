"""Linha de comando. Tudo responde em texto curto.

    python -m pixel_atelier gerar receita.json [--pasta saida]   # "-" lê a receita da entrada padrão
    python -m pixel_atelier formas                               # parâmetros de cada forma, com o padrão
    python -m pixel_atelier estilos                              # presets disponíveis
    python -m pixel_atelier registrar-estilo estilo.json [--nome nome] [--sobrescrever]
    python -m pixel_atelier mcp [--raiz pasta]                   # servidor MCP por stdio (extra [mcp])

Sem `--pasta`, `gerar` grava ao lado do arquivo da receita (ou na pasta atual, com "-").
Receita inválida sai com código 2 e a lista de problemas.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .estilo import descrever_estilos, registrar_estilo
from .gerador import gerar
from .receita import ErroDeReceita, descrever_formas, ler_receita


def _gerar(args: argparse.Namespace) -> int:
    if args.receita == "-":
        fonte, pasta_padrao = sys.stdin.read(), Path(".")
    else:
        fonte, pasta_padrao = Path(args.receita), Path(args.receita).parent
    try:
        resultado = gerar(ler_receita(fonte), pasta=args.pasta or pasta_padrao)
    except ErroDeReceita as erro:
        print(erro, file=sys.stderr)
        return 2
    print(resultado.resumo())
    return 0


def _registrar(args: argparse.Namespace) -> int:
    try:
        destino = registrar_estilo(Path(args.arquivo), args.nome, sobrescrever=args.sobrescrever)
    except (OSError, KeyError, ValueError, TypeError) as erro:
        print(f"estilo não registrado: {erro.args[0] if erro.args else erro}", file=sys.stderr)
        return 2
    print(f"preset {destino.stem} gravado em {destino.as_posix()}")
    return 0


def _mcp(args: argparse.Namespace) -> int:
    try:
        from .servidor import criar_servidor
    except ImportError as erro:
        if not (erro.name or "").startswith("mcp"):
            raise
        print("o servidor MCP precisa do extra mcp: pip install pixel-atelier[mcp]", file=sys.stderr)
        return 1
    raiz = args.raiz or Path.cwd()
    if not raiz.is_dir():
        print(f"raiz {raiz.as_posix()} não é uma pasta", file=sys.stderr)
        return 2
    os.chdir(raiz)  # estilo por caminho dentro da receita também parte da raiz
    criar_servidor(Path.cwd()).run("stdio")
    return 0


def main(argv: list[str] | None = None) -> int:
    for saida in (sys.stdout, sys.stderr):  # acento certo também quando a saída vai para um pipe
        if hasattr(saida, "reconfigure"):
            saida.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="pixel-atelier", description="Pixel art a partir de receitas curtas.")
    comandos = parser.add_subparsers(dest="comando", required=True)

    p = comandos.add_parser("gerar", help="desenha uma receita JSON")
    p.add_argument("receita", help='arquivo da receita, ou "-" para ler da entrada padrão')
    p.add_argument("--pasta", "-o", type=Path, help="onde gravar (padrão: ao lado da receita)")
    p.set_defaults(funcao=_gerar)

    p = comandos.add_parser("formas", help="lista as formas e os parâmetros")
    p.set_defaults(funcao=lambda _: print(descrever_formas()) or 0)

    p = comandos.add_parser("estilos", help="lista os presets de estilo")
    p.set_defaults(funcao=lambda _: print(descrever_estilos()) or 0)

    p = comandos.add_parser("registrar-estilo", help="guarda um estilo JSON como preset com nome")
    p.add_argument("arquivo", help='JSON do estilo (aceita "base" para partir de um preset)')
    p.add_argument("--nome", help="nome do preset (padrão: o campo nome do JSON)")
    p.add_argument("--sobrescrever", action="store_true", help="troca um preset do usuário que já existe")
    p.set_defaults(funcao=_registrar)

    p = comandos.add_parser("mcp", help="sobe o servidor MCP por stdio")
    p.add_argument("--raiz", type=Path, help="única pasta onde o servidor lê e grava (padrão: a atual)")
    p.set_defaults(funcao=_mcp)

    args = parser.parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    sys.exit(main())
