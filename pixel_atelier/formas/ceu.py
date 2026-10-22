"""Céu: degradê pontilhado entre as cores do estilo, estrelas e um astro (sol ou lua) com halo."""
from __future__ import annotations

import math
import random
from typing import Any

from PIL import Image, ImageChops

from ..cor import cor_mais_proxima, luminancia, misturar
from ..pontilhado import degrade
from ._base import preparar, semente

ASTROS = (None, "sol", "lua")


def ceu(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 1.0,
    laco: bool = True,
    deslocamento: int = 0,
    horizonte: float = 0.85,
    estrelas: int = 0,
    astro: str | None = None,
    posicao: list | tuple = (0.3, 0.25),
    raio: float = 0.07,
    halo: float = 0.35,
) -> Image.Image:
    """Fundo opaco que cobre a camada toda.

    - `horizonte`: onde o degradê chega na última cor do céu (fração da altura);
    - `estrelas`: quantas estrelas na metade de cima;
    - `astro`: None, "sol" ou "lua", com centro em `posicao` (frações de largura e altura);
    - `raio`: raio do astro em fração da altura;
    - `halo`: densidade do halo pontilhado em volta do astro (0 desliga).
    A profundidade não muda o céu: ele já é o fundo.
    """
    if astro not in ASTROS:
        raise ValueError(f"astro deve ser um de {ASTROS}, veio {astro!r}")
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    imagem = degrade(largura, altura, estilo.ceu, 0.0, horizonte)
    claras = sorted(estilo.paleta, key=luminancia)

    if estrelas:
        r = random.Random(semente(seed, 15))
        px = imagem.load()
        topo_ceu = estilo.ceu[0]
        for _ in range(estrelas):
            x, y = r.randrange(largura), r.randrange(max(1, int(altura * 0.55)))
            brilho = r.choice((0.35, 0.6, 1.0))
            c = cor_mais_proxima(misturar(topo_ceu, claras[-1], brilho), estilo.paleta)
            sx = tela.na_tela(x)
            if sx is not None:
                px[sx, y] = c + (255,)

    if astro:
        cx, cy, rr = posicao[0] * largura, posicao[1] * altura, max(2.0, raio * altura)
        cor_astro = claras[-1]
        if halo > 0:
            def densidade(x: int, y: int) -> float:
                dx = abs(x - cx)
                if laco:
                    dx = min(dx % largura, largura - dx % largura)
                d = math.hypot(dx, y - cy)
                return max(0.0, 1 - (d - rr) / (rr * 3.5)) ** 2 * halo

            meio = estilo.ceu[min(len(estilo.ceu) - 1, int(posicao[1] * len(estilo.ceu)))]
            cor_halo = cor_mais_proxima(misturar(meio, cor_astro, 0.45), estilo.paleta)
            mascara = tela.pontilhar(densidade)
            imagem.paste(cor_halo + (255,), mask=mascara)
        disco = tela.nova_mascara()
        tela.elipse(disco, cx, cy, rr, rr)
        imagem.paste(cor_astro + (255,), mask=disco)
        if astro == "lua":
            sombra = cor_mais_proxima(misturar(cor_astro, estilo.ceu[0], 0.3), estilo.paleta)
            crateras = tela.nova_mascara()
            for ox, oy, k in ((-0.35, -0.2, 0.25), (0.3, 0.2, 0.3), (-0.1, 0.45, 0.18)):
                tela.elipse(crateras, cx + ox * rr, cy + oy * rr, rr * k, rr * k)
            imagem.paste(sombra + (255,), mask=ImageChops.multiply(crateras, disco))
    return imagem
