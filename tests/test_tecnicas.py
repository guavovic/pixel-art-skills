"""Técnicas: cor, rampas, quantização, pontilhado, tela com laço, luz de contorno e ampliação."""
from __future__ import annotations

import colorsys
import json

import pytest
from PIL import Image

from pixel_atelier import (
    Estilo,
    Tela,
    ampliar,
    carregar_estilo,
    compor,
    contorno,
    cores_usadas,
    degrade,
    gerar_rampa,
    hex_para_rgb,
    ladrilhar,
    listar_estilos,
    luz_de_contorno,
    mascara_pontilhada,
    quantizar,
    rgb_para_hex,
    ruido_periodico,
    salvar_estilo,
)
from pixel_atelier.cor import luminancia


def test_hex_ida_e_volta():
    assert hex_para_rgb("#1d3d52") == (29, 61, 82)
    assert hex_para_rgb("abc") == (170, 187, 204)
    assert rgb_para_hex((29, 61, 82)) == "#1d3d52"
    with pytest.raises(ValueError):
        hex_para_rgb("#12345")


def test_rampa_clareia_e_muda_o_matiz():
    base = (60, 140, 52)
    rampa = gerar_rampa(base, passos=5, matiz=24)
    assert len(rampa) == 5
    lums = [luminancia(c) for c in rampa]
    assert lums == sorted(lums) and lums[0] < lums[-1]
    matizes = [colorsys.rgb_to_hsv(*(v / 255 for v in c))[0] * 360 for c in rampa]
    h_base = colorsys.rgb_to_hsv(*(v / 255 for v in base))[0] * 360
    assert matizes[-1] < h_base - 5, "a luz devia puxar o verde para o amarelo"
    assert matizes[0] > h_base + 5, "a sombra devia puxar o verde para o azul"


def test_quantizar_so_usa_a_paleta():
    paleta = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
    imagem = Image.new("RGBA", (16, 16))
    imagem.putdata([(x * 16, y * 16, (x + y) * 8, 255 if x != y else 40) for y in range(16) for x in range(16)])
    saida = quantizar(imagem, paleta)
    assert cores_usadas(saida) <= set(paleta)
    assert {a for _, a in saida.getchannel("A").getcolors()} <= {0, 255}


def test_ruido_periodico_fecha_o_periodo():
    f = ruido_periodico(5, 160)
    assert f(0) == pytest.approx(f(160), abs=1e-9)
    assert -1 <= min(f(x) for x in range(160)) and max(f(x) for x in range(160)) <= 1


def test_pontilhado_segue_a_densidade():
    vazia = mascara_pontilhada(32, 32, lambda x, y: 0.0)
    cheia = mascara_pontilhada(32, 32, lambda x, y: 1.0)
    meia = mascara_pontilhada(32, 32, lambda x, y: 0.5)
    assert vazia.getbbox() is None
    assert cheia.histogram()[255] == 32 * 32
    assert meia.histogram()[255] == 32 * 32 // 2


def test_degrade_vai_da_primeira_a_ultima_cor():
    cores = [(0, 0, 0), (128, 128, 128), (255, 255, 255)]
    imagem = degrade(16, 64, cores)
    assert imagem.getpixel((0, 0))[:3] == cores[0]
    assert imagem.getpixel((0, 63))[:3] == cores[-1]
    assert cores_usadas(imagem) <= set(cores)


def test_tela_com_laco_da_a_volta():
    tela = Tela(64, 32, laco=True)
    m = tela.nova_mascara()
    tela.elipse(m, 62, 16, 6, 6)  # passa da borda direita
    assert m.getpixel((1, 16)) == 255, "o pedaço que passou da borda tem que aparecer na esquerda"
    deslocada = tela.deslocar(m, 10, 0)
    assert deslocada.getpixel((10, 16)) == 255


def test_tela_sem_laco_prende_na_borda_de_baixo():
    tela = Tela(40, 20, laco=False)
    m = tela.nova_mascara()
    tela.retangulo(m, 0, 10, 39, 19)
    sombra = tela.faixa(m, (0, 1), 1)  # borda de baixo
    assert sombra.getbbox() is None, "o pé da imagem não é borda: não pode ganhar sombra"


def test_luz_de_contorno_so_do_lado_da_luz():
    imagem = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    imagem.paste((10, 10, 10, 255), (8, 8, 24, 24))
    saida = luz_de_contorno(imagem, (200, 220, 230), direcao=(-1, -1), laco=False)
    assert saida.getpixel((12, 8))[:3] == (200, 220, 230)  # topo
    assert saida.getpixel((8, 12))[:3] == (200, 220, 230)  # esquerda
    assert saida.getpixel((12, 23))[:3] == (10, 10, 10)  # embaixo continua escuro
    assert saida.getpixel((23, 12))[:3] == (10, 10, 10)  # direita continua escura


def test_contorno_fica_por_fora():
    imagem = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    imagem.paste((200, 0, 0, 255), (4, 4, 12, 12))
    saida = contorno(imagem, (0, 0, 0), laco=False)
    assert saida.getpixel((3, 6)) == (0, 0, 0, 255)
    assert saida.getpixel((4, 6)) == (200, 0, 0, 255)
    assert saida.getpixel((3, 3))[3] == 0, "quina em cruz: sem pixel na diagonal"


def test_ampliar_por_vizinho_mais_proximo():
    imagem = Image.new("RGBA", (2, 1))
    imagem.putdata([(255, 0, 0, 255), (0, 0, 255, 255)])
    grande = ampliar(imagem, 3)
    assert grande.size == (6, 3)
    assert {grande.getpixel((x, y)) for x in range(3) for y in range(3)} == {(255, 0, 0, 255)}
    assert {grande.getpixel((x, y)) for x in range(3, 6) for y in range(3)} == {(0, 0, 255, 255)}


def test_compor_e_ladrilhar():
    fundo = Image.new("RGBA", (8, 4), (0, 0, 255, 255))
    frente = Image.new("RGBA", (8, 4), (0, 0, 0, 0))
    frente.putpixel((1, 1), (255, 0, 0, 255))
    cena = compor([fundo, frente])
    assert cena.getpixel((1, 1)) == (255, 0, 0, 255) and cena.getpixel((0, 0)) == (0, 0, 255, 255)
    assert ladrilhar(cena, 3).size == (24, 4)


def test_vem_ao_menos_tres_estilos():
    assert {"game-boy", "metroidvania-noturno", "snes-diurno"} <= set(listar_estilos())


@pytest.mark.parametrize("nome", listar_estilos())
def test_estilo_ida_e_volta_pelo_json(nome, tmp_path):
    estilo = carregar_estilo(nome)
    caminho = salvar_estilo(estilo, tmp_path / f"{nome}.json")
    assert b"\r\n" not in caminho.read_bytes()
    de_volta = carregar_estilo(caminho)
    assert de_volta.paleta == estilo.paleta
    assert de_volta.rampas == estilo.rampas
    assert de_volta.ceu == estilo.ceu
    assert json.loads(caminho.read_text(encoding="utf-8"))["nome"] == nome


def test_estilo_com_rampa_gerada_e_papel_que_falta():
    estilo = Estilo.de_dicionario({
        "nome": "teste",
        "ceu": ["#000000", "#202040"],
        "atmosfera": "#406080",
        "luz": "#ffffff",
        "rampas": {"pedra": {"base": "#808090", "passos": 4}},
    })
    assert len(estilo.rampas["pedra"]) == 4
    assert estilo.rampa("folha") == estilo.rampa("pedra")  # sem folha, usa a reserva
    assert set(estilo.rampa("pedra", 0.8)) <= set(estilo.paleta)


def test_estilo_invalido():
    with pytest.raises(ValueError):
        Estilo.de_dicionario({"nome": "x", "ceu": ["#000"], "atmosfera": "#000", "luz": "#fff",
                              "rampas": {"pedra": ["#111"]}, "sombreamento": "aquarela"})
    with pytest.raises(KeyError):
        carregar_estilo("nao-existe")
