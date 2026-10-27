"""Pintura: transforma as máscaras de uma forma em pixels com volume, no jeito do estilo.

Por peça, do fundo para a frente:
- tom médio da rampa do papel, na profundidade da camada;
- `faixas`: faixa de sombra do lado oposto à luz e faixa clara do lado da luz;
- `pontilhado`: as mesmas faixas com uma segunda faixa em xadrez, a transição do Game Boy;
- `chapado`: só o tom médio, a silhueta do metroidvania;
- luz de contorno: 1 pixel claro na borda voltada para a luz, fora das partes finas;
- contorno: 1 pixel escuro em volta de tudo, quando o estilo pede; com selout, cada trecho do
  contorno sai no tom mais escuro da peça que ele cerca.

Com geração (`estilo.geracao`), `degraus` põe mais de um tom em cada faixa (o mais forte na borda)
e `textura` salpica manchas do tom vizinho dentro das peças, presas ao mundo (andam com o laço).

A luz e a sombra só aparecem do lado de cada uma, nunca em volta toda (isso seria pillow shading).
"""
from __future__ import annotations

from typing import Iterable, Sequence

from PIL import Image, ImageChops

from .cor import RGB, misturar, quantizar
from .estilo import Estilo
from .imagem import iguais, vizinho
from .pontilhado import xadrez
from .ruido import hash01
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

    margem = 2 * faixa * estilo.degraus + 3  # alcance das faixas e da abertura morfológica, com folga
    manchas, manchas_macias = None, None
    if estilo.textura:
        manchas = _manchas(tela, estilo.textura)
        manchas_macias = _manchas(tela, estilo.textura / 2)
    tons_do_selout: list[tuple[Image.Image, RGB, RGB]] = []
    for peca in pecas:
        caixa = _caixa(peca.mascara, margem, tela)
        if caixa is None:
            continue
        uniao = ImageChops.lighter(uniao, peca.mascara)
        m = peca.mascara.crop(caixa)  # as contas valem só perto da peça: bem mais rápido que a tela toda
        rampa = estilo.rampa(peca.papel, profundidade)
        i = _indice(estilo, rampa, peca.tom)
        imagem.paste(rampa[i] + (255,), caixa, mask=m)
        if estilo.selout:
            tons_do_selout.append((peca.mascara, rampa[0], rampa[i]))
        if peca.liso:
            continue
        if manchas is not None:
            da_peca = manchas_macias if peca.papel in PAPEIS_MACIOS else manchas
            escuras, claras = (ImageChops.multiply(m, mancha.crop(caixa)) for mancha in da_peca)
            imagem.paste(rampa[max(0, i - 1)] + (255,), caixa, mask=escuras)
            imagem.paste(rampa[min(len(rampa) - 1, i + 1)] + (255,), caixa, mask=claras)
        if estilo.sombreamento in ("faixas", "pontilhado"):
            escura, clara = rampa[max(0, i - 1)], rampa[min(len(rampa) - 1, i + 1)]
            banda_sombra = tela.faixa(m, sombra, faixa * estilo.degraus)
            banda_luz = tela.faixa(m, luz, faixa * estilo.degraus)
            if tabuleiro is not None:
                casas = tabuleiro.crop(caixa)
                sombra2 = ImageChops.multiply(ImageChops.subtract(tela.faixa(m, sombra, faixa * 2), banda_sombra), casas)
                luz2 = ImageChops.multiply(ImageChops.subtract(tela.faixa(m, luz, faixa * 2), banda_luz), casas)
                imagem.paste(escura + (255,), caixa, mask=sombra2)
                imagem.paste(clara + (255,), caixa, mask=luz2)
            imagem.paste(escura + (255,), caixa, mask=banda_sombra)
            imagem.paste(clara + (255,), caixa, mask=banda_luz)
            for degrau in range(2, estilo.degraus + 1):
                largura = faixa * (estilo.degraus - degrau + 1)
                clara = rampa[min(len(rampa) - 1, i + degrau)]
                imagem.paste(rampa[max(0, i - degrau)] + (255,), caixa, mask=tela.faixa(m, sombra, largura))
                imagem.paste(clara + (255,), caixa, mask=tela.faixa(m, luz, largura))
            topo = clara
        else:
            topo = rampa[i]
        if estilo.luz_contorno:
            borda = ImageChops.multiply(tela.faixa(m, luz, 1), tela.partes_grossas(m))
            cor_borda = estilo.cor(misturar(topo, cor_luz, estilo.forca_luz))
            imagem.paste(cor_borda + (255,), caixa, mask=borda)

    if estilo.contorno and uniao.getbbox() is not None:
        anel = ImageChops.subtract(tela.dilatar(uniao, cruz=True), uniao)
        imagem.paste(estilo.cor(estilo.contorno_cor, profundidade) + (255,), mask=anel)
        for mascara, escuro, medio in tons_do_selout:
            volta = tela.dilatar(mascara, cruz=True)
            imagem.paste(escuro + (255,), mask=ImageChops.multiply(anel, volta))
            imagem.paste(medio + (255,), mask=ImageChops.multiply(anel, tela.faixa(volta, luz, 1)))

    if estilo.sombreamento != "pontilhado":
        imagem = limpar_soltos(imagem, tela.laco)
    return quantizar(imagem, estilo.paleta)


PAPEIS_MACIOS = {"nuvem", "nevoa"}  # textura pela metade: mancha forte em nuvem vira camuflagem
_CAMPOS: dict[tuple, Image.Image] = {}


def _manchas(tela: Tela, textura: float) -> tuple[Image.Image, Image.Image]:
    """Máscaras das manchas escuras e claras da textura: a ponta alta do campo vira mancha escura e a
    baixa, clara. `textura` 1 cobre perto de um quarto da peça."""
    campo = _campo_da_textura(tela)
    corte = round(255 * 0.3 * textura)
    escuras = campo.point(lambda v: 255 if v > 255 - corte else 0)
    claras = campo.point(lambda v: 255 if v < corte else 0)
    return escuras, claras


def _campo_da_textura(tela: Tela) -> Image.Image:
    """Ruído de valor em duas escalas (casas de 4 e 2 pixels, que dividem a largura do laço), de 0 a
    255, preso ao mundo: anda com o deslocamento e dá a volta com o laço."""
    chave = (tela.largura, tela.altura, tela.laco, tela.deslocamento)
    if chave not in _CAMPOS:
        grossas, finas = (_ruido_em_casas(tela, casa) for casa in (4, 2))
        campo = Image.new("L", tela.tamanho)
        campo.putdata([round(255 * (0.65 * a + 0.35 * b)) for a, b in zip(grossas, finas)])
        _CAMPOS[chave] = campo
    return _CAMPOS[chave]


def _ruido_em_casas(tela: Tela, casa: int) -> list[float]:
    """Ruído de valor com um sorteio por canto de casa e mistura linear dentro dela, linha por linha."""
    colunas = max(1, tela.largura // casa)

    def coluna(c: int) -> int:
        if tela.laco:
            return c % colunas
        return c

    xs = []
    for x in range(tela.largura):
        mx = tela.no_mundo(x)
        xs.append((coluna(mx // casa), coluna(mx // casa + 1), (mx % casa) / casa))
    usadas = {c for c0, c1, _ in xs for c in (c0, c1)}
    valores: list[float] = []
    for y in range(tela.altura):
        cy, fy = divmod(y, casa)
        ty = fy / casa
        cima = {c: hash01(c, cy, casa) for c in usadas}
        baixo = {c: hash01(c, cy + 1, casa) for c in usadas}
        for c0, c1, tx in xs:
            a = cima[c0] + (cima[c1] - cima[c0]) * tx
            b = baixo[c0] + (baixo[c1] - baixo[c0]) * tx
            valores.append(a + (b - a) * ty)
    return valores


def _caixa(mascara: Image.Image, margem: int, tela: Tela) -> tuple[int, int, int, int] | None:
    """Recorte da tela onde a peça e as contas em volta dela cabem; None se a máscara está vazia.

    Na vertical o recorte para na borda da tela, que prende do mesmo jeito. Na horizontal, se a
    margem passa da borda, vale a largura toda: assim o laço dá a volta igual à tela inteira.
    """
    caixa = mascara.getbbox()
    if caixa is None:
        return None
    x0, y0, x1, y1 = caixa
    if x0 - margem < 0 or x1 + margem > tela.largura:
        x0, x1 = 0, tela.largura
    else:
        x0, x1 = x0 - margem, x1 + margem
    return (x0, max(0, y0 - margem), x1, min(tela.altura, y1 + margem))


def limpar_soltos(imagem: Image.Image, laco: bool = True) -> Image.Image:
    """Tira pixel solto: o que tem os 4 vizinhos de uma mesma cor diferente da dele vira essa cor.

    Vale para pixel opaco ilhado no vazio (some) e para furo de 1 pixel (fecha). Fora da imagem
    conta como o próprio pixel, salvo na horizontal com `laco`, que dá a volta.
    """
    direita, esquerda, baixo, cima = (vizinho(imagem, dx, dy, laco) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    solto = iguais(direita, esquerda)
    for outro in (baixo, cima):
        solto = ImageChops.multiply(solto, iguais(direita, outro))
    solto = ImageChops.subtract(solto, iguais(direita, imagem))  # vizinhos iguais entre si, mas não a ele
    alfa_vizinho = direita.getchannel("A")
    algum_cheio = ImageChops.lighter(alfa_vizinho, imagem.getchannel("A")).point(lambda v: 255 if v else 0)
    solto = ImageChops.multiply(solto, algum_cheio)  # vazio cercado de vazio fica como está
    vazio = Image.new(imagem.mode, imagem.size, (0, 0, 0, 0))
    nova = Image.composite(direita, vazio, alfa_vizinho.point(lambda v: 255 if v else 0))
    return Image.composite(nova, imagem, solto)


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
