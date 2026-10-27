"""Gera a embalagem de cada ferramenta de agente a partir de uma fonte só.

Fonte (editada à mão):
    AGENTS.md                       seções "Por onde começar", "Fluxo de trabalho" e "Regras de arte"
    pixel_atelier/guia/             nomes dos capítulos
    pixel_atelier/servidor.py       ferramentas MCP (nome e docstring de cada uma)
    pyproject.toml                  pacote, versão, descrição e o comando (o servidor sobe com `python -m <módulo>`)

Saída (nunca editada à mão, sempre regenerada por este script):
    embalagens/claude-code/         plugin do Claude Code (.claude-plugin/plugin.json, .mcp.json, skill)
    embalagens/codex/               skill em .agents/skills e servidor em .codex/config.toml
    embalagens/gemini/              extensão do Gemini CLI (gemini-extension.json, GEMINI.md)
    embalagens/antigravity/         plugin do Antigravity CLI (plugin.json, mcp_config.json, skill)
    embalagens/cursor/              regra em .cursor/rules e servidor em .cursor/mcp.json
    embalagens/copilot/             .github/copilot-instructions.md, servidor do VS Code em .vscode/mcp.json
                                    e do Copilot CLI em .github/mcp.json
    embalagens/README.md            onde colocar cada uma
    .claude-plugin/marketplace.json marketplace do repositório, aponta para embalagens/claude-code

Uso (Python 3.11+, sem dependência):
    python scripts/embalar.py             regenera tudo
    python scripts/embalar.py --conferir  só confere; sai com 1 se alguma embalagem estiver desatualizada
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = "embalagens"
MARKETPLACE = ".claude-plugin/marketplace.json"

REPO = "https://github.com/guavovic/pixel-art-skills"
AUTOR = {"name": "Gustavo Victor", "url": "https://github.com/guavovic"}
# Vira True depois da primeira publicação no PyPI (.github/workflows/publicar.yml): todas as embalagens passam a
# mandar `pip install "<pacote>[mcp]"`. Depois de trocar, rode este script e atualize o comando no README.md e em
# docs/referencia.md (tests/test_embalagens.py confere que os dois batem com instalar()).
NO_PYPI = False
# Interpretador que sobe o servidor (`python -m pixel_atelier mcp`), igual em todas as embalagens: nenhuma das
# ferramentas tem campo por sistema no servidor MCP, então vale o nome que existe em mais lugares.
# `python` é o comando do Windows (o instalador do python.org e o venv do Windows não trazem python3; o
# `python3` do gerenciador de instalação "não é recomendado", docs.python.org/3/using/windows.html) e, pela
# PEP 394, "sempre disponível" dentro de um venv ativado em qualquer sistema. Os exemplos de servidor Python
# do Gemini CLI, do VS Code e do Claude Code também usam `python`. Linux e macOS fora de venv (só python3):
# o embalagens/README.md diz para trocar o comando.
PYTHON = "python"
DESCRICAO_SKILL = (
    "Pixel art por receita JSON curta com o servidor MCP pixel-atelier: cenário em camadas com laço, "
    "estilo tirado de uma imagem de referência e revisão das regras de pixel art em texto, sem abrir a imagem. "
    "Use quando o pedido for criar, ajustar ou revisar pixel art (cenário, parallax, paleta, sprite)."
)
SECOES_AGENTS = ("Por onde começar", "Fluxo de trabalho", "Regras de arte")
# Trechos do AGENTS.md que só fazem sentido dentro do repositório; cada um precisa existir na fonte.
TROCAS_AGENTS = [("Formato em `docs/referencia.md`, seção Receita.",
                  f"Formato na [seção Receita da referência]({REPO}/blob/main/docs/referencia.md#receita).")]

AVISO = ("Arquivo gerado por scripts/embalar.py a partir de AGENTS.md, pixel_atelier/guia/, "
         "pixel_atelier/servidor.py e pyproject.toml. Não edite à mão: mude a fonte e rode o script de novo.")


class ErroDeFonte(Exception):
    """A fonte não tem o que o script espera; melhor parar do que gerar embalagem errada."""


# ---------------------------------------------------------------- leitura da fonte

def ler(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8").replace("\r\n", "\n")


def projeto(raiz: Path) -> dict:
    """Do pyproject.toml: o pacote (nome do plugin, da extensão e do pip install), versão, descrição e o
    comando de [project.scripts], que dá nome à skill e ao servidor MCP e diz o módulo que `python -m` roda."""
    dados = tomllib.loads(ler(raiz / "pyproject.toml"))["project"]
    comandos = dados.get("scripts", {})
    if len(comandos) != 1:
        raise ErroDeFonte("pyproject.toml precisa de exatamente um comando em [project.scripts]")
    (nome, alvo), = comandos.items()
    modulo = alvo.split(":")[0].removesuffix(".__main__")
    if not (raiz / modulo / "__main__.py").is_file():
        raise ErroDeFonte(f"{modulo}/__main__.py não existe; sem ele `python -m {modulo}` não sobe o servidor")
    return {"pacote": dados["name"], "nome": nome, "versao": dados["version"], "descricao": dados["description"],
            "modulo": modulo}


def instalar(f: dict, no_pypi: bool = NO_PYPI) -> str:
    """O comando que instala o servidor. Enquanto o pacote não está no PyPI, vem do repositório."""
    if no_pypi:
        return f'pip install "{f["pacote"]}[mcp]"'
    return f'pip install "{f["pacote"]}[mcp] @ git+{REPO}"'


def secoes_agents(raiz: Path) -> str:
    """As seções de uso do AGENTS.md, na ordem, com os trechos de dentro do repositório trocados."""
    texto = ler(raiz / "AGENTS.md")
    partes = []
    for titulo in SECOES_AGENTS:
        achou = re.search(rf"^## {re.escape(titulo)}\n(.*?)(?=^## |\Z)", texto, re.M | re.S)
        if not achou:
            raise ErroDeFonte(f"AGENTS.md sem a seção '## {titulo}'")
        partes.append(f"## {titulo}\n{achou.group(1).strip()}\n")
    secoes = "\n".join(partes)
    for antes, depois in TROCAS_AGENTS:
        if antes not in secoes:
            raise ErroDeFonte(f"AGENTS.md sem o trecho {antes!r}; ajuste TROCAS_AGENTS em scripts/embalar.py")
        secoes = secoes.replace(antes, depois)
    return secoes


def capitulos(raiz: Path) -> list[str]:
    pasta = raiz / "pixel_atelier" / "guia"
    nomes = sorted(a.stem for a in pasta.glob("*.md") if a.stem != "indice")
    if not nomes:
        raise ErroDeFonte("pixel_atelier/guia/ sem capítulo")
    return nomes


def ferramentas(raiz: Path) -> list[tuple[str, str]]:
    """(nome, descrição) de cada ferramenta MCP, lidos de `@ferramenta(name=...)` em servidor.py."""
    arvore = ast.parse(ler(raiz / "pixel_atelier" / "servidor.py"))
    lista = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        for decorador in no.decorator_list:
            if isinstance(decorador, ast.Call) and getattr(decorador.func, "id", None) == "ferramenta":
                nome = next((k.value.value for k in decorador.keywords if k.arg == "name"), None)
                if not nome or not ast.get_docstring(no):
                    raise ErroDeFonte(f"ferramenta em servidor.py sem name ou sem docstring (linha {no.lineno})")
                lista.append((nome, " ".join(ast.get_docstring(no).split())))
    if not lista:
        raise ErroDeFonte("nenhuma @ferramenta(name=...) em pixel_atelier/servidor.py")
    return lista


def fonte(raiz: Path = RAIZ) -> dict:
    return {**projeto(raiz), "secoes": secoes_agents(raiz), "capitulos": capitulos(raiz),
            "ferramentas": ferramentas(raiz)}


# ---------------------------------------------------------------- texto comum

def instrucoes(f: dict) -> str:
    """O texto que toda embalagem carrega: servidor, ferramentas, o fluxo do AGENTS.md e o guia."""
    lista = "\n".join(f"- `{nome}`: {descricao}" for nome, descricao in f["ferramentas"])
    nomes = ", ".join(f"`{n}`" for n in f["capitulos"])
    return (
        f"# {f['nome']}\n\n"
        f"{f['descricao']}\n\n"
        "## Servidor MCP\n"
        f"Esta embalagem registra o servidor `{f['nome']}` (`{PYTHON} -m {f['modulo']} mcp --raiz <pasta do projeto>`), "
        "que só lê e grava dentro da raiz. Ele precisa estar instalado:\n\n"
        f"```\n{instalar(f)}\n```\n\n"
        "Ferramentas (toda resposta é texto, nenhuma devolve imagem):\n\n"
        f"{lista}\n\n"
        "Sem o servidor ligado, o mesmo fluxo roda pela linha de comando `python -m pixel_atelier`.\n\n"
        f"{f['secoes']}\n"
        "## Guia\n"
        f"Capítulos: {nomes}. Comece pelo índice (`guia` sem capítulo) e leia só o capítulo do assunto da vez.\n"
    )


def json_texto(dados: dict) -> str:
    return json.dumps(dados, ensure_ascii=False, indent=2) + "\n"


def yaml_texto(valor: str) -> str:
    """String YAML entre aspas duplas (dois-pontos na descrição quebram YAML sem aspas)."""
    return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'


def frontmatter(campos: dict[str, str | bool]) -> str:
    linhas = [f"{k}: {str(v).lower() if isinstance(v, bool) else yaml_texto(v)}" for k, v in campos.items()]
    return "---\n" + "\n".join(linhas) + "\n---\n"


def markdown(texto: str, campos: dict | None = None) -> str:
    return (frontmatter(campos) + "\n" if campos else "") + f"<!-- {AVISO} -->\n\n" + texto


def args_do_servidor(f: dict, raiz: str | None = None) -> list[str]:
    """`-m pixel_atelier mcp [--raiz <variável da pasta do projeto>]`."""
    return ["-m", f["modulo"], "mcp"] + (["--raiz", raiz] if raiz else [])


def servidor_stdio(f: dict, raiz: str | None, **extra) -> dict:
    """Entrada de servidor stdio: `python -m pixel_atelier mcp [--raiz <pasta do projeto>]`."""
    return {f["nome"]: {**extra, "command": PYTHON, "args": args_do_servidor(f, raiz)}}


def skill(f: dict) -> str:
    return markdown(instrucoes(f), {"name": f["nome"], "description": DESCRICAO_SKILL})


# ---------------------------------------------------------------- cada ferramenta

def claude_code(f: dict) -> dict[str, str]:
    base = f"{SAIDA}/claude-code"
    plugin = {"name": f["pacote"], "version": f["versao"], "description": f["descricao"], "author": AUTOR,
              "homepage": REPO, "repository": REPO, "license": "MIT",
              "keywords": ["pixel-art", "mcp", "parallax", "paleta"]}
    return {
        f"{base}/.claude-plugin/plugin.json": json_texto(plugin),
        f"{base}/.mcp.json": json_texto({"mcpServers": servidor_stdio(f, "${CLAUDE_PROJECT_DIR}")}),
        f"{base}/skills/{f['nome']}/SKILL.md": skill(f),
        MARKETPLACE: json_texto({
            "name": f["pacote"],
            "description": f"Marketplace do {f['pacote']}: o plugin com o servidor MCP e a skill do fluxo.",
            "owner": AUTOR,
            "plugins": [{"name": f["pacote"], "source": f"./{base}", "description": f["descricao"],
                         "category": "design"}],
        }),
    }


def codex(f: dict) -> dict[str, str]:
    base = f"{SAIDA}/codex"
    config = (
        f"# {AVISO}\n"
        "# Sem cwd, o Codex sobe o servidor na pasta da sessão (onde abriu, ou a de --cd), que vira a raiz;\n"
        "# para outra raiz, acrescente \"--raiz\", \"<pasta>\" em args.\n"
        f"[mcp_servers.{f['nome']}]\n"
        f"command = {json.dumps(PYTHON)}\n"
        f"args = {json.dumps(args_do_servidor(f))}\n"
    )
    return {
        f"{base}/.agents/skills/{f['nome']}/SKILL.md": skill(f),
        f"{base}/.codex/config.toml": config,
    }


def gemini(f: dict) -> dict[str, str]:
    base = f"{SAIDA}/gemini"
    manifesto = {"name": f["pacote"], "version": f["versao"], "description": f["descricao"],
                 "mcpServers": servidor_stdio(f, "${workspacePath}"), "contextFileName": "GEMINI.md"}
    return {
        f"{base}/gemini-extension.json": json_texto(manifesto),
        f"{base}/GEMINI.md": markdown(instrucoes(f)),
    }


def antigravity(f: dict) -> dict[str, str]:
    base = f"{SAIDA}/antigravity"
    plugin = {"$schema": "https://antigravity.google/schemas/v1/plugin.json", "name": f["pacote"],
              "version": f["versao"], "description": f["descricao"], "author": AUTOR, "homepage": REPO,
              "repository": REPO, "license": "MIT", "keywords": ["pixel-art", "mcp", "parallax", "paleta"]}
    return {
        f"{base}/plugin.json": json_texto(plugin),
        f"{base}/mcp_config.json": json_texto({"mcpServers": servidor_stdio(f, None)}),
        f"{base}/skills/{f['nome']}/SKILL.md": skill(f),
    }


def cursor(f: dict) -> dict[str, str]:
    base = f"{SAIDA}/cursor/.cursor"
    regra = {"description": DESCRICAO_SKILL, "alwaysApply": False}
    return {
        f"{base}/rules/{f['nome']}.mdc": markdown(instrucoes(f), regra),
        f"{base}/mcp.json": json_texto({"mcpServers": servidor_stdio(f, "${workspaceFolder}", type="stdio")}),
    }


def copilot(f: dict) -> dict[str, str]:
    base = f"{SAIDA}/copilot"
    # O Copilot CLI não lê .vscode/mcp.json: lê .github/mcp.json, com servidor "local" e sem variável de pasta.
    cli = servidor_stdio(f, None, type="local")
    cli[f["nome"]]["tools"] = ["*"]
    return {
        f"{base}/.github/copilot-instructions.md": markdown(instrucoes(f)),
        f"{base}/.github/mcp.json": json_texto({"mcpServers": cli}),
        f"{base}/.vscode/mcp.json": json_texto({"servers": servidor_stdio(f, "${workspaceFolder}", type="stdio")}),
    }


LEIAME = """<!-- {aviso} -->

# Embalagens

O pixel-atelier no formato de cada ferramenta de agente. Tudo aqui é gerado por `python scripts/embalar.py` a partir de `AGENTS.md`, do guia, de `pixel_atelier/servidor.py` e do `pyproject.toml`: para mudar, edite a fonte e rode o script. Cada embalagem registra o servidor MCP e leva o mesmo texto de fluxo (estilo ou `ref`, receita, `gerar`, `revisar` em texto, imagem só na aprovação final).

Antes de qualquer uma, instale o servidor:

```
{instalar}
```

| Pasta | Ferramenta | O que tem | Onde colocar |
|---|---|---|---|
| `claude-code/` | Claude Code | plugin: `.claude-plugin/plugin.json`, `.mcp.json` e a skill `skills/{nome}/` | `/plugin install {pacote} --marketplace guavovic/{pacote}`, ou em dois passos `/plugin marketplace add guavovic/{pacote}` e `/plugin install {pacote}@{pacote}` (o marketplace fica em `.claude-plugin/marketplace.json` na raiz do repositório); no clone, `claude --plugin-dir embalagens/claude-code` |
| `codex/` | OpenAI Codex | skill em `.agents/skills/{nome}/` e servidor em `.codex/config.toml` | as duas pastas na raiz do projeto (o `.codex/config.toml` do projeto só vale em projeto confiável), ou a skill em `~/.agents/skills/` e o trecho `[mcp_servers.{nome}]` em `~/.codex/config.toml` |
| `gemini/` | Gemini CLI | extensão: `gemini-extension.json` (com o servidor) e `GEMINI.md` | `gemini extensions install <clone>/embalagens/gemini` (ou `gemini extensions link` para acompanhar o clone); a extensão fica em `~/.gemini/extensions/{pacote}/`, com o nome do manifesto, então a pasta de origem pode se chamar `gemini` |
| `antigravity/` | Antigravity CLI | plugin: `plugin.json`, `mcp_config.json` (com o servidor) e a skill `skills/{nome}/` | `agy plugin install <clone>/embalagens/antigravity`; o CLI copia para `~/.gemini/antigravity-cli/plugins/{pacote}/`, com o nome do manifesto |
| `cursor/` | Cursor | regra `.cursor/rules/{nome}.mdc`, aplicada quando o agente acha que o pedido pede, e servidor em `.cursor/mcp.json` | a pasta `.cursor/` na raiz do projeto, ou o servidor em `~/.cursor/mcp.json` |
| `copilot/` | GitHub Copilot | `.github/copilot-instructions.md`, servidor do VS Code em `.vscode/mcp.json` e do Copilot CLI em `.github/mcp.json` | as duas pastas na raiz do repositório; se ele já tiver `copilot-instructions.md` ou `.github/mcp.json`, junte ao que existe. No Copilot CLI, um `.mcp.json` na mesma pasta ganha do `.github/mcp.json`; para valer em todo projeto, o trecho de `mcpServers` vai em `~/.copilot/mcp-config.json` |

Toda embalagem sobe o servidor com `{python} -m {modulo} mcp`, sem depender do comando `{nome}` no PATH. É a ferramenta que roda esse `{python}`, com o PATH dela, então ele precisa ser o do ambiente onde o pacote foi instalado: instale fora de venv, abra a ferramenta com o venv ativado, ou troque `command` no arquivo de MCP pelo caminho absoluto do interpretador (`...\\.venv\\Scripts\\python.exe` no Windows, `.../.venv/bin/python` no Linux e no macOS). `{python}` é o nome que o Windows e todo venv ativado têm; num Linux ou macOS fora de venv, onde só existe `python3`, troque por `python3`. Com `pipx` o pacote fica num ambiente à parte que o `{python}` não vê: nesse caso use `"command": "{nome}"` e tire `-m` e `{modulo}` de `args`.

O servidor recebe a pasta do projeto pela variável de cada ferramenta (`${{CLAUDE_PROJECT_DIR}}`, `${{workspacePath}}`, `${{workspaceFolder}}`). O Codex, o Copilot CLI e o Antigravity CLI não documentam variável de pasta: neles o servidor sobe sem `--raiz` e usa a pasta em que a ferramenta o abre (no Codex, a pasta da sessão, conferido no código do Codex). Se a ferramenta abrir o servidor em outra pasta, acrescente `"--raiz", "<pasta do projeto>"` em `args`.

| Ferramenta | Situação |
|---|---|
| Claude Code | testado de ponta a ponta (#8) |
| OpenAI Codex, Gemini CLI, Antigravity CLI, Cursor, GitHub Copilot | formato validado pela documentação (`tests/test_formato_embalagens.py`) e servidor testado com cliente MCP; teste de ponta a ponta pendente |
"""


def montar(raiz: Path = RAIZ) -> dict[str, str]:
    """Todos os arquivos gerados, caminho relativo à raiz do repositório para o conteúdo."""
    f = fonte(raiz)
    arquivos: dict[str, str] = {}
    for embalagem in (claude_code, codex, gemini, antigravity, cursor, copilot):
        arquivos.update(embalagem(f))
    arquivos[f"{SAIDA}/README.md"] = LEIAME.format(aviso=AVISO, instalar=instalar(f), nome=f["nome"], pacote=f["pacote"], python=PYTHON,
                                                   modulo=f["modulo"])
    return arquivos


def existentes(raiz: Path = RAIZ) -> dict[str, str]:
    """O que está no disco hoje: tudo em embalagens/ e o marketplace."""
    caminhos = [c for c in (raiz / SAIDA).rglob("*") if c.is_file()] if (raiz / SAIDA).exists() else []
    if (raiz / MARKETPLACE).is_file():
        caminhos.append(raiz / MARKETPLACE)
    return {c.relative_to(raiz).as_posix(): ler(c) for c in caminhos}


def diferencas(raiz: Path = RAIZ) -> list[str]:
    """Caminhos que faltam, sobram ou mudaram em relação ao que a fonte gera."""
    novos, atuais = montar(raiz), existentes(raiz)
    return sorted(set(novos) ^ set(atuais) | {k for k in set(novos) & set(atuais) if novos[k] != atuais[k]})


def gravar(raiz: Path = RAIZ) -> int:
    novos = montar(raiz)
    shutil.rmtree(raiz / SAIDA, ignore_errors=True)
    for relativo, conteudo in novos.items():
        destino = raiz / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(conteudo)
    return len(novos)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera as embalagens de cada ferramenta a partir da fonte.")
    parser.add_argument("--conferir", action="store_true", help="só confere se as embalagens estão em dia")
    args = parser.parse_args(argv)
    for saida in (sys.stdout, sys.stderr):  # acento certo também no console do Windows
        if hasattr(saida, "reconfigure"):
            saida.reconfigure(encoding="utf-8")
    try:
        if args.conferir:
            faltam = diferencas()
            if faltam:
                print("embalagens desatualizadas; rode python scripts/embalar.py. Diferenças:")
                print("\n".join(f"  {c}" for c in faltam))
                return 1
            print(f"embalagens em dia ({len(montar())} arquivos)")
            return 0
        print(f"{gravar()} arquivos gerados em {SAIDA}/ e {MARKETPLACE}")
    except ErroDeFonte as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
