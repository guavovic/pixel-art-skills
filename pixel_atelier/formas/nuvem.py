"""Nuvens: fofas (bolas com base reta, com volume) ou em fiapo (faixa pontilhada)."""
from __future__ import annotations

import random
from typing import Any

from PIL import Image, ImageChops

from ..pintura import pintar
from ..ruido import esticar, ruido_periodico, sortear
from ..tela import Peca, Tela
from ._base import preparar, semente

TIPOS = ("fofa", "fiapo")


def nuvem_fofa(tela: Tela, cx: float, base: float, w: float, r: random.Random) -> Peca:
    m = tela.nova_mascara()
    n = r.randint(4, 7)
    for i in range(n):
        t = (i + 0.5) / n * 2 - 1  # -1 a 1 ao longo da nuvem
        raio = w * 0.5 * (0.32 + 0.3 * (1 - abs(t))) * r.uniform(0.85, 1.15)
        x = cx + t * w * 0.38
        tela.elipse(m, x, base - raio * 0.55, raio, raio * 0.8)
    corte = tela.nova_mascara()
    tela.retangulo(corte, -2, base, tela.largura + 2, tela.altura)
    return Peca(ImageChops.subtract(m, corte), "nuvem")


def nuvem(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.9,
    laco: bool = True,
    deslocamento: int = 0,
    tipo: str = "fofa",
    quantidade: int = 5,
    faixa: list | tuple = (0.12, 0.38),
    tamanho: float | list = (0.25, 0.45),
    densidade: float = 0.4,
) -> Image.Image:
    """Nuvens entre as alturas `faixa` (frações da altura, de cima).

    - `tipo`: "fofa" (bolas com volume e base reta) ou "fiapo" (névoa alta pontilhada);
    - `tamanho`: largura da nuvem fofa, em fração da altura da camada;
    - `densidade`: só no fiapo, quanto a faixa enche (0 a 1).
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo de nuvem deve ser um de {TIPOS}, veio {tipo!r}")
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    r = random.Random(semente(seed, 5))
    topo, fundo = faixa[0] * altura, faixa[1] * altura

    if tipo == "fofa":
        pecas = []
        for i in range(quantidade):
            cx = (i + r.uniform(0.1, 0.9)) * largura / max(1, quantidade)
            w = sortear(r, tamanho) * altura
            base = r.uniform(topo + w * 0.3, max(topo + w * 0.3 + 1, fundo))
            pecas.append(nuvem_fofa(tela, cx, base, w, random.Random(r.randrange(1 << 30))))
        return pintar(tela, pecas, estilo, profundidade)

    ruido_a = ruido_periodico(semente(seed, 6), largura, 6)
    ruido_b = ruido_periodico(semente(seed, 7), largura, 8, queda=0.3)
    centro, meia = (topo + fundo) / 2, max(1.0, (fundo - topo) / 2)

    def bruto(x: int, y: int) -> float:
        return ruido_a(x) * 0.7 + ruido_b(x * 2 + y * 3) * 0.3

    linhas_do_miolo = range(int(centro - meia / 2), int(centro + meia / 2) + 1)
    esticado = esticar(bruto, largura, linhas_do_miolo)

    def campo(x: int, y: int) -> float:
        faixa_y = max(0.0, 1 - abs(y - centro) / meia)
        v = esticado(x, y)
        return max(0.0, v - (1 - densidade)) * 2.0 * faixa_y

    mascara = tela.pontilhar(campo, escala=2)
    miolo = tela.pontilhar(lambda x, y: campo(x, y) - 0.5, escala=2)
    rampa = estilo.rampa("nuvem", profundidade)
    camada = Image.new("RGBA", tela.tamanho, (0, 0, 0, 0))
    camada.paste(rampa[max(0, len(rampa) - 2)] + (255,), mask=mascara)
    camada.paste(rampa[-1] + (255,), mask=miolo)
    return camada
