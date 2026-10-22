"""Ruído determinístico: periódico na horizontal (para o laço sem emenda) e hash por pixel."""
from __future__ import annotations

import math
import random
from typing import Callable


def ruido_periodico(seed: int, periodo: float, harmonicos: int = 6, queda: float = 0.5) -> Callable[[float], float]:
    """Função de x que devolve de -1 a 1 e se repete a cada `periodo`.

    Só usa harmônicas inteiras do período, então o valor em x = periodo é igual ao valor em x = 0.
    `queda` controla quanto as harmônicas altas pesam: maior deixa o contorno mais áspero.
    """
    gerador = random.Random(seed)
    partes = []
    for k in range(1, harmonicos + 1):
        partes.append((k, gerador.uniform(0, math.tau), 1.0 / (1.0 + (k - 1) * queda)))
    total = sum(p[2] for p in partes)
    vistos: dict[float, float] = {}  # as formas pedem o mesmo x linha após linha: guarda o já calculado

    def valor(x: float) -> float:
        v = vistos.get(x)
        if v is None:
            v = vistos[x] = sum(a * math.sin(math.tau * k * x / periodo + fase) for k, fase, a in partes) / total
        return v

    return valor


def hash01(x: int, y: int, seed: int = 0) -> float:
    """Número de 0 a 1 que depende só de (x, y, seed). Serve de ruído branco reproduzível."""
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def sortear(gerador: random.Random, valor: float | int | tuple | list) -> float:
    """Aceita um número fixo ou um intervalo `[mínimo, máximo]` e devolve um valor."""
    if isinstance(valor, (tuple, list)):
        if len(valor) != 2:
            raise ValueError(f"intervalo precisa de 2 valores: {valor!r}")
        return gerador.uniform(float(valor[0]), float(valor[1]))
    return float(valor)
