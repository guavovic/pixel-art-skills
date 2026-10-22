"""Gera os GIFs do README em docs/, só com o próprio pacote (e Pillow).

    python scripts/gifs_readme.py

- parallax.gif: a cena de exemplos/montar_cena.py no estilo noturno, com a câmera indo e voltando e
  cada camada andando na sua velocidade (o laço deixa a camada dar a volta na borda).
- estilos.gif: a mesma receita nos três presets do pacote.
- revisar.gif: antes e depois do `revisar`, com o relatório em texto.
- referencia.gif: uma referência pintada aqui mesmo vira paleta e rampas pelo `ref`, e a receita
  de exemplo sai no estilo novo.

Tudo ampliado por vizinho mais próximo, em escala inteira. O texto usa uma fonte monoespaçada do
sistema sem suavização; sem ela, a fonte padrão do Pillow.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pixel_atelier import ampliar, carregar_estilo, compor, desenhar, extrair_estilo, gerar, revisar  # noqa: E402

PASTA = RAIZ / "docs"
ESCALA = 3
LARGURA, ALTURA = 320, 180
FUNDO = (18, 16, 28)
TEXTO = (214, 210, 224)
APAGADO = (128, 122, 146)
OK = (126, 200, 120)
ALERTA = (240, 150, 80)
FONTES = ("consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc", "LiberationMono-Regular.ttf")


def _carregar_montar_cena():
    spec = importlib.util.spec_from_file_location("montar_cena", RAIZ / "exemplos" / "montar_cena.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


MONTAR = _carregar_montar_cena()


def fonte(tamanho: int):
    for nome in FONTES:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(tamanho)


FONTE = fonte(18)
ALTURA_LINHA = 24
MARGEM = 18


def camadas_da_cena(estilo, ajustes: dict) -> list[Image.Image]:
    """As camadas da receita de montar_cena.py, do fundo para a frente."""
    camadas = []
    for forma, parametros, *nome in MONTAR.RECEITA:
        ajuste = ajustes.get(nome[0] if nome else forma, {})
        camadas.append(desenhar(forma, estilo, LARGURA, ALTURA, **{**parametros, **ajuste}))
    for forma, parametros in ajustes.get("extras", []):
        camadas.append(desenhar(forma, estilo, LARGURA, ALTURA, **parametros))
    return camadas


def rolar(imagem: Image.Image, dx: int) -> Image.Image:
    """Anda a camada dx pixels para a esquerda, dando a volta na borda (a camada tem laço)."""
    dx %= imagem.width
    if dx == 0:
        return imagem
    nova = Image.new(imagem.mode, imagem.size)
    nova.paste(imagem.crop((dx, 0, imagem.width, imagem.height)), (0, 0))
    nova.paste(imagem.crop((0, 0, dx, imagem.height)), (imagem.width - dx, 0))
    return nova


def gravar_gif(quadros: list[Image.Image], duracoes: list[int] | int, nome: str) -> Path:
    """Grava com uma paleta só, tirada das cores de todos os quadros (pixel art cabe em 256)."""
    cores: dict[tuple[int, int, int], None] = {}
    for q in quadros:
        for _, cor in q.convert("RGB").getcolors(maxcolors=1 << 16) or []:
            cores[cor] = None
    if len(cores) > 255:  # um índice fica livre para a transparência dos quadros de diferença
        raise ValueError(f"{nome}: {len(cores)} cores, o GIF guarda 255 e um transparente")
    paleta = Image.new("P", (1, 1))
    planas = [c for cor in cores for c in cor]
    paleta.putpalette(planas + planas[:3] * (256 - len(cores)))
    indexados = [q.convert("RGB").quantize(palette=paleta, dither=Image.Dither.NONE) for q in quadros]
    destino = PASTA / nome
    indexados[0].save(destino, save_all=True, append_images=indexados[1:], duration=duracoes, loop=0,
                      optimize=True, disposal=1)
    return destino


def painel(linhas: list[tuple[str, tuple[int, int, int]]], largura: int, altura: int) -> Image.Image:
    img = Image.new("RGB", (largura, altura), FUNDO)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"  # sem suavização: o texto fica com poucas cores e sem borrão
    y = MARGEM
    for texto, cor in linhas:
        d.text((MARGEM, y), texto, font=FONTE, fill=cor)
        y += ALTURA_LINHA
    return img


def quebrar(texto: str, largura: int) -> list[str]:
    """Quebra por palavra para caber em `largura` pixels."""
    linhas, atual = [], ""
    for palavra in texto.split(" "):
        tentativa = f"{atual} {palavra}" if atual else palavra
        if atual and FONTE.getlength(tentativa) > largura:
            linhas.append(atual)
            atual = "  " + palavra
        else:
            atual = tentativa
    linhas.append(atual)
    return linhas


def empilhar(cima: Image.Image, baixo: Image.Image) -> Image.Image:
    img = Image.new("RGB", (cima.width, cima.height + baixo.height))
    img.paste(cima.convert("RGB"), (0, 0))
    img.paste(baixo, (0, cima.height))
    return img


# ------------------------------------------------------------------ GIFs

def gif_parallax() -> Path:
    """A câmera vai e volta com aceleração suave; cada camada anda na proporção da sua distância.

    Ida e volta em vez de uma volta inteira da cena: com laço, cada camada só fecha o ciclo depois de
    andar a largura toda, e isso pede centenas de quadros (o GIF passaria de 5 MB).
    """
    nome = "metroidvania-noturno"
    camadas = camadas_da_cena(carregar_estilo(nome), MONTAR.AJUSTES[nome])
    # céu, nuvem, montanhas, pinheiros, névoa, mata, chão, cristal, rocha, copa; névoa baixa, raios
    fatores = [0, 0.1, 0.05, 0.35, 0.45, 0.65, 1, 1, 1, 1.3, 1, 0]
    assert len(fatores) == len(camadas)
    passos, percurso = 50, 96  # quadros da ida; pixels reais que a camada de fator 1 anda
    posicoes = [percurso * (1 - math.cos(math.pi * f / passos)) / 2 for f in range(passos + 1)]
    ida = [ampliar(compor(rolar(c, round(k * p)) for c, k in zip(camadas, fatores)), ESCALA) for p in posicoes]
    quadros = ida + ida[-2:0:-1]
    duracoes = [50] * len(quadros)
    duracoes[0] = duracoes[passos] = 900  # pausa nas pontas
    return gravar_gif(quadros, duracoes, "parallax.gif")


def gif_estilos() -> Path:
    quadros = []
    for nome, ajustes in MONTAR.AJUSTES.items():
        cena = ampliar(compor(camadas_da_cena(carregar_estilo(nome), ajustes)), ESCALA)
        quadros.append(empilhar(cena, painel([(f'"estilo": "{nome}"', TEXTO)], cena.width, 60)))
    return gravar_gif(quadros, 1800, "estilos.gif")


def receita_vale(mata: float, chao: float) -> dict:
    return {"cena": "vale", "estilo": "metroidvania-noturno", "seed": 7, "camadas": [
        {"forma": "ceu", "astro": "lua", "estrelas": 60, "posicao": [0.72, 0.22]},
        {"forma": "terreno", "nome": "montanhas", "profundidade": 0.85, "base": 0.62, "amplitude": 0.3,
         "papel": "pedra"},
        {"forma": "arvore", "nome": "mata", "profundidade": mata, "tipo": "pinheiro", "base": 0.85},
        {"forma": "terreno", "nome": "chao", "seed": 5, "profundidade": chao, "base": 0.9},
    ]}


def gif_revisar() -> Path:
    largura = LARGURA * ESCALA
    casos = [("antes", 0.85, 0.85), ("depois", 0.4, 0.0)]
    blocos = []
    for rotulo, mata, chao in casos:
        resultado = gerar(receita_vale(mata, chao))
        relatorio = revisar(resultado.composto, camadas=[c.imagem for c in resultado.camadas])
        linhas = [(f'# {rotulo}: "profundidade" {mata} na mata e {chao} no chão', APAGADO),
                  ("$ pixel-atelier revisar vale.png", TEXTO)]
        for linha in relatorio.resumo().splitlines()[:4]:
            cor = ALERTA if linha.startswith("alerta") else OK if linha.startswith("ok") else TEXTO
            linhas.extend((parte, cor) for parte in quebrar(linha.replace("imagem:", "vale.png:"), largura - 2 * MARGEM))
        blocos.append((ampliar(resultado.composto, ESCALA), linhas))
    altura = max(len(l) for _, l in blocos) * ALTURA_LINHA + 2 * MARGEM
    quadros = [empilhar(cena, painel(linhas, largura, altura)) for cena, linhas in blocos]
    return gravar_gif(quadros, [4000, 4000], "revisar.gif")


def pintar_referencia() -> Image.Image:
    """Um pôr do sol pintado aqui, pixel a pixel, para servir de referência (160x90)."""
    w, h = 160, 90
    img = Image.new("RGB", (w, h))
    px = img.load()
    faixas = [(0, (42, 27, 69)), (6, (69, 36, 90)), (11, (110, 47, 102)), (16, (163, 64, 106)),
              (21, (216, 96, 79)), (26, (240, 143, 76)), (31, (249, 196, 107))]
    for y in range(h):
        for x in range(w):
            cor = faixas[0][1]
            for i, (inicio, c) in enumerate(faixas):
                # degrau pontilhado de 2 linhas na troca de faixa
                if y >= inicio + (1 if i and (x + y) % 2 else 0):
                    cor = c
            px[x, y] = cor
    d = ImageDraw.Draw(img)
    d.ellipse((98, 36, 120, 58), fill=(255, 226, 160))
    for x0, y0, comprimento in [(14, 14, 26), (60, 22, 34), (126, 9, 22), (36, 31, 18)]:
        d.line((x0, y0, x0 + comprimento, y0), fill=(230, 220, 220))
        d.line((x0 + 4, y0 + 1, x0 + comprimento - 6, y0 + 1), fill=(200, 188, 196))

    def silhueta(base: float, amplitude: float, passo: float, fase: float) -> list[int]:
        return [round(base + amplitude * (math.sin(x * passo + fase) + 0.5 * math.sin(x * passo * 2.7 + fase)))
                for x in range(w)]

    camadas = [
        (silhueta(56, 5, 0.09, 1.0), [(108, 102, 114), (84, 78, 92), (66, 62, 74)]),
        (silhueta(66, 4, 0.07, 3.0), [(207, 129, 80), (168, 94, 58), (126, 68, 48), (90, 46, 42)]),
        (silhueta(77, 3, 0.11, 5.0), [(90, 138, 70), (51, 96, 58), (31, 61, 42), (18, 38, 30)]),
    ]
    for topo, rampa in camadas:
        for x in range(w):
            for y in range(topo[x], h):
                fundo = y - topo[x]
                px[x, y] = rampa[min(len(rampa) - 1, 0 if fundo == 0 else 1 + fundo // 6)]
    for x in range(6, w, 23):  # pinheiros escuros no morro da frente
        t = silhueta(77, 3, 0.11, 5.0)[x]
        for k in range(12):
            meia = k // 3
            d.line((x - meia, t - 12 + k, x + meia, t - 12 + k), fill=(18, 38, 30))
    return img


def desenhar_paleta(referencia, largura: int, altura: int) -> Image.Image:
    img = Image.new("RGB", (largura, altura), FUNDO)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    d.text((MARGEM, MARGEM), "$ pixel-atelier ref por-do-sol.png --nome por-do-sol", font=FONTE, fill=TEXTO)
    d.text((MARGEM, MARGEM + ALTURA_LINHA), f"paleta: {len(referencia.paleta)} cores, rampas do escuro ao claro",
           font=FONTE, fill=APAGADO)
    lado, y = 44, MARGEM + 3 * ALTURA_LINHA
    for rampa in referencia.rampas:
        d.text((MARGEM, y + 12), ", ".join(rampa.papeis), font=FONTE, fill=TEXTO)
        for i, cor in enumerate(rampa.cores):
            x = 300 + i * (lado + 6)
            d.rectangle((x, y, x + lado - 1, y + lado - 1), fill=cor)
        y += lado + 14
    return img


def gif_referencia() -> Path:
    largura, altura = LARGURA * ESCALA, ALTURA * ESCALA
    pintura = ampliar(pintar_referencia(), 6)
    referencia = extrair_estilo(pintura, "por-do-sol")
    ajustes = MONTAR.AJUSTES["snes-diurno"]
    cena = ampliar(compor(camadas_da_cena(carregar_estilo(referencia.estilo), ajustes)), ESCALA)
    rotulos = ["1. referência, vista uma vez", "2. paleta e rampas tiradas pelo ref",
               '3. a receita de exemplo com "estilo": "por-do-sol"']
    quadros = [empilhar(img, painel([(r, TEXTO)], largura, 60))
               for img, r in zip([pintura, desenhar_paleta(referencia, largura, altura), cena], rotulos)]
    return gravar_gif(quadros, [2600, 3200, 3200], "referencia.gif")


def main() -> None:
    PASTA.mkdir(exist_ok=True)
    for gerar_gif in (gif_parallax, gif_estilos, gif_revisar, gif_referencia):
        destino = gerar_gif()
        print(f"{destino.relative_to(RAIZ).as_posix()}: {destino.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
