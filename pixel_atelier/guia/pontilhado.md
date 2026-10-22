# Pontilhado (dithering)

Pontilhado mistura dois tons alternando pixels, para fazer um tom intermediário que a paleta não tem ou uma transição.

## Regras
- Use padrão ordenado (matriz de Bayer 4x4: 17 níveis entre dois tons) ou xadrez 50%. Nada de pontilhado aleatório (vira ruído).
- Só entre tons vizinhos da rampa; pontilhar dois tons com valor muito distante cria textura áspera.
- Faixa de transição curta: 2 a 4 linhas de xadrez entre duas áreas lisas. Degradê inteiro em pontilhado fica pesado.
- Bom para: céu, névoa, raio de luz, halo, transição em paleta de 4 cores, textura de material (pedra, areia).
- Evite em: sprite pequeno que se move (cintila), borda de silhueta (fica serrilhada), personagem.

## Pontilhado em vez de transparência
- Névoa e raio em pixel art são máscaras pontilhadas em cima da cena, não camadas com alfa parcial. Assim a cena continua só com cores da paleta e alfa 0 ou 255.
- Densidade baixa (0,2 a 0,4) para névoa leve; escala 1 (cada ponto é 1 pixel). Escala 2 fica pesada.

## No motor e no revisar
- `pontilhado.py`: `mascara_pontilhada` e `degrade` (Bayer 4x4).
- Formas: `nevoa` (`densidade`, `escala`, `espessura`, `ate_o_chao`), `raios` (`intensidade`, `abertura`), `ceu` (degradê do topo ao horizonte, `halo` do astro).
- Estilo: `"sombreamento": "pontilhado"` faz a transição de tom em xadrez.
- `revisar`: pontilhado não conta como pixel solto (a mesma cor volta na diagonal ou no passo de 2 e 4 pixels). Camada de névoa e raio (mais borda que miolo, `ATMOSFERA` = 0,5) fica fora do contraste, porque é transparente de propósito. Trecho com mais de 25% de blocos 2x2 em xadrez não conta como composição repetida.

Fontes: Lospec, tutoriais de pontilhado (lospec.com/pixel-art-tutorials); Derek Yu, "Pixel Art Tutorial" (derekyu.com/makegames/pixelart.html).
