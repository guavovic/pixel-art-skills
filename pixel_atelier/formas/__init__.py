"""Formas: cada uma desenha uma camada RGBA inteira, com a mesma assinatura (ver `_base`)."""
from __future__ import annotations

from typing import Any, Callable

from PIL import Image

from .arvore import arvore
from .ceu import ceu
from .cristal import cristal
from .nevoa import nevoa, raios
from .nuvem import nuvem
from .rocha import rocha
from .terreno import terreno

FORMAS: dict[str, Callable[..., Image.Image]] = {
    "ceu": ceu,
    "nuvem": nuvem,
    "terreno": terreno,
    "arvore": arvore,
    "rocha": rocha,
    "cristal": cristal,
    "nevoa": nevoa,
    "raios": raios,
}


def desenhar(forma: str, estilo: Any, largura: int, altura: int, **parametros: Any) -> Image.Image:
    """Desenha a forma pelo nome. É a porta de entrada para receitas: `desenhar("arvore", "snes-diurno", 320, 180, seed=3)`."""
    if forma not in FORMAS:
        raise KeyError(f"forma {forma!r} não existe; as que existem: {', '.join(FORMAS)}")
    return FORMAS[forma](estilo, largura, altura, **parametros)


__all__ = ["FORMAS", "desenhar", "arvore", "ceu", "cristal", "nevoa", "nuvem", "raios", "rocha", "terreno"]
