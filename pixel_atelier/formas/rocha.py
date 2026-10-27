"""Rochas: pedras soltas ou em grupo, com rachadura e musgo opcional."""
from __future__ import annotations

import math
import random
from typing import Any

from PIL import Image, ImageChops

from ..pintura import pintar
from ..ruido import sortear
from ..tela import Peca, Tela
from ._base import preparar, semente


def contorno_de_rocha(cx: float, base: float, w: float, h: float, r: random.Random, lados: int = 8) -> list[tuple[float, float]]:
    """Polígono de pedra: meia elipse irregular por cima e base reta."""
    pontos = [(cx - w / 2, base)]
    for i in range(lados + 1):
        a = math.pi - math.pi * i / lados
        raio = r.uniform(0.82, 1.08)
        pontos.append((cx + math.cos(a) * w / 2 * raio, base - math.sin(a) * h * raio))
    pontos.append((cx + w / 2, base))
    return pontos


def pedra(tela: Tela, cx: float, base: float, w: float, h: float, r: random.Random, musgo: float = 0.0,
          tom_musgo: int = 0) -> list[Peca]:
    m = tela.nova_mascara()
    tela.poligono(m, contorno_de_rocha(cx, base, w, h, r, lados=r.randint(6, 9)))
    pecas = [Peca(m, "pedra")]
    if w >= 10:
        racha = tela.nova_mascara()
        x0 = cx + r.uniform(-w * 0.2, w * 0.2)
        y0 = base - h * r.uniform(0.55, 0.8)
        tela.linha(racha, [(x0, y0), (x0 + r.uniform(-3, 3), y0 + h * 0.25), (x0 + r.uniform(-4, 4), y0 + h * 0.45)])
        miolo = tela.erodir(tela.erodir(m))
        pecas.append(Peca(ImageChops.multiply(racha, miolo), "pedra", tom=-1, liso=True))
    if musgo > 0 and r.random() < musgo:
        topo = tela.faixa(m, (0, -1), max(1, int(h * 0.18)))
        pecas.append(Peca(topo, "grama", tom=tom_musgo, liso=True))
    return pecas


def rocha(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.0,
    laco: bool = True,
    deslocamento: int = 0,
    quantidade: int = 6,
    base: float = 0.88,
    tamanho: float | list = (0.05, 0.12),
    achatamento: float | list = (0.55, 0.8),
    grupo: float = 0.5,
    musgo: float = 0.0,
) -> Image.Image:
    """Pedras espalhadas pela largura, apoiadas em `base`.

    - `tamanho`: largura da pedra em fração da altura da camada;
    - `achatamento`: altura da pedra em fração da largura dela;
    - `grupo`: chance de uma pedra pequena encostada na grande;
    - `musgo`: chance de musgo (papel "grama") no topo.
    """
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    r = random.Random(semente(seed, 3))
    y_base = base * altura
    pecas: list[Peca] = []
    luz_de_cima = estilo.direcao_luz[1] < 0
    tom_musgo = 1 if luz_de_cima else 0
    for i in range(quantidade):
        cx = (i + r.uniform(0.15, 0.85)) * largura / max(1, quantidade)
        w = max(4.0, sortear(r, tamanho) * altura)
        h = w * sortear(r, achatamento)
        sorteio = random.Random(r.randrange(1 << 30))
        pecas.extend(pedra(tela, cx, y_base + 1, w, h, sorteio, musgo, tom_musgo))
        if r.random() < grupo:
            lado = r.choice((-1, 1))
            w2 = w * r.uniform(0.35, 0.55)
            pecas.extend(pedra(tela, cx + lado * (w * 0.5 + w2 * 0.2), y_base + 1, w2, w2 * 0.7, sorteio, musgo,
                              tom_musgo))
    return pintar(tela, pecas, estilo, profundidade)
