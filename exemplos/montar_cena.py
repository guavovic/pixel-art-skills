"""Monta a mesma cena em vários estilos e grava os PNGs nesta pasta (tamanho real e ampliado 3x).

A receita é uma só: as camadas, as seeds e os parâmetros não mudam de um estilo para outro.
Só o céu troca de astro (lua à noite, sol de dia), o brilho do cristal some de dia, as montanhas
da noite ficam mais longe (para separar dos pinheiros) e a noite ganha duas camadas a mais na
frente: névoa baixa e raios de luz. Ajuste vale para a forma ou, quando a camada tem nome (terceiro
item), só para ela.

Uso: python exemplos/montar_cena.py [estilo ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pixel_atelier import ampliar, carregar_estilo, compor, desenhar  # noqa: E402

LARGURA, ALTURA = 320, 180
PASTA = Path(__file__).resolve().parent

RECEITA = [
    ("ceu", dict(seed=1, horizonte=0.8)),
    ("nuvem", dict(seed=2, profundidade=0.95, quantidade=4, faixa=(0.12, 0.34), tamanho=(0.3, 0.5))),
    ("terreno", dict(seed=3, profundidade=0.85, base=0.62, amplitude=0.3, aspereza=0.45, papel="pedra",
                     superficie="neve", pedrinhas=0, escurecer=False), "montanhas"),
    ("arvore", dict(seed=4, profundidade=0.65, tipo="pinheiro", base=0.7, tamanho=(0.14, 0.24), espaco=(0.5, 0.9))),
    ("nevoa", dict(seed=5, profundidade=0.55, centro=0.66, espessura=0.1, densidade=0.4)),
    ("arvore", dict(seed=6, profundidade=0.35, tipo="mista", base=0.8, tamanho=(0.3, 0.48), espaco=(0.8, 1.6))),
    ("terreno", dict(seed=9, profundidade=0.0, base=0.88, amplitude=0.03, superficie="grama")),
    ("cristal", dict(seed=7, profundidade=0.0, quantidade=2, base=0.87, tamanho=(0.12, 0.18))),
    ("rocha", dict(seed=8, profundidade=0.0, quantidade=3, base=0.875, tamanho=(0.08, 0.14), musgo=0.6)),
    ("arvore", dict(seed=10, profundidade=0.0, tipo="copa", base=1.02, tamanho=(0.75, 0.85), espaco=(5.0, 6.0),
                    inicio=0.0, fim=0.1, macico=False)),
]

AJUSTES = {
    "metroidvania-noturno": {
        "ceu": dict(estrelas=70, astro="lua", posicao=(0.7, 0.22)),
        "nuvem": dict(tipo="fiapo", densidade=0.3),
        "montanhas": dict(profundidade=0.95),
        "extras": [
            ("nevoa", dict(seed=11, profundidade=0.6, centro=0.97, espessura=0.06, densidade=0.3, ate_o_chao=True)),
            ("raios", dict(seed=12, profundidade=0.9, quantidade=3, intensidade=0.3, abertura=0.25)),
        ],
    },
    "snes-diurno": {
        "ceu": dict(astro="sol", posicao=(0.78, 0.18), halo=0.35),
        "cristal": dict(brilho=0.0),
    },
    "game-boy": {
        "ceu": dict(astro="sol", posicao=(0.78, 0.2), halo=0.0),
    },
}


def montar(nome_estilo: str):
    estilo = carregar_estilo(nome_estilo)
    ajustes = AJUSTES.get(nome_estilo, {})
    camadas = []
    for forma, parametros, *nome in RECEITA:
        ajuste = ajustes.get(nome[0] if nome else forma, {})
        camadas.append(desenhar(forma, estilo, LARGURA, ALTURA, **{**parametros, **ajuste}))
    for forma, parametros in ajustes.get("extras", []):
        camadas.append(desenhar(forma, estilo, LARGURA, ALTURA, **parametros))
    return compor(camadas)


def main(estilos: list[str]) -> None:
    for nome in estilos:
        inicio = time.perf_counter()
        cena = montar(nome)
        cena.save(PASTA / f"{nome}.png")
        ampliar(cena, 3).save(PASTA / f"{nome}-3x.png")
        print(f"{nome}: {time.perf_counter() - inicio:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1:] or list(AJUSTES))
