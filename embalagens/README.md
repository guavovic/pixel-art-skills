<!-- Arquivo gerado por scripts/embalar.py a partir de AGENTS.md, pixel_atelier/guia/, pixel_atelier/servidor.py e pyproject.toml. Não edite à mão: mude a fonte e rode o script de novo. -->

# Embalagens

O pixel-atelier no formato de cada ferramenta de agente. Tudo aqui é gerado por `python scripts/embalar.py` a partir de `AGENTS.md`, do guia, de `pixel_atelier/servidor.py` e do `pyproject.toml`: para mudar, edite a fonte e rode o script. Cada embalagem registra o servidor MCP e leva o mesmo texto de fluxo (estilo ou `ref`, receita, `gerar`, `revisar` em texto, imagem só na aprovação final).

Antes de qualquer uma, instale o servidor:

```
pip install "pixel-atelier[mcp] @ git+https://github.com/guavovic/pixel-atelier"
```

| Pasta | Ferramenta | O que tem | Onde colocar |
|---|---|---|---|
| `claude-code/` | Claude Code | plugin: `.claude-plugin/plugin.json`, `.mcp.json` e a skill `skills/pixel-atelier/` | `/plugin install pixel-atelier --marketplace guavovic/pixel-atelier`, ou em dois passos `/plugin marketplace add guavovic/pixel-atelier` e `/plugin install pixel-atelier@pixel-atelier` (o marketplace fica em `.claude-plugin/marketplace.json` na raiz do repositório); no clone, `claude --plugin-dir embalagens/claude-code` |
| `codex/` | OpenAI Codex | skill em `.agents/skills/pixel-atelier/` e servidor em `.codex/config.toml` | as duas pastas na raiz do projeto (o `.codex/config.toml` do projeto só vale em projeto confiável), ou a skill em `~/.agents/skills/` e o trecho `[mcp_servers.pixel-atelier]` em `~/.codex/config.toml` |
| `gemini/` | Gemini CLI | extensão: `gemini-extension.json` (com o servidor) e `GEMINI.md` | `gemini extensions install <clone>/embalagens/gemini` (ou `gemini extensions link` para acompanhar o clone); a extensão fica em `~/.gemini/extensions/pixel-atelier/`, com o nome do manifesto, então a pasta de origem pode se chamar `gemini` |
| `antigravity/` | Antigravity CLI | plugin: `plugin.json`, `mcp_config.json` (com o servidor) e a skill `skills/pixel-atelier/` | `agy plugin install <clone>/embalagens/antigravity`; o CLI copia para `~/.gemini/antigravity-cli/plugins/pixel-atelier/`, com o nome do manifesto |
| `cursor/` | Cursor | regra `.cursor/rules/pixel-atelier.mdc`, aplicada quando o agente acha que o pedido pede, e servidor em `.cursor/mcp.json` | a pasta `.cursor/` na raiz do projeto, ou o servidor em `~/.cursor/mcp.json` |
| `copilot/` | GitHub Copilot | `.github/copilot-instructions.md`, servidor do VS Code em `.vscode/mcp.json` e do Copilot CLI em `.github/mcp.json` | as duas pastas na raiz do repositório; se ele já tiver `copilot-instructions.md` ou `.github/mcp.json`, junte ao que existe. No Copilot CLI, um `.mcp.json` na mesma pasta ganha do `.github/mcp.json`; para valer em todo projeto, o trecho de `mcpServers` vai em `~/.copilot/mcp-config.json` |

Toda embalagem sobe o servidor com `python -m pixel_atelier mcp`, sem depender do comando `pixel-atelier` no PATH. É a ferramenta que roda esse `python`, com o PATH dela, então ele precisa ser o do ambiente onde o pacote foi instalado: instale fora de venv, abra a ferramenta com o venv ativado, ou troque `command` no arquivo de MCP pelo caminho absoluto do interpretador (`...\.venv\Scripts\python.exe` no Windows, `.../.venv/bin/python` no Linux e no macOS). `python` é o nome que o Windows e todo venv ativado têm; num Linux ou macOS fora de venv, onde só existe `python3`, troque por `python3`. Com `pipx` o pacote fica num ambiente à parte que o `python` não vê: nesse caso use `"command": "pixel-atelier"` e tire `-m` e `pixel_atelier` de `args`.

O servidor recebe a pasta do projeto pela variável de cada ferramenta (`${CLAUDE_PROJECT_DIR}`, `${workspacePath}`, `${workspaceFolder}`). O Codex, o Copilot CLI e o Antigravity CLI não documentam variável de pasta: neles o servidor sobe sem `--raiz` e usa a pasta em que a ferramenta o abre (no Codex, a pasta da sessão, conferido no código do Codex). Se a ferramenta abrir o servidor em outra pasta, acrescente `"--raiz", "<pasta do projeto>"` em `args`.

| Ferramenta | Situação |
|---|---|
| Claude Code | testado de ponta a ponta (#8) |
| OpenAI Codex, Gemini CLI, Antigravity CLI, Cursor, GitHub Copilot | formato validado pela documentação (`tests/test_formato_embalagens.py`) e servidor testado com cliente MCP; teste de ponta a ponta pendente |
