# Estilos

Um estilo é o conjunto de limites: resolução, cores, contorno e jeito de sombrear. Respeitar o limite é o que faz parecer da época.

## SNES (16 bits)
- Resolução 256x224 (ou 320x180 para 16:9). Cores de 15 bits (32 níveis por canal).
- Subpaleta de 16 cores por sprite ou ladrilho (15 e o transparente); até 128 cores de fundo e 128 de sprite na tela.
- Rampas de 4 a 5 tons com mudança de matiz forte, cores saturadas, contorno escuro colorido (não preto), sombreado em faixas.
- Preset: `snes-diurno` (dia, faixas de 2 px, contorno, luz de contorno amarela).

## Game Boy
- 160x144, 4 tons (o verde clássico: `#0f380f`, `#306230`, `#8bac0f`, `#9bbc0f`).
- Com 4 tons, valor é tudo: fundo nos 2 claros, ação e contorno nos 2 escuros. Transição só por pontilhado.
- Ladrilho 8x8; sprite de 8x8 ou 8x16, 3 cores e o transparente.
- Preset: `game-boy` (contorno escuro, sombreado pontilhado, o longe some no claro).

## Metroidvania moderno
- 320x180 ou 480x270 (ampliação inteira para 1080p). Sem limite de hardware: o limite é escolha.
- Paleta de 32 a 64 cores, fria e escura no cenário, com uma cor de destaque (ciano, laranja) em poucos pontos.
- Fundo em silhuetas chapadas que clareiam com a distância; luz de contorno separa silhueta de silhueta; névoa e raios em pontilhado.
- Personagem pequeno (20 a 32 px) com contorno e o maior contraste da tela.
- Preset: `metroidvania-noturno` (sombreado chapado, sem contorno no cenário, luz de contorno ciano).

## Por geração
- Presets `8-bits`, `16-bits`, `32-bits` e `moderno`: o tema do `snes-diurno` (com a sombra da nuvem mais fria) e a técnica de cada época. `"geracao"` num estilo ou na receita troca só a técnica. Ver o capítulo `geracoes`.

## Estilo novo
- A partir de um preset: `{"base": "snes-diurno", "contorno": false, "sombreamento": "chapado"}` na receita.
- A partir de uma imagem: `python -m pixel_atelier ref referencia.png --nome nome`. Guarda paleta e rampas, não o desenho.
- Guardar: `registrar-estilo estilo.json --nome nome`.
- Conferir a paleta: `revisar cena.png --estilo nome` (cor fora da paleta é alerta).

Fontes: Pan Docs, paletas do Game Boy (gbdev.io/pandocs/Palettes.html); SNESdev Wiki, paletas e cores do SNES (snes.nesdev.org/wiki/Palettes); Lospec (lospec.com/palette-list).
