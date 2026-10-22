"""Utilidades de imagem: abrir, compor camadas, ampliar sem borrar, voltar ao tamanho real e repetir lado a lado."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image


def compor(camadas: Iterable[Image.Image]) -> Image.Image:
    """Empilha as camadas RGBA na ordem (a primeira fica no fundo)."""
    camadas = list(camadas)
    if not camadas:
        raise ValueError("nenhuma camada para compor")
    base = Image.new("RGBA", camadas[0].size, (0, 0, 0, 0))
    for camada in camadas:
        if camada.size != base.size:
            raise ValueError(f"camada {camada.size} com tamanho diferente da cena {base.size}")
        base = Image.alpha_composite(base, camada.convert("RGBA"))
    return base


def ampliar(imagem: Image.Image, fator: int) -> Image.Image:
    """Amplia por vizinho mais próximo: cada pixel vira um bloco `fator` x `fator`, sem borrar."""
    if fator < 1:
        raise ValueError("o fator de ampliação precisa ser 1 ou mais")
    return imagem.resize((imagem.width * fator, imagem.height * fator), Image.Resampling.NEAREST)


def ladrilhar(imagem: Image.Image, vezes: int = 2) -> Image.Image:
    """Repete a imagem lado a lado. Serve para conferir o laço: a emenda não pode aparecer."""
    saida = Image.new(imagem.mode, (imagem.width * vezes, imagem.height))
    for i in range(vezes):
        saida.paste(imagem, (i * imagem.width, 0))
    return saida


def abrir(imagem: "str | Path | Image.Image") -> Image.Image:
    """Arquivo ou imagem já aberta, sempre em RGBA."""
    if isinstance(imagem, Image.Image):
        return imagem.convert("RGBA")
    with Image.open(imagem) as aberta:
        return aberta.convert("RGBA")


def escala_inteira(imagem: Image.Image) -> int:
    """N quando a imagem é toda feita de blocos NxN (ampliada por vizinho mais próximo), senão 1."""
    if len(imagem.getcolors(maxcolors=2) or []) == 1:
        return 1  # cor única: qualquer N serviria
    px = imagem.load()
    largura, altura = imagem.size
    n = 0
    for linhas, colunas, ponto in ((altura, largura, lambda a, b: px[b, a]), (largura, altura, lambda a, b: px[a, b])):
        for a in range(linhas):
            inicio = 0
            for b in range(1, colunas + 1):
                if b == colunas or ponto(a, b) != ponto(a, b - 1):
                    n = math.gcd(n, b - inicio)
                    if n == 1:
                        return 1
                    inicio = b
    # blocos grandes demais ou imagem que encolheria para menos de 16 pixels: é arte chapada, não ampliada
    return n if n <= 16 and min(largura, altura) // n >= 16 else 1


def reduzir(imagem: Image.Image, n: int) -> Image.Image:
    """Desfaz `ampliar(imagem, n)`: um pixel por bloco NxN."""
    return imagem if n == 1 else imagem.resize((imagem.width // n, imagem.height // n), Image.Resampling.NEAREST)
