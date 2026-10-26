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
- Cenário vivo: `"animacao": {"quadros": 48, "duracao": 100, "voltas": 2}` na receita. Cada camada é desenhada uma vez e anda inteira (o pontilhado anda junto, não pisca). A camada mais perto dá `voltas` voltas no laço, a funda menos (`voltas x (1 - profundidade)`, arredondado); nuvem e névoa ganham 1 volta de vento; raios pulsam. Toda camada dá voltas inteiras, então o quadro depois do último é o primeiro. Camada sem laço fica parada.
- O passo sai da largura (`voltas x largura / quadros`), então vale em qualquer tamanho e estilo. Movimento mais lento: mais quadros ou menos voltas, não mais tempo por quadro.
- Sai `<cena>.gif` para ver, `<cena>-quadros.png` (quadros lado a lado) e `<cena>-quadros.json` (quadros, duração em ms, tamanho do quadro, colunas) para o jogo.
- `revisar` no GIF ou na folha confere o tempo de cada quadro e o resto das regras no primeiro quadro.
  - `TEMPO_MINIMO` 20 ms: com 0 ou 10 ms o navegador toca o GIF a 100 ms; 20 ms é o mais rápido que toca certo.
  - `TEMPO_MAXIMO` 300 ms: o quadro mais lento da tabela acima (parado); mais que isso vira sequência de fotos.

Fontes: Raymond Schlitter, "Pixelblog 8: Intro to Animation" e "Pixelblog 25: Motion Cycles" (slynyrd.com/pixelblog-catalogue); tutoriais de Pedro Medeiros, "Squash", "Easings", "Motion Blur" (saint11.art/blog/pixel-art-tutorials); Jeremiah Johnson (nullsleep), "Animated GIF Minimum Frame Delay Browser Compatibility Study" (2012), sobre o tempo mínimo do GIF.
