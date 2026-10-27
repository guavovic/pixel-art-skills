"""Formas: cada uma desenha uma camada RGBA inteira, com a mesma assinatura (ver `_base`)."""
from __future__ import annotations

from typing import Any, Callable

from PIL import Image

from ..cor import limitar_cores
from ..estilo import carregar_estilo
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
    """Desenha a forma pelo nome. É a porta de entrada para receitas: `desenhar("arvore", "snes-diurno", 320, 180, seed=3)`.

    Com geração no estilo, a camada fica no limite de cores por camada da época (as menos usadas
    viram a mais parecida das que ficam).
    """
    if forma not in FORMAS:
        raise KeyError(f"forma {forma!r} não existe; as que existem: {', '.join(FORMAS)}")
    estilo = carregar_estilo(estilo)
    imagem = FORMAS[forma](estilo, largura, altura, **parametros)
    tem_limite_por_camada = estilo.geracao is not None and estilo.geracao.cores_camada is not None
    if tem_limite_por_camada:
        imagem = limitar_cores(imagem, estilo.geracao.cores_camada)
    return imagem


__all__ = ["FORMAS", "desenhar", "arvore", "ceu", "cristal", "nevoa", "nuvem", "raios", "rocha", "terreno"]
