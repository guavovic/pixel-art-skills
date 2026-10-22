# Ângulo e perspectiva

Escolha uma vista por jogo e mantenha em tudo: personagem, cenário e itens. Misturar vistas é o erro que mais denuncia arte montada de pedaços.

| Vista | Como desenhar | Onde usa |
| --- | --- | --- |
| Lateral (side view) | Câmera na altura do corpo; chão é uma linha; profundidade só por camadas (parallax) | plataforma, metroidvania, luta |
| Top-down | Visto de cima, levemente inclinado: topo das coisas grande, frente quase sem altura | ação de cima, estratégia |
| 3/4 (top-down oblíquo) | Mostra o topo e a frente; a frente dos objetos ocupa de 1/3 a 1/2 da altura | RPG de 16 bits |
| Isométrico 2:1 | Linhas do chão com degrau de 2 pixels na horizontal por 1 na vertical (26,6°); verticais retas | estratégia, construção, cena de vitrine |

## Regras com número
- Isométrico 2:1: a linha é 2,2,2...; nunca 2,1,2 (vira serrilhado). Ladrilho de chão com largura = 2 x altura (32x16, 64x32).
- Nas quinas do losango isométrico, junte os dois pixels de topo (ponta com 2 de largura) para a linha casar no ladrilho vizinho.
- 3/4: personagem com cabeça grande lê melhor (cabeça de 1/3 a 1/2 da altura em sprite de 16 a 32 px).
- Top-down: sombra projetada simples (elipse de 1 tom) embaixo do personagem ancora ele no chão.

## Faça e evite
- Faça: a mesma direção de luz em tudo, combinando com a vista (ver `luz`).
- Faça: na lateral, separe planos por valor e pela atmosfera, não por perspectiva desenhada (ver `composicao`).
- Evite: perspectiva com ponto de fuga em pixel art de jogo; linha que converge serrilha e quebra o ladrilho.
- Evite: objeto em 3/4 num cenário lateral, ou porta isométrica num chão top-down.

## No motor
- As formas de hoje (`ceu`, `terreno`, `arvore`, `rocha`, `cristal`, `nevoa`, `raios`, `nuvem`) são de vista lateral, em camadas com laço horizontal.
- Top-down, 3/4 e isométrico ainda não têm forma: desenhe por fora e use o `revisar` (serrilhado pega linha 2:1 quebrada).

Fontes: Raymond Schlitter, "Pixelblog 4: Graphical Projection Part 2" e "Pixelblog 41: Isometric Pixel Art" (slynyrd.com/pixelblog-catalogue); tutoriais de Pedro Medeiros, "Isometric" (saint11.art/blog/pixel-art-tutorials).
