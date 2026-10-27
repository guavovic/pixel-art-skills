# Animação

Poucos quadros bem escolhidos valem mais que muitos quadros iguais. Silhueta muda a cada quadro, senão o movimento não lê.

## Quadros e tempo
| Ação | Quadros | Tempo por quadro |
| --- | --- | --- |
| parado (respiração) | 2 a 4 | 150 a 300 ms |
| andar | 4 a 8 | 80 a 120 ms |
| correr | 6 a 8 | 60 a 100 ms |
| pulo | 1 subindo, 1 no alto, 1 caindo (mais 1 de agachar e 1 de pouso) | por estado |
| ataque | antecipação 1 a 2, golpe 1, recuperação 2 a 3 | golpe rápido (40 a 60 ms), antecipação e recuperação mais lentas |

- Ciclo de andar de 4: contato, passagem, contato (outro pé), passagem. Na passagem o corpo sobe 1 pixel.
- Ciclo de 8: contato, descida, passagem, subida, para cada pé.
- Tempo variável dá peso: segure o quadro de impacto um pouco mais.

## Regras
- Mexa em pixels inteiros; deslocar meio pixel não existe. Para movimento mais suave que 1 px, mude a forma (subpixel: troca de tom na borda), não a posição.
- Squash and stretch: no pouso, 1 a 2 px mais baixo e mais largo; no salto, mais alto e mais fino. Mantenha a área parecida.
- Smear: no golpe rápido, 1 quadro com a forma esticada ou um rastro chapado no lugar do borrão.
- Antecipação antes de toda ação forte (recuar antes de golpear, agachar antes de pular).
- Partes que seguem o corpo (cabelo, capa, cauda) atrasam 1 quadro (follow-through).
- Mesma paleta e mesmo contorno em todos os quadros; cor nova num quadro só pisca.

## Faça e evite
- Faça: desenhe as poses-chave primeiro, depois os intermediários.
- Faça: teste em tamanho real e na velocidade real; ampliado engana.
- Evite: pixel que acende e apaga entre quadros sem motivo (ruído animado).
- Evite: o corpo inteiro tremendo no parado; mexa 1 ou 2 partes.

## No motor
- Cenário vivo: `"animacao": {}` na receita (padrão 96 quadros de 100 ms e 4 voltas em 320x180). Cada camada é desenhada uma vez e anda inteira (o pontilhado anda junto, não pisca). A camada mais perto dá `voltas` voltas no laço e as mais fundas menos: cada profundidade ganha a sua velocidade enquanto houver voltas para todas, senão as vizinhas dividem a mesma (`voltas x (1 - profundidade)`, arredondado). Só o céu (profundidade 1) fica parado; abaixo dele toda camada dá pelo menos 1 volta. Nuvem e névoa ganham 1 volta de vento por cima da sua; raios pulsam. Toda camada dá voltas inteiras, então o quadro depois do último é o primeiro. Camada sem laço fica parada.
- `"voltas": N` numa camada fixa a velocidade dela no lugar da profundidade (pede laço).
- O passo sai da largura (`voltas x largura / quadros` pixels por quadro), então vale em qualquer tamanho e estilo. No padrão em 320x180 a frente anda 13,3 px por quadro e a mais lenta 3,3; mais voltas é mais velocidades diferentes, mas um passo maior. Movimento mais lento: mais quadros ou menos voltas, não mais tempo por quadro.
- A folha de quadros tem no máximo 4096 por lado, então o padrão encolhe no tamanho grande: 66 quadros e 2 voltas em 640x360, 15 quadros e 1 volta em 1280x720. Sem `voltas`, a receita usa 1 volta a cada 24 quadros, até 4.
- Sai `<cena>.gif` para ver, `<cena>-quadros.png` (quadros lado a lado) e `<cena>-quadros.json` (quadros, duração em ms, tamanho do quadro, colunas) para o jogo.
- `revisar` no GIF ou na folha confere o tempo de cada quadro, a volta do último quadro para o primeiro e o resto das regras no primeiro quadro.
  - `TEMPO_MINIMO` 20 ms: com 0 ou 10 ms o navegador toca o GIF a 100 ms; 20 ms é o mais rápido que toca certo.
  - `TEMPO_MAXIMO` 300 ms: o quadro mais lento da tabela acima (parado); mais que isso vira sequência de fotos.
  - `LACO_QUADROS` 1,1 (heurística): com os quadros reduzidos a 32 px de largura (onde o passo grande não satura a conta), a diferença do último para o primeiro passa de 1,1 vez a maior diferença entre quadros seguidos: a animação pula no fim do laço. Num laço certo a volta é só mais um passo (chega a 1,03 pelo arredondamento do passo); um laço cortado no meio passa de 1,1 na maioria dos casos. GIF que toca uma vez pula.

Fontes: Raymond Schlitter, "Pixelblog 8: Intro to Animation" e "Pixelblog 25: Motion Cycles" (slynyrd.com/pixelblog-catalogue); tutoriais de Pedro Medeiros, "Squash", "Easings", "Motion Blur" (saint11.art/blog/pixel-art-tutorials); Jeremiah Johnson (nullsleep), "Animated GIF Minimum Frame Delay Browser Compatibility Study" (2012), sobre o tempo mínimo do GIF.
