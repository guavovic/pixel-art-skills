"""`revisar`: cada regra com uma imagem pequena feita no teste, o caso bom e o caso com problema."""
from __future__ import annotations

import json
import random

import pytest
from PIL import Image

from pixel_atelier import Checagem, ampliar, carregar_estilo, compor, gerar, revisar
from pixel_atelier.__main__ import main
from pixel_atelier.imagem import escala_inteira, gravar_png
from pixel_atelier.revisao import CONTRASTE_FRENTE, DICA_CONTRASTE, _contraste, _medida

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

    parecidas = poucas.copy()  # a paleta do motor já não tem par quase igual; imagem de fora ainda pode ter
    parecidas.paste(cinza(22), (0, 0, 3, 8))
    c = regra(revisar(parecidas), "cores")
    assert c.estado == "ok" and "1 par quase igual (#141414~#161616)" in c.detalhe


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
    for alerta in (c, legivel):  # a ação certa no fim: mais contraste na frente, nunca escurecer o fundo
        assert alerta.detalhe.endswith(DICA_CONTRASTE) and "nunca escureça nem apague o fundo" in alerta.detalhe


def test_fundo_apagado_e_alerta_mesmo_com_contraste():
    """Regra da casa: destacar por contraste, não escurecendo o fundo até sumir."""
    fundo = faixas(48, 48, [8, 12, 16])
    frente = caixa(48, 48, cinza(240), (16, 12, 32, 40))
    revisao = revisar(compor([fundo, frente]), camadas=[fundo, frente])
    contraste = regra(revisao, "contraste")
    assert contraste.estado == "ok" and DICA_CONTRASTE not in contraste.detalhe  # dica só com alerta
    legivel = regra(revisao, "legibilidade")
    assert legivel.estado == "alerta" and "fundo apagado" in legivel.detalhe
    assert legivel.linha().endswith("clareie ou escureça a frente ou o contorno), nunca escureça nem apague o fundo")


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
    assert c.detalhe.endswith("aumente o contraste de valor do sprite (luz, sombra e contorno mais separados)")


def test_cena_sem_camadas_pula_o_que_precisa_delas():
    revisao = revisar(faixas(32, 32, [50, 150]))
    assert {c.regra for c in revisao.checagens if c.estado == "pulada"} == {
        "contraste", "legibilidade", "pillow shading", "serrilhado", "escala", "laço", "matiz da rampa",
        "contorno preto", "anti-alias", "linha 2:1"}  # escala: chapado demais


# --- laço ----------------------------------------------------------------------------------------

def morro(largura: int, altura: int, alturas: list[int]) -> Image.Image:
    """Camada com uma coluna cheia de baixo para cima em cada x, da altura pedida."""
    imagem = chapa(largura, altura)
    for x, h in enumerate(alturas):
        if h:
            imagem.paste(cinza(90), (x, altura - h, x + 1, altura))
    return imagem


def test_laco_bom_passa_e_quebrado_alerta():
    largura = 32
    bom = chapa(largura, 16)  # degradê que sobe e desce: a borda direita encosta na esquerda
    for x in range(largura):
        bom.paste(cinza(60 + 8 * abs(x - largura // 2)), (x, 0, x + 1, 16))
    ok = regra(revisar(bom, laco=True), "laço")
    assert ok.estado == "ok" and ok.detalhe.startswith("emenda x31|x0 dentro do normal")
    quebrado = chapa(largura, 16)  # degradê que só sobe: a emenda é um salto
    for x in range(largura):
        quebrado.paste(cinza(40 + 6 * x), (x, 0, x + 1, 16))
    alerta = regra(revisar(quebrado, laco=True), "laço")
    assert alerta.estado == "alerta" and "quebrada em composto" in alerta.detalhe and "(máx 3x a média)" in alerta.detalhe
    assert regra(revisar(quebrado), "laço").estado == "pulada"  # sem pedir, não confere


def test_laco_quebrado_numa_camada():
    largura, altura = 32, 16
    ceu = chapa(largura, altura, cinza(200))
    inteiro = morro(largura, altura, [1 + min(x, largura - x) // 2 for x in range(largura)])  # volta ao começo
    cortado = morro(largura, altura, [1 + x * 12 // largura for x in range(largura)])  # sobe e para na borda
    ok = regra(revisar(compor([ceu, inteiro]), camadas=[ceu, inteiro], laco=True), "laço")
    assert ok.estado == "ok" and "composto e 2 camadas" in ok.detalhe
    alerta = regra(revisar(compor([ceu, cortado]), camadas=[ceu, cortado], laco=True), "laço")
    assert alerta.estado == "alerta" and "quebrada em 02" in alerta.detalhe
    assert alerta.detalhe.endswith("desenhe a camada com laço")


def test_laco_pela_marca_que_o_gerar_grava(tmp_path):
    gerar({**PEQUENA, "ampliar": 2}, pasta=tmp_path / "com")
    for arquivo in ("vale.png", "vale-2x.png", "vale/01-ceu.png"):  # composto, ampliado e camada levam a marca
        ok = regra(revisar(tmp_path / "com" / arquivo), "laço")
        assert ok.estado == "ok" and ok.detalhe.endswith("laço pela marca do gerar"), arquivo
    assert regra(revisar(tmp_path / "com" / "vale.png", laco=False), "laço").detalhe == (
        "conferência do laço desligada no pedido")
    forcado = regra(revisar(tmp_path / "com" / "vale.png", laco=True), "laço")
    assert forcado.estado == "ok" and "marca" not in forcado.detalhe

    gerar({**PEQUENA, "laco": False}, pasta=tmp_path / "sem")
    sem = regra(revisar(tmp_path / "sem" / "vale.png"), "laço")
    assert sem.estado == "pulada" and sem.detalhe.startswith("a cena foi gerada sem laço")
    assert regra(revisar(tmp_path / "sem" / "vale.png", laco=True), "laço").estado in ("ok", "alerta")

    with Image.open(tmp_path / "com" / "vale.png") as aberta:
        aberta.copy().save(tmp_path / "salva-de-novo.png")  # outro programa salva sem o texto do PNG
    solta = regra(revisar(tmp_path / "salva-de-novo.png"), "laço")
    assert solta.estado == "pulada" and solta.detalhe.startswith("imagem sem a marca de laço")


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


# --- matiz da rampa ------------------------------------------------------------------------------

def listras(cores) -> Image.Image:
    """Uma faixa vertical de 4 pixels por cor, para a imagem usar a rampa inteira."""
    imagem = chapa(4 * len(cores), 8)
    for i, cor in enumerate(cores):
        imagem.paste(tuple(cor) + (255,), (4 * i, 0, 4 * i + 4, 8))
    return imagem


def test_rampa_com_e_sem_mudanca_de_matiz():
    snes = carregar_estilo("snes-diurno")
    ok = regra(revisar(listras(snes.rampas["folha"]), estilo=snes), "matiz da rampa")
    assert ok.estado == "ok" and "menor mudança 48° em folha (mín 3°)" in ok.detalhe

    plastico = carregar_estilo({"base": "snes-diurno", "nome": "plastico",
                                "rampas": {"folha": {"base": "#3c8c34", "passos": 5, "matiz": 0}}})
    c = regra(revisar(listras(plastico.rampas["folha"]), estilo=plastico), "matiz da rampa")
    assert c.estado == "alerta" and c.detalhe.startswith("folha #") and "muda 0°, em (0,0) (mín 3°)" in c.detalhe
    assert c.detalhe.endswith("puxe a sombra para o frio e a luz para o quente (guia cor)")

    noite = carregar_estilo("metroidvania-noturno")  # folha toda abaixo de 0,25: no escuro o matiz não conta
    assert regra(revisar(listras(noite.rampas["folha"]), estilo=noite), "matiz da rampa").estado == "pulada"
    assert regra(revisar(listras(snes.rampas["folha"])), "matiz da rampa").detalhe.startswith("sem estilo")


# --- contorno preto ------------------------------------------------------------------------------

def contornado(contorno) -> Image.Image:
    """Sprite 16x16: contorno de 1 pixel, miolo médio e um brilho no meio."""
    sprite = caixa(16, 16, contorno, (2, 2, 14, 14))
    sprite.paste(cinza(150), (3, 3, 13, 13))
    sprite.paste(cinza(220), (5, 5, 9, 9))
    return sprite


def test_contorno_preto_puro_e_contorno_da_rampa():
    c = regra(revisar(contornado((0, 0, 0, 255))), "contorno preto")
    assert c.estado == "alerta" and c.detalhe.startswith("1 de 1 contornos em preto puro (até #080808)")
    assert "o primeiro em sprite (" in c.detalhe and c.detalhe.endswith("(guia fundamentos)")
    assert regra(revisar(contornado((32, 24, 58, 255))), "contorno preto").detalhe.startswith("0 de 1")
    chapado = caixa(16, 16, (0, 0, 0, 255), (2, 2, 14, 14))  # silhueta toda preta: não é contorno
    assert regra(revisar(chapado), "contorno preto").detalhe == "nenhuma silhueta com contorno de uma cor só"


# --- anti-alias ----------------------------------------------------------------------------------

def test_anti_alias_em_volta_da_forma_e_borda_limpa():
    fundo = faixas(32, 32, [60])
    limpo = caixa(14, 14, cinza(240), (1, 1, 13, 13))
    c = regra(revisar(limpo, fundo=fundo), "anti-alias")
    assert c.estado == "ok" and c.heuristica

    borrado = caixa(14, 14, cinza(150), (0, 0, 14, 14))  # anel de meio-tom entre o branco e o fundo
    borrado.paste(cinza(240), (1, 1, 13, 13))
    c = regra(revisar(borrado, fundo=fundo), "anti-alias")
    assert c.estado == "alerta" and "sprite: meio-tom em 100%+ da borda nos 4 lados (máx 80%)" in c.detalhe
    assert c.detalhe.endswith("(guia fundamentos)")

    meio_alfa = caixa(16, 16, (240, 240, 240, 128), (1, 1, 15, 15))  # sprite sozinho: alfa parcial na borda
    meio_alfa.paste(cinza(240), (2, 2, 14, 14))
    assert regra(revisar(meio_alfa), "anti-alias").estado == "alerta"


# --- linha 2:1 -----------------------------------------------------------------------------------

def test_linha_isometrica_inteira_e_quebrada():
    c = regra(revisar(rampa([2] * 9)), "linha 2:1")
    assert c.estado == "ok" and c.detalhe == "1 linha 2:1, nenhuma quebrada"
    quebrada = revisar(rampa([2, 2, 2, 2, 1, 2, 2, 2, 2]))
    c = regra(quebrada, "linha 2:1")
    assert c.estado == "alerta" and c.detalhe.startswith("1 degrau fora do 2 em 1 linha 2:1, o primeiro de 1 em sprite")
    assert c.detalhe.endswith("o 2:1 é 2,2,2, nunca 2,1,2 (guia angulo)")
    assert regra(quebrada, "serrilhado").estado == "ok"  # o serrilhado genérico não pega o 2,1,2
    ondulado = regra(revisar(rampa([2, 2, 3, 2, 3, 2, 2, 2])), "linha 2:1")  # terreno: menos de 85% de 2
    assert ondulado.estado == "ok" and ondulado.detalhe.startswith("nenhuma linha 2:1")


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


def test_arte_chapada_nao_passa_por_ampliada():
    """Faixas de céu de altura par e um retângulo: tudo cai no passo 2 por acaso, mas é tamanho real."""
    chapada = chapa(64, 64, cinza(200))
    y = 0
    for i, altura in enumerate((4, 6, 8, 10, 6, 4)):
        chapada.paste(cinza(60 + 20 * i), (0, y, 64, y + altura))
        y += altura
    chapada.paste(cinza(30), (20, 30, 44, 64))
    assert escala_inteira(chapada) == 1
    assert revisar(chapada).escala == 1


def test_ampliada_pequena_pela_marca_ou_pelo_nome(tmp_path):
    sprite = ruido(10, 6, seed=4)  # menor que 16 pixels por lado: sem marca não dá para ter certeza
    grande = ampliar(sprite, 4)
    gravar_png(grande, tmp_path / "heroi.png", laco=False, escala=4)
    grande.save(tmp_path / "heroi-4x.png")
    for arquivo in ("heroi.png", "heroi-4x.png"):
        revisao = revisar(tmp_path / arquivo)
        assert revisao.escala == 4 and (revisao.largura, revisao.altura) == (10, 6), arquivo
    # marca que não bate com os blocos não vale: a imagem é revisada como veio
    gravar_png(sprite, tmp_path / "errada.png", laco=False, escala=3)
    assert revisar(tmp_path / "errada.png").escala == 1


def test_gerar_marca_a_escala_do_ampliado(tmp_path):
    receita = {"cena": "mini", "tamanho": [16, 12], "estilo": "snes-diurno", "ampliar": 3, "laco": False,
               "camadas": [{"forma": "ceu"}, {"forma": "rocha", "quantidade": 1, "tamanho": [0.6, 0.8]}]}
    gerar(receita, pasta=tmp_path)
    revisao = revisar(tmp_path / "mini-3x.png")
    assert revisao.escala == 3 and (revisao.largura, revisao.altura) == (16, 12)


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
    assert len(linhas) == 14 and all(linha.split()[0] in ("ok", "alerta", "pulada") for linha in linhas[1:])
    assert sum("[heurística]" in linha for linha in linhas) == 6
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
    assert main(["revisar", str(tmp_path / "vale.png"), "--laco"]) == 0
    assert "ok laço: emenda" in capsys.readouterr().out
    assert main(["revisar", str(tmp_path / "vale.png")]) == 0  # sem --laco, vale a marca do gerar
    assert "laço pela marca do gerar" in capsys.readouterr().out
    assert main(["revisar", str(tmp_path / "nada.png")]) == 2
    assert "revisão não feita" in capsys.readouterr().err


def test_medida_perto_do_limite_nao_arredonda_para_o_limite():
    assert _medida(0.0996, 0.10) == "0.0996"
    assert _medida(0.13, 0.10) == "0.13" and _medida(0.10, 0.10) == "0.10"
    assert _medida(0.2504, 0.25, ".0%") == "25.04%"
    alerta = _contraste([("fundo", [(0, 0, 0.3)]), ("frente", [(0, 0, CONTRASTE_FRENTE - 0.0004)])])
    assert alerta.estado == "alerta" and "fundo 0.0996 (mín 0.10)" in alerta.detalhe
