# pixel-atelier

Ateliê de pixel art para agentes de IA. O motor guarda a técnica (paleta, rampas, luz, pontilhado, laço sem emenda) e as formas; o agente só escolhe o que vai na cena. Tudo é determinístico por seed.

> README de trabalho. A vitrine do projeto vem na #9.

## O que já existe (v0.1, issue #1)

- **Técnicas** (`pixel_atelier/`)
  - `cor.py`: rampas com mudança de matiz (`gerar_rampa`), mistura, quantização para a paleta (`quantizar`).
  - `estilo.py`: o `Estilo` (paleta, rampas por papel, atmosfera, luz, jeito de sombrear), lido de dicionário ou JSON.
  - `pontilhado.py`: dithering ordenado de Bayer 4x4 (`mascara_pontilhada`, `degrade`).
  - `tela.py`: tela com laço horizontal; desenho e operações de máscara dão a volta na borda.
  - `pintura.py`: volume por faixas de luz e sombra, luz de contorno, contorno, limpeza de pixel solto.
  - `imagem.py`: `compor`, `ampliar` (vizinho mais próximo) e `ladrilhar`.
- **Formas** (`pixel_atelier/formas/`): `ceu`, `nuvem`, `terreno`, `arvore`, `rocha`, `cristal`, `nevoa`, `raios`. Cada uma devolve uma camada RGBA no tamanho real de pixel, só com cores da paleta e alfa 0 ou 255.
- **Estilos** (`pixel_atelier/estilos/*.json`): `metroidvania-noturno`, `snes-diurno`, `game-boy`.
- **Exemplo**: `exemplos/montar_cena.py` monta a mesma receita nos três estilos.

| metroidvania-noturno | snes-diurno | game-boy |
| --- | --- | --- |
| ![](exemplos/metroidvania-noturno-3x.png) | ![](exemplos/snes-diurno-3x.png) | ![](exemplos/game-boy-3x.png) |

## Uso

```python
from pixel_atelier import ampliar, carregar_estilo, compor, desenhar

estilo = carregar_estilo("snes-diurno")
cena = compor([
    desenhar("ceu", estilo, 320, 180, astro="sol"),
    desenhar("terreno", estilo, 320, 180, seed=3, profundidade=0.85, base=0.62, amplitude=0.3, papel="pedra"),
    desenhar("arvore", estilo, 320, 180, seed=4, profundidade=0.4, tipo="mista", base=0.85),
    desenhar("terreno", estilo, 320, 180, seed=5, base=0.88),
])
ampliar(cena, 3).save("cena.png")
```

Toda forma tem a mesma assinatura: `forma(estilo, largura, altura, *, seed=0, profundidade=0.0, laco=True, deslocamento=0, **parametros)`. Posições e tamanhos são frações da altura, então a mesma receita serve em qualquer resolução. Com laço, a largura precisa ser múltipla de 8.

`profundidade` vai de 0 (perto) a 1 (fundo) e puxa as cores para a atmosfera do estilo: é o que separa as camadas.

## Desenvolvimento

```
pip install -e .[dev]
pytest
python exemplos/montar_cena.py
```

Requer Python 3.11+ e Pillow. Sem numpy.

## Licença

MIT.
