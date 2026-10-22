"""Pixel Atelier: motor de pixel art que guarda técnica, não desenho.

Uso mínimo:

    from pixel_atelier import carregar_estilo, desenhar, compor, ampliar

    estilo = carregar_estilo("snes-diurno")
    cena = compor([
        desenhar("ceu", estilo, 320, 180, astro="sol"),
        desenhar("arvore", estilo, 320, 180, seed=2, profundidade=0.5),
        desenhar("terreno", estilo, 320, 180, seed=3),
    ])
    ampliar(cena, 3).save("cena.png")
"""
from .cor import cor_mais_proxima, cores_usadas, gerar_rampa, hex_para_rgb, misturar, quantizar, rgb_para_hex
from .estilo import PAPEIS, Estilo, carregar_estilo, listar_estilos, salvar_estilo
from .formas import FORMAS, arvore, ceu, cristal, desenhar, nevoa, nuvem, raios, rocha, terreno
from .imagem import ampliar, compor, ladrilhar
from .pintura import contorno, limpar_soltos, luz_de_contorno, pintar
from .pontilhado import degrade, limiar, mascara_pontilhada
from .ruido import hash01, ruido_periodico
from .tela import Peca, Tela

__version__ = "0.1.0"

__all__ = [
    "FORMAS", "PAPEIS", "Estilo", "Peca", "Tela",
    "ampliar", "arvore", "carregar_estilo", "ceu", "compor", "contorno", "cor_mais_proxima", "cores_usadas",
    "cristal", "degrade", "desenhar", "gerar_rampa", "hash01", "hex_para_rgb", "ladrilhar", "limiar",
    "limpar_soltos", "listar_estilos", "luz_de_contorno", "mascara_pontilhada", "misturar", "nevoa", "nuvem",
    "pintar", "quantizar", "raios", "rgb_para_hex", "rocha", "ruido_periodico", "salvar_estilo", "terreno",
]
