"""Utilidades de imagem: abrir, compor camadas, ampliar sem borrar, voltar ao tamanho real e repetir lado a lado."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops
from PIL.PngImagePlugin import PngInfo

MARCA_LACO = "pixel-atelier:laco"  # chave de texto no PNG que o `gerar` grava: "sim" ou "nao"


def gravar_png(imagem: Image.Image, destino: Path, laco: bool) -> None:
    """Grava o PNG com a marca de laço num bloco de texto (tEXt), que viaja junto com o arquivo."""
    info = PngInfo()
    info.add_text(MARCA_LACO, "sim" if laco else "nao")
    imagem.save(destino, pnginfo=info)


def marca_de_laco(arquivo: "str | Path") -> bool | None:
    """O que o `gerar` gravou no PNG: True (cena com laço), False (sem laço) ou None (sem marca)."""
    with Image.open(arquivo) as aberta:
        valor = aberta.info.get(MARCA_LACO)
    return {"sim": True, "nao": False}.get(valor) if isinstance(valor, str) else None


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


def vizinho(imagem: Image.Image, dx: int, dy: int, laco: bool = False) -> Image.Image:
    """Imagem em que cada pixel traz o vizinho a um passo (dx ou dy, o outro zero).

    Fora da borda fica o próprio pixel; com `laco`, a horizontal dá a volta.
    """
    if dx and laco:
        return ImageChops.offset(imagem, -dx, 0)
    largura, altura = imagem.size
    saida = imagem.copy()
    if dx:
        saida.paste(imagem.crop((max(0, dx), 0, largura + min(0, dx), altura)), (max(0, -dx), 0))
    if dy:
        saida.paste(imagem.crop((0, max(0, dy), largura, altura + min(0, dy))), (0, max(0, -dy)))
    return saida


def iguais(a: Image.Image, b: Image.Image) -> Image.Image:
    """Máscara L: 255 onde os dois pixels são iguais em todos os canais."""
    diferenca = ImageChops.difference(a, b)
    algum = diferenca.getchannel(0)
    for banda in range(1, len(diferenca.getbands())):
        algum = ImageChops.lighter(algum, diferenca.getchannel(banda))
    return algum.point(lambda v: 0 if v else 255)
