# Fundamentos

Cada pixel é uma decisão. Nada de filtro, borrão ou anti-alias automático.

## Pixel solto
- Pixel solto: um pixel cercado nos 4 lados por uma mesma cor diferente da dele. Lê como sujeira.
- Faça: agrupe a cor em massas de 2 ou mais pixels; detalhe é forma, não ruído.
- Evite: textura de pixels aleatórios no fundo; detalhe fino fica na camada de ação.
- Exceção: pontilhado (padrão regular) não é pixel solto. Ver `pontilhado`.
- `revisar`: alerta acima de **0,5%** dos pixels (`SOLTOS_MAX`). Os exemplos do pacote ficam abaixo de 0,1%; 0,5% é onde o ruído já aparece na cena inteira. O motor limpa com `pintura.limpar_soltos`.

## Serrilhado (jaggies)
- Linha inclinada é feita de degraus. Degraus regulares leem como reta: 1,1,1 (45°), 2,2,2 (26,6°, o 2:1), 3,3,3.
- Curva: degraus que crescem ou diminuem em ordem (1,1,2,3,4 ou 4,3,2,1,1).
- Evite: ritmo quebrado, como 3,1,3 ou 1,3,1; o olho vê um "dente".
- Evite: degrau em L (dois pixels formando quina dupla) numa linha de 1 pixel; tire o pixel do canto.
- `revisar`: alerta acima de **6%** dos degraus fora do ritmo (`SERRILHADO_MAX`, heurística). Forma orgânica (copa, nuvem) tem alguns degraus irregulares de propósito; os exemplos do pacote ficam entre 0,6% e 1,4%.

## Contorno
- Contorno de 1 pixel separa a forma do fundo. Use nas peças da ação (personagem, inimigo, item, tiro); o cenário fica sem contorno ou com contorno mais fraco.
- Contorno seletivo (selout): o contorno pega a cor da rampa da própria forma, mais escuro do lado da sombra e mais claro (ou some) do lado da luz. Deixa a forma menos "adesivo".
- Contorno preto puro em tudo achata; prefira a cor mais escura da rampa (no estilo: `contorno_cor`).
- Linha interna só onde há dobra ou separação de peças; não contorne cada detalhe.
- No motor: `"contorno": true` no estilo; `luz_contorno` dá a borda clara do lado da luz.

## Anti-alias à mão
- Anti-alias (AA) é um pixel de tom intermediário no canto do degrau para suavizar a curva. Feito à mão, poucos e só onde o degrau incomoda.
- Use 1 tom intermediário da rampa, no degrau mais longo; nunca em volta da forma inteira (vira borrão).
- Não use AA na borda externa de sprite que vai sobre fundo variado: o tom intermediário só serve contra uma cor de fundo.
- Sprite pequeno (16 px ou menos) quase nunca precisa de AA.

## Como pedir
- Contorno e luz de contorno: campos `contorno` e `luz_contorno` do estilo (`{"base": "snes-diurno", "contorno": false}` na receita).
- Conferir: `python -m pixel_atelier revisar cena.png` e ler as linhas `pixel solto` e `serrilhado`.

Fontes: Derek Yu, "Pixel Art Tutorial" (derekyu.com/makegames/pixelart.html) e "Common Mistakes" (derekyu.com/makegames/pixelart2.html); tutoriais de Pedro Medeiros (saint11.art/blog/pixel-art-tutorials).
