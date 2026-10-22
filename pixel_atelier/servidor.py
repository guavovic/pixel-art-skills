"""Servidor MCP (stdio): as mesmas ferramentas da linha de comando, para qualquer agente que fale MCP.

    pip install pixel-atelier[mcp]
    pixel-atelier mcp [--raiz pasta]

Toda ferramenta responde em texto curto e nunca devolve a imagem. Erro de receita volta como a
lista de problemas, sem stack trace.

Regra dos caminhos: tudo que o servidor lê ou grava por caminho (receita, pasta de saída, JSON
de estilo) fica dentro da raiz, que é a pasta de `--raiz` ou, sem ela, a pasta onde o servidor
subiu. Caminho relativo parte da raiz; caminho absoluto vale só se cair dentro dela; `..` ou
atalho que leve para fora é recusado. A exceção é `registrar_estilo`, que grava na pasta de
presets do usuário (a mesma da linha de comando), com nome validado.

Ferramenta nova entra em `criar_servidor` com `@ferramenta(name=...)`: uma função por ferramenta,
com a docstring curta (é a descrição que o agente lê a cada sessão).
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .estilo import descrever_estilos, registrar_estilo
from .gerador import gerar
from .receita import ErroDeReceita, descrever_formas
from .revisao import revisar

INSTRUCOES = ("Pixel art a partir de uma receita JSON curta. Veja descrever_formas e listar_estilos, "
              "depois gerar e revisar. Respostas em texto; abra o PNG só na aprovação final.")

SO_LEITURA = ToolAnnotations(read_only_hint=True)


def dentro_da_raiz(raiz: Path, caminho: str | Path, o_que: str) -> Path:
    """Caminho absoluto dentro da raiz; fora dela levanta `ToolError`."""
    destino = (raiz / caminho).resolve()  # `raiz / absoluto` dá o absoluto
    if not destino.is_relative_to(raiz):
        raise ToolError(f"{o_que} {str(caminho)!r} fica fora da raiz {raiz.as_posix()}; use um caminho dentro dela")
    return destino


def criar_servidor(raiz: str | Path | None = None) -> MCPServer:
    """Servidor com as ferramentas do ateliê. `raiz` limita onde ele lê e grava (padrão: pasta atual)."""
    raiz = Path(raiz or Path.cwd()).resolve()
    servidor = MCPServer("pixel-atelier", instructions=INSTRUCOES, version=__version__)

    def ferramenta(**opcoes: Any):
        return servidor.tool(structured_output=False, **opcoes)  # só o texto, sem cópia estruturada

    @ferramenta(name="gerar")
    def _gerar(
        receita: Annotated[dict[str, Any] | str, Field(description="objeto da receita ou caminho do JSON")],
        pasta: Annotated[str | None, Field(description="onde gravar (padrão: ao lado da receita, ou a raiz)")] = None,
    ) -> str:
        """Desenha a receita, grava os PNGs e responde com o resumo (arquivos, cores, cada camada)."""
        if isinstance(receita, str) and not receita.lstrip().startswith("{"):
            arquivo = dentro_da_raiz(raiz, receita, "receita")
            if not arquivo.is_file():
                raise ToolError(f"arquivo {receita!r} não existe dentro da raiz {raiz.as_posix()}")
            receita, padrao = arquivo, arquivo.parent
        else:
            padrao = raiz
        saida = dentro_da_raiz(raiz, pasta, "pasta") if pasta else padrao
        try:
            return gerar(receita, pasta=saida).resumo(base=raiz)
        except ErroDeReceita as erro:
            raise ToolError(str(erro)) from None

    @ferramenta(name="revisar", annotations=SO_LEITURA)
    def _revisar(
        imagem: Annotated[str, Field(description="caminho do PNG da cena ou do sprite")],
        camadas: Annotated[str | None, Field(description="pasta das camadas (padrão: <cena>/ ao lado)")] = None,
        fundo: Annotated[str | None, Field(description="cena por trás do sprite")] = None,
        posicao: Annotated[list[int] | None, Field(description="[x, y] do sprite no fundo (padrão: no meio)",
                                                   min_length=2, max_length=2)] = None,
        estilo: Annotated[str | None, Field(description="preset ou .json para conferir a paleta")] = None,
    ) -> str:
        """Confere a imagem pelas regras de pixel art e responde com o relatório: ok ou alerta por regra."""
        arquivo = dentro_da_raiz(raiz, imagem, "imagem")
        if not arquivo.is_file():
            raise ToolError(f"arquivo {imagem!r} não existe dentro da raiz {raiz.as_posix()}")
        if estilo and estilo.endswith(".json"):
            estilo = dentro_da_raiz(raiz, estilo, "estilo")
        try:
            return revisar(arquivo, camadas=dentro_da_raiz(raiz, camadas, "camadas") if camadas else None,
                           fundo=dentro_da_raiz(raiz, fundo, "fundo") if fundo else None,
                           posicao=tuple(posicao) if posicao else None, estilo=estilo).resumo()
        except (OSError, KeyError, ValueError) as erro:
            raise ToolError(f"revisão não feita: {erro.args[0] if erro.args else erro}") from None

    @ferramenta(name="descrever_formas", annotations=SO_LEITURA)
    def _descrever_formas() -> str:
        """Formas da receita e os parâmetros de cada uma, com o padrão."""
        return descrever_formas()

    @ferramenta(name="listar_estilos", annotations=SO_LEITURA)
    def _listar_estilos() -> str:
        """Presets de estilo (do pacote e do usuário), um por linha com a descrição."""
        return descrever_estilos()

    @ferramenta(name="registrar_estilo")
    def _registrar_estilo(
        estilo: Annotated[dict[str, Any] | str, Field(description='objeto do estilo (aceita "base") ou caminho .json')],
        nome: Annotated[str | None, Field(description="nome do preset (padrão: o campo nome)")] = None,
        sobrescrever: bool = False,
    ) -> str:
        """Guarda um estilo como preset com nome, para usar depois em "estilo" da receita."""
        if isinstance(estilo, str):
            if not estilo.endswith(".json"):
                raise ToolError('estilo deve ser um objeto ou o caminho de um arquivo .json')
            estilo = dentro_da_raiz(raiz, estilo, "estilo")
        try:
            destino = registrar_estilo(estilo, nome, sobrescrever=sobrescrever)
        except (OSError, KeyError, ValueError, TypeError) as erro:
            raise ToolError(f"estilo não registrado: {erro.args[0] if erro.args else erro}") from None
        return f"preset {destino.stem} gravado em {destino.as_posix()}"

    return servidor
