"""Tela de desenho com laço horizontal e operações de máscara que respeitam o laço.

Com `laco=True`, tudo que a forma desenha aparece também deslocado uma largura para cada lado,
e os deslocamentos de máscara dão a volta na horizontal. A camada vira um anel: a coluna depois
da última é a coluna 0, então a imagem repete lado a lado sem emenda. Na vertical a borda é
"presa" (fora da imagem conta como igual à beira), para o chão não ganhar sombra na última linha.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from PIL import Image, ImageChops, ImageDraw

from .pontilhado import mascara_pontilhada

Ponto = tuple[float, float]


@dataclass
class Peca:
    """Um pedaço de forma: máscara L (0 ou 255) e o papel de cor que ela usa no estilo.

    `tom` desloca o tom na rampa (-1 mais escuro, +1 mais claro). `liso` pinta só esse tom, sem
    faixas de luz e sombra (rachadura, face clara de cristal, pedrinha no chão).
    """

    mascara: Image.Image
    papel: str
    tom: int = 0
    liso: bool = False


class Tela:
    def __init__(self, largura: int, altura: int, laco: bool = True, deslocamento: int = 0):
        if largura <= 0 or altura <= 0:
            raise ValueError("largura e altura precisam ser positivas")
        if laco and largura % 8:
            raise ValueError(f"com laço a largura precisa ser múltipla de 8 (veio {largura}), senão o pontilhado emenda")
        self.largura = largura
        self.altura = altura
        self.laco = laco
        # o mundo anda `deslocamento` pixels para a direita; com laço, o que sai de um lado entra do outro
        self.deslocamento = deslocamento % largura if laco else deslocamento

    @property
    def tamanho(self) -> tuple[int, int]:
        return (self.largura, self.altura)

    def nova_mascara(self, valor: int = 0) -> Image.Image:
        return Image.new("L", self.tamanho, valor)

    def _deslocamentos(self) -> Sequence[int]:
        d = self.deslocamento
        return (d - self.largura, d, d + self.largura) if self.laco else (d,)

    # --- desenho (cada chamada desenha nas cópias do laço) -----------------------------------

    def poligono(self, mascara: Image.Image, pontos: Sequence[Ponto], valor: int = 255) -> None:
        d = ImageDraw.Draw(mascara)
        pontos = [(_q(x), _q(y)) for x, y in pontos]
        for dx in self._deslocamentos():
            d.polygon([(x + dx, y) for x, y in pontos], fill=valor)

    def elipse(self, mascara: Image.Image, cx: float, cy: float, rx: float, ry: float, valor: int = 255) -> None:
        d = ImageDraw.Draw(mascara)
        cx, cy, rx, ry = _q(cx), _q(cy), _q(rx), _q(ry)
        for dx in self._deslocamentos():
            d.ellipse([cx + dx - rx, cy - ry, cx + dx + rx, cy + ry], fill=valor)

    def retangulo(self, mascara: Image.Image, x0: float, y0: float, x1: float, y1: float, valor: int = 255) -> None:
        x0, y0, x1, y1 = _q(x0), _q(y0), _q(x1), _q(y1)
        vazio = x1 < x0 or y1 < y0
        if vazio:
            return
        d = ImageDraw.Draw(mascara)
        for dx in self._deslocamentos():
            d.rectangle([x0 + dx, y0, x1 + dx, y1], fill=valor)

    def linha(self, mascara: Image.Image, pontos: Sequence[Ponto], espessura: int = 1, valor: int = 255) -> None:
        d = ImageDraw.Draw(mascara)
        pontos = [(_q(x), _q(y)) for x, y in pontos]
        for dx in self._deslocamentos():
            d.line([(x + dx, y) for x, y in pontos], fill=valor, width=max(1, int(round(espessura))))

    def na_tela(self, x: int) -> int | None:
        """Coluna da tela onde cai o x do mundo, ou None se cair fora."""
        sx = x + self.deslocamento
        if self.laco:
            return sx % self.largura
        return sx if 0 <= sx < self.largura else None

    def no_mundo(self, x: int) -> int:
        """x do mundo que aparece na coluna `x` da tela."""
        mx = x - self.deslocamento
        return mx % self.largura if self.laco else mx

    def ponto(self, mascara: Image.Image, x: int, y: int, valor: int = 255) -> None:
        sx = self.na_tela(x)
        if sx is not None and 0 <= y < self.altura:
            mascara.putpixel((sx, y), valor)

    def pontilhar(self, densidade: Callable[[int, int], float], escala: int = 1) -> Image.Image:
        """Máscara pontilhada com `densidade(x, y)` em coordenadas do mundo (o limiar de Bayer é o da tela)."""
        mundo = [self.no_mundo(x) for x in range(self.largura)]
        return mascara_pontilhada(self.largura, self.altura, lambda x, y: densidade(mundo[x], y), escala)

    # --- operações de máscara ----------------------------------------------------------------

    def deslocar(self, mascara: Image.Image, dx: int, dy: int) -> Image.Image:
        """Move o conteúdo `dx`, `dy` pixels. Horizontal dá a volta com laço; vertical prende na borda."""
        saida = mascara
        if dx:
            if self.laco:
                saida = ImageChops.offset(saida, dx, 0)
            else:
                saida = _deslocar_preso(saida, dx, 0)
        if dy:
            saida = _deslocar_preso(saida, 0, dy)
        return saida

    def faixa(self, mascara: Image.Image, direcao: tuple[int, int], espessura: int) -> Image.Image:
        """Pixels da máscara a até `espessura` pixels da borda voltada para `direcao`."""
        dentro = mascara
        for i in range(1, espessura + 1):
            vizinho = self.deslocar(mascara, -direcao[0] * i, -direcao[1] * i)
            dentro = ImageChops.darker(dentro, vizinho)
        return ImageChops.subtract(mascara, dentro)

    def erodir(self, mascara: Image.Image) -> Image.Image:
        saida = mascara
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
            saida = ImageChops.darker(saida, self.deslocar(mascara, dx, dy))
        return saida

    def dilatar(self, mascara: Image.Image, cruz: bool = False) -> Image.Image:
        vizinhos = ((0, -1), (-1, 0), (1, 0), (0, 1))
        if not cruz:
            vizinhos += ((-1, -1), (1, -1), (-1, 1), (1, 1))
        saida = mascara
        for dx, dy in vizinhos:
            saida = ImageChops.lighter(saida, self.deslocar(mascara, dx, dy))
        return saida

    def partes_grossas(self, mascara: Image.Image) -> Image.Image:
        """Abertura morfológica: some com o que tem menos de 3 pixels de espessura (ponta de galho)."""
        return self.dilatar(self.erodir(mascara))


def _q(valor: float) -> float:
    """Arredonda para quartos de pixel, que o ponto flutuante representa exato.

    Assim a mesma forma andada um número inteiro de pixels rasteriza igualzinho, e o laço fecha
    pixel a pixel.
    """
    return round(valor * 4) / 4


def _deslocar_preso(mascara: Image.Image, dx: int, dy: int) -> Image.Image:
    largura, altura = mascara.size
    saida = Image.new(mascara.mode, mascara.size, 0)
    saida.paste(mascara, (dx, dy))
    if dy > 0:
        beira = mascara.crop((0, 0, largura, 1))
        for y in range(min(dy, altura)):
            saida.paste(beira, (0, y))
    elif dy < 0:
        beira = mascara.crop((0, altura - 1, largura, altura))
        for y in range(max(0, altura + dy), altura):
            saida.paste(beira, (0, y))
    if dx > 0:
        beira = mascara.crop((0, 0, 1, altura))
        for x in range(min(dx, largura)):
            saida.paste(beira, (x, 0))
    elif dx < 0:
        beira = mascara.crop((largura - 1, 0, largura, altura))
        for x in range(max(0, largura + dx), largura):
            saida.paste(beira, (x, 0))
    return saida
