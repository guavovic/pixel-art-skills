# Luz e volume

Volume é luz vindo de um lado. Defina a direção uma vez e use em tudo da cena.

## Regras
- Uma fonte principal; o padrão de jogo é de cima à esquerda (`direcao_luz: [-1, -1]`).
- Do lado da luz: tom claro da rampa. Do lado oposto: tom escuro. Entre os dois: o tom médio, que é a maior área.
- Sombra própria (na forma) e sombra projetada (no chão) usam a mesma rampa, um passo mais escuro.
- Luz refletida: um passo mais claro na borda da sombra, do lado oposto à luz. Pouco, senão vira pillow shading.
- Brilho especular: 1 a 3 pixels do tom mais claro, só em material duro (metal, cristal, olho).
- Luz de contorno (rim light): borda de 1 pixel clara do lado da luz. Separa silhueta escura de fundo escuro sem clarear a silhueta inteira.

## Pillow shading
- Erro: sombrear do contorno para o meio, igual nos 4 lados, como se a luz viesse de frente. A forma parece um travesseiro.
- Correção: escolha o lado da luz e deixe a borda oposta escura, a borda da luz clara.
- `revisar`: alerta quando a borda é **0,06** ou mais mais escura que o miolo (`PILLOW_MIOLO`) e os 4 lados ficam a até **0,04** um do outro (`PILLOW_LADOS`); heurística. 0,06 é pouco mais que o passo mínimo visível (0,05, ver `cor`); 0,04 abaixo dele quer dizer "os 4 lados parecem iguais". Luz de um lado só não cai aqui.

## Jeitos de sombrear (campo `sombreamento` do estilo)
| Valor | Visual | Quando |
| --- | --- | --- |
| `chapado` | 1 a 2 tons por forma, silhueta forte | noite, fundo distante, estilo minimalista |
| `faixas` | faixas de luz e sombra de `largura_faixa` px | 16 bits, dia |
| `pontilhado` | transição em xadrez entre tons | paleta de 4 cores (Game Boy) |

## Faça e evite
- Faça: volume em formas grandes primeiro (2 a 3 tons), detalhe depois.
- Faça: luz de contorno na cor da luz do ambiente (lua: ciano frio; fogo: laranja), pouca.
- Evite: luz de várias direções na mesma cena, a menos que haja uma fonte visível (tocha).
- Evite: clarear o fundo inteiro para destacar algo; destaque com borda de luz e valor (ver `erros`).

## Como pedir
- No estilo: `direcao_luz`, `sombreamento`, `largura_faixa`, `luz` (cor), `luz_contorno` (liga a borda clara), `forca_luz`.
- Na receita: `{"base": "metroidvania-noturno", "direcao_luz": [1, -1]}` troca a luz para a direita.

Fontes: Raymond Schlitter, "Pixelblog 6: Light and Shadow" (slynyrd.com/blog/2018/6/15/pixelblog-6-light-and-shadow); Derek Yu, "Pixel Art Tutorial" (derekyu.com/makegames/pixelart.html).
