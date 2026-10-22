"""Utilidades de imagem: abrir, compor camadas, ampliar sem borrar, voltar ao tamanho real e repetir lado a lado."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops
from PIL.PngImagePlugin import PngInfo

MARCA_LACO = "pixel-atelier:laco"  # chave de texto no PNG que o `gerar` grava: "sim" ou "nao"
MARCA_ESCALA = "pixel-atelier:escala"  # no composto ampliado: quantas vezes ("3")
BLOCO_MAX = 16  # sem marca, bloco maior que isso é arte chapada, não ampliada
ACASO = 65536  # sem marca, o bloco N vale se N elevado ao número de trocas passa disso (acaso de 1 em 65536)


def gravar_png(imagem: Image.Image, destino: Path, laco: bool, escala: int = 1) -> None:
    """Grava o PNG com a marca de laço (e a de escala, se ampliado) em blocos de texto (tEXt).

    As marcas viajam junto com o arquivo.
    """
    info = PngInfo()
    info.add_text(MARCA_LACO, "sim" if laco else "nao")
    if escala > 1:
        info.add_text(MARCA_ESCALA, str(escala))
    imagem.save(destino, pnginfo=info)


def marca_de_laco(arquivo: "str | Path") -> bool | None:
    """O que o `gerar` gravou no PNG: True (cena com laço), False (sem laço) ou None (sem marca)."""
    with Image.open(arquivo) as aberta:
        valor = aberta.info.get(MARCA_LACO)
    return {"sim": True, "nao": False}.get(valor) if isinstance(valor, str) else None


def escala_indicada(arquivo: "str | Path") -> int | None:
    """Ampliação que o arquivo declara: a marca do `gerar` ou o nome `<cena>-Nx.png`; None sem nenhuma."""
    with Image.open(arquivo) as aberta:
        valor = aberta.info.get(MARCA_ESCALA)
    if isinstance(valor, str) and valor.isdigit() and int(valor) > 1:
        return int(valor)
    sufixo = Path(arquivo).stem.rpartition("-")[2]
    if sufixo.endswith("x") and sufixo[:-1].isdigit() and int(sufixo[:-1]) > 1:
        return int(sufixo[:-1])
    return None


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


def trocas_de_cor(imagem: Image.Image) -> tuple[list[int], list[int]]:
    """Colunas x onde alguma linha troca de cor (x - 1 para x) e linhas y onde alguma coluna troca."""
    largura, altura = imagem.size
    xs: list[int] = []
    ys: list[int] = []
    if largura > 1:
        diferenca = ImageChops.difference(imagem.crop((1, 0, largura, altura)), imagem.crop((0, 0, largura - 1, altura)))
        xs = [x + 1 for x, troca in enumerate(diferenca.getprojection()[0]) if troca]
    if altura > 1:
        diferenca = ImageChops.difference(imagem.crop((0, 1, largura, altura)), imagem.crop((0, 0, largura, altura - 1)))
        ys = [y + 1 for y, troca in enumerate(diferenca.getprojection()[1]) if troca]
    return xs, ys


def escala_inteira(imagem: Image.Image, indicada: int | None = None) -> int:
    """N quando a imagem é toda feita de blocos NxN (ampliada por vizinho mais próximo), senão 1.

    Toda troca de cor cai num múltiplo de N, nas duas direções. Com `indicada` (a marca do `gerar`
    ou o `-Nx` do nome), basta isso, em qualquer tamanho. Sem ela, arte chapada engana: poucas
    trocas (faixas de céu, retângulos de lado par) caem no passo do bloco por acaso. Cada posição
    de troca diferente cai num múltiplo de N por acaso uma vez em N, então o bloco só vale com
    troca nos dois eixos, N até `BLOCO_MAX` e N elevado ao número de trocas acima de `ACASO`.
    """
    xs, ys = trocas_de_cor(imagem)
    if not xs and not ys:
        return 1  # cor única: qualquer N serviria
    n = math.gcd(imagem.width, imagem.height, *xs, *ys)
    if indicada and indicada > 1 and n % indicada == 0:
        return indicada
    if n == 1 or n > BLOCO_MAX or not xs or not ys or n ** (len(xs) + len(ys)) < ACASO:
        return 1
    return n


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
