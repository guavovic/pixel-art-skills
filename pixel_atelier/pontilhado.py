"""Dithering ordenado (matriz de Bayer): névoa, raios, halos e degradê sem meia transparência.

Cada pixel fica cheio ou vazio, comparando a densidade desejada com o limiar de Bayer da posição.
Com a largura múltipla de 4 vezes a escala, o padrão também fecha o laço horizontal.
"""
from __future__ import annotations

from typing import Callable, Sequence

from PIL import Image

from .cor import RGB

BAYER4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def limiar(x: int, y: int) -> float:
    """Limiar de Bayer 4x4 da posição, de 0 a 1."""
    return (BAYER4[y & 3][x & 3] + 0.5) / 16.0


def mascara_pontilhada(
    largura: int,
    altura: int,
    densidade: Callable[[int, int], float],
    escala: int = 1,
) -> Image.Image:
    """Máscara L (0 ou 255): o pixel acende quando `densidade(x, y)` passa do limiar de Bayer.

    `escala=2` deixa o pontilhado com pontos de 2x2, mais pesado; para névoa leve use 1.
    """
    mascara = Image.new("L", (largura, altura), 0)
    px = mascara.load()
    for y in range(altura):
        linha = BAYER4[(y // escala) & 3]
        for x in range(largura):
            d = densidade(x, y)
            if d > 0 and d > (linha[(x // escala) & 3] + 0.5) / 16.0:
                px[x, y] = 255
    return mascara


def escolher_no_degrade(cores: Sequence[RGB], valor: float, x: int, y: int) -> RGB:
    """Cor do degradê em `valor` (0 a 1), pontilhando entre os dois passos vizinhos."""
    v = min(0.999999, max(0.0, valor)) * (len(cores) - 1)
    i = int(v)
    if v - i > limiar(x, y) and i + 1 < len(cores):
        i += 1
    return cores[i]


def degrade(
    largura: int,
    altura: int,
    cores: Sequence[RGB],
    inicio: float = 0.0,
    fim: float = 1.0,
    horizontal: bool = False,
) -> Image.Image:
    """Degradê pontilhado entre `cores` (da primeira à última). `inicio` e `fim` em fração do eixo."""
    if not cores:
        raise ValueError("degradê sem cores")
    imagem = Image.new("RGBA", (largura, altura))
    px = imagem.load()
    total = largura if horizontal else altura
    a = inicio * total
    passo = max(1.0, fim * total - a - 1)  # a última linha da faixa já é a última cor
    for y in range(altura):
        for x in range(largura):
            p = x if horizontal else y
            r, g, bb = escolher_no_degrade(cores, (p - a) / passo, x, y)
            px[x, y] = (r, g, bb, 255)
    return imagem


def xadrez(largura: int, altura: int) -> Image.Image:
    """Máscara de xadrez 50%: o pontilhado mais simples, usado na transição entre tons."""
    mascara = Image.new("L", (largura, altura), 0)
    px = mascara.load()
    for y in range(altura):
        for x in range((y & 1), largura, 2):
            px[x, y] = 255
    return mascara
