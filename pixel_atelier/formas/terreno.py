"""Terreno: chão, morros e montanhas, com superfície de grama ou neve e solo que escurece para baixo."""
from __future__ import annotations

import random
from typing import Any

from PIL import Image, ImageChops

from ..pintura import pintar
from ..ruido import ruido_periodico
from ..tela import Peca
from ._base import preparar, semente

SUPERFICIES = ("nenhuma", "grama", "neve")


def terreno(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.0,
    laco: bool = True,
    deslocamento: int = 0,
    base: float = 0.85,
    amplitude: float = 0.04,
    aspereza: float = 0.3,
    harmonicos: int = 6,
    papel: str = "terra",
    superficie: str = "grama",
    pedrinhas: int = 12,
    escurecer: bool = True,
) -> Image.Image:
    """Perfil de terreno que vai da linha `base` até o pé da imagem.

    - `amplitude`: altura dos morros, em fração da altura (0.3 já é cordilheira);
    - `aspereza`: 0 deixa o perfil liso; 1 deixa recortado, com picos;
    - `papel`: rampa do corpo ("terra" para chão, "pedra" para montanha);
    - `superficie`: "grama", "neve" ou "nenhuma";
    - `pedrinhas`: quantas pedrinhas no solo;
    - `escurecer`: solo pontilhado para o tom de baixo conforme afunda.
    """
    if superficie not in SUPERFICIES:
        raise ValueError(f"superficie deve ser uma de {SUPERFICIES}, veio {superficie!r}")
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    r = random.Random(semente(seed, 8))
    liso = ruido_periodico(semente(seed, 9), largura, harmonicos)
    aspero = ruido_periodico(semente(seed, 10), largura, harmonicos * 3, queda=0.15)

    def topo(x: float) -> float:
        v = (liso(x) * 0.5 + 0.5) * (1 - aspereza) + (1 - abs(aspero(x))) * aspereza
        return base * altura - v * amplitude * altura

    perfil = [topo(x) for x in range(largura + 1)]
    corpo = tela.nova_mascara()
    # o contorno passa um pouco das duas bordas: as cópias do laço se sobrepõem em vez de só encostar
    contorno = [(x, topo(x)) for x in range(-4, largura + 5)]
    tela.poligono(corpo, [(-4, altura + 1)] + contorno + [(largura + 4, altura + 1)])
    pecas = [Peca(corpo, papel)]

    if escurecer:
        fundo = max(6.0, altura * 0.08)

        def densidade(x: int, y: int) -> float:
            return (y - perfil[min(max(x, 0), largura)] - fundo) / (fundo * 2)

        sombra = ImageChops.multiply(tela.pontilhar(densidade), corpo)
        pecas.append(Peca(sombra, papel, tom=-1, liso=True))

    for _ in range(pedrinhas):
        x = r.uniform(0, largura)
        y = perfil[int(x)] + r.uniform(4, max(5.0, altura * 0.12))
        m = tela.nova_mascara()
        w = r.uniform(1.5, 3.5)
        tela.elipse(m, x, y, w, w * 0.6)
        pecas.append(Peca(ImageChops.multiply(m, corpo), papel, tom=-1, liso=True))

    if superficie != "nenhuma":
        papel_topo = "grama" if superficie == "grama" else "neve"
        espessura = 2 if superficie == "grama" else max(2, int(amplitude * altura * 0.18))
        faixa = tela.faixa(corpo, (0, -1), espessura)
        pecas.append(Peca(faixa, papel_topo))
        if superficie == "grama":
            folhas = tela.nova_mascara()
            claras = tela.nova_mascara()
            for _ in range(largura // 2):
                x = r.uniform(0, largura)
                y = perfil[int(x)]
                h = r.randint(2, 5)
                alvo = claras if r.random() < 0.3 else folhas
                tela.linha(alvo, [(x, y + 1), (x + r.choice((-1, 0, 0, 1)), y - h)])
            pecas.append(Peca(folhas, "grama", liso=True))
            pecas.append(Peca(claras, "grama", tom=1, liso=True))
    return pintar(tela, pecas, estilo, profundidade)
