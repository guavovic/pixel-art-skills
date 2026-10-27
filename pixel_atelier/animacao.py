"""Cenário vivo: as camadas da receita andando num laço que fecha sem emenda.

Cada camada é desenhada uma vez e anda inteira, sem sortear de novo (o pontilhado anda junto e
não pisca). No laço de `quadros` quadros, a camada dá um número inteiro de voltas na largura,
então o quadro seguinte ao último é o primeiro:

- parallax: `voltas` da receita para a camada mais perto (profundidade 0), menos quanto mais
  funda (perto de `voltas * (1 - profundidade)`); o céu, no fundo (profundidade 1), fica parado.
  Toda camada mais perto que o céu dá pelo menos 1 volta, e profundidades diferentes dão voltas
  diferentes enquanto couberem em `voltas` (com 4 voltas, 4 profundidades andam cada uma na sua);
- `voltas` na camada fixa as voltas dela, sem olhar a profundidade;
- nuvem, névoa e raios (atmosfera) seguem só a conta acima, sem disputar voltas com as outras;
  nuvem e névoa dão 1 volta a mais, de vento;
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
from .receita import Animacao, Camada, Receita, colunas_da_folha, parametros_da_forma, quadros_por_folha

CORES_GIF = 256
COM_VENTO = ("nuvem", "nevoa")
ATMOSFERA = ("nuvem", "nevoa", "raios")
PULSOS = 2  # vezes que os raios caem e voltam no laço
PULSO_FUNDO = 0.55  # intensidade mais fraca do pulso, em fração da intensidade da receita
PULSO_DEGRAUS = 3  # degraus entre o fundo e o topo (cada degrau é um desenho a mais)


@dataclass
class Movimento:
    """O que uma camada faz no laço: `voltas` na largura, se os raios pulsam e quantos pixels anda por quadro."""

    voltas: int
    pulsa: bool = False
    passo: float = 0.0

    def descrever(self) -> str:
        voltas = f"{self.voltas} volta{'s' if self.voltas > 1 else ''} ({self.passo:.1f} px/quadro)".replace(".", ",")
        if self.pulsa and self.voltas:
            return f"pulsa e dá {voltas}"
        if self.pulsa:
            return "pulsa"
        if self.voltas:
            return voltas
        return "parada"


def _parametro(forma: str, parametros: dict, nome: str):
    if nome in parametros:
        return parametros[nome]
    return parametros_da_forma(forma)[nome].default


def _profundidade(c: Camada) -> float:
    return min(1.0, max(0.0, _parametro(c.forma, c.parametros, "profundidade")))


def voltas_por_profundidade(profundidades: list[float], voltas: int) -> dict[float, int]:
    """Voltas de cada profundidade: perto de `voltas * (1 - p)`, pelo menos 1 abaixo de 1 e uma
    para cada profundidade enquanto couberem em `voltas` (senão, arredondado)."""
    andam = sorted({p for p in profundidades if p < 1}, reverse=True)
    saida = {p: 0 for p in profundidades}
    cabem = len(andam) <= voltas
    anterior = 0
    for i, p in enumerate(andam):
        if not voltas:
            break
        menor = anterior + 1 if cabem else max(1, anterior)
        maior = voltas - (len(andam) - 1 - i) if cabem else voltas
        anterior = min(maior, max(menor, round(voltas * (1 - p))))
        saida[p] = anterior
    return saida


def movimentos(camadas: list[Camada], animacao: Animacao, largura: int) -> list[Movimento]:
    """Movimento de cada camada no laço."""
    def pela_profundidade(c: Camada) -> bool:
        return c.parametros["laco"] and c.voltas is None and c.forma not in ATMOSFERA

    solidas = voltas_por_profundidade([_profundidade(c) for c in camadas if pela_profundidade(c)], animacao.voltas)
    saida = []
    for c in camadas:
        if not c.parametros["laco"]:
            voltas = 0
        elif c.voltas is not None:
            voltas = c.voltas
        elif c.forma in ATMOSFERA:
            voltas = round(animacao.voltas * (1 - _profundidade(c))) + (c.forma in COM_VENTO)
        else:
            voltas = solidas[_profundidade(c)]
        saida.append(Movimento(voltas, c.forma == "raios", voltas * largura / animacao.quadros))
    return saida


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
        self.movimentos = movimentos(receita.camadas, self.animacao, receita.largura)
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
    """O JSON de tempo que acompanha a folha: o que o jogo precisa para tocar os quadros.

    Quando os quadros não cabem numa folha de 4096 por lado, eles seguem em páginas
    (`<cena>-quadros-1.png`, `-2.png`...): `folhas` lista as páginas na ordem e `quadros_por_folha`
    diz quantos quadros cada uma guarda (a última pode ter menos).
    """
    colunas = colunas_da_folha(animacao.quadros, tamanho[0])
    por_folha = quadros_por_folha(animacao.quadros, *tamanho)
    dados = {
        "cena": cena,
        "folha": arquivo_folha,
        "quadros": animacao.quadros,
        "duracao": animacao.duracao,
        "quadro": list(tamanho),
        "colunas": colunas,
        "linhas": -(-por_folha // colunas),
        "laco": laco,
    }
    if por_folha < animacao.quadros:
        paginas = -(-animacao.quadros // por_folha)
        base = arquivo_folha.removesuffix(".png")
        del dados["folha"]
        dados["folhas"] = [f"{base}-{i}.png" for i in range(1, paginas + 1)]
        dados["quadros_por_folha"] = por_folha
    return dados


def paginas(quadros: list[Image.Image], dados: dict) -> list[Image.Image]:
    """As folhas descritas em `dados` (de `tempo`), uma por página."""
    por_folha = dados.get("quadros_por_folha", len(quadros))
    return [folha(quadros[i:i + por_folha], dados["colunas"]) for i in range(0, len(quadros), por_folha)]


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
