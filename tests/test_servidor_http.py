"""Servidor MCP por HTTP: o comando `mcp --http`, o token na URL e um cliente MCP de verdade, sem rede."""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")

import httpx2  # noqa: E402
from mcp import Client  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

from pixel_atelier.__main__ import main  # noqa: E402
from pixel_atelier.servidor import VARIAVEL_DO_TOKEN, criar_servidor, opcoes_http  # noqa: E402

TOKEN = "t" * 43
INICIAR = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                      "clientInfo": {"name": "teste", "version": "0"}}}
CABECALHOS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def subidas(monkeypatch, tmp_path):
    """Troca o `run` do servidor por um que só anota o transporte e as opções."""
    anotadas = []
    monkeypatch.setattr(MCPServer, "run", lambda servidor, transporte="stdio", **opcoes: anotadas.append(
        (transporte, opcoes)))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(VARIAVEL_DO_TOKEN, raising=False)
    return anotadas


def test_sem_http_continua_no_stdio(subidas):
    assert main(["mcp"]) == 0
    assert subidas == [("stdio", {})]


def test_http_sobe_em_127_0_0_1_com_token_novo_a_cada_vez(subidas, capsys):
    assert main(["mcp", "--http"]) == 0
    assert main(["mcp", "--http"]) == 0
    (transporte, opcoes), (_, outras) = subidas
    assert transporte == "streamable-http"
    assert (opcoes["host"], opcoes["port"]) == ("127.0.0.1", 8000)
    caminho = opcoes["streamable_http_path"]
    assert caminho.startswith("/") and caminho.endswith("/mcp") and len(caminho) > 40
    assert caminho != outras["streamable_http_path"]
    assert f"http://127.0.0.1:8000{caminho}" in capsys.readouterr().out


def test_http_com_host_porta_e_token_da_variavel(subidas, monkeypatch):
    monkeypatch.setenv(VARIAVEL_DO_TOKEN, TOKEN)
    assert main(["mcp", "--http", "--host", "0.0.0.0", "--porta", "9001"]) == 0
    _, opcoes = subidas[0]
    assert (opcoes["host"], opcoes["port"], opcoes["streamable_http_path"]) == ("0.0.0.0", 9001, f"/{TOKEN}/mcp")


@pytest.mark.parametrize("token", ["curto", "x" * 40 + "/../"])
def test_http_recusa_token_fraco_da_variavel(subidas, monkeypatch, capsys, token):
    monkeypatch.setenv(VARIAVEL_DO_TOKEN, token)
    assert main(["mcp", "--http"]) == 2
    assert subidas == [] and VARIAVEL_DO_TOKEN in capsys.readouterr().err


def test_host_e_porta_sem_http_sao_recusados(subidas, capsys):
    assert main(["mcp", "--porta", "9001"]) == 2
    assert subidas == [] and "--http" in capsys.readouterr().err


def conversar(raiz, conversa):
    """Roda `conversa(cliente_http)` contra o app HTTP do servidor, em processo e sem rede."""
    app = criar_servidor(raiz).streamable_http_app(**opcoes_http(TOKEN))

    async def rodar():
        async with app.router.lifespan_context(app):
            transporte = httpx2.ASGITransport(app=app)
            async with httpx2.AsyncClient(transport=transporte, base_url="http://teste") as cliente:
                return await conversa(cliente)

    return asyncio.run(rodar())


@pytest.mark.parametrize("caminho", ["/mcp", "/outro-token/mcp", f"/{TOKEN}", f"/{TOKEN[:-1]}/mcp"])
def test_http_recusa_sem_o_token_certo(tmp_path, caminho):
    async def conversa(cliente):
        return await cliente.post(caminho, json=INICIAR, headers=CABECALHOS)

    assert conversar(tmp_path, conversa).status_code == 404


def test_http_com_token_inicia_lista_e_chama_ferramenta(tmp_path):
    async def conversa(cliente):
        resposta_crua = await cliente.post(f"/{TOKEN}/mcp", json=INICIAR,
                                           headers={**CABECALHOS, "Host": "exemplo.trycloudflare.com"})
        url = f"http://teste/{TOKEN}/mcp"
        async with Client(streamable_http_client(url, http_client=cliente)) as mcp:
            ferramentas = (await mcp.list_tools()).tools
            gerado = await mcp.call_tool("gerar", {"receita": {"cena": "http", "tamanho": [64, 32],
                                                               "camadas": [{"forma": "ceu"}]}})
        return resposta_crua, ferramentas, gerado

    resposta_crua, ferramentas, gerado = conversar(tmp_path, conversa)
    assert resposta_crua.status_code == 200
    assert resposta_crua.headers["content-type"].startswith("application/json")  # sem SSE, que o túnel não repassa
    assert resposta_crua.json()["result"]["serverInfo"]["name"] == "pixel-atelier"
    assert "gerar" in {f.name for f in ferramentas}
    assert not gerado.is_error
    assert (tmp_path / "http.png").is_file()  # o PNG fica na raiz do projeto
