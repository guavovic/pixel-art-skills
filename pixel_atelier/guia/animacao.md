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
- O motor ainda não anima. Fundo animado se faz com `deslocamento` (mesma camada, deslocada; com `laco`, dá a volta sem emenda) e com seeds diferentes para nuvem ou névoa que muda.
- `revisar` confere quadro a quadro (cores, pixel solto, serrilhado); não confere tempo.

Fontes: Raymond Schlitter, "Pixelblog 8: Intro to Animation" e "Pixelblog 25: Motion Cycles" (slynyrd.com/pixelblog-catalogue); tutoriais de Pedro Medeiros, "Squash", "Easings", "Motion Blur" (saint11.art/blog/pixel-art-tutorials).
