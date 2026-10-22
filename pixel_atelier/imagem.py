"""Utilidades de imagem: compor camadas, ampliar sem borrar e repetir lado a lado."""
from __future__ import annotations

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
