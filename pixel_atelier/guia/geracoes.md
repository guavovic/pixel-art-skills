# Gerações

A geração é a técnica de uma época de console; o estilo continua dando o tema (cores, céu, luz). Pedir: `"estilo": "16-bits"` (preset) ou `"geracao": 16` na receita, que vale com qualquer estilo: `{"estilo": "metroidvania-noturno", "geracao": 8}`. Aceita 8, 16, 32, `moderno` (= 64, também `hd`) e números no meio.

Sem `tamanho`, a receita usa o da geração. O PNG guarda a geração e o `revisar` usa os limites dela.

| Geração | Tamanho | Tons por rampa | Cores na cena | Cores por camada | Grade de cor | Sombra e contorno |
| --- | --- | --- | --- | --- | --- | --- |
| 8 | 256x240 | 3 | 25 | 13 | as 54 do NES | pontilhado, contorno preto |
| 16 | 256x224 | 5 | 121 | 15 | 15 bits | faixas de 2 px, contorno escuro |
| 32 | 320x240 | 6 | 256 | 255 | 15 bits | faixas em 2 degraus, selout, textura leve |
| moderno | 640x360 | 8 | 256 | livre | 24 bits | faixas largas, selout, textura |

De onde vêm os números:
- **8 bits (NES)**: 256x240; 4 subpaletas de fundo e 4 de sprite, 3 cores cada, mais o fundo comum: 25 cores na tela. Uma camada de fundo usa as 4 subpaletas de fundo e o fundo comum (13). Cores só das 54 do PPU.
- **16 bits (SNES)**: 256x224; cor de 15 bits (32 níveis por canal); 8 subpaletas de fundo de 15 cores e o transparente: 121 no fundo, 15 por camada.
- **32 bits (PlayStation, Saturn)**: 320x240 é o modo mais usado em 2D; cor de 15 bits; textura com tabela de 8 bits (256 cores, 255 e o transparente). Sem limite de tela além da tabela.
- **Moderno**: sem hardware; 640x360 amplia inteiro para 1280x720 (2x) e 1920x1080 (3x). O limite de cores vira escolha: 256 na cena ainda lê como pixel art.

Números no meio interpolam na escala de bits (log2) e pegam a técnica da geração mais perto: 12 dá 256x230, 63 cores, 14 por camada, faixas. O 12 é o meio-termo limpo; 10, 24 e 48 também desenham, mas a cena do pacote ainda dá alerta neles (pillow em 10, composição repetida em 24 e 48).

## O que o `revisar` muda por geração
- **cores**: o limite da cena vira o da geração (25, 121, 256) em vez dos **64** de `CORES_CENA`.
- **cores por camada**: regra nova, só com geração e camadas; alerta quando uma camada passa do limite da tabela. No moderno ela é pulada.
- **composição repetida**: 8 a 16 bits (até `LADRILHOS_ATE` = **16**) montavam o fundo com ladrilhos repetidos, então ali o alerta só sai com **5** cópias (`COPIAS_LADRILHOS`). A janela cresce **12** px a cada **180** linhas da geração (`LINHAS_POR_JANELA`): 24x24 no moderno, onde o detalhe é o dobro.
- Sem geração (receita antiga, PNG sem marca), tudo vale como antes. `--geracao 16` (ou `geracao` na ferramenta MCP) força os limites numa imagem sem marca.

## Como cada época se parece
- **8**: poucas cores e muito chapado; a transição é pontilhado, o contorno é preto. Céu em faixas pontilhadas.
- **16**: rampas de 4 a 5 tons em faixas largas e limpas; contorno colorido escuro.
- **32**: mais tons, faixas em degraus, contorno da cor da peça (selout: escuro no lado da sombra, meio-tom no da luz) e textura leve.
- **Moderno**: rampa longa, textura nas superfícies (metade nas nuvens e na névoa), selout. Mais resolução não é mais detalhe por pixel: o pixel continua visível.

Fontes: NESdev Wiki, PPU palettes (nesdev.org/wiki/PPU_palettes); Lospec, paleta do NES (lospec.com/palette-list/nintendo-entertainment-system); SNESdev Wiki, Palettes (snes.nesdev.org/wiki/Palettes); Rodrigo Copetti, arquitetura do PlayStation e do Saturn (copetti.org/writings/consoles).
