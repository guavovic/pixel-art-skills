"""Servidor MCP: as ferramentas chamadas por um cliente MCP de verdade, em processo e por stdio."""
from __future__ import annotations

import asyncio
import json
import sys

import pytest

pytest.importorskip("mcp")

from mcp import Client, StdioServerParameters  # noqa: E402

from pixel_atelier import carregar_estilo  # noqa: E402
from pixel_atelier.servidor import criar_servidor  # noqa: E402

PEQUENA = {"cena": "mcp", "tamanho": [64, 32], "saida": "composto",
           "camadas": [{"forma": "ceu"}, {"forma": "terreno", "seed": 3}]}


def chamar(servidor, ferramenta: str, **argumentos) -> tuple[bool, str]:
    """(deu erro?, texto da resposta) de uma chamada pelo cliente MCP."""
    async def rodar():
        async with Client(servidor) as cliente:
            return await cliente.call_tool(ferramenta, argumentos)

    resposta = asyncio.run(rodar())
    assert len(resposta.content) == 1 and resposta.content[0].type == "text"  # só texto, nunca imagem
    return resposta.is_error, resposta.content[0].text


def test_lista_as_ferramentas_so_com_texto(tmp_path):
    async def rodar():
        async with Client(criar_servidor(tmp_path)) as cliente:
            return (await cliente.list_tools()).tools

    ferramentas = {f.name: f for f in asyncio.run(rodar())}
    assert set(ferramentas) == {"gerar", "descrever_formas", "listar_estilos", "registrar_estilo"}
    assert all(f.output_schema is None for f in ferramentas.values())  # sem cópia estruturada do texto
    assert all(len(f.description) < 120 for f in ferramentas.values())


def test_gerar_com_objeto_grava_na_pasta_e_responde_o_resumo(tmp_path):
    erro, texto = chamar(criar_servidor(tmp_path), "gerar", receita=PEQUENA, pasta="saida")
    assert not erro
    assert (tmp_path / "saida" / "mcp.png").is_file()
    assert texto.splitlines()[:2] == ["mcp: 64x32, estilo snes-diurno, com laço, seed 0, 2 camadas",
                                      "composto: saida/mcp.png"]  # caminho relativo à raiz


def test_gerar_com_caminho_grava_ao_lado_da_receita(tmp_path):
    (tmp_path / "cenas").mkdir()
    (tmp_path / "cenas" / "receita.json").write_text(json.dumps(PEQUENA), encoding="utf-8")
    erro, texto = chamar(criar_servidor(tmp_path), "gerar", receita="cenas/receita.json")
    assert not erro and "composto: cenas/mcp.png" in texto
    assert (tmp_path / "cenas" / "mcp.png").is_file()


def test_gerar_com_texto_json_grava_na_raiz(tmp_path):
    erro, _ = chamar(criar_servidor(tmp_path), "gerar", receita=json.dumps(PEQUENA))
    assert not erro and (tmp_path / "mcp.png").is_file()


def test_receita_invalida_volta_a_lista_de_problemas(tmp_path):
    ruim = {"tamanho": [100, 32], "camadas": [{"forma": "arvores"}]}
    erro, texto = chamar(criar_servidor(tmp_path), "gerar", receita=ruim, pasta="saida")
    assert erro
    assert "receita inválida:" in texto and "quis dizer 'arvore'?" in texto and "múltipla de 8" in texto
    assert "Traceback" not in texto
    assert not (tmp_path / "saida").exists()


@pytest.mark.parametrize("argumentos", [
    {"receita": PEQUENA, "pasta": "../fora"},
    {"receita": PEQUENA, "pasta": "C:/fora" if sys.platform == "win32" else "/tmp/fora"},
    {"receita": "../receita.json"},
])
def test_caminho_fora_da_raiz_e_recusado(tmp_path, argumentos):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    (tmp_path / "receita.json").write_text(json.dumps(PEQUENA), encoding="utf-8")
    erro, texto = chamar(criar_servidor(raiz), "gerar", **argumentos)
    assert erro and "fora da raiz" in texto
    assert not (tmp_path / "fora").exists() and not (tmp_path / "mcp.png").exists()


def test_caminho_absoluto_dentro_da_raiz_vale(tmp_path):
    erro, _ = chamar(criar_servidor(tmp_path), "gerar", receita=PEQUENA, pasta=str(tmp_path / "saida"))
    assert not erro and (tmp_path / "saida" / "mcp.png").is_file()


def test_receita_que_nao_existe(tmp_path):
    erro, texto = chamar(criar_servidor(tmp_path), "gerar", receita="nada.json")
    assert erro and "'nada.json' não existe" in texto


def test_descrever_formas_e_listar_estilos(tmp_path):
    servidor = criar_servidor(tmp_path)
    erro, formas = chamar(servidor, "descrever_formas")
    assert not erro and formas.splitlines()[1].startswith("ceu: ") and "arvore: " in formas
    erro, estilos = chamar(servidor, "listar_estilos")
    assert not erro
    nomes = {linha.split(":")[0] for linha in estilos.splitlines()}
    assert {"game-boy", "metroidvania-noturno", "snes-diurno"} <= nomes
    assert "snes-diurno: Dia claro" in estilos


def test_registrar_estilo_por_objeto_e_por_arquivo(tmp_path):
    servidor = criar_servidor(tmp_path)
    erro, texto = chamar(servidor, "registrar_estilo", estilo={"base": "game-boy", "contorno": False},
                         nome="mcp-liso")
    assert not erro and texto.startswith("preset mcp-liso gravado em ")
    assert carregar_estilo("mcp-liso").contorno is False
    _, estilos = chamar(servidor, "listar_estilos")
    assert "mcp-liso" in estilos

    (tmp_path / "estilo.json").write_text('{"base": "snes-diurno", "nome": "mcp-arquivo"}', encoding="utf-8")
    erro, texto = chamar(servidor, "registrar_estilo", estilo="estilo.json")
    assert not erro and "preset mcp-arquivo gravado" in texto

    erro, texto = chamar(servidor, "registrar_estilo", estilo={"base": "game-boy"}, nome="snes-diurno")
    assert erro and "estilo não registrado: o preset 'snes-diurno' vem com o pacote" in texto
    erro, texto = chamar(servidor, "registrar_estilo", estilo="game-boy")
    assert erro and "objeto ou o caminho de um arquivo .json" in texto


def test_sobe_por_stdio_com_o_comando_mcp(tmp_path):
    parametros = StdioServerParameters(command=sys.executable,
                                       args=["-m", "pixel_atelier", "mcp", "--raiz", str(tmp_path)])

    async def rodar():
        async with Client(parametros) as cliente:
            return await cliente.call_tool("gerar", {"receita": PEQUENA, "pasta": "saida"})

    resposta = asyncio.run(rodar())
    assert not resposta.is_error and "composto: saida/mcp.png" in resposta.content[0].text
    assert (tmp_path / "saida" / "mcp.png").is_file()
