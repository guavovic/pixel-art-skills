"""Linha de comando. Tudo responde em texto curto.

    python -m pixel_atelier gerar receita.json [--pasta saida]   # "-" lê a receita da entrada padrão
    python -m pixel_atelier revisar cena.png [--fundo cena.png] [--estilo nome]   # relatório em texto
    python -m pixel_atelier formas                               # parâmetros de cada forma, com o padrão
    python -m pixel_atelier estilos                              # presets disponíveis
    python -m pixel_atelier registrar-estilo estilo.json [--nome nome] [--sobrescrever]
    python -m pixel_atelier ref referencia.png [--nome nome] [--base preset] [--cores 32] [--sobrescrever]
    python -m pixel_atelier mcp [--raiz pasta]                   # servidor MCP por stdio (extra [mcp])

Sem `--pasta`, `gerar` grava ao lado do arquivo da receita (ou na pasta atual, com "-").
Receita inválida sai com código 2 e a lista de problemas. `revisar` sai com 0 mesmo com alerta
(o relatório é a resposta) e com 2 quando não consegue ler a imagem. `ref` grava o preset tirado
da imagem e responde com o resumo (paleta, rampas, pixel e faixa de valor).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .estilo import descrever_estilos, registrar_estilo
from .gerador import gerar
from .receita import ErroDeReceita, descrever_formas, ler_receita
from .referencia import CORES, ref
from .revisao import revisar


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


def _revisar(args: argparse.Namespace) -> int:
    try:
        revisao = revisar(args.imagem, camadas=args.camadas, fundo=args.fundo,
                          posicao=tuple(args.posicao) if args.posicao else None, estilo=args.estilo)
    except (OSError, KeyError, ValueError) as erro:
        print(f"revisão não feita: {erro.args[0] if erro.args else erro}", file=sys.stderr)
        return 2
    print(revisao.resumo())
    return 0


def _registrar(args: argparse.Namespace) -> int:
    try:
        destino = registrar_estilo(Path(args.arquivo), args.nome, sobrescrever=args.sobrescrever)
    except (OSError, KeyError, ValueError, TypeError) as erro:
        print(f"estilo não registrado: {erro.args[0] if erro.args else erro}", file=sys.stderr)
        return 2
    print(f"preset {destino.stem} gravado em {destino.as_posix()}")
    return 0


def _ref(args: argparse.Namespace) -> int:
    try:
        referencia = ref(args.imagem, args.nome, base=args.base, cores=args.cores, sobrescrever=args.sobrescrever)
    except (OSError, KeyError, ValueError, TypeError) as erro:
        print(f"preset não gravado: {erro.args[0] if erro.args else erro}", file=sys.stderr)
        return 2
    print(referencia.resumo())
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

    p = comandos.add_parser("revisar", help="confere uma imagem pelas regras de pixel art")
    p.add_argument("imagem", type=Path, help="PNG da cena ou do sprite (ampliado também serve)")
    p.add_argument("--camadas", type=Path, help="pasta das camadas (padrão: a pasta <cena>/ ao lado, se existir)")
    p.add_argument("--fundo", type=Path, help="cena por trás do sprite, para medir contraste e legibilidade")
    p.add_argument("--posicao", type=int, nargs=2, metavar=("X", "Y"),
                   help="canto do sprite no fundo (padrão: no meio)")
    p.add_argument("--estilo", help="confere as cores contra a paleta deste estilo")
    p.set_defaults(funcao=_revisar)

    p = comandos.add_parser("formas", help="lista as formas e os parâmetros")
    p.set_defaults(funcao=lambda _: print(descrever_formas()) or 0)

    p = comandos.add_parser("estilos", help="lista os presets de estilo")
    p.set_defaults(funcao=lambda _: print(descrever_estilos()) or 0)

    p = comandos.add_parser("registrar-estilo", help="guarda um estilo JSON como preset com nome")
    p.add_argument("arquivo", help='JSON do estilo (aceita "base" para partir de um preset)')
    p.add_argument("--nome", help="nome do preset (padrão: o campo nome do JSON)")
    p.add_argument("--sobrescrever", action="store_true", help="troca um preset do usuário que já existe")
    p.set_defaults(funcao=_registrar)

    p = comandos.add_parser("ref", help="tira o estilo de uma imagem de referência e grava como preset")
    p.add_argument("imagem", type=Path, help="PNG de referência (ampliado também serve)")
    p.add_argument("--nome", help="nome do preset (padrão: o do arquivo, minúsculo com hífens)")
    p.add_argument("--base", default="snes-diurno", help="preset que dá o que a imagem não diz (padrão: snes-diurno)")
    p.add_argument("--cores", type=int, default=CORES, help=f"máximo de cores da paleta, de 2 a 256 (padrão: {CORES})")
    p.add_argument("--sobrescrever", action="store_true", help="troca um preset do usuário que já existe")
    p.set_defaults(funcao=_ref)

    p = comandos.add_parser("mcp", help="sobe o servidor MCP por stdio")
    p.add_argument("--raiz", type=Path, help="única pasta onde o servidor lê e grava (padrão: a atual)")
    p.set_defaults(funcao=_mcp)

    args = parser.parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    sys.exit(main())
