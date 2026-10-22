"""Névoa e raios de luz, os dois em pontilhado ordenado: textura de pixel art em vez de alfa liso."""
from __future__ import annotations

from typing import Any

from PIL import Image

from ..ruido import ruido_periodico
from ._base import preparar, semente


def nevoa(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.5,
    laco: bool = True,
    deslocamento: int = 0,
    centro: float = 0.75,
    espessura: float = 0.15,
    densidade: float = 0.5,
    escala: int = 1,
    ate_o_chao: bool = False,
    papel: str = "nevoa",
) -> Image.Image:
    """Faixa de névoa em volta de `centro` (fração da altura).

    - `espessura`: meia altura da faixa, em fração da altura;
    - `densidade`: 0 a 1; névoa leve fica entre 0.3 e 0.5;
    - `escala`: 1 é pontilhado fino, 2 é pesado;
    - `ate_o_chao`: a névoa não some embaixo do centro, cobre até o pé (névoa baixa).
    Não apaga o fundo: é sempre pontilhado, o que está atrás continua aparecendo.
    """
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    ruido_a = ruido_periodico(semente(seed, 11), largura, 5)
    ruido_b = ruido_periodico(semente(seed, 12), largura, 8, queda=0.3)
    y_centro, meia = centro * altura, max(1.0, espessura * altura)

    calculado: dict[tuple[int, int], float] = {}  # a névoa densa pede o mesmo campo da leve

    def campo(x: int, y: int) -> float:
        v = calculado.get((x, y))
        if v is None:
            v = calculado[(x, y)] = _campo(x, y)
        return v

    def _campo(x: int, y: int) -> float:
        distancia = (y - y_centro) / meia
        if ate_o_chao and distancia > 0:
            distancia = 0.0
        faixa = max(0.0, 1 - abs(distancia))
        v = (ruido_a(x) * 0.5 + 0.5) * 0.65 + (ruido_b(x * 2 + y * 2) * 0.5 + 0.5) * 0.35
        return faixa * max(0.0, v * (0.4 + densidade) - 0.25)

    leve = tela.pontilhar(campo, escala)
    densa = tela.pontilhar(lambda x, y: campo(x, y) - 0.35, escala)
    rampa = estilo.rampa(papel, profundidade)
    camada = Image.new("RGBA", tela.tamanho, (0, 0, 0, 0))
    camada.paste(rampa[max(0, len(rampa) - 2)] + (255,), mask=leve)
    camada.paste(rampa[-1] + (255,), mask=densa)
    return camada


def raios(
    estilo: Any,
    largura: int,
    altura: int,
    *,
    seed: int = 0,
    profundidade: float = 0.3,
    laco: bool = True,
    deslocamento: int = 0,
    quantidade: int = 4,
    inclinacao: float = 0.5,
    abertura: float = 0.35,
    intensidade: float = 0.35,
    alcance: float = 0.85,
) -> Image.Image:
    """Raios de luz diagonais caindo de cima, na cor da luz do estilo.

    - `quantidade`: raios na largura toda (o laço fecha porque o período divide a largura);
    - `inclinacao`: quanto o raio anda na horizontal a cada pixel que desce;
    - `abertura`: largura do raio em fração do espaço entre raios;
    - `intensidade`: densidade no topo (0 a 1); pouco já basta;
    - `alcance`: até onde o raio desce, em fração da altura.
    """
    estilo, tela = preparar(estilo, largura, altura, laco, deslocamento)
    periodo = largura / max(1, quantidade)
    meia = max(1.0, periodo * abertura / 2)
    variacao = ruido_periodico(semente(seed, 13), largura, 4)
    fase = (semente(seed, 14) % 1000) / 1000 * periodo

    def campo(x: int, y: int) -> float:
        u = (x - y * inclinacao + fase) % periodo
        faixa = max(0.0, 1 - abs(u - periodo / 2) / meia)
        queda = max(0.0, 1 - y / max(1.0, altura * alcance))
        return faixa * queda * intensidade * (0.7 + 0.3 * (variacao(x) * 0.5 + 0.5))

    mascara = tela.pontilhar(campo)
    camada = Image.new("RGBA", tela.tamanho, (0, 0, 0, 0))
    camada.paste(estilo.cor_da_luz(profundidade) + (255,), mask=mascara)
    return camada
