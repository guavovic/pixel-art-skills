# Cor

Valor (claro e escuro) carrega a leitura; matiz e saturação dão o clima. Escolha o valor primeiro.

## Rampas
- Rampa: a sequência de tons de um material, do escuro ao claro. 3 a 5 passos bastam para quase tudo; 2 em sprite pequeno.
- Mudança de matiz (hue shift): a sombra puxa para o frio (azul, roxo), a luz para o quente (amarelo). Rampa que só muda o brilho fica "plástica" e briga com as outras.
- Faixa útil: 15° a 30° de matiz entre a ponta escura e a clara.
- `revisar --estilo` (linha `matiz da rampa`): alerta quando uma rampa do estilo usada na imagem muda menos de **3** graus (`RAMPA_MATIZ`) do tom escuro ao claro. Abaixo de 3° é só o arredondamento do RGB: a rampa muda só o brilho. De 3° a 15° é escolha de clima (noite fria quase num matiz só).
- Só contam cores com saturação de pelo menos **0,10** (`RAMPA_SATURACAO`; abaixo disso é quase cinza e, na grade de 15 bits, o matiz é só arredondamento), e a rampa toda abaixo de valor **0,25** (`RAMPA_ESCURA`) fica de fora: no escuro o matiz quase não aparece. Rampa clara e pouco saturada (nuvem, neve) muda o matiz no trecho claro, por isso o corte é baixo.
- Com geração, a rampa do tema (antes da grade) também precisa mudar 3°: o arredondamento da grade sozinho passa disso e esconderia uma rampa que só muda o brilho. O alerta diz `no tema`.
- Saturação: mais alta nos tons médios e escuros, cai no tom mais claro. Luz quase branca e saturada demais "queima".
- Passo de valor entre vizinhos da rampa: pelo menos **0,05** (cerca de 13 em 255), senão os dois tons viram um só. É o mesmo número que o `revisar` usa para dizer que uma borda some (`SOME`).
- Compartilhe tons entre rampas (o escuro da folha serve de sombra da pedra). Paleta fica menor e mais coesa.

## Paleta limitada
- Comece com poucas cores e só acrescente quando faltar. Sprite: até **16** cores (`CORES_SPRITE`). Cena: até **64** (`CORES_CENA`).
- Por quê: 16 é uma subpaleta de console 16 bits (15 cores e o transparente); uma tela de SNES mostra até 128 cores de fundo (8 subpaletas de 16), então 64 deixa folga sem virar foto.
- Mais de 256 cores: o `revisar` avisa que não parece pixel art (borrão, anti-alias automático ou JPEG).
- Duas cores a menos de **4** de distância RGB (`QUASE_IGUAL`) o olho não separa: junte. A paleta que o estilo monta das rampas já junta sozinha; numa paleta fechada à mão, o `revisar` só informa esses pares.
- Uma cor de destaque por cena, usada pouco (lanterna, cristal, olho do inimigo). É o que dá vida.
- Paletas prontas: lospec.com/palette-list (escolha pelo número de cores).

## Faça e evite
- Faça: teste em escala de cinza. Se o desenho não lê em cinza, a cor não vai salvar.
- Faça: fundo em cor fria e dessaturada; personagem e perigo em cores quentes e saturadas que o cenário não usa.
- Evite: preto e branco puros como tom comum; guarde para contorno e brilho máximo.
- Evite: cada material com sua rampa isolada de 6 ou mais tons.

## Como pedir
- Rampa gerada com mudança de matiz: `"rampas": {"pedra": {"base": "#7c7c90", "passos": 5, "matiz": 16}}` (`escuro`, `claro` e `saturacao` opcionais).
- Rampa fechada: lista de hex do escuro ao claro. Paleta fechada: campo `paleta`.
- Estilo a partir de uma imagem: `python -m pixel_atelier ref referencia.png --nome meu-estilo` (responde paleta, rampas e passo de valor de cada uma).
- Conferir: `revisar --estilo nome` acusa cor fora da paleta.

Fontes: Raymond Schlitter, "Pixelblog 1: Color Palettes" (slynyrd.com/blog/2018/1/10/pixelblog-1-color-palettes); Lospec (lospec.com/palette-list).
