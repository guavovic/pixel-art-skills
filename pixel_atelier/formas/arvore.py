"""Árvores em fileira: pinheiro, copa redonda, árvore seca ou uma mistura."""
from __future__ import annotations

import math
import random
from typing import Any

from PIL import Image

from ..pintura import pintar
from ..ruido import sortear
from ..tela import Peca, Tela
from ._base import preparar, semente

TIPOS = ("pinheiro", "copa", "seca", "mista")
PROPORCAO = {"pinheiro": 0.42, "copa": 0.72, "seca": 0.55}


def _andar(y_baixo: float, alto: float, meia: int, topo: float, compasso: int) -> tuple[int, float]:
    """Pé e ponta do andar. O lado íngreme cai em degraus iguais (2,2,2 e não 2,2,3): a altura vira
    múltiplo da meia largura, e o pé desce até o compasso do primeiro andar para o degrau de um andar
    não cair no meio do degrau do andar de baixo."""
    y_baixo = round(y_baixo)
    alto = min(alto, y_baixo - topo)
    ingreme = alto >= 1.5 * meia
    if not ingreme:
        return y_baixo, y_baixo - alto
    degrau = round(alto / meia)
    y_baixo += (compasso - y_baixo) % degrau
    degrau = max(1, min(degrau, int((y_baixo - topo) / meia)))
    return y_baixo, y_baixo - degrau * meia


def _pinheiro(tela: Tela, x: float, base: float, h: float, w: float, r: random.Random) -> list[Peca]:
    pecas = []
    tronco = tela.nova_mascara()
    grossura = max(1.0, w * 0.07)
    tela.retangulo(tronco, x - grossura, base - h * 0.25, x + grossura, base)
    pecas.append(Peca(tronco, "tronco"))
    andares = max(3, min(8, int(h / 10)))
    altura_andar = h * 0.85 / andares
    compasso = round(base - h * 0.12)
    for i in range(andares):
        meia = max(1, round(w * 0.5 * (1.0 - 0.78 * i / andares) * r.uniform(0.9, 1.08)))
        ponta = round(x + r.uniform(-0.6, 0.6))
        y_baixo, y_topo = _andar(compasso - altura_andar * i, altura_andar * 1.9, meia, base - h, compasso)
        m = tela.nova_mascara()
        tela.poligono(m, [(ponta - meia, y_baixo), (ponta, y_topo), (ponta + meia, y_baixo), (x, y_baixo - 1)])
        pecas.append(Peca(m, "folha"))
    return pecas


def _copa(tela: Tela, x: float, base: float, h: float, w: float, r: random.Random) -> list[Peca]:
    tronco = tela.nova_mascara()
    g = max(1.5, w * 0.07)
    tela.poligono(tronco, [(x - g * 2.0, base), (x - g, base - h * 0.55), (x + g, base - h * 0.55), (x + g * 2.0, base)])
    for lado in (-1, 1):
        tela.linha(tronco, [(x, base - h * 0.45), (x + lado * w * 0.22, base - h * 0.62)], espessura=max(1, int(g)))
    pecas = [Peca(tronco, "tronco")]
    bolas = []
    for _ in range(r.randint(7, 11)):
        cx = x + r.uniform(-w * 0.34, w * 0.34)
        cy = base - h * r.uniform(0.55, 0.86)
        raio = w * r.uniform(0.17, 0.27)
        bolas.append((cy, cx, raio))
    bolas.append((base - h * 0.84, x, w * 0.24))  # garante o topo da copa
    for cy, cx, raio in sorted(bolas, reverse=True):  # de baixo para cima: o alto, iluminado, fica na frente
        m = tela.nova_mascara()
        tela.elipse(m, cx, cy, raio, raio * 0.86)
        pecas.append(Peca(m, "folha"))
    return pecas


def _galho(tela: Tela, m: Image.Image, x: float, y: float, angulo: float, comprimento: float,
           espessura: float, r: random.Random, nivel: int) -> None:
    x2 = x + math.cos(angulo) * comprimento
    y2 = y - math.sin(angulo) * comprimento
    tela.linha(m, [(x, y), (x2, y2)], espessura=max(1, int(espessura)))
    if nivel <= 0 or comprimento < 4:
        return
    for lado in (-1, 1):
        if r.random() < 0.85:
            _galho(tela, m, x2, y2, angulo + lado * r.uniform(0.35, 0.75), comprimento * r.uniform(0.6, 0.78),
                   espessura * 0.68, r, nivel - 1)


def _seca(tela: Tela, x: float, base: float, h: float, w: float, r: random.Random) -> list[Peca]:
    m = tela.nova_mascara()
    g = max(1.5, h * 0.045)
    tela.poligono(m, [(x - g * 1.7, base), (x - g * 0.6, base - h * 0.45), (x + g * 0.6, base - h * 0.45), (x + g * 1.7, base)])
    _galho(tela, m, x, base - h * 0.42, math.pi / 2 + r.uniform(-0.2, 0.2), h * 0.32, g * 1.2, r, 4)
    return [Peca(m, "tronco")]


def _macico(tela: Tela, y_base: float, altura: int, r: random.Random) -> list[Peca]:
    """Mata baixa no pé da fileira: moitas redondas lado a lado sobre uma faixa cheia até o pé."""
    chao = tela.nova_mascara()
    tela.retangulo(chao, -2, y_base, tela.largura + 2, altura)
    pecas = [Peca(chao, "folha", tom=-1)]
    x = r.uniform(0, 4)
    while x < tela.largura:
        raio = altura * r.uniform(0.025, 0.05)
        m = tela.nova_mascara()
        tela.elipse(m, x, y_base - raio * 0.2, raio * 1.3, raio)
        pecas.append(Peca(m, "folha", tom=-1))
        x += raio * r.uniform(1.4, 2.2)
    return pecas


DESENHOS = {"pinheiro": _pinheiro, "copa": _copa, "seca": _seca}


def arvore(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.0,
    laco: bool = True,
    deslocamento: int = 0,
    tipo: str = "pinheiro",
    base: float = 0.85,
    tamanho: float | list = (0.3, 0.5),
    espaco: float | list = (0.7, 1.3),
    inicio: float = 0.0,
    fim: float = 1.0,
    macico: bool = True,
) -> Image.Image:
    """Fileira de árvores apoiadas em `base` (fração da altura).

    - `tipo`: "pinheiro", "copa", "seca" ou "mista" (sorteia entre as três);
    - `tamanho`: altura de cada árvore, em fração da altura da camada;
    - `espaco`: distância entre árvores, em larguras de árvore (menos de 1 encosta uma na outra);
    - `inicio`, `fim`: trecho da largura onde nascem árvores (0 a 1), para um bosque só num canto;
    - `macico`: faixa de mata contínua no pé das árvores, para a fileira não flutuar.
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo de árvore deve ser um de {TIPOS}, veio {tipo!r}")
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    r = random.Random(semente(seed, 1))
    y_base = base * altura
    pecas: list[Peca] = []

    x = largura * inicio + r.uniform(0, largura * 0.05)
    while x < largura * fim:
        escolha = r.choices(("pinheiro", "copa", "seca"), weights=(5, 4, 1))[0] if tipo == "mista" else tipo
        h = sortear(r, tamanho) * altura
        w = h * PROPORCAO[escolha] * r.uniform(0.85, 1.15)
        pecas.extend(DESENHOS[escolha](tela, x, y_base, h, w, random.Random(r.randrange(1 << 30))))
        x += max(2.0, w * sortear(r, espaco))

    if macico:
        pecas.extend(_macico(tela, y_base, altura, random.Random(semente(seed, 2))))
    return pintar(tela, pecas, estilo, profundidade)
