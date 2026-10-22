"""Cristais: aglomerados de prismas com face clara e face escura, e um halo pontilhado opcional."""
from __future__ import annotations

import math
import random
from typing import Any

from PIL import Image

from ..pintura import pintar
from ..ruido import sortear
from ..tela import Peca, Tela
from ._base import preparar, semente
from .rocha import pedra


def prisma(tela: Tela, cx: float, base: float, h: float, w: float, inclinacao: float, lado_luz: int = -1) -> list[Peca]:
    """Um prisma de 5 lados. A metade do lado da luz (`lado_luz` -1 esquerda, 1 direita) ganha um tom acima."""
    ponta = (cx + inclinacao * h, base - h)
    ombro = base - h * 0.62
    corpo = [(cx - w, base), (cx - w, ombro), ponta, (cx + w, ombro), (cx + w, base)]
    borda = cx + w * (1 if lado_luz > 0 else -1)
    face = [(borda, base), (borda, ombro), ponta, (cx + inclinacao * h * 0.6, ombro + 1), (cx, base)]
    m, f = tela.nova_mascara(), tela.nova_mascara()
    tela.poligono(m, corpo)
    tela.poligono(f, face)
    return [Peca(m, "cristal"), Peca(f, "cristal", tom=1, liso=True)]


def aglomerado(tela: Tela, cx: float, base: float, h: float, r: random.Random, lado_luz: int = -1) -> list[Peca]:
    pecas = []
    hastes = [(-0.38, r.uniform(0.5, 0.7), -0.28), (0.36, r.uniform(0.55, 0.75), 0.24), (0.0, 1.0, r.uniform(-0.08, 0.08))]
    if h > 24 and r.random() < 0.6:
        hastes.insert(0, (r.choice((-0.6, 0.6)), r.uniform(0.3, 0.45), r.choice((-0.4, 0.4))))
    for dx, escala, inclinacao in hastes:
        altura = h * escala
        pecas.extend(prisma(tela, cx + dx * h * 0.5, base, altura, max(1.5, altura * 0.2), inclinacao, lado_luz))
    return pecas


def cristal(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.0,
    laco: bool = True,
    deslocamento: int = 0,
    quantidade: int = 4,
    base: float = 0.88,
    tamanho: float | list = (0.1, 0.22),
    brilho: float = 0.3,
    raio_brilho: float = 1.3,
    pedra_na_base: bool = True,
) -> Image.Image:
    """Aglomerados de cristal ao longo da largura.

    - `tamanho`: altura do prisma maior, em fração da altura da camada;
    - `brilho`: densidade do halo pontilhado em volta (0 desliga);
    - `raio_brilho`: raio do halo em alturas de cristal;
    - `pedra_na_base`: pedra de apoio embaixo de cada aglomerado.
    """
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    r = random.Random(semente(seed, 4))
    y_base = base * altura
    pecas: list[Peca] = []
    centros = []
    for i in range(quantidade):
        cx = (i + r.uniform(0.2, 0.8)) * largura / max(1, quantidade)
        h = max(6.0, sortear(r, tamanho) * altura)
        sorteio = random.Random(r.randrange(1 << 30))
        if pedra_na_base:
            pecas.extend(pedra(tela, cx, y_base + 2, h * 0.9, h * 0.3, sorteio))
        pecas.extend(aglomerado(tela, cx, y_base - h * 0.08, h, sorteio, estilo.direcao_luz[0] or -1))
        centros.append((cx, y_base - h * 0.55, h))

    corpo = pintar(tela, pecas, estilo, profundidade)
    if brilho <= 0:
        return corpo

    def densidade(x: int, y: int) -> float:
        melhor = 0.0
        for cx, cy, h in centros:
            dx = abs(x - cx)
            if laco:
                dx = min(dx % largura, largura - dx % largura)
            d = math.hypot(dx, (y - cy) * 1.15) / (h * raio_brilho)
            melhor = max(melhor, max(0.0, 1.0 - d) ** 2)
        return melhor * brilho

    halo = tela.pontilhar(densidade)
    rampa = estilo.rampa("cristal", profundidade)
    camada = Image.new("RGBA", tela.tamanho, (0, 0, 0, 0))
    camada.paste(rampa[-1] + (255,), mask=halo)
    return Image.alpha_composite(camada, corpo)
