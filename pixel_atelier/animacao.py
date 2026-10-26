"""Cenário vivo: as camadas da receita andando num laço que fecha sem emenda.

Cada camada é desenhada uma vez e anda inteira, sem sortear de novo (o pontilhado anda junto e
não pisca). No laço de `quadros` quadros, a camada dá um número inteiro de voltas na largura,
então o quadro seguinte ao último é o primeiro:

- parallax: `voltas` da receita para a camada mais perto (profundidade 0), menos quanto mais
  funda (`round(voltas * (1 - profundidade))`); o céu, no fundo, fica parado;
- nuvem e névoa: 1 volta a mais, de vento;
- raios: pulsam (a intensidade cai e volta duas vezes no laço, em poucos degraus);
- camada sem laço não anda (a borda abriria um buraco).

O mundo anda para a esquerda, como a câmera indo para a direita. O quadro 0 é o composto parado.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageChops

from .formas import desenhar
from .imagem import MARCA_LACO, ampliar, compor
from .receita import Animacao, Receita, colunas_da_folha, parametros_da_forma

CORES_GIF = 256
COM_VENTO = ("nuvem", "nevoa")
PULSOS = 2  # vezes que os raios caem e voltam no laço
PULSO_FUNDO = 0.55  # intensidade mais fraca do pulso, em fração da intensidade da receita
PULSO_DEGRAUS = 3  # degraus entre o fundo e o topo (cada degrau é um desenho a mais)


@dataclass
class Movimento:
    """O que uma camada faz no laço: `voltas` na largura e se os raios pulsam."""

    voltas: int
    pulsa: bool = False

    def descrever(self) -> str:
        if self.pulsa and self.voltas:
            return f"pulsa e dá {self.voltas} volta{'s' if self.voltas > 1 else ''}"
        if self.pulsa:
            return "pulsa"
        if self.voltas:
            return f"{self.voltas} volta{'s' if self.voltas > 1 else ''}"
        return "parada"


def _parametro(forma: str, parametros: dict, nome: str):
    if nome in parametros:
        return parametros[nome]
    return parametros_da_forma(forma)[nome].default


def movimento(forma: str, parametros: dict, animacao: Animacao) -> Movimento:
    pulsa = forma == "raios"
    if not parametros["laco"]:
        return Movimento(0, pulsa)
    profundidade = min(1.0, max(0.0, _parametro(forma, parametros, "profundidade")))
    voltas = round(animacao.voltas * (1 - profundidade))
    if forma in COM_VENTO:
        voltas += 1
    return Movimento(voltas, pulsa)


def deslocamento_no_quadro(voltas: int, largura: int, quadro: int, quadros: int) -> int:
    """Quanto a camada andou no `quadro` (para a esquerda). No quadro `quadros` volta ao 0."""
    return -round(voltas * largura * (quadro % quadros) / quadros)


def fator_do_pulso(quadro: int, quadros: int) -> float:
    """Intensidade dos raios no quadro, em fração da da receita: 1 no quadro 0, cai até `PULSO_FUNDO` e volta."""
    onda = 0.5 + 0.5 * math.cos(2 * math.pi * PULSOS * quadro / quadros)
    degrau = round(onda * PULSO_DEGRAUS) / PULSO_DEGRAUS
    return PULSO_FUNDO + (1 - PULSO_FUNDO) * degrau


class Animador:
    """Monta os quadros a partir das camadas já desenhadas (a primeira desenhada de cada raio vem pronta)."""

    def __init__(self, receita: Receita, imagens: list[Image.Image]):
        if receita.animacao is None:
            raise ValueError("a receita não tem animacao")
        self.receita = receita
        self.animacao = receita.animacao
        self.imagens = imagens
        self.movimentos = [movimento(c.forma, c.parametros, self.animacao) for c in receita.camadas]
        self._pulsos: dict[tuple[int, float], Image.Image] = {}

    def _camada(self, indice: int, quadro: int) -> Image.Image:
        c = self.receita.camadas[indice]
        imagem = self.imagens[indice]
        if self.movimentos[indice].pulsa:
            fator = fator_do_pulso(quadro, self.animacao.quadros)
            if fator != 1:
                chave = (indice, fator)
                if chave not in self._pulsos:
                    parametros = {**c.parametros, "intensidade": _parametro(c.forma, c.parametros, "intensidade") * fator}
                    r = self.receita
                    self._pulsos[chave] = desenhar(c.forma, r.estilo, r.largura, r.altura, **parametros)
                imagem = self._pulsos[chave]
        dx = deslocamento_no_quadro(self.movimentos[indice].voltas, self.receita.largura, quadro, self.animacao.quadros)
        return ImageChops.offset(imagem, dx, 0) if dx else imagem

    def quadro(self, quadro: int) -> Image.Image:
        return compor(self._camada(i, quadro) for i in range(len(self.imagens)))

    def quadros(self) -> list[Image.Image]:
        return [self.quadro(q) for q in range(self.animacao.quadros)]


def folha(quadros: list[Image.Image], colunas: int) -> Image.Image:
    """Quadros lado a lado, `colunas` por linha, da esquerda para a direita e de cima para baixo."""
    largura, altura = quadros[0].size
    linhas = -(-len(quadros) // colunas)
    saida = Image.new("RGBA", (largura * colunas, altura * linhas), (0, 0, 0, 0))
    for i, q in enumerate(quadros):
        saida.paste(q, ((i % colunas) * largura, (i // colunas) * altura))
    return saida


def tempo(cena: str, animacao: Animacao, tamanho: tuple[int, int], laco: bool, arquivo_folha: str) -> dict:
    """O JSON de tempo que acompanha a folha: o que o jogo precisa para tocar os quadros."""
    colunas = colunas_da_folha(animacao.quadros, tamanho[0])
    return {
        "cena": cena,
        "folha": arquivo_folha,
        "quadros": animacao.quadros,
        "duracao": animacao.duracao,
        "quadro": list(tamanho),
        "colunas": colunas,
        "linhas": -(-animacao.quadros // colunas),
        "laco": laco,
    }


def gravar_gif(quadros: list[Image.Image], destino: Path, duracao: int, laco: bool, escala: int = 1) -> bool:
    """GIF com uma paleta só para todos os quadros, cor exata (sem pontilhar) e alfa 0 ou 255.

    O GIF guarda até 256 cores. Animação com mais (paleta grande, alta definição) sai com a paleta de
    cada quadro reduzida a 256, sem pontilhar, e a função devolve False: o GIF é só para ver, a folha
    PNG continua exata.
    """
    cores: set[tuple[int, int, int]] = set()
    transparente = False
    for q in quadros:
        for _, (r, g, b, a) in q.getcolors(q.width * q.height):
            if a == 0:
                transparente = True
            else:
                cores.add((r, g, b))
    lista = sorted(cores)
    if transparente:
        lista.insert(0, next(c for c in ((255, 0, v) for v in range(255, -1, -1)) if c not in cores))
    exato = len(lista) <= CORES_GIF
    if exato:
        paleta = Image.new("P", (1, 1))
        paleta.putpalette([canal for cor in lista + [lista[-1]] * (CORES_GIF - len(lista)) for canal in cor])
        indexados = [_indexar(q, paleta, transparente) for q in quadros]
        opcoes = {"transparency": 0, "disposal": 2} if transparente else {}
    else:
        indexados = [q.convert("RGB").quantize(CORES_GIF, dither=Image.Dither.NONE) for q in quadros]
        opcoes = {}
    convertidos = [ampliar(q, escala) for q in indexados]
    convertidos[0].save(destino, save_all=True, append_images=convertidos[1:], duration=duracao, loop=0,
                        optimize=False, comment=f"{MARCA_LACO}={'sim' if laco else 'nao'}", **opcoes)
    return exato


def _indexar(quadro: Image.Image, paleta: Image.Image, transparente: bool) -> Image.Image:
    saida = quadro.convert("RGB").quantize(palette=paleta, dither=Image.Dither.NONE)
    if transparente:
        saida.paste(0, mask=quadro.getchannel("A").point(lambda a: 255 if a == 0 else 0))
    return saida


def gravar_tempo(dados: dict, destino: Path) -> None:
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
