"""Cor: conversões, rampas com mudança de matiz e quantização para uma paleta fechada.

Toda cor que o motor pinta passa por `cor_mais_proxima` ou `quantizar`, então a imagem final
só tem cores da paleta do estilo. Isso deixa a arte com cara de pixel art de verdade e permite
conferir a paleta depois.
"""
from __future__ import annotations

import colorsys
from functools import lru_cache
from typing import Iterable, Sequence

from PIL import Image

RGB = tuple[int, int, int]

AMARELO = 60 / 360  # para onde a luz puxa o matiz
AZUL = 240 / 360  # para onde a sombra puxa o matiz


def hex_para_rgb(valor: str) -> RGB:
    """`"#1d3d52"` ou `"1d3d52"` ou `"#abc"` para `(29, 61, 82)`."""
    texto = valor.strip().lstrip("#")
    if len(texto) == 3:
        texto = "".join(c * 2 for c in texto)
    if len(texto) != 6:
        raise ValueError(f"cor inválida: {valor!r}")
    try:
        return (int(texto[0:2], 16), int(texto[2:4], 16), int(texto[4:6], 16))
    except ValueError as erro:
        raise ValueError(f"cor inválida: {valor!r}") from erro


def rgb_para_hex(cor: Sequence[int]) -> str:
    return "#%02x%02x%02x" % (cor[0], cor[1], cor[2])


def misturar(a: Sequence[int], b: Sequence[int], t: float) -> RGB:
    """Mistura linear de `a` (t=0) até `b` (t=1)."""
    t = min(1.0, max(0.0, t))
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t))


def luminancia(cor: Sequence[int]) -> float:
    """Luminância relativa aproximada, de 0 a 1 (sem correção gama, serve para ordenar)."""
    return (0.2126 * cor[0] + 0.7152 * cor[1] + 0.0722 * cor[2]) / 255


def distancia2(a: Sequence[int], b: Sequence[int]) -> int:
    """Distância euclidiana ao quadrado em RGB, a mesma que o Pillow usa ao quantizar."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def cor_mais_proxima(cor: Sequence[int], paleta: Sequence[RGB]) -> RGB:
    """Cor da paleta mais perto de `cor`. Em empate fica a que vem primeiro na paleta."""
    if not paleta:
        raise ValueError("paleta vazia")
    melhor = paleta[0]
    melhor_d = distancia2(cor, melhor)
    for candidata in paleta[1:]:
        d = distancia2(cor, candidata)
        if d < melhor_d:
            melhor, melhor_d = candidata, d
    return melhor


def sem_repetir(cores: Iterable[RGB]) -> list[RGB]:
    vistas: set[RGB] = set()
    saida = []
    for c in cores:
        if c not in vistas:
            vistas.add(c)
            saida.append(c)
    return saida


def _puxar_matiz(h: float, alvo: float, quanto: float) -> float:
    """Move o matiz `h` em direção a `alvo` pelo caminho mais curto, sem passar dele (tudo de 0 a 1)."""
    diferenca = (alvo - h + 0.5) % 1.0 - 0.5
    passo = max(-abs(diferenca), min(abs(diferenca), quanto)) * (1 if diferenca >= 0 else -1)
    return (h + passo) % 1.0


def gerar_rampa(
    base: Sequence[int],
    passos: int = 5,
    matiz: float = 20.0,
    escuro: float = 0.18,
    claro: float = 0.92,
    saturacao: float = 1.0,
) -> list[RGB]:
    """Rampa do escuro ao claro a partir de uma cor, com mudança de matiz.

    A sombra puxa o matiz para o azul e a luz puxa para o amarelo, `matiz` graus no máximo em cada
    ponta. A saturação sobe um pouco na sombra e cai na luz. É o que faz a rampa parecer pintada,
    não só a mesma cor mais clara e mais escura.
    """
    if passos < 2:
        raise ValueError("a rampa precisa de pelo menos 2 passos")
    h, s, _ = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
    rampa = []
    for i in range(passos):
        t = i / (passos - 1)
        u = t * 2 - 1  # -1 na sombra, 1 na luz
        if u < 0:
            hh = _puxar_matiz(h, AZUL, -u * matiz / 360)
        else:
            hh = _puxar_matiz(h, AMARELO, u * matiz / 360)
        ss = min(1.0, max(0.0, s * saturacao * (1.0 - 0.22 * u)))
        vv = escuro + (claro - escuro) * t
        r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
        rampa.append((round(r * 255), round(g * 255), round(b * 255)))
    return rampa


@lru_cache(maxsize=64)
def _imagem_de_paleta(paleta: tuple[RGB, ...]) -> Image.Image:
    if len(paleta) > 256:
        raise ValueError("a paleta tem mais de 256 cores")
    valores: list[int] = []
    for c in paleta:
        valores.extend(c)
    valores.extend(list(paleta[0]) * (256 - len(paleta)))  # repete a primeira: não muda o resultado
    imagem = Image.new("P", (1, 1))
    imagem.putpalette(valores)
    return imagem


def limpar_alfa(imagem: Image.Image, limite: int = 128) -> Image.Image:
    """Alfa vira 0 ou 255. Pixel art não tem meia transparência."""
    rgba = imagem.convert("RGBA")
    alfa = rgba.getchannel("A").point(lambda v: 255 if v >= limite else 0)
    vazio = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    cheio = rgba.copy()
    cheio.putalpha(255)
    return Image.composite(cheio, vazio, alfa)


def quantizar(imagem: Image.Image, paleta: Sequence[RGB]) -> Image.Image:
    """Troca cada pixel pela cor mais próxima da paleta, sem dithering. Devolve RGBA com alfa 0 ou 255."""
    rgba = limpar_alfa(imagem)
    alfa = rgba.getchannel("A")
    indexada = rgba.convert("RGB").quantize(palette=_imagem_de_paleta(tuple(paleta)), dither=Image.Dither.NONE)
    saida = indexada.convert("RGB").convert("RGBA")
    return Image.composite(saida, Image.new("RGBA", rgba.size, (0, 0, 0, 0)), alfa)


def cores_usadas(imagem: Image.Image) -> set[RGB]:
    """Cores dos pixels visíveis (alfa > 0)."""
    rgba = imagem.convert("RGBA")
    contagem = rgba.getcolors(maxcolors=rgba.width * rgba.height) or []
    return {(r, g, b) for _, (r, g, b, a) in contagem if a > 0}
