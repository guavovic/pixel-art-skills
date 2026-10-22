# Erros comuns

O mais caro de todos: a arte não lê. O personagem some no cenário, ou o cenário some para o personagem aparecer.

## Legibilidade: contraste, não fundo apagado
- **Regra: legibilidade vem do contraste de valor, nunca de apagar ou escurecer o fundo.**
- Erro típico: o personagem some numa parte cheia da tela; a "correção" empurra todo o cenário para o escuro (o mais claro do fundo abaixo de 0,25). O personagem aparece e o mundo desaparece.
- O que funciona:
  - cada camada de fundo numa faixa de valor estreita e média; só a camada da ação vai do escuro ao claro (ver `composicao`);
  - contorno escuro de 1 px nas peças da ação, que lê em fundo claro e escuro (ver `fundamentos`);
  - luz de contorno separando silhuetas (ver `luz`);
  - cor complementar: fundo frio, ação quente e saturada.
- Teste rápido: imagem em escala de cinza. Se o personagem não se destaca em cinza, a separação depende só de cor e vai falhar.

## Números do `revisar` (linha `legibilidade`)
- A borda da frente some onde a diferença de valor contra o fundo fica abaixo de **0,05** (`SOME`): o passo mínimo visível (ver `cor`). Alerta se isso passa de **25%** da borda (`SOME_MAX`): um quarto do contorno sumido já quebra a silhueta.
- Fundo apagado: faixa de valor do fundo (percentil 5 a 95) abaixo de **0,20** (`FAIXA_FUNDO`) é alerta, mesmo com a frente contrastando. 0,20 é a faixa do erro típico acima (fundo entre 0,05 e 0,25); os exemplos do pacote ficam entre 0,33 e 0,55.
- Sprite sozinho: faixa de valor de pelo menos **0,30** (`FAIXA_SPRITE`), o mínimo para luz, tom médio e sombra separados em escala de cinza.
- Contraste (linha `contraste`): **0,10** da frente contra o fundo e **0,05** entre camadas (ver `composicao`).

## Outros erros e onde ler
| Erro | Sinal | Capítulo |
| --- | --- | --- |
| pixel solto, ruído | textura suja | `fundamentos` |
| serrilhado fora do ritmo | linha com dentes | `fundamentos` |
| contorno preto em tudo | arte "adesivo" | `fundamentos` |
| anti-alias automático, borrão | mais de 256 cores | `fundamentos`, `cor` |
| rampa sem mudança de matiz | cor de plástico | `cor` |
| cores demais ou quase iguais | paleta sem coesão | `cor` |
| pillow shading | forma de travesseiro | `luz` |
| luz de várias direções | volume confuso | `luz` |
| pixel de tamanhos diferentes | sprite ampliado no meio | `escala` |
| vistas misturadas | 3/4 num cenário lateral | `angulo` |
| detalhe igual em todo canto | nada é foco | `composicao` |
| objeto copiado 3 vezes | repetição à vista | `composicao` |

Fontes: Derek Yu, "Common Pixel Art Mistakes" (derekyu.com/makegames/pixelart2.html); Raymond Schlitter, "Pixelblog 11: Landscape Pixeling" (slynyrd.com/pixelblog-catalogue).
