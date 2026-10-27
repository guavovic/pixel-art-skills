"""Formato de cada embalagem conferido contra a documentação oficial de cada ferramenta (issue #8).

Cada regra aqui é algo que a documentação (ou o código-fonte aberto da ferramenta) diz com todas as letras:
campo obrigatório, tipo, nome de chave, frontmatter, variável de pasta aceita, lugar do arquivo. A fonte vem
no comentário de cada bloco, consultada em 22/10/2026. O teste roda offline: nada é baixado em tempo de teste;
as listas de chaves aceitas foram copiadas do schema publicado quando existe um.

O que o formato não garante (a ferramenta abrir, achar a skill, chamar o servidor) é o teste de ponta a ponta,
feito no Claude Code e pendente nas outras ferramentas.
"""
from __future__ import annotations

import importlib.util
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import urlparse

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("embalar", RAIZ / "scripts" / "embalar.py")
embalar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embalar)

ARQUIVOS = embalar.montar()
_PROJETO = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]
PACOTE = _PROJETO["name"]  # plugin, marketplace, extensão do Gemini e plugin do Antigravity
(NOME, _ALVO), = _PROJETO["scripts"].items()  # skill, regra e servidor MCP
MODULO = _ALVO.split(":")[0].removesuffix(".__main__")


def json_de(caminho: str) -> dict:
    assert caminho in ARQUIVOS, f"{caminho} não é gerado"
    return json.loads(ARQUIVOS[caminho])


def frontmatter(caminho: str) -> dict[str, str | bool]:
    """Frontmatter YAML do arquivo. O gerador só escreve `chave: "texto"` ou `chave: true|false`;
    qualquer outra forma falha aqui, para não depender de um parser YAML."""
    texto = ARQUIVOS[caminho]
    assert texto.startswith("---\n"), f"{caminho} sem frontmatter YAML no começo"
    bloco, _, corpo = texto[4:].partition("\n---\n")
    assert corpo.strip(), f"{caminho} sem corpo depois do frontmatter"
    campos: dict[str, str | bool] = {}
    for linha in bloco.splitlines():
        chave, separador, valor = linha.partition(": ")
        assert separador and re.fullmatch(r"[A-Za-z][\w-]*", chave), f"{caminho}: linha fora do formato {linha!r}"
        if valor in ("true", "false"):
            campos[chave] = valor == "true"
        else:
            assert valor.startswith('"') and valor.endswith('"'), f"{caminho}: {chave} sem aspas duplas"
            campos[chave] = json.loads(valor)  # string YAML entre aspas duplas com \\ e \" também é JSON
    return campos


def variaveis(valor) -> set[str]:
    """Todas as `${...}` usadas em strings dentro de `valor` (dict, lista ou string)."""
    if isinstance(valor, dict):
        return set().union(*(variaveis(v) for v in valor.values())) if valor else set()
    if isinstance(valor, list):
        return set().union(*(variaveis(v) for v in valor)) if valor else set()
    return set(re.findall(r"\$\{([^}]*)\}", valor)) if isinstance(valor, str) else set()


def confere_servidor_stdio(servidor: dict, aceitas: set[str], obrigatorias: set[str], onde: str) -> None:
    """Regras comuns: chaves conhecidas, `command` sem argumento dentro, `args` lista de strings,
    e o servidor sobe por `python -m <pacote> mcp` (e `--raiz <pasta>` quando a ferramenta passa a pasta), sem
    depender do comando do pacote no PATH (issue #23)."""
    assert set(servidor) <= aceitas, f"{onde}: chaves desconhecidas {set(servidor) - aceitas}"
    assert obrigatorias <= set(servidor), f"{onde}: faltam {obrigatorias - set(servidor)}"
    assert isinstance(servidor["command"], str) and " " not in servidor["command"], onde
    assert isinstance(servidor["args"], list) and all(isinstance(a, str) for a in servidor["args"]), onde
    assert servidor["command"] == "python" and servidor["args"][:3] == ["-m", MODULO, "mcp"], onde
    assert servidor["args"][3:] in ([], ["--raiz", servidor["args"][-1]]), onde
    assert (RAIZ / MODULO / "__main__.py").is_file(), "sem __main__.py o python -m não sobe o servidor"


# ---------------------------------------------------------------- Agent Skills (Claude Code e Codex)
# https://agentskills.io/specification : name 1-64, [a-z0-9-], sem hífen no começo, no fim nem duplo,
# igual ao nome da pasta; description 1-1024. Claude Code: https://code.claude.com/docs/en/skills ;
# Codex lê .agents/skills (https://learn.chatgpt.com/docs/build-skills) e exige name e description.
NOME_SKILL = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
CAMPOS_SKILL = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


@pytest.mark.parametrize("caminho", [
    f"embalagens/claude-code/skills/{NOME}/SKILL.md",
    f"embalagens/codex/.agents/skills/{NOME}/SKILL.md",
    f"embalagens/antigravity/skills/{NOME}/SKILL.md",
])
def test_skill_no_padrao_agent_skills(caminho):
    campos = frontmatter(caminho)
    assert set(campos) <= CAMPOS_SKILL and {"name", "description"} <= set(campos), caminho
    nome = campos["name"]
    assert 1 <= len(nome) <= 64 and NOME_SKILL.fullmatch(nome), nome
    assert nome == Path(caminho).parent.name, "name tem que ser igual ao nome da pasta da skill"
    assert 1 <= len(campos["description"]) <= 1024


# ---------------------------------------------------------------- Claude Code
# Plugin: https://code.claude.com/docs/en/plugins-reference (manifest em .claude-plugin/plugin.json, `name`
# obrigatório em kebab-case, author objeto com name, homepage tem que ser URL, keywords lista; o resto fica
# na raiz do plugin: skills/<nome>/SKILL.md e .mcp.json). Variáveis em command/args/env de servidor stdio:
# ${CLAUDE_PLUGIN_ROOT}, ${CLAUDE_PLUGIN_DATA}, ${CLAUDE_PROJECT_DIR} e ${user_config.KEY}.
# Marketplace: https://code.claude.com/docs/en/plugins/marketplace-reference (name, owner e plugins
# obrigatórios; entrada com name e source; source relativa começa com ./, sem .., a partir da raiz do repositório).
CAMPOS_PLUGIN = {"$schema", "name", "displayName", "version", "description", "author", "homepage", "repository",
                 "license", "keywords", "metadata", "icon", "documentationUrl", "supportUrl", "privacyPolicyUrl",
                 "termsOfServiceUrl", "defaultEnabled", "dependencies", "settings", "userConfig", "types",
                 "channels", "skills", "commands", "agents", "hooks", "mcpServers", "lspServers", "outputStyles",
                 "workflows", "experimental"}
NOME_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")  # cada parte de plugin@marketplace
RESERVADOS_MARKETPLACE = {"claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
                          "anthropic-marketplace", "anthropic-plugins", "agent-skills", "inline", "builtin",
                          "skills-dir", "synced", "npm", "pip", "uv", "cargo", "github", "gh"}


def test_claude_code_plugin_json():
    base = "embalagens/claude-code"
    assert set(c for c in ARQUIVOS if c.startswith(f"{base}/.claude-plugin/")) == {
        f"{base}/.claude-plugin/plugin.json"}, "só o manifesto fica em .claude-plugin/; o resto vai na raiz"
    plugin = json_de(f"{base}/.claude-plugin/plugin.json")
    assert set(plugin) <= CAMPOS_PLUGIN, set(plugin) - CAMPOS_PLUGIN
    assert plugin["name"] == PACOTE and NOME_SKILL.fullmatch(plugin["name"])
    assert not re.match(r"(claude|anthropic|anthropics|cc-plugin)-", plugin["name"])
    for campo in ("version", "description", "repository", "license"):
        assert isinstance(plugin[campo], str) and plugin[campo], campo
    assert isinstance(plugin["author"], dict) and plugin["author"]["name"]
    assert set(plugin["author"]) <= {"name", "email", "url"}
    url = urlparse(plugin["homepage"])
    assert url.scheme == "https" and url.netloc, "homepage tem que ser URL, senão o plugin não carrega"
    assert isinstance(plugin["keywords"], list) and all(isinstance(k, str) for k in plugin["keywords"])
    assert f"{base}/skills/{NOME}/SKILL.md" in ARQUIVOS


def test_claude_code_mcp_json():
    servidores = json_de("embalagens/claude-code/.mcp.json")
    assert set(servidores) == {"mcpServers"}
    servidor = servidores["mcpServers"][NOME]
    confere_servidor_stdio(servidor, {"type", "command", "args", "env"}, {"command", "args"}, ".mcp.json")
    usadas = variaveis(servidor)
    assert usadas <= {"CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR"}, usadas
    assert servidor["args"][3:] == ["--raiz", "${CLAUDE_PROJECT_DIR}"]


def test_claude_code_marketplace_json():
    mercado = json_de(embalar.MARKETPLACE)
    assert embalar.MARKETPLACE == ".claude-plugin/marketplace.json"  # caminho que o marketplace add procura
    assert {"name", "owner", "plugins"} <= set(mercado)
    assert NOME_ID.fullmatch(mercado["name"]) and ".." not in mercado["name"]
    assert mercado["name"].lower() not in RESERVADOS_MARKETPLACE and not mercado["name"].startswith("claudeai-")
    assert mercado["owner"]["name"] and set(mercado["owner"]) <= {"name", "email", "url"}
    assert mercado.get("description"), "sem description o claude plugin validate avisa"
    nomes = [p["name"] for p in mercado["plugins"]]
    assert len(nomes) == len(set(nomes))
    for entrada in mercado["plugins"]:
        assert {"name", "source"} <= set(entrada) and NOME_ID.fullmatch(entrada["name"])
        fonte = entrada["source"]
        assert fonte.startswith("./") and ".." not in fonte and "\\" not in fonte
        assert f"{fonte[2:]}/.claude-plugin/plugin.json" in ARQUIVOS, "source tem que apontar para um plugin"
        assert "version" not in entrada, "versão só no plugin.json (no marketplace o plugin.json ganha e avisa)"


# ---------------------------------------------------------------- OpenAI Codex
# https://learn.chatgpt.com/docs/extend/mcp?surface=cli : [mcp_servers.<nome>] em config.toml (o do projeto
# em .codex/config.toml, só em projeto confiável), command obrigatório, args, env, cwd opcionais.
# Chaves aceitas: definição RawMcpServerConfig (additionalProperties false) do schema publicado em
# https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json (commit a3d93e1e69).
# A doc não traz variável de pasta do projeto. Sem `cwd`, o Codex sobe o servidor na pasta da sessão:
# codex-rs/rmcp-client/src/stdio_server_launcher.rs (`cwd.unwrap_or(fallback_cwd)`) com fallback_cwd =
# config.cwd em codex-rs/core/src/session/mcp_runtime.rs. Por isso a embalagem não passa --raiz nem cwd.
CHAVES_CODEX = {"args", "auth", "bearer_token_env_var", "command", "cwd", "default_tools_approval_mode",
                "disabled_tools", "enabled", "enabled_tools", "env", "env_http_headers", "env_vars",
                "environment_id", "http_headers", "http_headers_helper", "name", "oauth", "oauth_resource",
                "omit_tools_from", "required", "scopes", "startup_readiness", "startup_timeout_ms",
                "startup_timeout_sec", "supports_parallel_tool_calls", "tool_input_schema_max_bytes",
                "tool_timeout_sec", "tools", "url"}


def test_codex_config_toml():
    config = tomllib.loads(ARQUIVOS["embalagens/codex/.codex/config.toml"])
    assert set(config) == {"mcp_servers"}
    servidor = config["mcp_servers"][NOME]
    confere_servidor_stdio(servidor, CHAVES_CODEX, {"command"}, "config.toml")
    assert not variaveis(servidor), "o Codex não documenta variável em config.toml"
    assert "cwd" not in servidor and "--raiz" not in servidor["args"], "sem cwd e sem --raiz: raiz = pasta da sessão"


def test_codex_skill_onde_o_codex_procura():
    assert f"embalagens/codex/.agents/skills/{NOME}/SKILL.md" in ARQUIVOS


# ---------------------------------------------------------------- Gemini CLI
# https://geminicli.com/docs/extensions/reference/ : gemini-extension.json na raiz da extensão; name em
# minúsculas, números e hífen; mcpServers aceita todas as opções de servidor menos `trust`; contextFileName
# (padrão GEMINI.md); variáveis ${extensionPath}, ${workspacePath}, ${/} (e ${pathSeparator} no código).
# Código (google-gemini/gemini-cli, commit c690b9df15), packages/cli/src/config/extension-manager.ts:
# name e version obrigatórios; validateName exige /^[a-zA-Z0-9-]+$/. O install copia para
# ~/.gemini/extensions/<name do manifesto> (extensions/storage.ts), então a pasta de origem (`gemini`)
# não precisa bater com o nome: a pasta instalada já sai com o nome certo.
# Chaves de servidor: MCPServerConfig de https://github.com/google-gemini/gemini-cli/blob/main/schemas/settings.schema.json ;
# `type` só aceita sse ou http (packages/core/src/config/config.ts), então servidor stdio vai sem type.
CAMPOS_GEMINI = {"name", "version", "description", "mcpServers", "contextFileName", "excludeTools", "settings",
                 "themes", "plan", "migratedTo"}
CHAVES_SERVIDOR_GEMINI = {"args", "authProviderType", "command", "cwd", "description", "env", "excludeTools",
                          "headers", "httpUrl", "includeTools", "oauth", "targetAudience", "targetServiceAccount",
                          "tcp", "timeout", "url"}  # `trust` e `extension` ficam de fora numa extensão


def test_gemini_extension_json():
    base = "embalagens/gemini"
    manifesto = json_de(f"{base}/gemini-extension.json")
    assert set(manifesto) <= CAMPOS_GEMINI, set(manifesto) - CAMPOS_GEMINI
    assert isinstance(manifesto["name"], str) and re.fullmatch(r"[a-z0-9-]+", manifesto["name"])
    assert manifesto["name"] == PACOTE
    assert isinstance(manifesto["version"], str) and manifesto["version"]
    servidor = manifesto["mcpServers"][NOME]
    confere_servidor_stdio(servidor, CHAVES_SERVIDOR_GEMINI, {"command", "args"}, "gemini-extension.json")
    assert variaveis(servidor) <= {"extensionPath", "workspacePath", "/", "pathSeparator"}
    assert servidor["args"][3:] == ["--raiz", "${workspacePath}"]
    contexto = manifesto["contextFileName"]
    assert f"{base}/{contexto}" in ARQUIVOS and ARQUIVOS[f"{base}/{contexto}"].strip()


# ---------------------------------------------------------------- Antigravity CLI
# Plugin: https://antigravity.google/docs/plugins : pasta com plugin.json (obrigatório), mcp_config.json,
# skills/<nome>/SKILL.md, agents/ e rules/; `name` obrigatório no CLI (`agy plugin install`), ^[a-zA-Z0-9_-]+$.
# Chaves do manifesto: schema https://antigravity.google/schemas/v1/plugin.json (additionalProperties false).
# MCP: https://antigravity.google/docs/mcp : mcpServers; stdio com command obrigatório, args, env, cwd e as
# opções comuns disabled, enabledTools, disabledTools, timeoutSeconds. Nenhuma variável de pasta documentada.
# Skill: https://antigravity.google/docs/skills : frontmatter com description obrigatória e name opcional.
# Consultado em 27/10/2026.
CAMPOS_ANTIGRAVITY = {"$schema", "author", "description", "disabled", "displayName", "display_name", "extensions",
                      "homepage", "keywords", "license", "logo", "name", "repository", "skills", "source",
                      "sourcePath", "source_path", "suggestedPrompts", "suggested_prompts", "version"}
CHAVES_SERVIDOR_ANTIGRAVITY = {"command", "args", "env", "cwd", "disabled", "enabledTools", "disabledTools",
                               "timeoutSeconds"}


def test_antigravity_plugin_json():
    base = "embalagens/antigravity"
    plugin = json_de(f"{base}/plugin.json")
    assert set(plugin) <= CAMPOS_ANTIGRAVITY, set(plugin) - CAMPOS_ANTIGRAVITY
    assert plugin["$schema"] == "https://antigravity.google/schemas/v1/plugin.json"
    assert plugin["name"] == PACOTE and re.fullmatch(r"[a-zA-Z0-9_-]+", plugin["name"])
    for campo in ("version", "description", "homepage", "repository", "license"):
        assert isinstance(plugin[campo], str) and plugin[campo], campo
    assert set(plugin["author"]) <= {"name", "email", "url"}
    assert all(isinstance(k, str) for k in plugin["keywords"])
    assert f"{base}/skills/{NOME}/SKILL.md" in ARQUIVOS


def test_antigravity_mcp_config_json():
    config = json_de("embalagens/antigravity/mcp_config.json")
    assert set(config) == {"mcpServers"}
    servidor = config["mcpServers"][NOME]
    confere_servidor_stdio(servidor, CHAVES_SERVIDOR_ANTIGRAVITY, {"command"}, "mcp_config.json")
    assert not variaveis(servidor), "o Antigravity não documenta variável de pasta"


# ---------------------------------------------------------------- Cursor
# Regras: https://cursor.com/docs/context/rules : .cursor/rules/*.mdc (um .md ali é ignorado), frontmatter
# description, globs, alwaysApply. alwaysApply false + description e sem globs = "Apply Intelligently".
# MCP: https://cursor.com/docs/context/mcp : .cursor/mcp.json com mcpServers; stdio com type "stdio" e
# command obrigatórios, args, env, envFile opcionais; variáveis ${env:NOME}, ${userHome}, ${workspaceFolder},
# ${workspaceFolderBasename}, ${pathSeparator}, ${/} em command, args, env, url e headers.
def test_cursor_regra_mdc():
    regras = [c for c in ARQUIVOS if c.startswith("embalagens/cursor/.cursor/rules/")]
    assert regras and all(c.endswith(".mdc") for c in regras)
    for caminho in regras:
        campos = frontmatter(caminho)
        assert set(campos) <= {"description", "globs", "alwaysApply"}, caminho
        assert campos["alwaysApply"] is False and campos["description"] and "globs" not in campos


def test_cursor_mcp_json():
    servidores = json_de("embalagens/cursor/.cursor/mcp.json")
    assert set(servidores) == {"mcpServers"}
    servidor = servidores["mcpServers"][NOME]
    confere_servidor_stdio(servidor, {"type", "command", "args", "env", "envFile"}, {"type", "command"},
                           ".cursor/mcp.json")
    assert servidor["type"] == "stdio"
    usadas = {v for v in variaveis(servidor) if not v.startswith("env:")}
    assert usadas <= {"userHome", "workspaceFolder", "workspaceFolderBasename", "pathSeparator", "/"}, usadas
    assert servidor["args"][3:] == ["--raiz", "${workspaceFolder}"]


# ---------------------------------------------------------------- GitHub Copilot
# Instruções: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
# (.github/copilot-instructions.md, Markdown sem frontmatter).
# VS Code: https://code.visualstudio.com/docs/copilot/reference/mcp-configuration : .vscode/mcp.json com
# `servers` (e `inputs`, `sandbox` opcionais); stdio com type "stdio" e command obrigatórios, args, env,
# envFile, cwd opcionais; nome sem espaço nem caractere especial. Variáveis predefinidas do VS Code:
# https://code.visualstudio.com/docs/reference/variables-reference
# Copilot CLI: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers
# (reconsultado em 27/10/2026): não lê .vscode/mcp.json; no projeto lê .mcp.json (da pasta atual até a raiz do
# repositório, ganha do .github/mcp.json na mesma pasta) e .github/mcp.json (o compartilhado, que vai no
# repositório); no usuário, ~/.copilot/mcp-config.json. mcpServers, servidor local com type "local", command,
# args, env e tools (padrão "*"). Nenhuma variável de pasta documentada.
VARIAVEIS_VSCODE = {"workspaceFolder", "workspaceFolderBasename", "userHome", "cwd", "pathSeparator", "/"}


def test_copilot_instrucoes():
    texto = ARQUIVOS["embalagens/copilot/.github/copilot-instructions.md"]
    assert not texto.startswith("---"), "copilot-instructions.md é Markdown puro, sem frontmatter"
    assert texto.strip()


def test_copilot_vscode_mcp_json():
    config = json_de("embalagens/copilot/.vscode/mcp.json")
    assert "servers" in config and set(config) <= {"servers", "inputs", "sandbox"}
    assert "mcpServers" not in config, "o VS Code usa servers, não mcpServers"
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+", nome) for nome in config["servers"])
    servidor = config["servers"][NOME]
    confere_servidor_stdio(servidor, {"type", "command", "args", "env", "envFile", "cwd"}, {"type", "command"},
                           ".vscode/mcp.json")
    assert servidor["type"] == "stdio"
    usadas = {v for v in variaveis(servidor) if not v.startswith(("env:", "input:"))}
    assert usadas <= VARIAVEIS_VSCODE, usadas
    assert servidor["args"][3:] == ["--raiz", "${workspaceFolder}"]


def test_copilot_cli_mcp_json():
    config = json_de("embalagens/copilot/.github/mcp.json")
    assert set(config) == {"mcpServers"}
    servidor = config["mcpServers"][NOME]
    confere_servidor_stdio(servidor, {"type", "command", "args", "env", "tools"}, {"type", "command"},
                           ".github/mcp.json")
    assert servidor["type"] == "local" and servidor["tools"] == ["*"]
    assert not variaveis(servidor), "o Copilot CLI não documenta variável de pasta"
