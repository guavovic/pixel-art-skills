# AGENTS.md

Instruções para qualquer agente que use ou altere este repositório.

## O que é
Ateliê de pixel art para agentes. O motor (`pixel_atelier/`) guarda a técnica: paleta, rampas, luz, pontilhado, laço sem emenda e formas. O agente escreve uma receita JSON curta e lê respostas em texto; não precisa ver a imagem para trabalhar. Só Python 3.11+ e Pillow; servidor MCP no extra `[mcp]`.

## Por onde começar
1. **Primeiro passo, sempre, antes de qualquer outra ferramenta:** leia o índice do guia, `guia` sem capítulo (`python -m pixel_atelier guia`, ou a ferramenta MCP `guia` sem argumento, ou `pixel_atelier/guia/indice.md`). Não pule para um capítulo nem para a receita sem ele: é o índice que diz qual capítulo ler e qual regra do `revisar` cada um explica.
2. Leia só o capítulo do assunto da vez (`guia cor`, `guia composicao`...). Não carregue o guia inteiro.
3. Veja o que existe: `python -m pixel_atelier formas` e `python -m pixel_atelier estilos`.

## Fluxo de trabalho
1. **Estilo**: um preset (`estilos`) ou um novo tirado de uma imagem de referência (`ref referencia.png --nome nome`). A imagem de referência é vista uma vez; depois só o nome.
2. **Receita**: camadas do fundo para a frente, com `forma`, `profundidade` e parâmetros. Formato em `docs/referencia.md`, seção Receita.
3. **Gerar**: `python -m pixel_atelier gerar receita.json --pasta saida`. Responde com o resumo (arquivos, cores, cada camada).
4. **Revisar em texto**: `python -m pixel_atelier revisar saida/<cena>.png`. O laço se confere sozinho: o `gerar` grava no PNG se a cena tem laço e o `revisar` lê essa marca (`--laco`, ou `laco` na ferramenta MCP, só para forçar numa imagem sem a marca). Uma linha por regra (`ok`, `alerta`, `pulada`) com o número e onde. Alerta: ajuste a receita e gere de novo. O capítulo de cada regra está no índice do guia.
5. **Aprovação final**: só aqui abra o PNG (o ampliado, `<cena>-Nx.png`) e confira o que é `[heurística]`.

Pelo servidor MCP o fluxo é o mesmo: `guia` sem capítulo primeiro, depois `descrever_formas`, `listar_estilos`, `ref`, `gerar`, `revisar` e `guia` com o capítulo do assunto. Toda resposta é texto; nenhuma ferramenta devolve imagem.

## Regras de arte
- Legibilidade vem do contraste de valor, nunca de apagar ou escurecer o fundo (capítulo `erros`). Alerta de contraste ou de legibilidade se resolve na frente: clareie ou escureça a frente ou o contorno; nunca proponha escurecer o fundo.
- Guardar técnica, não desenho: não copie imagem de terceiros para o repositório. Referência vira paleta e rampas pelo `ref`.

## Desenvolvimento
```
pip install -e .[dev]
pytest
python exemplos/montar_cena.py          # regrava os PNGs de exemplo
```
- Mudou um limiar no topo de `pixel_atelier/revisao.py`: atualize o capítulo do guia que cita a constante (o teste `test_cada_limiar_do_revisar_esta_no_guia` confere).
- Mudou uma forma ou um preset: rode `montar_cena.py` e confira que os exemplos passam no `revisar` sem alerta (`tests/test_guia.py`).
- Capítulo novo do guia: um `.md` curto em `pixel_atelier/guia/`, com linha no `indice.md`.
- Ferramenta MCP nova: uma função em `criar_servidor` (`pixel_atelier/servidor.py`), docstring curta, resposta em texto.
- Embalagens das ferramentas de agente (`embalagens/` e `.claude-plugin/marketplace.json`) saem de `python scripts/embalar.py` e nunca são editadas à mão. A fonte é este arquivo (seções Por onde começar, Fluxo de trabalho e Regras de arte), os capítulos do guia, as ferramentas de `servidor.py` e o `pyproject.toml`: mudou algum, rode o script (o teste `tests/test_embalagens.py` falha se esquecer).

## Contribuição
- Tudo em português do Brasil: código, comentários, mensagens, documentação.
- Commits no padrão Conventional Commits, em pt-BR (`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `refactor: ...`).
- Uma issue por mudança; a PR começa com `Resolve #N.` e diz como foi testada.
- Testes passando antes da PR.
