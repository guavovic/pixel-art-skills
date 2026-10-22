# Composição

Cena de jogo em camadas: o fundo dá o clima, a camada da ação precisa ler em qualquer ponto da tela.

## Camadas por profundidade
| Plano | Valor | Contraste e detalhe |
| --- | --- | --- |
| céu e longe | faixa estreita, perto da cor da atmosfera | pouco; formas grandes, sem contorno |
| meio | faixa média | médio |
| ação (personagem, chão onde pisa) | do mais escuro ao mais claro da cena | o maior; contorno e detalhe fino ficam aqui |
| frente (passa na frente da ação) | quase silhueta, escura | só recorte e um acento de cor; pouca área |

- Perspectiva atmosférica: quanto mais longe, mais a camada puxa para a cor do céu ou da névoa: menos contraste e saturação, **sem escurecer**.
- Camadas vizinhas precisam se separar: a borda de cada camada contra o que está atrás dela tem diferença de valor mediana de pelo menos **0,05** (`CONTRASTE_CAMADAS`). É o passo mínimo visível (o mesmo de `SOME` e do passo de rampa em `cor`): abaixo disso as duas camadas viram uma mancha só. O longe pode ter pouco contraste, nunca nenhum.
- A camada da frente (a última com borda) contra tudo atrás: pelo menos **0,10** (`CONTRASTE_FRENTE`), o dobro do mínimo, porque é ela que tem de ler.
- Rolagem em camadas (parallax): camada longe anda devagar, perto anda rápido; frente pode andar mais rápido que o mundo.

## Foco e leitura
- Um ponto de interesse por tela: o maior contraste de valor e a cor de destaque ficam nele.
- Deixe área de descanso (céu liso, chão simples) em volta do foco; detalhe em toda parte não deixa nada ler.
- Linhas do cenário (galhos, morros, raios) levam o olho para o foco, não para fora da tela.
- Teste com o personagem na parte mais cheia de detalhe da tela, com um inimigo junto.

## Repetição
- Fundo em laço repete por natureza; o problema é o mesmo objeto, igualzinho, 3 vezes à vista. Varie seed, tamanho e espaço.
- `revisar`: alerta quando um trecho de **12x12** com detalhe aparece igual **3** ou mais vezes sem sobrepor (`JANELA`, `COPIAS`; heurística). 12 px é o tamanho de um objeto pequeno numa cena 320x180; 2 cópias ainda passam por padrão de ladrilho. Textura periódica, listras e pontilhado não contam.

## Laço
- Fundo de rolagem dá a volta: a coluna da borda direita encosta na da esquerda. Emenda visível (árvore cortada, degradê que não volta) pisca a cada volta da câmera.
- `revisar` confere o laço sozinho na cena que o `gerar` marcou com laço (a marca fica no PNG; `--laco`, ou `laco` na ferramenta MCP, força a conferência numa imagem sem marca). Ele mede a diferença de valor entre a coluna da direita e a da esquerda, no composto e em cada camada; pixel cheio contra vazio conta 1. Alerta quando a emenda passa de **3** vezes a média das diferenças entre colunas vizinhas (`LACO_EMENDA`) e também da maior delas. Num laço certo a emenda é só mais um par de colunas; 3 vezes a média deixa folga para a borda de um objeto que cai bem na emenda.
- Conserto: a camada com `"laco": true` (padrão da receita), largura múltipla de 8.

## Como pedir
- Camadas do fundo para a frente; `profundidade` de 1 (longe) a 0 (perto) puxa as cores para a atmosfera do estilo.
- Separação entre camadas: afaste as `profundidade` de camadas vizinhas (0,85 e 0,65 já é pouco no noturno; 0,95 e 0,65 separa) ou troque o `papel` de uma delas.
- Variação: `seed` por camada, `espaco`, `tamanho`, `quantidade`.
- Conferir: `revisar cena.png` lê as camadas da pasta `<cena>/` e diz qual camada tem o contraste mais baixo. Sem a pasta, o contraste sai das silhuetas que o `revisar` separa no composto: mais fraco (camadas de cores quase iguais viram uma só), então para a cena final grave as camadas (`"saida": "tudo"`).

Fontes: Raymond Schlitter, "Pixelblog 11: Landscape Pixeling" e "Pixelblog 23: Parallax Scrolling" (slynyrd.com/pixelblog-catalogue); tutoriais de Pedro Medeiros, "Parallax" (saint11.art/blog/pixel-art-tutorials).
