"""Embalagens de cada ferramenta: geradas de uma fonte só e em dia com ela."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("embalar", RAIZ / "scripts" / "embalar.py")
embalar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embalar)

FERRAMENTAS = {"gerar", "revisar", "descrever_formas", "listar_estilos", "registrar_estilo", "ref", "guia"}


def test_embalagens_em_dia_com_a_fonte():
    faltam = embalar.diferencas()
    assert not faltam, f"rode python scripts/embalar.py; desatualizados: {faltam}"


def test_ferramentas_lidas_do_servidor():
    assert {nome for nome, _ in embalar.ferramentas(RAIZ)} == FERRAMENTAS


def test_ferramentas_iguais_as_do_servidor_de_verdade(tmp_path):
    pytest.importorskip("mcp")
    import asyncio

    from mcp import Client

    from pixel_atelier.servidor import criar_servidor

    async def rodar():
        async with Client(criar_servidor(tmp_path)) as cliente:
            return {f.name: f.description for f in (await cliente.list_tools()).tools}

    assert dict(embalar.ferramentas(RAIZ)) == asyncio.run(rodar())


def test_cada_embalagem_registra_o_servidor_e_leva_o_fluxo():
    arquivos = embalar.montar()
    servidores = {
        "embalagens/claude-code/.mcp.json": lambda d: d["mcpServers"],
        "embalagens/gemini/gemini-extension.json": lambda d: d["mcpServers"],
        "embalagens/cursor/.cursor/mcp.json": lambda d: d["mcpServers"],
        "embalagens/copilot/.vscode/mcp.json": lambda d: d["servers"],
    }
    for caminho, pegar in servidores.items():
        servidor = pegar(json.loads(arquivos[caminho]))["pixel-atelier"]
        assert servidor["command"] == "pixel-atelier" and servidor["args"][0] == "mcp", caminho
    codex = tomllib.loads(arquivos["embalagens/codex/.codex/config.toml"])
    assert codex["mcp_servers"]["pixel-atelier"] == {"command": "pixel-atelier", "args": ["mcp"]}

    texto = {"embalagens/claude-code/skills/pixel-atelier/SKILL.md", "embalagens/codex/.agents/skills/pixel-atelier/SKILL.md",
             "embalagens/gemini/GEMINI.md", "embalagens/cursor/.cursor/rules/pixel-atelier.mdc",
             "embalagens/copilot/.github/copilot-instructions.md"}
    for caminho in texto:
        conteudo = arquivos[caminho]
        assert "Não edite à mão" in conteudo, caminho
        assert all(f"`{nome}`" in conteudo for nome in FERRAMENTAS), caminho
        assert "## Fluxo de trabalho" in conteudo and "**Aprovação final**" in conteudo, caminho


def test_skills_com_frontmatter_do_padrao():
    arquivos = embalar.montar()
    for caminho in ("embalagens/claude-code/skills/pixel-atelier/SKILL.md",
                    "embalagens/codex/.agents/skills/pixel-atelier/SKILL.md"):
        cabecalho = arquivos[caminho].split("---\n")[1]
        assert 'name: "pixel-atelier"' in cabecalho
        assert len(embalar.DESCRICAO_SKILL) <= 1024  # limite do padrão Agent Skills


def test_marketplace_aponta_para_o_plugin():
    arquivos = embalar.montar()
    mercado = json.loads(arquivos[embalar.MARKETPLACE])
    plugin = json.loads(arquivos["embalagens/claude-code/.claude-plugin/plugin.json"])
    entrada = mercado["plugins"][0]
    assert entrada["name"] == plugin["name"] == "pixel-atelier"
    assert entrada["source"] == "./embalagens/claude-code"
    assert plugin["version"] == tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def test_fonte_mudada_deixa_a_embalagem_desatualizada(tmp_path):
    for parte in ("AGENTS.md", "pyproject.toml", "pixel_atelier/servidor.py", "pixel_atelier/guia",
                  "embalagens", ".claude-plugin"):
        origem, destino = RAIZ / parte, tmp_path / parte
        destino.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if origem.is_dir() else shutil.copy)(origem, destino)
    assert embalar.diferencas(tmp_path) == []

    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8").replace("Regras de arte\n", "Regras de arte\n- nova\n"),
                      encoding="utf-8")
    (tmp_path / "pixel_atelier" / "guia" / "novo.md").write_text("# Novo\n", encoding="utf-8")
    assert "embalagens/gemini/GEMINI.md" in embalar.diferencas(tmp_path)
    assert embalar.gravar(tmp_path) and embalar.diferencas(tmp_path) == []


def test_fonte_sem_secao_para_o_script(tmp_path):
    for parte in ("pyproject.toml", "pixel_atelier/servidor.py", "pixel_atelier/guia"):
        origem, destino = RAIZ / parte, tmp_path / parte
        destino.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if origem.is_dir() else shutil.copy)(origem, destino)
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\n\n## Por onde começar\nnada\n", encoding="utf-8")
    with pytest.raises(embalar.ErroDeFonte, match="Fluxo de trabalho"):
        embalar.montar(tmp_path)
