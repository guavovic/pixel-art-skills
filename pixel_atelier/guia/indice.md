# Guia de pixel art

Conhecimento de artista em capítulos curtos. Leia só o capítulo do assunto da vez, não o guia inteiro.

Ler um capítulo: `python -m pixel_atelier guia <capitulo>`, a ferramenta MCP `guia` com `capitulo`, ou o arquivo `pixel_atelier/guia/<capitulo>.md`.

| Capítulo | Quando ler | Regras do `revisar` |
| --- | --- | --- |
| `fundamentos` | pixel solto, serrilhado, contorno, anti-alias | pixel solto, serrilhado, contorno preto, anti-alias |
| `cor` | montar paleta ou rampa, cor que não "casa" | cores, matiz da rampa (com `--estilo`) |
| `angulo` | escolher a vista: lateral, top-down, 3/4, isométrico | linha 2:1 |
| `escala` | tamanho do sprite, pixels por unidade, ampliar | escala |
| `luz` | volume, direção da luz, sombra, luz de contorno | pillow shading |
| `pontilhado` | degradê, névoa, transição de tom | pixel solto (exceção) |
| `animacao` | quadros, tempo, ciclo de andar, cenário animado | tempo |
| `composicao` | camadas, profundidade, onde está o foco, laço | contraste, composição repetida, laço |
| `estilos` | SNES, Game Boy, metroidvania moderno | cores (com `--estilo`) |
| `erros` | a arte "não lê", personagem some, fundo apagado | legibilidade, contraste |

Regra central: **legibilidade vem do contraste de valor, nunca de apagar ou escurecer o fundo.** Valor é a luminância de 0 a 1 (o teste da imagem em escala de cinza).

Os números do `revisar` ficam no topo de `pixel_atelier/revisao.py`; cada um está explicado no capítulo da regra.
