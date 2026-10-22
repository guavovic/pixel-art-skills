# Escala e pixels por unidade

Todo pixel da tela tem o mesmo tamanho. Pixel de tamanho diferente no mesmo quadro (sprite ampliado 2x ao lado de um em 1x) é o erro de escala.

## Resolução e tamanho
| Resolução real | Ampliação inteira | Uso |
| --- | --- | --- |
| 160x144 | 4x a 7x | Game Boy |
| 256x224 | 4x a 5x | SNES |
| 320x180 | 4x = 1280x720, 6x = 1920x1080 | metroidvania moderno (16:9) |
| 480x270 | 4x = 1920x1080 | cena com mais detalhe |

- Personagem: 16 a 32 px de altura em 320x180 (1/10 a 1/6 da tela). Menor que 12 px vira símbolo; maior que 48 px pede animação muito mais cara.
- Ladrilho (tile): 8, 16 ou 32 px. 16x16 é o padrão para 320x180.
- Pixels por unidade (PPU, nos motores de jogo): 1 unidade do mundo = 1 ladrilho. Ladrilho de 16 px, PPU 16. Use o mesmo PPU em todos os sprites do projeto.
- Câmera: ajuste para que a altura visível seja a resolução real inteira (ex.: 180 px) e o filtro de textura seja "ponto" (nearest), sem mipmap e sem compressão.

## Ampliar
- Só por número inteiro e vizinho mais próximo. 1,5x ou filtro bilinear borra e cria pixel de tamanhos diferentes.
- No motor: `ampliar` na receita (1 a 16; o ampliado tem no máximo 4096 por lado). Grava `<cena>-Nx.png` ao lado do tamanho real.
- Rotação e escala em tempo de jogo também quebram o grid; prefira quadros desenhados.

## Revisar
- `revisar` mede o bloco de pixel em ladrilhos de **16x16** (`LADRILHO`) e dá alerta quando **2 ou mais** ladrilhos (`LADRILHOS_FORA`) têm bloco diferente do resto (heurística). 16 é o ladrilho padrão; 2 evita alerta por um único ladrilho chapado que engana a medida.
- Imagem ampliada (`-3x.png`) é revisada no tamanho real, sozinha. O ampliado do `gerar` leva a escala gravada no PNG; sem marca nem `-Nx` no nome, arte chapada (faixas, retângulos de lado par) não passa por ampliada: o bloco precisa de troca de cor nos dois eixos, todas no passo dele.

## Como pedir
- `"tamanho": [320, 180]` e `"ampliar": 4` na receita. Posições e tamanhos das formas são frações da altura, então a mesma receita serve em qualquer resolução; com laço, largura múltipla de 8.

Fontes: tutoriais de Pedro Medeiros (saint11.art/blog/pixel-art-tutorials); Pan Docs, especificação do Game Boy (gbdev.io/pandocs).
