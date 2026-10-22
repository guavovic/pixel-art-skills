"""Peças comuns às formas.

Toda forma tem a mesma assinatura, para uma receita poder chamar qualquer uma pelo nome:

    forma(estilo, largura, altura, *, seed=0, profundidade=0.0, laco=True, deslocamento=0, **parâmetros) -> Image RGBA

- `estilo`: nome de preset, dicionário ou `Estilo`;
- `largura`, `altura`: tamanho real em pixels da camada (com laço, largura múltipla de 8);
- `profundidade`: 0 é perto, 1 é o fundo; puxa as cores para a atmosfera;
- `deslocamento`: anda a camada inteira esse tanto de pixels para a direita, sem sortear de novo
  (com laço, o que sai de um lado entra do outro; múltiplo de 8 mantém o pontilhado igual);
- posições e tamanhos são frações da altura (ou da largura, quando dito), para a mesma receita
  servir em qualquer resolução;
- onde cabe um intervalo, vale um número fixo ou `[mínimo, máximo]`, sorteado pela seed.
"""
from __future__ import annotations

from typing import Any

from ..estilo import Estilo, carregar_estilo
from ..tela import Tela


def preparar(estilo: Any, largura: int, altura: int, laco: bool, deslocamento: int = 0) -> tuple[Estilo, Tela]:
    return carregar_estilo(estilo), Tela(largura, altura, laco, deslocamento)


def semente(seed: int, *partes: int) -> int:
    """Semente derivada, para cada parte da forma ter o próprio sorteio sem mexer nas outras."""
    valor = seed * 1000003
    for p in partes:
        valor = (valor ^ (p + 0x9E3779B9)) * 16777619 & 0xFFFFFFFF
    return valor
