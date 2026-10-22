"""`revisar`: cada regra com uma imagem pequena feita no teste, o caso bom e o caso com problema."""
from __future__ import annotations

import json
import random

import pytest
from PIL import Image

from pixel_atelier import Checagem, ampliar, carregar_estilo, compor, gerar, revisar
from pixel_atelier.__main__ import main

VAZIO = (0, 0, 0, 0)


def regra(revisao, nome: str) -> Checagem:
    return next(c for c in revisao.checagens if c.regra == nome)


def cinza(v: int) -> tuple[int, int, int, int]:
    return (v, v, v, 255)


def chapa(largura: int, altura: int, cor=VAZIO) -> Image.Image:
    return Image.new("RGBA", (largura, altura), cor)


def faixas(largura: int, altura: int, valores: list[int]) -> Image.Image:
    """Fundo opaco em faixas horizontais de cinza, uma por valor."""
    imagem = chapa(largura, altura)
    for i, v in enumerate(valores):
        imagem.paste(cinza(v), (0, i * altura // len(valores), largura, (i + 1) * altura // len(valores)))
    return imagem


def caixa(largura: int, altura: int, cor, area: tuple[int, int, int, int]) -> Image.Image:
    imagem = chapa(largura, altura)
    imagem.paste(cor, area)
    return imagem


def ruido(largura: int, altura: int, seed: int, cores: int = 6) -> Image.Image:
    """Detalhe sem nada repetido: cada pixel sorteado entre `cores` tons."""
    sorteio = random.Random(seed)
    imagem = chapa(largura, altura)
    imagem.putdata([cinza(40 + 30 * sorteio.randrange(cores)) for _ in range(largura * altura)])
    return imagem


# --- cores ---------------------------------------------------------------------------------------

def test_cores_dentro_do_limite_e_acima_dele():
    poucas = chapa(16, 16)
    for i in range(5):
        poucas.paste(cinza(40 * i + 20), (i * 3, 0, i * 3 + 3, 16))
    assert regra(revisar(poucas), "cores").estado == "ok"

    muitas = chapa(22, 6)  # borda transparente: é sprite
    for i in range(20):
        muitas.paste(cinza(10 * i + 10), (i + 1, 1, i + 2, 5))
    c = regra(revisar(muitas), "cores")
    assert c.estado == "alerta" and c.detalhe.startswith("20 (limite 16)")  # sprite: limite 16


def test_cor_fora_da_paleta_do_estilo():
    paleta = carregar_estilo("game-boy").paleta
    dentro = chapa(8, 8, paleta[0] + (255,))
    assert regra(revisar(dentro, estilo="game-boy"), "cores").estado == "ok"
    fora = dentro.copy()
    fora.paste((255, 0, 0, 255), (0, 0, 4, 8))
    c = regra(revisar(fora, estilo="game-boy"), "cores")
    assert c.estado == "alerta" and "1 fora da paleta de game-boy (#ff0000)" in c.detalhe


# --- contraste e legibilidade --------------------------------------------------------------------

def test_frente_que_contrasta_com_o_fundo():
    fundo = faixas(48, 48, [70, 110, 150])
    frente = caixa(48, 48, cinza(245), (16, 12, 32, 40))
    revisao = revisar(compor([fundo, frente]), camadas=[fundo, frente])
    assert regra(revisao, "contraste").estado == "ok"
    assert regra(revisao, "legibilidade").estado == "ok"


def test_frente_que_some_no_fundo():
    fundo = faixas(48, 48, [70, 110, 150])
    frente = caixa(48, 48, cinza(112), (16, 18, 32, 30))  # dentro da faixa de 110
    revisao = revisar(compor([fundo, frente]), camadas=[fundo, frente])
    c = regra(revisao, "contraste")
    assert c.estado == "alerta" and "frente (02) x fundo" in c.detalhe
    legivel = regra(revisao, "legibilidade")
    assert legivel.estado == "alerta" and "some no fundo" in legivel.detalhe and "x15-32" in legivel.detalhe


def test_fundo_apagado_e_alerta_mesmo_com_contraste():
    """Regra da casa: destacar por contraste, não escurecendo o fundo até sumir."""
    fundo = faixas(48, 48, [8, 12, 16])
    frente = caixa(48, 48, cinza(240), (16, 12, 32, 40))
    revisao = revisar(compor([fundo, frente]), camadas=[fundo, frente])
    assert regra(revisao, "contraste").estado == "ok"
    legivel = regra(revisao, "legibilidade")
    assert legivel.estado == "alerta" and "fundo apagado" in legivel.detalhe


def test_camadas_do_meio_sem_contraste_entre_si():
    fundo = faixas(48, 48, [100, 100, 100])
    meio = caixa(48, 48, cinza(102), (0, 24, 48, 48))
    frente = caixa(48, 48, cinza(250), (20, 4, 28, 20))
    c = regra(revisar(compor([fundo, meio, frente]), camadas=[fundo, meio, frente]), "contraste")
    assert c.estado == "alerta" and "baixo em 02" in c.detalhe


def test_sprite_sobre_fundo_na_posicao():
    fundo = faixas(64, 32, [60, 140])
    sprite = caixa(8, 8, cinza(250), (0, 0, 8, 8))
    revisao = revisar(sprite, fundo=fundo, posicao=(4, 4))
    assert revisao.tipo == "sprite sobre fundo"
    assert regra(revisao, "contraste").detalhe.startswith("sprite x fundo")
    escondido = revisar(caixa(8, 8, cinza(60), (0, 0, 8, 8)), fundo=fundo, posicao=(4, 4))
    assert regra(escondido, "legibilidade").estado == "alerta"


def test_sprite_sozinho_precisa_de_faixa_de_valor():
    largo = caixa(16, 16, cinza(30), (2, 2, 14, 14))
    largo.paste(cinza(220), (4, 4, 10, 10))
    assert regra(revisar(largo), "legibilidade").estado == "ok"
    chapado = caixa(16, 16, cinza(120), (2, 2, 14, 14))
    chapado.paste(cinza(130), (4, 4, 10, 10))
    c = regra(revisar(chapado), "legibilidade")
    assert c.estado == "alerta" and "faixa de valor do sprite 0.04" in c.detalhe


def test_cena_sem_camadas_pula_o_que_precisa_delas():
    revisao = revisar(faixas(32, 32, [50, 150]))
    assert {c.regra for c in revisao.checagens if c.estado == "pulada"} == {
        "contraste", "legibilidade", "pillow shading", "serrilhado", "escala"}  # escala: chapado demais


# --- pixel solto ---------------------------------------------------------------------------------

def test_pixel_solto_e_pontilhado():
    pontilhado = faixas(32, 32, [80])
    for y in range(8, 16):
        for x in range(32):
            if (x + y) % 2:
                pontilhado.putpixel((x, y), cinza(160))  # xadrez: não é pixel solto
    c = regra(revisar(pontilhado), "pixel solto")
    assert c.estado == "ok" and c.detalhe.startswith("0 ")

    sujo = faixas(32, 32, [80])
    for i in range(10):
        sujo.putpixel((3 + 3 * i, 3 + 3 * (i % 3) * 3), cinza(200))
    c = regra(revisar(sujo), "pixel solto")
    assert c.estado == "alerta" and c.detalhe.startswith("10 (") and "em (3,3)" in c.detalhe


# --- pillow shading ------------------------------------------------------------------------------

def test_pillow_shading_e_luz_de_um_lado():
    pillow = chapa(24, 24)
    for borda, v in enumerate((60, 110, 170, 220)):  # anéis do escuro na borda ao claro no meio
        pillow.paste(cinza(v), (2 + borda, 2 + borda, 22 - borda, 22 - borda))
    c = regra(revisar(pillow), "pillow shading")
    assert c.estado == "alerta" and c.heuristica and "sprite: borda" in c.detalhe

    luz = caixa(24, 24, cinza(140), (2, 2, 22, 22))
    luz.paste(cinza(220), (2, 2, 22, 4))   # topo
    luz.paste(cinza(220), (2, 2, 4, 22))   # esquerda
    luz.paste(cinza(70), (4, 20, 22, 22))  # base
    luz.paste(cinza(70), (20, 4, 22, 22))  # direita
    assert regra(revisar(luz), "pillow shading").estado == "ok"


# --- serrilhado ----------------------------------------------------------------------------------

def rampa(degraus: list[int]) -> Image.Image:
    """Morro cheio até o chão; o topo sobe 1 pixel a cada degrau, com o comprimento dado."""
    largura = sum(degraus) + 4
    imagem = chapa(largura, len(degraus) + 8)
    x = 2
    for i, comprimento in enumerate(degraus):
        imagem.paste(cinza(120), (x, len(degraus) + 2 - i, x + comprimento, imagem.height))
        x += comprimento
    return imagem


def test_serrilhado_degraus_regulares_e_fora_do_ritmo():
    c = regra(revisar(rampa([3] * 9)), "serrilhado")
    assert c.estado == "ok" and c.detalhe.startswith("0 degraus")
    c = regra(revisar(rampa([3, 1] * 5)), "serrilhado")
    assert c.estado == "alerta" and c.heuristica and "mais em sprite" in c.detalhe


# --- escala --------------------------------------------------------------------------------------

def test_escala_mista_e_imagem_ampliada():
    cena = ruido(64, 64, seed=1)
    assert regra(revisar(cena), "escala").estado == "ok"

    misturada = cena.copy()
    misturada.paste(ampliar(ruido(16, 16, seed=2), 2), (16, 16))  # um pedaço desenhado em 2x
    c = regra(revisar(misturada), "escala")
    assert c.estado == "alerta" and "4 com bloco 2x em x16-32 y16-32" in c.detalhe

    revisao = revisar(ampliar(cena, 3))
    assert revisao.escala == 3 and (revisao.largura, revisao.altura) == (64, 64)
    assert "ampliada 3x" in revisao.resumo().splitlines()[0]


# --- composição repetida -------------------------------------------------------------------------

def test_composicao_repetida_e_textura_periodica():
    objeto = ruido(14, 14, seed=7)
    copiada = ruido(96, 40, seed=3)
    for x, y in ((2, 2), (40, 20), (78, 6)):
        copiada.paste(objeto, (x, y))
    c = regra(revisar(copiada), "composição repetida")
    assert c.estado == "alerta" and c.heuristica and "3 cópias em (2,2) (78,6) (40,20)" in c.detalhe

    variada = ruido(96, 40, seed=3)
    for i, (x, y) in enumerate(((2, 2), (40, 20), (78, 6))):
        variada.paste(ruido(14, 14, seed=10 + i), (x, y))
    assert regra(revisar(variada), "composição repetida").estado == "ok"

    listras = chapa(96, 24)
    for x in range(96):
        listras.paste(cinza(40 + 40 * (x % 5)), (x, 0, x + 1, 24))  # textura: repete sozinha
    assert regra(revisar(listras), "composição repetida").estado == "ok"


# --- integração ----------------------------------------------------------------------------------

PEQUENA = {"cena": "vale", "tamanho": [96, 64], "ampliar": 2, "camadas": [
    {"forma": "ceu", "astro": "sol"},
    {"forma": "arvore", "profundidade": 0.5, "tipo": "mista"},
    {"forma": "terreno", "nome": "chao", "base": 0.85},
]}


def test_cena_do_gerar_acha_as_camadas_e_responde_curto(tmp_path):
    gerar(PEQUENA, pasta=tmp_path)
    revisao = revisar(tmp_path / "vale.png")
    assert revisao.camadas == ["01-ceu", "02-arvore", "03-chao"]
    linhas = revisao.resumo().splitlines()
    assert linhas[0].startswith("vale.png: 96x64, cena com 3 camadas, ")
    assert len(linhas) == 9 and all(linha.split()[0] in ("ok", "alerta", "pulada") for linha in linhas[1:])
    assert sum("[heurística]" in linha for linha in linhas) == 4
    assert len(revisao.resumo()) < 1200  # é o que o agente lê no lugar da imagem
    ampliada = revisar(tmp_path / "vale-2x.png")
    assert ampliada.escala == 2 and ampliada.camadas == revisao.camadas
    assert ampliada.resumo().splitlines()[1:] == linhas[1:]
    assert json.dumps(revisao.para_dicionario())


def test_camada_de_outro_tamanho_e_recusada(tmp_path):
    with pytest.raises(ValueError, match="camada 01"):
        revisar(chapa(16, 16, cinza(10)), camadas=[chapa(5, 5, cinza(10))])


def test_linha_de_comando_revisa_e_responde_em_texto(tmp_path, capsys):
    gerar(PEQUENA, pasta=tmp_path)
    assert main(["revisar", str(tmp_path / "vale.png"), "--estilo", "snes-diurno"]) == 0
    saida = capsys.readouterr().out
    assert saida.startswith("vale.png: 96x64") and "pixel solto:" in saida
    assert main(["revisar", str(tmp_path / "nada.png")]) == 2
    assert "revisão não feita" in capsys.readouterr().err
