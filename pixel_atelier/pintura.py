"""Pintura: transforma as máscaras de uma forma em pixels com volume, no jeito do estilo.

Por peça, do fundo para a frente:
- tom médio da rampa do papel, na profundidade da camada;
- `faixas`: faixa de sombra do lado oposto à luz e faixa clara do lado da luz;
- `pontilhado`: as mesmas faixas com uma segunda faixa em xadrez, a transição do Game Boy;
- `chapado`: só o tom médio, a silhueta do metroidvania;
- luz de contorno: 1 pixel claro na borda voltada para a luz, fora das partes finas;
- contorno: 1 pixel escuro em volta de tudo, quando o estilo pede.

A luz e a sombra só aparecem do lado de cada uma, nunca em volta toda (isso seria pillow shading).
"""
from __future__ import annotations

from typing import Iterable, Sequence

from PIL import Image, ImageChops

from .cor import RGB, misturar, quantizar
from .estilo import Estilo
from .pontilhado import xadrez
from .tela import Peca, Tela


def _juntar(pecas: Sequence[Peca], tela: Tela) -> list[Peca]:
    """No chapado, peças do mesmo papel e tom viram uma silhueta só (as lisas ficam por cima)."""
    grupos: dict[tuple[str, int], Image.Image] = {}
    ordem: list[tuple[str, int]] = []
    lisas = []
    for p in pecas:
        if p.liso:
            lisas.append(p)
            continue
        chave = (p.papel, p.tom)
        if chave not in grupos:
            grupos[chave] = tela.nova_mascara()
            ordem.append(chave)
        grupos[chave] = ImageChops.lighter(grupos[chave], p.mascara)
    return [Peca(grupos[k], k[0], k[1]) for k in ordem] + lisas


def _indice(estilo: Estilo, rampa: Sequence[RGB], tom: int) -> int:
    base = round(estilo.tom_base * (len(rampa) - 1)) + tom
    return max(0, min(len(rampa) - 1, base))


def pintar(tela: Tela, pecas: Iterable[Peca], estilo: Estilo, profundidade: float = 0.0) -> Image.Image:
    """Pinta as peças em ordem e devolve a camada RGBA, só com cores da paleta do estilo."""
    pecas = list(pecas)
    if estilo.sombreamento == "chapado":
        pecas = _juntar(pecas, tela)
    imagem = Image.new("RGBA", tela.tamanho, (0, 0, 0, 0))
    luz = estilo.direcao_luz
    sombra = (-luz[0], -luz[1])
    faixa = estilo.largura_faixa
    tabuleiro = xadrez(*tela.tamanho) if estilo.sombreamento == "pontilhado" else None
    cor_luz = estilo.cor_da_luz(profundidade)
    uniao = tela.nova_mascara()

    for peca in pecas:
        m = peca.mascara
        if m.getbbox() is None:
            continue
        uniao = ImageChops.lighter(uniao, m)
        rampa = estilo.rampa(peca.papel, profundidade)
        i = _indice(estilo, rampa, peca.tom)
        imagem.paste(rampa[i] + (255,), mask=m)
        if peca.liso:
            continue
        if estilo.sombreamento in ("faixas", "pontilhado"):
            escura, clara = rampa[max(0, i - 1)], rampa[min(len(rampa) - 1, i + 1)]
            banda_sombra = tela.faixa(m, sombra, faixa)
            banda_luz = tela.faixa(m, luz, faixa)
            if tabuleiro is not None:
                sombra2 = ImageChops.multiply(ImageChops.subtract(tela.faixa(m, sombra, faixa * 2), banda_sombra), tabuleiro)
                luz2 = ImageChops.multiply(ImageChops.subtract(tela.faixa(m, luz, faixa * 2), banda_luz), tabuleiro)
                imagem.paste(escura + (255,), mask=sombra2)
                imagem.paste(clara + (255,), mask=luz2)
            imagem.paste(escura + (255,), mask=banda_sombra)
            imagem.paste(clara + (255,), mask=banda_luz)
            topo = clara
        else:
            topo = rampa[i]
        if estilo.luz_contorno:
            borda = ImageChops.multiply(tela.faixa(m, luz, 1), tela.partes_grossas(m))
            cor_borda = estilo.cor(misturar(topo, cor_luz, estilo.forca_luz))
            imagem.paste(cor_borda + (255,), mask=borda)

    if estilo.contorno and uniao.getbbox() is not None:
        anel = ImageChops.subtract(tela.dilatar(uniao, cruz=True), uniao)
        imagem.paste(estilo.cor(estilo.contorno_cor, profundidade) + (255,), mask=anel)

    if estilo.sombreamento != "pontilhado":
        imagem = limpar_soltos(imagem, tela.laco)
    return quantizar(imagem, estilo.paleta)


def limpar_soltos(imagem: Image.Image, laco: bool = True) -> Image.Image:
    """Tira pixel solto: o que tem os 4 vizinhos de uma mesma cor diferente da dele vira essa cor.

    Vale para pixel opaco ilhado no vazio (some) e para furo de 1 pixel (fecha).
    """
    largura, altura = imagem.size
    fonte = imagem.load()
    saida = imagem.copy()
    px = saida.load()
    for y in range(altura):
        for x in range(largura):
            atual = fonte[x, y]
            vizinhos = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if laco:
                    nx %= largura
                elif not 0 <= nx < largura:
                    nx = x
                if not 0 <= ny < altura:
                    ny = y
                vizinhos.append(fonte[nx, ny])
            primeiro = vizinhos[0]
            if primeiro != atual and all(v == primeiro for v in vizinhos[1:]):
                if primeiro[3] == 0 and atual[3] == 0:
                    continue
                px[x, y] = primeiro if primeiro[3] else (0, 0, 0, 0)
    return saida


def luz_de_contorno(
    imagem: Image.Image,
    cor: RGB,
    direcao: tuple[int, int] = (-1, -1),
    laco: bool = True,
    pular_finas: bool = True,
) -> Image.Image:
    """Pinta de `cor` a borda de 1 pixel voltada para a luz em qualquer camada RGBA.

    É o que separa uma silhueta escura da outra. Com `pular_finas`, ponta de galho fica escura.
    """
    tela = Tela(imagem.width, imagem.height, laco=laco and imagem.width % 8 == 0)
    mascara = imagem.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    borda = tela.faixa(mascara, direcao, 1)
    if pular_finas:
        borda = ImageChops.multiply(borda, tela.partes_grossas(mascara))
    saida = imagem.convert("RGBA").copy()
    saida.paste(tuple(cor[:3]) + (255,), mask=borda)
    return saida


def contorno(imagem: Image.Image, cor: RGB, laco: bool = True) -> Image.Image:
    """Contorno de 1 pixel por fora da silhueta (vizinhança em cruz, sem engrossar as quinas)."""
    tela = Tela(imagem.width, imagem.height, laco=laco and imagem.width % 8 == 0)
    mascara = imagem.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    anel = ImageChops.subtract(tela.dilatar(mascara, cruz=True), mascara)
    saida = imagem.convert("RGBA").copy()
    saida.paste(tuple(cor[:3]) + (255,), mask=anel)
    return saida
