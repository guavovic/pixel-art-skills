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

Ou a cena inteira numa receita JSON (ver `receita`):

    from pixel_atelier import gerar
    print(gerar("exemplos/snes-diurno.json", pasta="saida").resumo())

E a conferência pelas regras de pixel art, também em texto (ver `revisao`):

    from pixel_atelier import revisar
    print(revisar("saida/snes-diurno.png").resumo())

E um estilo novo tirado de uma imagem de referência, gravado como preset (ver `referencia`):

    from pixel_atelier import ref
    print(ref("referencias/floresta.png", "floresta").resumo())
"""
from .cor import cor_mais_proxima, cores_usadas, gerar_rampa, hex_para_rgb, misturar, quantizar, rgb_para_hex
from .estilo import (PAPEIS, Estilo, carregar_estilo, dados_do_estilo, descrever_estilos, listar_estilos,
                     pasta_de_presets, registrar_estilo, salvar_estilo)
from .formas import FORMAS, arvore, ceu, cristal, desenhar, nevoa, nuvem, raios, rocha, terreno
from .gerador import CamadaGerada, Resultado, gerar
from .imagem import ampliar, compor, ladrilhar
from .pintura import contorno, limpar_soltos, luz_de_contorno, pintar
from .receita import Camada, ErroDeReceita, Receita, descrever_formas, ler_receita, validar_receita
from .referencia import Referencia, extrair_estilo, ref
from .revisao import Checagem, Revisao, revisar
from .pontilhado import degrade, limiar, mascara_pontilhada
from .ruido import hash01, ruido_periodico
from .tela import Peca, Tela

__version__ = "0.1.0"

__all__ = [
    "FORMAS", "PAPEIS", "Camada", "CamadaGerada", "Checagem", "ErroDeReceita", "Estilo", "Peca", "Receita",
    "Referencia", "Resultado", "Revisao", "Tela",
    "ampliar", "arvore", "carregar_estilo", "ceu", "compor", "contorno", "cor_mais_proxima", "cores_usadas",
    "cristal", "dados_do_estilo", "degrade", "descrever_estilos", "descrever_formas", "desenhar", "extrair_estilo", "gerar",
    "gerar_rampa", "hash01", "hex_para_rgb", "ladrilhar", "ler_receita", "limiar", "limpar_soltos", "listar_estilos",
    "luz_de_contorno", "mascara_pontilhada", "misturar", "nevoa", "nuvem", "pasta_de_presets", "pintar", "quantizar",
    "raios", "ref", "registrar_estilo", "revisar", "rgb_para_hex", "rocha", "ruido_periodico", "salvar_estilo", "terreno",
    "validar_receita",
]
