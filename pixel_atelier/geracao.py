"""Geração: a técnica de uma época de console, separada do tema (as cores e a luz do estilo).

`"geracao": 16` (ou `"16-bits"`) num estilo ou na receita troca a técnica do tema pela da época:
resolução de referência, passos das rampas, grade de cores, limite de cores da cena e de cada
camada, sombreamento, contorno e textura. O tema continua dando as cores, o céu e a atmosfera.

Os números ficam em `ANCORAS` (8, 16 e 32 bits, e moderno = 64). Valor entre duas âncoras (10, 12,
24) interpola os números na escala de bits (log2) e pega a técnica da âncora mais perto (grade,
sombreamento, contorno, textura e fundo em ladrilhos); acima de 64 vale o moderno. As fontes de
cada número estão no capítulo `geracoes` do guia.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from .cor import (RAMPA_MATIZ, RGB, cor_mais_proxima, distancia2, hex_para_rgb, luminancia, mudanca_de_matiz,
                  sem_repetir)

MODERNO = 64
NOMES = {"8-bits": 8, "16-bits": 16, "32-bits": 32, "moderno": MODERNO, "hd": MODERNO}
FOLGA_DA_GRADE = 2  # candidata da grade até 2 vezes a distância (ao quadrado) da cor mais perto
VALOR_GUARDADO = 0.5  # na grade, o degrau de valor entre tons vizinhos da paleta fechada fica com metade ou mais
COMBINACOES_MAX = 10_000

# NES (2C02), como a paleta "Nintendo Entertainment System" do Lospec
CORES_NES = tuple(hex_para_rgb(c) for c in (
    "#000000", "#fcfcfc", "#f8f8f8", "#bcbcbc", "#7c7c7c", "#a4e4fc", "#3cbcfc", "#0078f8", "#0000fc", "#b8b8f8",
    "#6888fc", "#0058f8", "#0000bc", "#d8b8f8", "#9878f8", "#6844fc", "#4428bc", "#f8b8f8", "#f878f8", "#d800cc",
    "#940084", "#f8a4c0", "#f85898", "#e40058", "#a80020", "#f0d0b0", "#f87858", "#f83800", "#a81000", "#fce0a8",
    "#fca044", "#e45c10", "#881400", "#f8d878", "#f8b800", "#ac7c00", "#503000", "#d8f878", "#b8f818", "#00b800",
    "#007800", "#b8f8b8", "#58d854", "#00a800", "#006800", "#b8f8d8", "#58f898", "#00a844", "#005800", "#00fcfc",
    "#00e8d8", "#008888", "#004058", "#f8d8f8", "#787878",
))


@dataclass(frozen=True)
class Geracao:
    numero: int
    nome: str
    tamanho: tuple[int, int]
    passos: int  # tons em cada rampa
    cores_cena: int  # cores na cena inteira
    cores_camada: int | None  # cores em cada camada; None: sem limite além do da cena
    grade: str  # "nes" (as 54 cores do NES), "15-bits" (5 bits por canal) ou "livre"
    sombreamento: str
    largura_faixa: int
    degraus: int  # tons da rampa em cada faixa, da borda para dentro
    contorno: str  # "preto", "escuro" (a cor de contorno do tema) ou "selout" (o tom mais escuro da peça)
    textura: float  # 0 a 1: manchas de tom vizinho dentro das peças
    ladrilhos: bool  # fundo montado com ladrilhos repetidos: o `revisar` tolera mais cópias
    detalhe: float  # tamanho do detalhe em relação ao de 8 a 32 bits: a janela da composição repetida


ANCORAS = {
    8: Geracao(8, "8-bits", (256, 240), 3, 25, 13, "nes", "pontilhado", 1, 1, "preto", 0.0, True, 1.0),
    16: Geracao(16, "16-bits", (256, 224), 5, 121, 15, "15-bits", "faixas", 2, 1, "escuro", 0.0, True, 1.0),
    32: Geracao(32, "32-bits", (320, 240), 6, 256, 255, "15-bits", "faixas", 2, 2, "selout", 0.7, False, 1.0),
    MODERNO: Geracao(MODERNO, "moderno", (640, 360), 8, 256, None, "livre", "faixas", 3, 2, "selout", 1.0, False, 2.0),
}


def ler_geracao(valor: object) -> int:
    """Número da geração a partir de 16, "16", "16-bits", "moderno" ou "hd"."""
    if isinstance(valor, str):
        texto = valor.strip().lower()
        if texto in NOMES:
            return NOMES[texto]
        valor = int(texto) if texto.isdigit() else None
    numero_valido = isinstance(valor, int) and not isinstance(valor, bool) and valor >= 8
    if not numero_valido:
        raise ValueError(f"geracao deve ser um número de bits a partir de 8 (8, 12, 16, 32, 64) ou um de "
                         f"{', '.join(NOMES)}, veio {valor!r}")
    return min(int(valor), MODERNO)


def _vizinhas(numero: int) -> tuple[Geracao, Geracao, float]:
    """As âncoras de cada lado de `numero` e a posição entre elas (0 a 1) na escala log2."""
    chaves = sorted(ANCORAS)
    for menor, maior in zip(chaves, chaves[1:]):
        if menor <= numero <= maior:
            t = (math.log2(numero) - math.log2(menor)) / (math.log2(maior) - math.log2(menor))
            return ANCORAS[menor], ANCORAS[maior], t
    return ANCORAS[chaves[-1]], ANCORAS[chaves[-1]], 0.0


def _entre(a: float, b: float, t: float) -> float:
    return math.exp(math.log(a) + (math.log(b) - math.log(a)) * t)


def _multiplo(valor: float, passo: int) -> int:
    return max(passo, round(valor / passo) * passo)


def geracao(valor: object) -> Geracao:
    """A `Geracao` pedida, interpolada entre as âncoras quando cai entre duas."""
    numero = ler_geracao(valor)
    if numero in ANCORAS:
        return ANCORAS[numero]
    a, b, t = _vizinhas(numero)
    perto = a if t < 0.5 else b
    if a.cores_camada is None or b.cores_camada is None:
        cores_camada = perto.cores_camada
    else:
        cores_camada = round(_entre(a.cores_camada, b.cores_camada, t))
    return Geracao(
        numero=numero,
        nome=f"{numero}-bits",
        tamanho=(_multiplo(_entre(a.tamanho[0], b.tamanho[0], t), 8), _multiplo(_entre(a.tamanho[1], b.tamanho[1], t), 2)),
        passos=round(a.passos + (b.passos - a.passos) * t),
        cores_cena=round(_entre(a.cores_cena, b.cores_cena, t)),
        cores_camada=cores_camada,
        grade=perto.grade,
        sombreamento=perto.sombreamento,
        largura_faixa=perto.largura_faixa,
        degraus=perto.degraus,
        contorno=perto.contorno,
        textura=perto.textura,
        ladrilhos=perto.ladrilhos,
        detalhe=round(_entre(a.detalhe, b.detalhe, t), 3),
    )


def na_grade(cor: RGB, grade: str) -> RGB:
    """`cor` levada para a grade de cores da geração."""
    if grade == "nes":
        return cor_mais_proxima(cor, CORES_NES)
    if grade == "15-bits":
        return tuple((q << 3) | (q >> 2) for q in (round(v * 31 / 255) for v in cor))  # type: ignore[return-value]
    return tuple(cor)  # type: ignore[return-value]


def _candidatas(cor: RGB, grade: str) -> list[RGB]:
    """Cores da grade perto de `cor`: a mais perto e as que ficam até `FOLGA_DA_GRADE` vezes a distância dela."""
    if grade == "nes":
        limite = distancia2(cor, cor_mais_proxima(cor, CORES_NES)) * FOLGA_DA_GRADE
        return [c for c in CORES_NES if distancia2(cor, c) <= limite]
    if grade == "15-bits":
        lados = [{math.floor(v * 31 / 255), math.ceil(v * 31 / 255)} for v in cor]
        return [tuple((q << 3) | (q >> 2) for q in canais) for canais in itertools.product(*lados)]  # type: ignore[misc]
    return [cor]


def _guarda_o_matiz(rampa: list[RGB], sentido: float) -> bool:
    muda = mudanca_de_matiz(rampa)
    return muda is not None and abs(muda[0]) >= RAMPA_MATIZ and muda[0] * sentido > 0


def matiz_na_grade(rampa: list[RGB], grade: str) -> list[RGB]:
    """A rampa do tema pronta para a grade, sem perder a mudança de matiz.

    Fica igual quando a cor mais perto da grade guarda o matiz (a paleta leva cada tom para ela).
    Se ali a rampa passa a mudar menos de `RAMPA_MATIZ`, como o cristal azul que o NES põe numa
    coluna só, vale a combinação de candidatas (`_candidatas`) que muda o matiz no mesmo sentido do
    tema e mais perto dele, com a menor distância somada no empate; sem nenhuma assim, fica igual.
    """
    tema = mudanca_de_matiz(rampa)
    perto = mudanca_de_matiz([na_grade(c, grade) for c in rampa])
    tema_muda = tema is not None and abs(tema[0]) >= RAMPA_MATIZ
    grade_parou = perto is not None and abs(perto[0]) < RAMPA_MATIZ
    if not (tema_muda and grade_parou):
        return rampa
    combinacoes = (list(r) for r in itertools.product(*(_candidatas(c, grade) for c in rampa)))
    opcoes = [r for r in combinacoes if _guarda_o_matiz(r, tema[0])]
    if not opcoes:
        return rampa

    def longe_do_tema(opcao: list[RGB]) -> tuple[float, int]:
        graus = abs(mudanca_de_matiz(opcao)[0] - tema[0])
        return graus, sum(distancia2(a, b) for a, b in zip(rampa, opcao))

    return min(opcoes, key=longe_do_tema)


def valor_na_grade(paleta: list[RGB], grade: str) -> dict[RGB, RGB]:
    """Cor da grade para cada cor de uma paleta fechada, sem juntar o valor de tons vizinhos.

    Fica a cor mais perto quando ela guarda pelo menos `VALOR_GUARDADO` de cada degrau de valor
    entre tons vizinhos. Se não guarda, como os dois verdes escuros do Game Boy que o NES põe a 0,04
    um do outro, vale a combinação de candidatas (`_candidatas`) que guarda a maior fração do degrau
    mais apertado, com a menor distância somada no empate.
    """
    cores = sorted(sem_repetir(paleta), key=luminancia)
    degraus_do_tema = [max(luminancia(b) - luminancia(a), 0.01) for a, b in zip(cores, cores[1:])]

    def guardado(opcao: tuple[RGB, ...]) -> float:
        degraus = [luminancia(b) - luminancia(a) for a, b in zip(opcao, opcao[1:])]
        return min((d / t for d, t in zip(degraus, degraus_do_tema)), default=1.0)

    perto = tuple(na_grade(c, grade) for c in cores)
    candidatas = [_candidatas(c, grade) for c in cores]
    muitas = math.prod(len(c) for c in candidatas) > COMBINACOES_MAX
    if guardado(perto) >= VALOR_GUARDADO or muitas:
        return dict(zip(cores, perto))

    def perda(opcao: tuple[RGB, ...]) -> tuple[float, int]:
        return -guardado(opcao), sum(distancia2(a, b) for a, b in zip(cores, opcao))

    return dict(zip(cores, min(itertools.product(*candidatas), key=perda)))


def reduzir_paleta(cores: list[RGB], limite: int) -> list[RGB]:
    """Junta as duas cores mais parecidas até sobrarem `limite`; fica a que vem antes na lista."""
    cores = list(cores)
    while len(cores) > limite:
        _, _, depois = min((distancia2(a, b), i, j) for i, a in enumerate(cores) for j, b in enumerate(cores) if i < j)
        del cores[depois]
    return cores
