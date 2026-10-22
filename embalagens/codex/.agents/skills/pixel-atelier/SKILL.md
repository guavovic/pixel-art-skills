---
name: "pixel-atelier"
description: "Pixel art por receita JSON curta com o servidor MCP pixel-atelier: cenário em camadas com laço, estilo tirado de uma imagem de referência e revisão das regras de pixel art em texto, sem abrir a imagem. Use quando o pedido for criar, ajustar ou revisar pixel art (cenário, parallax, paleta, sprite)."
---

<!-- Arquivo gerado por scripts/embalar.py a partir de AGENTS.md, pixel_atelier/guia/, pixel_atelier/servidor.py e pyproject.toml. Não edite à mão: mude a fonte e rode o script de novo. -->

# pixel-atelier

Ateliê de pixel art para agentes de IA: técnica guardada no motor, arte saindo de receitas curtas.

## Servidor MCP
Esta embalagem registra o servidor `pixel-atelier` (`python -m pixel_atelier mcp --raiz <pasta do projeto>`), que só lê e grava dentro da raiz. Ele precisa estar instalado:

```
pip install "pixel-atelier[mcp] @ git+https://github.com/guavovic/pixel-atelier"
```

Ferramentas (toda resposta é texto, nenhuma devolve imagem):

- `gerar`: Desenha a receita, grava os PNGs e responde com o resumo (arquivos, cores, cada camada).
- `revisar`: Confere a imagem pelas regras de pixel art e responde com o relatório: ok ou alerta por regra.
- `descrever_formas`: Campos da receita e as formas com os parâmetros de cada uma, com o padrão.
- `listar_estilos`: Presets de estilo (do pacote e do usuário), um por linha com a descrição.
- `guia`: Guia de pixel art. Comece por aqui, sem capítulo (o índice); depois um capítulo curto do assunto.
- `registrar_estilo`: Guarda um estilo como preset com nome, para usar depois em "estilo" da receita.
- `ref`: Tira paleta, rampas, pixel e contraste de uma imagem de referência e grava como preset.

Sem o servidor ligado, o mesmo fluxo roda pela linha de comando `python -m pixel_atelier`.

## Por onde começar
1. **Primeiro passo, sempre, antes de qualquer outra ferramenta:** leia o índice do guia, `guia` sem capítulo (`python -m pixel_atelier guia`, ou a ferramenta MCP `guia` sem argumento, ou `pixel_atelier/guia/indice.md`). Não pule para um capítulo nem para a receita sem ele: é o índice que diz qual capítulo ler e qual regra do `revisar` cada um explica.
2. Leia só o capítulo do assunto da vez (`guia cor`, `guia composicao`...). Não carregue o guia inteiro.
3. Veja o que existe: `python -m pixel_atelier formas` e `python -m pixel_atelier estilos`.

## Fluxo de trabalho
1. **Estilo**: um preset (`estilos`) ou um novo tirado de uma imagem de referência (`ref referencia.png --nome nome`). A imagem de referência é vista uma vez; depois só o nome.
2. **Receita**: camadas do fundo para a frente, com `forma`, `profundidade` e parâmetros. Formato na [seção Receita da referência](https://github.com/guavovic/pixel-atelier/blob/main/docs/referencia.md#receita).
3. **Gerar**: `python -m pixel_atelier gerar receita.json --pasta saida`. Responde com o resumo (arquivos, cores, cada camada).
4. **Revisar em texto**: `python -m pixel_atelier revisar saida/<cena>.png`. O laço se confere sozinho: o `gerar` grava no PNG se a cena tem laço e o `revisar` lê essa marca (`--laco`, ou `laco` na ferramenta MCP, só para forçar numa imagem sem a marca). Uma linha por regra (`ok`, `alerta`, `pulada`) com o número e onde. Alerta: ajuste a receita e gere de novo. O capítulo de cada regra está no índice do guia.
5. **Aprovação final**: só aqui abra o PNG (o ampliado, `<cena>-Nx.png`) e confira o que é `[heurística]`.

Pelo servidor MCP o fluxo é o mesmo: `guia` sem capítulo primeiro, depois `descrever_formas`, `listar_estilos`, `ref`, `gerar`, `revisar` e `guia` com o capítulo do assunto. Toda resposta é texto; nenhuma ferramenta devolve imagem.

## Regras de arte
- Legibilidade vem do contraste de valor, nunca de apagar ou escurecer o fundo (capítulo `erros`). Alerta de contraste ou de legibilidade se resolve na frente: clareie ou escureça a frente ou o contorno; nunca proponha escurecer o fundo.
- Guardar técnica, não desenho: não copie imagem de terceiros para o repositório. Referência vira paleta e rampas pelo `ref`.

## Guia
Capítulos: `angulo`, `animacao`, `composicao`, `cor`, `erros`, `escala`, `estilos`, `fundamentos`, `luz`, `pontilhado`. Comece pelo índice (`guia` sem capítulo) e leia só o capítulo do assunto da vez.
