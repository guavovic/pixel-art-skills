# Referência

O detalhe de cada parte do pixel-atelier: a receita e a linha de comando, o uso em Python, o servidor MCP, o `revisar`, o `ref` e as embalagens. A visão geral está no [README](../README.md); o fluxo para agentes, no [`AGENTS.md`](../AGENTS.md).

## Receita

A cena inteira cabe num JSON curto. Só `camadas` é obrigatório; as camadas vão do fundo para a frente.

```json
{
  "cena": "vale",
  "tamanho": [320, 180],
  "estilo": {"base": "snes-diurno", "contorno": false},
  "seed": 7,
  "ampliar": 3,
  "camadas": [
    {"forma": "ceu", "astro": "sol", "posicao": [0.78, 0.18]},
    {"forma": "terreno", "nome": "montanhas", "profundidade": 0.85, "base": 0.62, "amplitude": 0.3, "papel": "pedra"},
    {"forma": "arvore", "profundidade": 0.4, "tipo": "mista", "base": 0.85},
    {"forma": "terreno", "nome": "chao", "seed": 5, "base": 0.88}
  ]
}
```

| Campo | Padrão | O que é |
| --- | --- | --- |
| `cena` | `"cena"` | nome dos arquivos de saída |
| `descricao` | `""` | texto livre |
| `tamanho` | `[320, 180]` | largura e altura reais |
| `estilo` | `"snes-diurno"` | preset, caminho de JSON ou dicionário de estilo (aceita `base`) |
| `laco` | `true` | laço horizontal; com ele a largura precisa ser múltipla de 8 |
| `seed` | `0` | sorteia as camadas sem `seed` própria; camada com `seed` fica fixa |
| `ampliar` | `1` | grava também o composto ampliado N vezes (de 1 a 16; o ampliado fica com no máximo 4096 por lado) |
| `saida` | `"tudo"` | `"tudo"`, `"composto"` ou `"camadas"` |
| `camadas` | obrigatório | `forma`, `nome` opcional e os parâmetros da forma |

```
python -m pixel_atelier gerar receita.json [--pasta saida]   # ou "-" para ler da entrada padrão
python -m pixel_atelier formas                               # parâmetros de cada forma, com o padrão
python -m pixel_atelier estilos
python -m pixel_atelier registrar-estilo meu-estilo.json [--nome nome] [--sobrescrever]
python -m pixel_atelier ref referencia.png [--nome nome]       # estilo novo a partir de uma imagem
python -m pixel_atelier guia [capitulo]                      # guia de pixel art: índice ou capítulo
```

Grava `<cena>.png`, `<cena>-3x.png` e `<cena>/01-ceu.png`... e responde em texto, sem precisar abrir a imagem:

```
vale: 320x180, estilo snes-diurno, com laço, seed 7, 4 camadas
composto: saida/vale.png, saida/vale-3x.png
cores: 28 de 146 da paleta
camadas em saida/vale (seed, área coberta, cores):
  01 ceu: seed 10909, 100%, 7 cores 01-ceu.png
  02 montanhas: seed 33290, 57%, 6 cores 02-montanhas.png
  03 arvore: seed 45195, 33%, 10 cores 03-arvore.png
  04 chao: seed 5, 15%, 6 cores 04-chao.png
```

Camada vazia ou que tapa a tela inteira sai como `aviso:` no fim.

Os presets do usuário ficam em `~/.pixel-atelier/estilos` (ou na pasta da variável `PIXEL_ATELIER_ESTILOS`). Os nomes do pacote são reservados.

## Em Python

```python
from pixel_atelier import ampliar, carregar_estilo, compor, desenhar

estilo = carregar_estilo("snes-diurno")
cena = compor([
    desenhar("ceu", estilo, 320, 180, astro="sol"),
    desenhar("terreno", estilo, 320, 180, seed=3, profundidade=0.85, base=0.62, amplitude=0.3, papel="pedra"),
    desenhar("arvore", estilo, 320, 180, seed=4, profundidade=0.4, tipo="mista", base=0.85),
    desenhar("terreno", estilo, 320, 180, seed=5, base=0.88),
])
ampliar(cena, 3).save("cena.png")
```

Toda forma tem a mesma assinatura: `forma(estilo, largura, altura, *, seed=0, profundidade=0.0, laco=True, deslocamento=0, **parametros)`. Posições e tamanhos são frações da altura, então a mesma receita serve em qualquer resolução. Com laço, a largura precisa ser múltipla de 8.

`profundidade` vai de 0 (perto) a 1 (fundo) e puxa as cores para a atmosfera do estilo: é o que separa as camadas.

## Servidor MCP

`servidor.py` expõe o ateliê por MCP (stdio), para qualquer cliente que fale o protocolo. O núcleo continua só com Pillow; o servidor vem no extra `mcp`.

```
pip install "pixel-atelier[mcp] @ git+https://github.com/guavovic/pixel-atelier"
python -m pixel_atelier mcp --raiz caminho/do/projeto   # ou o comando pixel-atelier mcp, se estiver no PATH
```

| Ferramenta | O que faz |
| --- | --- |
| `gerar` | desenha uma receita (objeto, texto JSON ou caminho) e grava os PNGs; responde com o resumo |
| `revisar` | confere um PNG pelas regras de pixel art e responde com o relatório (ver [Revisão](#revisão)) |
| `descrever_formas` | campos da receita, formas e parâmetros, com o padrão |
| `listar_estilos` | presets do pacote e do usuário |
| `registrar_estilo` | guarda um estilo (objeto ou caminho `.json`) como preset com nome |
| `ref` | tira o estilo de uma imagem de referência e grava como preset (ver [Estilo por referência](#estilo-por-referência)) |
| `guia` | o índice do guia de pixel art, ou um capítulo pelo nome |

Toda resposta é texto curto, nunca a imagem. Receita inválida volta como erro com a lista de problemas.

**Caminhos**: o servidor só lê e grava dentro da raiz (`--raiz`, ou a pasta onde ele subiu). Caminho relativo parte da raiz; caminho absoluto ou com `..` que saia dela é recusado. Sem `pasta`, `gerar` grava ao lado do arquivo da receita, ou na raiz quando a receita vem como objeto. `registrar_estilo` e `ref` gravam na pasta de presets do usuário, como na linha de comando; a imagem que `ref` lê fica dentro da raiz.

Configuração num cliente MCP genérico (o formato `mcpServers` que a maioria aceita):

```json
{
  "mcpServers": {
    "pixel-atelier": {
      "command": "python",
      "args": ["-m", "pixel_atelier", "mcp", "--raiz", "/caminho/do/projeto"]
    }
  }
}
```

O cliente MCP sobe o servidor com o PATH dele, então o `python` que ele acha precisa ser o do ambiente onde o pacote está instalado: abra a ferramenta com o venv ativado, ou ponha em `command` o caminho absoluto do interpretador (`C:\caminho\.venv\Scripts\python.exe`, com as barras dobradas no JSON, ou `/caminho/.venv/bin/python`). Num Linux ou macOS sem venv, onde só existe `python3`, troque `python` por `python3`. Instalado com `pipx`, o pacote fica num ambiente à parte que o `python` não vê: use `"command": "pixel-atelier"` com `"args": ["mcp", ...]`.

## Revisão

`revisao.py` confere a imagem pelas regras de pixel art e responde em texto, uma linha por regra: `ok`, `alerta` ou `pulada`, o número que justifica e onde. O agente lê o relatório no lugar da imagem e só abre o PNG na aprovação final.

```
python -m pixel_atelier revisar saida/vale.png [--estilo snes-diurno]     # acha as camadas em saida/vale/
python -m pixel_atelier revisar heroi.png --fundo saida/vale.png [--posicao 40 120]
python -m pixel_atelier revisar saida/vale.png --laco                    # força a emenda numa imagem sem a marca de laço
```

O laço se confere sozinho: o `gerar` grava em cada PNG (composto, ampliado e camadas) um texto `pixel-atelier:laco` com `sim` ou `nao`, e o `revisar` confere a emenda quando a marca diz `sim`. `--laco` força a conferência numa imagem sem a marca (salva de novo por outro programa, por exemplo, que costuma descartar o texto do PNG); `laco=False` em Python, ou `false` na ferramenta MCP, pula.

A receita `vale` acima, depois de `gerar`:

```
vale.png: 320x180, cena com 4 camadas, nenhum alerta
ok cores: 28 (limite 64)
ok contraste: frente (04-chao) x fundo 0.31 (mín 0.10); entre camadas mín 0.18 em 03-arvore (mín 0.05)
ok legibilidade: frente some no fundo em 0% da borda (máx 25%); fundo com faixa de valor 0.32 (mín 0.20)
ok pixel solto: 0 (0.00%, máx 0.5%)
ok pillow shading [heurística]: 3 silhuetas, nenhuma com miolo 0.06+ mais claro que a borda nos 4 lados
ok serrilhado [heurística]: 3 degraus fora do ritmo em 742 (0.4%, máx 6%); mais em 03-arvore (2, o primeiro em (246,145))
ok escala [heurística]: bloco 1x em 148 de 148 ladrilhos 16x16
ok composição repetida [heurística]: nenhum trecho 12x12 igual 3+ vezes
ok laço: emenda x319|x0 dentro do normal no composto e 4 camadas (composto 0.04, média entre colunas 0.05; máx 3x a média); laço pela marca do gerar
```

Com problema, a linha diz o quanto e onde, por exemplo `alerta legibilidade: frente some no fundo em 100% da borda (máx 25%), x15-32 y17-30; ...`. Alerta de contraste ou de legibilidade termina com a ação: aumentar o contraste de valor da frente, nunca escurecer nem apagar o fundo.

| Regra | Alerta quando |
| --- | --- |
| cores | mais de 16 num sprite ou 64 numa cena; com `--estilo`, cor fora da paleta |
| contraste | mediana da diferença de valor na borda abaixo de 0,05 entre camadas ou 0,10 da frente contra o fundo |
| legibilidade | a frente some (diferença < 0,05) em mais de 25% da borda, ou o fundo tem faixa de valor < 0,20 (fundo apagado: destaque por contraste, não escurecendo o fundo); sprite sozinho com faixa < 0,30 |
| laço | cena marcada com laço pelo `gerar` (ou com `--laco`): a emenda (coluna da direita contra a da esquerda) passa de 3x a média entre colunas vizinhas e da maior delas, no composto ou numa camada |
| pixel solto | mais de 0,5% dos pixels (pontilhado não conta) |
| pillow shading | borda 0,06+ mais escura que o miolo nos 4 lados por igual |
| serrilhado | mais de 6% dos degraus da silhueta fora do ritmo (3,1,3 ou 1,3,1) |
| escala | 2+ ladrilhos de 16x16 com bloco de pixel diferente do resto |
| composição repetida | trecho de 12x12 com detalhe igual 3+ vezes |

Valor é a luminância (o teste em escala de cinza). Contraste, legibilidade e silhuetas precisam das camadas (a pasta que `gerar` grava, achada sozinha, ou `--camadas`) ou de um `--fundo`; sem elas a regra sai como `pulada`. Imagem ampliada (`-3x.png`) é revisada no tamanho real. As regras marcadas `[heurística]` são aproximações: confira na aprovação final. Névoa e raios em pontilhado ficam fora do contraste, porque são transparentes de propósito. Os limiares ficam no topo de `revisao.py`; o porquê de cada número está no capítulo da regra no guia.

## Estilo por referência

`referencia.py` tira o estilo de uma imagem de referência e grava como preset. A imagem é vista uma vez; depois a receita usa só o nome (`"estilo": "dia-claro"`).

```
python -m pixel_atelier ref referencia.png --nome dia-claro [--base snes-diurno] [--cores 32] [--sobrescrever]
```

```
preset dia-claro gravado em ~/.pixel-atelier/estilos/dia-claro.json, base snes-diurno
referência snes-diurno-3x.png: 960x540, ampliada 3x (pixel real 320x180)
paleta: 31 cores (de 57 na imagem)
valor: 0.11 a 0.92, faixa 0.55 (p5 a p95)
rampas, do escuro ao claro (céu: do topo ao horizonte):
  folha, grama: 6 cores #245a31 > #bae884, valor 0.30 a 0.84, passo 0.11
  terra, tronco: 3 cores #82552d > #c17e95, valor 0.36 a 0.56, passo 0.10
  pedra: 5 cores #675a5e > #acb2b3, valor 0.36 a 0.69, passo 0.08
  nuvem, nevoa, neve: 4 cores #c5dbf0 > #dfebf8, valor 0.85 a 0.92, passo 0.02
  ceu: 5 cores #3868c8 > #78a8f0, valor 0.40 a 0.64, passo 0.06
da base, só com cores da paleta: cristal
luz #dfebf8, contorno #20183a, atmosfera #78a8f0
aviso: 57 cores na referência; paleta reduzida para 31 (cores sobe o limite)
```

- **Pixel**: imagem ampliada (blocos NxN) é lida no tamanho real.
- **Paleta**: as cores da imagem, exatas até `--cores` (padrão 32); acima disso, quantizada pelo corte de mediana do Pillow, com aviso. Foto ou imagem com anti-aliasing (mais de 256 cores) é reduzida pela média até 256 por lado antes, com aviso para conferir as rampas.
- **Rampas**: cada cor cai numa família pelo matiz, do escuro ao claro: verde vai para `folha` e `grama`, quente (vermelho, laranja, marrom) para `terra` e `tronco`, cinza para `pedra`, cinza claro para `nuvem`, `nevoa` e `neve`, roxo para `cristal`. O céu é a cor mais comum de cada linha do terço de cima, do topo ao horizonte; a do horizonte vira a atmosfera. Luz é a cor mais clara, contorno a mais escura.
- **Contraste**: faixa de valor (p5 a p95, como no `revisar`) e o passo de valor de cada rampa, no texto e no bloco `referencia` do preset.
- **Base**: o que a imagem não diz (sombreamento, contorno, direção da luz, papel sem família) vem de `--base`. A paleta do preset é fechada nas cores da referência, então até o que vem da base é pintado só com elas.

## Embalagens

O mesmo ateliê empacotado para cada ferramenta de agente, gerado de uma fonte só (`AGENTS.md`, guia, ferramentas do `servidor.py` e `pyproject.toml`) por `python scripts/embalar.py`. Cada embalagem registra o servidor MCP e leva o fluxo: estilo ou `ref`, receita, `gerar`, `revisar` em texto, imagem só na aprovação final. Onde colocar cada uma, e a situação de cada ferramenta, está em [`embalagens/README.md`](../embalagens/README.md).

O formato de cada embalagem (campos obrigatórios, tipos, frontmatter, variáveis de pasta, lugar de cada arquivo) é conferido por `tests/test_formato_embalagens.py`, com a fonte de cada regra no comentário. O servidor foi chamado pelo MCP Inspector com o comando exato de cada embalagem (#8).

```
python scripts/embalar.py             # regenera embalagens/ e .claude-plugin/marketplace.json
python scripts/embalar.py --conferir  # sai com 1 se alguma estiver desatualizada (o pytest também confere)
```

### Chats do navegador

Os chats no navegador (claude.ai, ChatGPT) só ligam servidor MCP remoto: o conector recebe uma URL HTTPS e quem conecta é a nuvem do serviço, não o computador de quem usa. O pixel-atelier é um servidor local por stdio, que grava os PNGs numa pasta do projeto; para virar conector ele precisaria ser hospedado com transporte HTTP, e as imagens ficariam no servidor, longe do projeto. Por isso não há embalagem de conector. No computador, o Claude Desktop e outros clientes que aceitam servidor local podem usar a configuração `mcpServers` da seção acima.

## Desenvolvimento

```
pip install -e .[dev]
pytest
python exemplos/montar_cena.py
python -m pixel_atelier gerar exemplos/snes-diurno.json
python -m pixel_atelier revisar exemplos/snes-diurno-3x.png
```

Requer Python 3.11+ e Pillow. Sem numpy. O servidor MCP pede o pacote `mcp` (extra `[mcp]`, já incluso no `[dev]`).

O que existe no pacote:

- **Técnicas** (`pixel_atelier/`): `cor.py` (rampas com mudança de matiz, mistura, quantização para a paleta), `estilo.py` (o `Estilo`: paleta, rampas por papel, atmosfera, luz, jeito de sombrear), `pontilhado.py` (Bayer 4x4), `tela.py` (tela com laço horizontal), `pintura.py` (volume por faixas de luz e sombra, luz de contorno, contorno, limpeza de pixel solto) e `imagem.py` (`compor`, `ampliar` por vizinho mais próximo, `ladrilhar`).
- **Formas** (`pixel_atelier/formas/`): `ceu`, `nuvem`, `terreno`, `arvore`, `rocha`, `cristal`, `nevoa`, `raios`. Cada uma devolve uma camada RGBA no tamanho real de pixel, só com cores da paleta e alfa 0 ou 255.
- **Estilos** (`pixel_atelier/estilos/*.json`): `metroidvania-noturno`, `snes-diurno`, `game-boy`.
- **Receitas**: `receita.py` valida antes de desenhar, com todos os erros de uma vez e sugestão de nome parecido; `gerador.py` desenha e devolve o resumo em texto.
- **Exemplos**: `exemplos/montar_cena.py` monta a mesma cena nos três estilos; `exemplos/*.json` são as mesmas cenas em receita.
- **GIFs do README**: `python scripts/gifs_readme.py` regrava os de `docs/`.
