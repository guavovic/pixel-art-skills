"""`revisar`: confere uma imagem pelas regras de pixel art e responde em texto curto.

    from pixel_atelier import revisar

    print(revisar("saida/vale.png").resumo())               # cena; acha as camadas em saida/vale/
    print(revisar("heroi.png", fundo="saida/vale.png").resumo())  # sprite por cima de uma cena
    print(revisar("saida/vale.png", laco=True).resumo())    # força a conferência da emenda

O relatório é o que o agente lê no lugar da imagem: uma linha por regra, `ok`, `alerta` ou
`pulada`, com o número que justifica e onde (x, y em pixel real). O PNG só precisa ser aberto
na aprovação final. Tudo é determinístico e só usa Pillow.

O que entra:
- cena (imagem opaca): com as camadas (a pasta `<cena>/` que `gerar` grava, achada sozinha, ou
  `camadas=`), dá para medir contraste entre camadas, frente contra o fundo e silhuetas; sem elas,
  contraste e legibilidade saem das silhuetas que `silhuetas.separar` tira do composto (heurística:
  mediana da borda entre elas e a borda das que chegam no pé da imagem), e pillow shading e
  serrilhado pulam;
- sprite (imagem com transparência): sozinho ou por cima de um `fundo`, em `posicao`;
- imagem ampliada (blocos NxN, como `<cena>-3x.png`) volta para o tamanho real antes da revisão.

Regras e limiares (as constantes abaixo). Valor é a luminância de `cor.luminancia`, de 0 a 1:
olhar valor e não matiz é o teste da imagem em escala de cinza.
- cores: até 16 num sprite e 64 numa cena; com `estilo`, cor fora da paleta também é alerta.
  Pares de cores quase iguais (distância RGB < 4) aparecem no texto, sem virar alerta.
- contraste: na borda de cada silhueta, a diferença de valor contra o que está atrás (o pixel da
  borda ou o de dentro dele, o que contrastar mais, para o contorno escuro em fundo escuro não
  contar como falha). Mediana de pelo menos 0,05 entre camadas e 0,10 da frente contra o fundo.
- legibilidade: a frente some no fundo onde a diferença fica abaixo de 0,05; alerta se isso
  passar de 25% da borda. Regra da casa: destacar por contraste, não apagar o fundo; fundo com
  faixa de valor (percentil 5 a 95) abaixo de 0,20 é alerta de fundo apagado. Sprite sozinho
  precisa de faixa de valor de pelo menos 0,30. Alerta de contraste ou de legibilidade termina com
  a ação certa: mais contraste de valor na frente, nunca escurecer ou apagar o fundo.
- pixel solto: a mesma definição de `pintura.limpar_soltos` (os 4 vizinhos de uma mesma cor
  diferente da dele), sem contar pontilhado (mesma cor na diagonal ou a 2 e 4 pixels). Alerta
  acima de 0,5% dos pixels.
- pillow shading (heurística): borda da silhueta mais escura que o miolo nos 4 lados (0,06 ou
  mais) e lados parecidos entre si (até 0,04). Luz de um lado só não cai aqui.
- serrilhado (heurística): no perfil de cada lado da silhueta, um degrau com comprimento fora do
  ritmo dos vizinhos (3,1,3 ou 1,3,1; diferença de 2 ou mais). Alerta acima de 6% dos degraus.
- escala (heurística): em ladrilhos de 16x16 com 3 ou mais comprimentos de trecho de cor, o
  máximo divisor comum deles é o bloco; dois ou mais ladrilhos com bloco diferente do resto é
  alerta (sprite ampliado no meio da cena).
- composição repetida (heurística): trecho de 12x12 que aparece igual 3 vezes ou mais, sem
  sobrepor. Só conta trecho com detalhe: 4 cores ou mais, nenhuma em mais de 60% e pelo menos 6
  linhas e 6 colunas diferentes (tronco e faixa não contam); textura periódica e pontilhado (mais
  de 25% de blocos 2x2 em xadrez) também não.
- laço (a imagem sozinha não diz se a cena dá a volta: vale a marca que o `gerar` grava no PNG, ou
  `laco=True`/`--laco` para forçar e `laco=False` para pular): a diferença de
  valor entre a coluna da borda direita e a da esquerda (a emenda), no composto e em cada camada.
  Pixel cheio contra vazio conta 1. Alerta quando a emenda passa de 3 vezes a média das
  diferenças entre colunas vizinhas e também da maior delas: num laço certo a emenda é só mais um
  par de colunas, então nunca é a maior da imagem com folga; num laço quebrado (objeto cortado,
  degradê que não volta) ela é.
- matiz da rampa (precisa do `estilo`): cada rampa do estilo que a imagem usa, com 3 ou mais cores de
  saturação 0,2+, muda pelo menos 3 graus de matiz do tom escuro ao claro. Rampa toda abaixo de
  valor 0,25 (silhueta noturna) fica de fora.
- contorno preto: contorno é a borda com 85% ou mais numa cor só, diferente do miolo. Alerta quando
  todos os contornos são preto puro (canal até 8).
- anti-alias (heurística): meio-tom na borda (alfa parcial, ou valor entre o de dentro e o de trás a
  0,05 de cada um) em 80% ou mais de cada um dos 4 lados da silhueta.
- linha 2:1 (heurística): escada de 6+ degraus (sem as pontas) com 85% ou mais de degraus de 2 é
  linha isométrica; degrau de 1 ou 3 entre dois de 2 é alerta (o serrilhado genérico não pega 2,1,2).

Cada limiar está explicado no capítulo da regra no guia (`pixel_atelier/guia/`, índice em
`indice.md`); mudou aqui, muda lá.

Camada de atmosfera (névoa e raios em pontilhado: mais borda do que miolo) fica fora do
contraste e das silhuetas, porque ela é transparente de propósito.
"""
from __future__ import annotations

import colorsys
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from PIL import Image, ImageChops

from .cor import QUASE_IGUAL, distancia2, luminancia, rgb_para_hex
from .estilo import Estilo, carregar_estilo
from .imagem import abrir, compor, escala_indicada, escala_inteira, marca_de_laco, reduzir, vizinho
from .silhuetas import separar

CORES_SPRITE = 16
CORES_CENA = 64  # o SNES põe até 128 cores de fundo na tela (8 subpaletas de 16); 64 deixa folga sem virar foto
# QUASE_IGUAL (4, em `cor`): distância RGB abaixo disso, duas cores que o olho não separa (só informa);
# a paleta que o estilo monta das rampas já sai sem esses pares
CONTRASTE_CAMADAS = 0.05  # o passo mínimo visível (= SOME): o longe pode ter pouco contraste, não nenhum
CONTRASTE_FRENTE = 0.10  # o dobro do mínimo: a frente é o que precisa ler
SOME = 0.05  # diferença de valor abaixo disso: a borda some no fundo
SOME_MAX = 0.25
FAIXA_FUNDO = 0.20  # fundo empurrado todo para o escuro (0,05 a 0,25) já é fundo apagado
FAIXA_SPRITE = 0.30
SOLTOS_MAX = 0.005
PILLOW_MIOLO = 0.06
PILLOW_LADOS = 0.04
SERRILHADO_MAX = 0.06
LADRILHO = 16
LADRILHOS_FORA = 2
JANELA = 12
JANELA_CORES = 4
JANELA_DOMINANTE = 0.6  # trecho com uma cor em mais disso é liso demais para contar como cópia
JANELA_VARIADA = 6  # linhas e colunas diferentes que o trecho precisa ter
COPIAS = 3
ATMOSFERA = 0.5  # camada com mais pixels de borda do que isso (fração) é névoa ou raio pontilhado
LACO_EMENDA = 3  # emenda acima disso vezes a média entre colunas vizinhas (e acima da maior) é laço quebrado
RAMPA_MATIZ = 3  # graus do escuro ao claro: abaixo disso é só o arredondamento do RGB, a rampa só muda o brilho
RAMPA_SATURACAO = 0.2  # cor menos saturada que isso é quase cinza: o matiz dela não conta
RAMPA_ESCURA = 0.25  # rampa toda abaixo desse valor (silhueta noturna): no escuro o matiz quase não aparece
CONTORNO_UMA_COR = 0.85  # fração da borda numa cor só para ela contar como contorno
PRETO = 8  # canal até isso (#080808): preto puro
AA_LADO = 0.8  # fração da borda em meio-tom, em cada um dos 4 lados, para ser anti-alias em volta da forma
ISO_DEGRAUS = 6  # degraus de uma linha (sem as pontas) para ela contar como linha 2:1
ISO_DOIS = 0.85  # fração desses degraus com 2 pixels para a linha ser 2:1 (1 fora do 2 a cada 7)
DICA_CONTRASTE = ("aumente o contraste de valor da frente (clareie ou escureça a frente ou o contorno), "
                  "nunca escureça nem apague o fundo")

VIZINHOS = ((1, 0), (-1, 0), (0, 1), (0, -1))
LADOS = {(0, -1): "topo", (0, 1): "base", (-1, 0): "esquerda", (1, 0): "direita"}


@dataclass
class Checagem:
    regra: str
    estado: str  # "ok", "alerta" ou "pulada"
    detalhe: str
    heuristica: bool = False

    def linha(self) -> str:
        return f"{self.estado} {self.regra}{' [heurística]' if self.heuristica else ''}: {self.detalhe}"


@dataclass
class Revisao:
    nome: str
    largura: int
    altura: int
    tipo: str  # "cena", "sprite" ou "sprite sobre fundo"
    escala: int  # 1, ou N quando a imagem veio ampliada N vezes
    camadas: list[str]
    checagens: list[Checagem]
    imagem: Image.Image = field(repr=False)

    def alertas(self) -> list[Checagem]:
        return [c for c in self.checagens if c.estado == "alerta"]

    def resumo(self) -> str:
        """Uma linha de cabeçalho e uma por regra."""
        partes = [f"{self.nome}: {self.largura}x{self.altura}, {self.tipo}"]
        if self.camadas:
            partes[0] += f" com {len(self.camadas)} camadas"
        if self.escala > 1:
            partes.append(f"ampliada {self.escala}x (revisada no tamanho real)")
        quantos = len(self.alertas())
        partes.append("nenhum alerta" if not quantos else f"{quantos} alerta{'s' if quantos > 1 else ''}")
        return "\n".join([", ".join(partes)] + [c.linha() for c in self.checagens])

    def para_dicionario(self) -> dict[str, Any]:
        return {
            "nome": self.nome, "tamanho": [self.largura, self.altura], "tipo": self.tipo, "escala": self.escala,
            "camadas": self.camadas,
            "checagens": [{"regra": c.regra, "estado": c.estado, "detalhe": c.detalhe, "heuristica": c.heuristica}
                          for c in self.checagens],
        }


# --- leitura -------------------------------------------------------------------------------------

def _camadas_ao_lado(arquivo: Path) -> list[Path]:
    """As camadas que `gerar` grava: `<cena>/NN-nome.png` ao lado de `<cena>.png` ou `<cena>-Nx.png`."""
    nome = arquivo.stem
    base, _, sufixo = nome.rpartition("-")
    if base and sufixo.endswith("x") and sufixo[:-1].isdigit():
        nome = base
    pasta = arquivo.parent / nome
    return sorted(pasta.glob("[0-9][0-9]-*.png")) if pasta.is_dir() else []


def _indicada(imagem: "str | Path | Image.Image") -> int | None:
    return escala_indicada(imagem) if isinstance(imagem, (str, Path)) else None


def _ler_camadas(camadas: "str | Path | Sequence[str | Path | Image.Image]") -> list[tuple[str, Image.Image]]:
    if isinstance(camadas, (str, Path)):
        pasta = Path(camadas)
        if not pasta.is_dir():
            raise ValueError(f"pasta de camadas {pasta.as_posix()} não existe")
        camadas = sorted(pasta.glob("*.png"))
        if not camadas:
            raise ValueError(f"nenhum PNG na pasta de camadas {pasta.as_posix()}")
    lidas = []
    for i, c in enumerate(camadas):
        nome = Path(c).stem if isinstance(c, (str, Path)) else f"{i + 1:02d}"
        lidas.append((nome, abrir(c)))
    return lidas


# --- medidas de apoio ----------------------------------------------------------------------------

class _Px:
    """Pixels de uma imagem RGBA com acesso rápido a cor, alfa e valor.

    `alfa` e `valores` são planos, linha após linha (o pixel x, y fica em y * largura + x): os
    laços quentes leem direto deles, sem chamada por pixel.
    """

    def __init__(self, imagem: Image.Image):
        self.imagem = imagem
        self.largura, self.altura = imagem.size
        self.px = imagem.load()
        self.alfa = imagem.getchannel("A").tobytes()
        cores = memoryview(imagem.tobytes()).cast("I").tolist()  # um número por pixel (os 4 bytes RGBA)
        por_cor = {c: luminancia(c.to_bytes(4, sys.byteorder)) for c in set(cores)}
        self.valores = [por_cor[c] for c in cores]

    def dentro(self, x: int, y: int) -> bool:
        return 0 <= x < self.largura and 0 <= y < self.altura

    def cheio(self, x: int, y: int) -> bool:
        return self.dentro(x, y) and self.alfa[y * self.largura + x] > 0

    def valor(self, x: int, y: int) -> float:
        return self.valores[y * self.largura + x]

    def cheios(self) -> list[int]:
        """Índices dos pixels cheios, em ordem de leitura."""
        return [i for i, a in enumerate(self.alfa) if a]

    def valores_cheios(self) -> list[float]:
        return [v for v, a in zip(self.valores, self.alfa) if a]


def _percentil(valores: Sequence[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(p * len(ordenados)))]


def _mediana(valores: Sequence[float]) -> float:
    return _percentil(valores, 0.5)


def _regiao(pontos: Iterable[tuple[int, int]]) -> str:
    pontos = list(pontos)
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    return f"x{min(xs)}-{max(xs)} y{min(ys)}-{max(ys)}"


def _medida(valor: float, limite: float, formato: str = ".2f") -> str:
    """O valor no formato do limite, com mais casas quando o arredondamento o deixaria igual ao limite."""
    tipo, casas = formato[-1], int(formato[1:-1])
    while casas < 4 and valor != limite and format(valor, f".{casas}{tipo}") == format(limite, f".{casas}{tipo}"):
        casas += 1
    return format(valor, f".{casas}{tipo}")


def _faixa(valores: Sequence[float]) -> float:
    return _percentil(valores, 0.95) - _percentil(valores, 0.05) if valores else 0.0


def _borda(frente: _Px, tras: _Px) -> list[tuple[int, int, float]]:
    """(x, y, diferença de valor) em cada passo da silhueta da frente para fora, contra o de trás."""
    largura, altura = frente.largura, frente.altura
    alfa, valores, alfa_tras, valores_tras = frente.alfa, frente.valores, tras.alfa, tras.valores
    saida = []
    for i in frente.cheios():
        y, x = divmod(i, largura)
        for dx, dy in VIZINHOS:
            fx, fy = x + dx, y + dy
            if not (0 <= fx < largura and 0 <= fy < altura):
                continue
            j = i + dx + dy * largura
            if alfa[j] or not alfa_tras[j]:
                continue
            atras = valores_tras[j]
            diferenca = abs(valores[i] - atras)
            k = i - dx - dy * largura  # o de dentro: contorno escuro em fundo escuro
            if 0 <= x - dx < largura and 0 <= y - dy < altura and alfa[k]:
                diferenca = max(diferenca, abs(valores[k] - atras))
            saida.append((fx, fy, diferenca))
    return saida


def _profundidade(silhueta: _Px) -> dict[tuple[int, int], int]:
    """Distância (em passos de 4 vizinhos) de cada pixel cheio até o vazio; 1 é a borda."""
    largura, altura, alfa = silhueta.largura, silhueta.altura, silhueta.alfa
    atual = []
    plano: dict[int, int] = {}
    cheio = silhueta.imagem.getchannel("A").point(lambda v: 255 if v else 0)
    miolo = cheio
    for dx, dy in VIZINHOS:  # fora da imagem conta como o próprio pixel: a beira não é borda
        miolo = ImageChops.darker(miolo, vizinho(cheio, dx, dy))
    for i, b in enumerate(ImageChops.subtract(cheio, miolo).tobytes()):
        if b:
            plano[i] = 1
            atual.append(i)
    nivel = 1
    while atual:
        nivel += 1
        proximo = []
        for i in atual:
            y, x = divmod(i, largura)
            for dx, dy in VIZINHOS:
                if not (0 <= x + dx < largura and 0 <= y + dy < altura):
                    continue
                j = i + dx + dy * largura
                if j not in plano and alfa[j]:
                    plano[j] = nivel
                    proximo.append(j)
        atual = proximo
    return {(i % largura, i // largura): v for i, v in plano.items()}


def _atmosfera(silhueta: _Px, prof: dict[tuple[int, int], int]) -> bool:
    cheios = len(silhueta.alfa) - silhueta.alfa.count(0)
    borda = sum(1 for v in prof.values() if v == 1)
    return cheios == 0 or borda > ATMOSFERA * cheios


@dataclass
class _DoComposto:
    """Silhuetas separadas só pelo composto (`silhuetas.separar`), quando não há camadas nem fundo."""

    silhuetas: int
    borda: list[tuple[int, int, float]]  # a borda de todas contra o que encosta nelas
    frente: list[tuple[int, int, float]]  # a borda das que chegam no pé da imagem: o mais perto, na vista lateral


def _do_composto(cena: _Px) -> _DoComposto:
    resultado = _DoComposto(0, [], [])
    for s in separar(cena.imagem):
        # tudo no recorte da silhueta com 1 pixel de folga: na beira da imagem o recorte para nela, igual
        x0, y0, x1, y1 = s.caixa
        caixa = (max(0, x0 - 1), max(0, y0 - 1), min(cena.largura, x1 + 1), min(cena.altura, y1 + 1))
        f = _Px(s.imagem.crop(caixa))
        if _atmosfera(f, _profundidade(f)):
            continue
        borda = [(x + caixa[0], y + caixa[1], d) for x, y, d in _borda(f, _Px(cena.imagem.crop(caixa)))]
        if not borda:
            continue
        resultado.silhuetas += 1
        resultado.borda.extend(borda)
        if s.caixa[3] == cena.altura:
            resultado.frente.extend(borda)
    return resultado


# --- regras --------------------------------------------------------------------------------------

def _cores(alvo: Image.Image, limite: int, estilo: Estilo | None) -> Checagem:
    contagem = alvo.getcolors(maxcolors=alvo.width * alvo.height) or []
    cores = sorted({(r, g, b) for _, (r, g, b, a) in contagem if a > 0})
    if len(cores) > 256:
        return Checagem("cores", "alerta", f"{len(cores)}: não parece pixel art (borrado, anti-alias ou JPEG?)")
    detalhe = f"{len(cores)} (limite {limite})"
    alerta = len(cores) > limite
    pares = [(a, b) for i, a in enumerate(cores) for b in cores[i + 1:] if distancia2(a, b) < QUASE_IGUAL ** 2]
    if pares:
        a, b = pares[0]
        quantos = f"{len(pares)} pares quase iguais" if len(pares) > 1 else "1 par quase igual"
        detalhe += f"; {quantos} ({rgb_para_hex(a)}~{rgb_para_hex(b)})"
    if estilo is not None:
        fora = [c for c in cores if c not in set(estilo.paleta)]
        if fora:
            alerta = True
            detalhe += f"; {len(fora)} fora da paleta de {estilo.nome} ({rgb_para_hex(fora[0])})"
    return Checagem("cores", "alerta" if alerta else "ok", detalhe)


def _contraste(pares: list[tuple[str, list[tuple[int, int, float]]]]) -> Checagem:
    if not pares:
        return Checagem("contraste", "pulada", "sem camadas nem fundo (passe camadas ou fundo)")
    medianas = [(nome, _mediana([d for _, _, d in borda])) for nome, borda in pares]
    *trás, (nome_frente, frente) = medianas
    ruins = [(n, m) for n, m in trás if m < CONTRASTE_CAMADAS]
    rotulo = "sprite" if nome_frente == "sprite" else f"frente ({nome_frente})"
    partes = [f"{rotulo} x fundo {_medida(frente, CONTRASTE_FRENTE)} (mín {CONTRASTE_FRENTE:.2f})"]
    if trás:
        pior = min(trás, key=lambda t: t[1])
        partes.append(f"entre camadas mín {_medida(pior[1], CONTRASTE_CAMADAS)} em {pior[0]} (mín {CONTRASTE_CAMADAS:.2f})")
    if ruins:
        partes.append("baixo em " + ", ".join(f"{n} {_medida(m, CONTRASTE_CAMADAS)}" for n, m in ruins[:3]))
    alerta = frente < CONTRASTE_FRENTE or bool(ruins)
    if alerta:
        partes.append(DICA_CONTRASTE)
    return Checagem("contraste", "alerta" if alerta else "ok", "; ".join(partes))


def _contraste_do_composto(composto: _DoComposto) -> Checagem:
    if not composto.borda:
        return Checagem("contraste", "pulada", "sem camadas nem fundo, e o composto não separou silhuetas "
                                               "(passe camadas ou fundo)")
    mediana = _mediana([d for _, _, d in composto.borda])
    partes = [f"pelo composto, sem camadas: {composto.silhuetas} silhuetas, mediana "
              f"{_medida(mediana, CONTRASTE_CAMADAS)} na borda entre elas (mín {CONTRASTE_CAMADAS:.2f})"]
    if mediana < CONTRASTE_CAMADAS:
        partes.append(DICA_CONTRASTE)
    return Checagem("contraste", "alerta" if mediana < CONTRASTE_CAMADAS else "ok", "; ".join(partes), True)


def _legibilidade_do_composto(composto: _DoComposto) -> Checagem:
    if not composto.borda:
        return Checagem("legibilidade", "pulada", "sem camadas nem fundo, e o composto não separou silhuetas "
                                                  "(passe camadas ou fundo)")
    if not composto.frente:
        return Checagem("legibilidade", "pulada", "sem camadas nem fundo, e nenhuma silhueta do composto chega no pé "
                                                  "da imagem (passe camadas ou fundo)")
    somem = [(x, y) for x, y, d in composto.frente if d < SOME]
    fracao = len(somem) / len(composto.frente)
    partes = [f"pelo composto: a borda das silhuetas da frente (as que chegam no pé da imagem) some em {_medida(fracao, SOME_MAX, '.0%')} "
              f"(máx {SOME_MAX:.0%})"]
    if fracao > SOME_MAX:
        partes[0] += f", {_regiao(somem)}"
        partes.append(DICA_CONTRASTE)
    else:
        partes.append("fundo apagado só se mede com as camadas")
    return Checagem("legibilidade", "alerta" if fracao > SOME_MAX else "ok", "; ".join(partes), True)


def _legibilidade(borda_frente: list[tuple[int, int, float]] | None, fundo: _Px | None,
                  alvo: _Px | None, rotulo: str = "frente") -> Checagem:
    if borda_frente is not None and fundo is not None:
        somem = [(x, y) for x, y, d in borda_frente if d < SOME]
        fracao = len(somem) / len(borda_frente)
        faixa = _faixa(fundo.valores_cheios())
        partes = [f"{rotulo} some no fundo em {_medida(fracao, SOME_MAX, '.0%')} da borda (máx {SOME_MAX:.0%})"]
        if fracao > SOME_MAX:
            partes[0] += f", {_regiao(somem)}"
        partes.append(f"fundo com faixa de valor {_medida(faixa, FAIXA_FUNDO)} (mín {FAIXA_FUNDO:.2f})")
        if faixa < FAIXA_FUNDO:
            partes.append("fundo apagado")
        alerta = fracao > SOME_MAX or faixa < FAIXA_FUNDO
        if alerta:
            partes.append(DICA_CONTRASTE)
        return Checagem("legibilidade", "alerta" if alerta else "ok", "; ".join(partes))
    if alvo is not None:
        faixa = _faixa(alvo.valores_cheios())
        detalhe = f"faixa de valor do sprite {_medida(faixa, FAIXA_SPRITE)} (mín {FAIXA_SPRITE:.2f}; teste em escala de cinza)"
        if faixa < FAIXA_SPRITE:
            return Checagem("legibilidade", "alerta",
                            detalhe + "; aumente o contraste de valor do sprite (luz, sombra e contorno mais separados)")
        return Checagem("legibilidade", "ok", detalhe)
    return Checagem("legibilidade", "pulada", "sem camadas nem fundo (passe camadas ou fundo)")


def _soltos(alvo: _Px) -> Checagem:
    px = alvo.px
    soltos, total = [], 0
    for y in range(1, alvo.altura - 1):
        for x in range(1, alvo.largura - 1):
            atual = px[x, y]
            if atual[3]:
                total += 1
            primeiro = px[x + 1, y]
            if primeiro == atual or not all(px[x + dx, y + dy] == primeiro for dx, dy in VIZINHOS[1:]):
                continue
            if primeiro[3] == 0 and atual[3] == 0:
                continue
            # pontilhado: a mesma cor volta na diagonal ou no passo do padrão de Bayer
            if any(alvo.dentro(x + dx, y + dy) and px[x + dx, y + dy] == atual
                   for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1), (2, 2), (2, -2), (-2, 2), (-2, -2),
                                  (4, 0), (-4, 0), (0, 4), (0, -4), (2, 0), (-2, 0), (0, 2), (0, -2))):
                continue
            soltos.append((x, y))
    fracao = len(soltos) / max(1, total)
    detalhe = f"{len(soltos)} ({fracao:.2%}, máx {SOLTOS_MAX:.1%})"
    if soltos:
        detalhe += " em " + " ".join(f"({x},{y})" for x, y in soltos[:3]) + (" ..." if len(soltos) > 3 else "")
    return Checagem("pixel solto", "alerta" if fracao > SOLTOS_MAX else "ok", detalhe)


def _pillow(silhuetas: list[tuple[str, _Px, dict[tuple[int, int], int]]]) -> Checagem:
    if not silhuetas:
        return Checagem("pillow shading", "pulada", "sem silhueta (passe camadas ou um sprite)", True)
    achadas, conferidas = [], 0
    for nome, s, prof in silhuetas:
        borda = [p for p, v in prof.items() if v == 1]
        if not borda:
            continue  # sem pixel vazio em volta (alfa parcial, imagem cheia): não há silhueta para medir
        cores = Counter(s.px[x, y] for x, y in borda)
        cor, quantas = cores.most_common(1)[0]
        resto = [s.valor(*p) for p, v in prof.items() if v > 1]
        casca = 1
        if resto and quantas >= 0.85 * len(borda) and luminancia(cor) < _mediana(resto):
            casca = 2  # a borda é o contorno: o sombreado começa um pixel para dentro
        lados: dict[str, list[float]] = {lado: [] for lado in LADOS.values()}
        miolo = []
        for (x, y), v in prof.items():
            if v >= casca + 2:
                miolo.append(s.valor(x, y))
            elif v == casca:
                for (dx, dy), lado in LADOS.items():  # a beira da imagem não é lado da silhueta
                    if s.dentro(x + dx, y + dy) and prof.get((x + dx, y + dy), 0) < casca:
                        lados[lado].append(s.valor(x, y))
        if len(miolo) < 8 or any(len(v) < 4 for v in lados.values()):
            continue
        conferidas += 1
        medias = [sum(v) / len(v) for v in lados.values()]
        centro = sum(miolo) / len(miolo)
        if max(medias) <= centro - PILLOW_MIOLO and max(medias) - min(medias) <= PILLOW_LADOS:
            achadas.append(f"{nome}: borda {centro - max(medias):.2f} mais escura que o miolo nos 4 lados")
    if achadas:
        return Checagem("pillow shading", "alerta", "; ".join(achadas[:3]) + "; luz de um lado só", True)
    if not conferidas:
        return Checagem("pillow shading", "pulada", "nenhuma silhueta fechada grande o bastante", True)
    return Checagem("pillow shading", "ok", f"{conferidas} silhueta{'s' if conferidas > 1 else ''}, nenhuma com "
                    f"miolo {PILLOW_MIOLO:.2f}+ mais claro que a borda nos 4 lados", True)


def _perfis(s: _Px) -> Iterable[list[tuple[int, int, tuple[int, int]]]]:
    """Perfil de cada lado da silhueta, visto de fora: trechos contínuos de (posição, distância, pixel)."""
    L, A = s.largura, s.altura
    linhas = [s.alfa[y * L:(y + 1) * L] for y in range(A)]
    transposta = s.imagem.getchannel("A").transpose(Image.Transpose.TRANSPOSE).tobytes()
    colunas = [transposta[x * A:(x + 1) * A] for x in range(L)]

    def do_inicio(fila: bytes) -> int | None:
        vazios = len(fila) - len(fila.lstrip(b"\0"))
        return vazios if vazios < len(fila) else None

    def do_fim(fila: bytes) -> int | None:
        vazios = len(fila) - len(fila.rstrip(b"\0"))
        return vazios if vazios < len(fila) else None

    varreduras = (
        (colunas, do_inicio, lambda a, b: (a, b)),          # topo: coluna a, de cima para baixo
        (colunas, do_fim, lambda a, b: (a, A - 1 - b)),     # base
        (linhas, do_inicio, lambda a, b: (b, a)),           # esquerda: linha a, da esquerda para a direita
        (linhas, do_fim, lambda a, b: (L - 1 - b, a)),      # direita
    )
    for filas, primeiro, ponto in varreduras:
        perfil: list[tuple[int, int, tuple[int, int]]] = []
        for a, fila in enumerate(filas):
            achado = primeiro(fila)
            if achado is None:
                if perfil:
                    yield perfil
                perfil = []
                continue
            perfil.append((a, achado, ponto(a, achado)))
        if perfil:
            yield perfil


def _serrilhado(silhuetas: list[tuple[str, _Px, dict[tuple[int, int], int]]]) -> Checagem:
    if not silhuetas:
        return Checagem("serrilhado", "pulada", "sem silhueta (passe camadas ou um sprite)", True)
    quebrados: list[tuple[str, tuple[int, int]]] = []
    degraus = 0
    for nome, s, _ in silhuetas:
        for perfil in _perfis(s):
            trechos: list[list[Any]] = []  # [comprimento, distância, primeiro pixel], um por degrau
            for _, h, pixel in perfil:
                if trechos and trechos[-1][1] == h:
                    trechos[-1][0] += 1
                else:
                    trechos.append([1, h, pixel])
            degraus += len(trechos)
            for antes, meio, depois in zip(trechos, trechos[1:], trechos[2:]):
                passo = meio[1] - antes[1]
                if abs(passo) != 1 or depois[1] - meio[1] != passo:
                    continue  # só dentro de uma linha inclinada, degrau de 1 pixel
                d1, d2 = meio[0] - antes[0], depois[0] - meio[0]
                if d1 * d2 < 0 and min(abs(d1), abs(d2)) >= 2:
                    quebrados.append((nome, meio[2]))
    fracao = len(quebrados) / max(1, degraus)
    detalhe = f"{len(quebrados)} degraus fora do ritmo em {degraus} ({fracao:.1%}, máx {SERRILHADO_MAX:.0%})"
    if quebrados:
        nome, quantos = Counter(n for n, _ in quebrados).most_common(1)[0]
        x, y = next(p for n, p in quebrados if n == nome)
        detalhe += f"; mais em {nome} ({quantos}, o primeiro em ({x},{y}))"
    return Checagem("serrilhado", "alerta" if fracao > SERRILHADO_MAX else "ok", detalhe, True)


def _bloco_do_ladrilho(px, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int]:
    """(máximo divisor comum, quantos comprimentos diferentes) dos trechos de cor inteiros no ladrilho."""
    n = 0
    comprimentos: set[int] = set()
    for linhas, ponto in (((y0, y1, x0, x1), lambda a, b: px[b, a]), ((x0, x1, y0, y1), lambda a, b: px[a, b])):
        a0, a1, b0, b1 = linhas
        for a in range(a0, a1):
            inicio = None
            for b in range(b0 + 1, b1):
                if ponto(a, b) != ponto(a, b - 1):
                    if inicio is not None:
                        n = math.gcd(n, b - inicio)
                        comprimentos.add(b - inicio)
                    inicio = b
    return n, len(comprimentos)


def _escala(cena: Image.Image) -> Checagem:
    px = cena.load()
    blocos: dict[tuple[int, int], int] = {}
    for y0 in range(0, cena.height - LADRILHO + 1, LADRILHO):
        for x0 in range(0, cena.width - LADRILHO + 1, LADRILHO):
            n, variedade = _bloco_do_ladrilho(px, x0, y0, x0 + LADRILHO, y0 + LADRILHO)
            if variedade >= 3:  # pontilhado e listras repetem um comprimento só e não contam
                blocos[(x0, y0)] = n
    if not blocos:
        return Checagem("escala", "pulada", "pouco detalhe para medir", True)
    comum = Counter(blocos.values()).most_common(1)[0][0]
    fora = [p for p, n in blocos.items() if n != comum]
    detalhe = f"bloco {comum}x em {len(blocos) - len(fora)} de {len(blocos)} ladrilhos {LADRILHO}x{LADRILHO}"
    if fora:
        outros = Counter(blocos[p] for p in fora).most_common(1)[0][0]
        detalhe += f"; {len(fora)} com bloco {outros}x em {_regiao(fora)} (máx {LADRILHOS_FORA - 1})"
    return Checagem("escala", "alerta" if len(fora) >= LADRILHOS_FORA else "ok", detalhe, True)


def _repeticao(alvo: Image.Image) -> Checagem:
    largura, altura = alvo.size
    if largura < JANELA or altura < JANELA:
        return Checagem("composição repetida", "pulada", f"imagem menor que {JANELA}x{JANELA}", True)
    dados = alvo.tobytes()
    passo, w = largura * 4, JANELA * 4
    # cada trecho de JANELA pixels numa linha vira um número; a janela é a pilha de JANELA trechos
    trechos: dict[bytes, int] = {}
    por_linha = []
    for y in range(altura):
        linha = dados[y * passo:(y + 1) * passo]
        por_linha.append([trechos.setdefault(linha[x * 4:x * 4 + w], len(trechos))
                          for x in range(largura - JANELA + 1)])
    grupos: dict[tuple[int, ...], list[tuple[int, int]]] = {}
    for y in range(altura - JANELA + 1):
        for x, pilha in enumerate(zip(*por_linha[y:y + JANELA])):
            grupos.setdefault(pilha, []).append((x, y))
    objetos: dict[tuple[tuple[int, int], ...], list[tuple[int, int]]] = {}
    for posicoes in grupos.values():
        if len(posicoes) < COPIAS:
            continue
        copias: list[tuple[int, int]] = []
        for x, y in posicoes:  # em ordem de leitura; guarda só cópias que não se sobrepõem
            if all(abs(x - cx) >= JANELA or abs(y - cy) >= JANELA for cx, cy in copias):
                copias.append((x, y))
        if len(copias) < COPIAS:
            continue
        x0, y0 = copias[0]
        inicio = y0 * passo + x0 * 4
        if not _detalhada(b"".join(dados[inicio + r * passo:inicio + r * passo + w] for r in range(JANELA))):
            continue
        x0, y0 = copias[0]
        deslocamentos = tuple((x - x0, y - y0) for x, y in copias)
        objetos.setdefault(deslocamentos, []).append((x0, y0))
    if not objetos:
        return Checagem("composição repetida", "ok",
                        f"nenhum trecho {JANELA}x{JANELA} igual {COPIAS}+ vezes", True)
    deslocamentos, origens = max(objetos.items(), key=lambda item: (len(item[0]), len(item[1])))
    x0, y0 = min(origens)
    lugares = " ".join(f"({x0 + dx},{y0 + dy})" for dx, dy in deslocamentos[:4])
    detalhe = (f"{len(objetos)} trecho{'s' if len(objetos) > 1 else ''} repetido{'s' if len(objetos) > 1 else ''}; "
               f"maior: {len(deslocamentos)} cópias em {lugares}{' ...' if len(deslocamentos) > 4 else ''}")
    return Checagem("composição repetida", "alerta", detalhe, True)


def _diferencas_de_colunas(p: _Px) -> tuple[list[float], float]:
    """Diferença média de valor entre cada par de colunas vizinhas e na emenda (a última com a primeira).

    Cheio contra vazio conta 1.
    """
    largura = p.largura
    colunas = [(p.valores[x::largura], p.alfa[x::largura]) for x in range(largura)]

    def diferenca(a: int, b: int) -> float:
        (valores_a, alfa_a), (valores_b, alfa_b) = colunas[a], colunas[b]
        total = 0.0
        for va, vb, cheio_a, cheio_b in zip(valores_a, valores_b, alfa_a, alfa_b):
            if cheio_a and cheio_b:
                total += abs(va - vb)
            elif bool(cheio_a) != bool(cheio_b):
                total += 1
        return total / p.altura

    return [diferenca(x, x + 1) for x in range(largura - 1)], diferenca(largura - 1, 0)


def _laco(imagens: list[tuple[str, Image.Image]], pedido: bool | None, marca: bool | None) -> Checagem:
    """`pedido` vem de quem chama (None: decide a marca); `marca` é a que o `gerar` gravou no PNG."""
    if pedido is False:
        return Checagem("laço", "pulada", "conferência do laço desligada no pedido")
    if pedido is None and marca is None:
        return Checagem("laço", "pulada", "imagem sem a marca de laço do gerar; passe laco (--laco) se a cena "
                                          "dá a volta na horizontal")
    if pedido is None and marca is False:
        return Checagem("laço", "pulada", "a cena foi gerada sem laço (marca do gerar); passe laco (--laco) para "
                                          "conferir mesmo assim")
    origem = "" if pedido else "; laço pela marca do gerar"
    largura = imagens[0][1].width
    if largura < 3:
        return Checagem("laço", "pulada", "imagem estreita demais para medir a emenda")
    medidas = []  # (nome, emenda, média, maior)
    for nome, imagem in imagens:
        vizinhas, emenda = _diferencas_de_colunas(_Px(imagem))
        medidas.append((nome, emenda, sum(vizinhas) / len(vizinhas), max(vizinhas)))
    quebradas = [m for m in medidas if m[1] > LACO_EMENDA * m[2] and m[1] > m[3]]
    _, emenda, media, _ = medidas[0]
    if not quebradas:
        onde = f"composto e {len(imagens) - 1} camadas" if len(imagens) > 1 else "composto"
        return Checagem("laço", "ok", f"emenda x{largura - 1}|x0 dentro do normal no {onde} (composto {emenda:.2f}, "
                                      f"média entre colunas {media:.2f}; máx {LACO_EMENDA}x a média){origem}")
    nome, emenda, media, maior = max(quebradas, key=lambda m: m[1] / max(m[2], 1e-9))
    outras = f" e mais {len(quebradas) - 1}" if len(quebradas) > 1 else ""
    return Checagem("laço", "alerta", f"emenda x{largura - 1}|x0 quebrada em {nome}{outras}: {emenda:.2f} contra média "
                                      f"{media:.2f} e maior {maior:.2f} entre colunas vizinhas (máx {LACO_EMENDA}x a "
                                      "média); a borda direita não continua na esquerda: desenhe a camada com laço")


def _detalhada(janela: bytes) -> bool:
    """Trecho com cores bastante e que não é textura periódica (pontilhado, listras)."""
    pixels = [janela[i:i + 4] for i in range(0, len(janela), 4)]
    contagem = Counter(pixels)
    if len(contagem) < JANELA_CORES or contagem.most_common(1)[0][1] > JANELA_DOMINANTE * len(pixels):
        return False  # pouca cor ou quase tudo de uma cor só: céu, chão liso, beira reta
    linhas = {tuple(pixels[r * JANELA:(r + 1) * JANELA]) for r in range(JANELA)}
    colunas = {tuple(pixels[c::JANELA]) for c in range(JANELA)}
    if min(len(linhas), len(colunas)) < JANELA_VARIADA:
        return False  # quase igual numa direção: tronco, faixa, degradê
    xadrez = 0  # blocos 2x2 em xadrez (a b / b a): muito disso é pontilhado, que se repete sozinho
    for r in range(JANELA - 1):
        for c in range(JANELA - 1):
            a, b = pixels[r * JANELA + c], pixels[r * JANELA + c + 1]
            xadrez += a != b and pixels[(r + 1) * JANELA + c] == b and pixels[(r + 1) * JANELA + c + 1] == a
    if xadrez > 0.25 * (JANELA - 1) ** 2:
        return False
    for p in range(1, JANELA // 2 + 1):  # igual a si mesma andando p pixels: listra ou textura
        n = len(pixels)
        if all(pixels[i] == pixels[i + p] for i in range(n - p) if i % JANELA < JANELA - p):
            return False
        if all(pixels[i] == pixels[i + p * JANELA] for i in range(n - p * JANELA)):
            return False
    return True


# --- regras do guia: rampa, contorno, anti-alias e linha 2:1 -------------------------------------

def _hsv(cor: Sequence[int]) -> tuple[float, float]:
    """(matiz em graus, saturação de 0 a 1)."""
    h, s, _ = colorsys.rgb_to_hsv(cor[0] / 255, cor[1] / 255, cor[2] / 255)
    return h * 360, s


def _rampa_matiz(alvo: Image.Image, estilo: Estilo | None) -> Checagem:
    """Rampas do estilo que a imagem usa: o matiz precisa andar do escuro ao claro."""
    if estilo is None:
        return Checagem("matiz da rampa", "pulada", "sem estilo (passe estilo: as rampas vêm dele)")
    px = alvo.load()
    onde: dict[tuple[int, int, int], tuple[int, int]] = {}
    for y in range(alvo.height):
        for x in range(alvo.width):
            r, g, b, a = px[x, y]
            if a and (r, g, b) not in onde:
                onde[(r, g, b)] = (x, y)
    conferidas, sem = [], []
    for papel, rampa in estilo.rampas.items():
        if sum(c in onde for c in set(rampa)) < 2:
            continue  # rampa que a imagem não usa
        if max(luminancia(c) for c in rampa) < RAMPA_ESCURA:
            continue
        cores = sorted({c for c in rampa if _hsv(c)[1] >= RAMPA_SATURACAO}, key=luminancia)
        if len(cores) < 3:
            continue  # rampa quase cinza ou curta demais para ter matiz
        muda = abs((_hsv(cores[-1])[0] - _hsv(cores[0])[0] + 180) % 360 - 180)
        conferidas.append((papel, muda))
        if muda < RAMPA_MATIZ:
            x, y = next(onde[c] for c in rampa if c in onde)
            sem.append(f"{papel} {rgb_para_hex(cores[0])} > {rgb_para_hex(cores[-1])} muda {muda:.0f}°, em ({x},{y})")
    if not conferidas:
        return Checagem("matiz da rampa", "pulada", f"nenhuma rampa de {estilo.nome} com 3+ cores saturadas na imagem")
    if sem:
        return Checagem("matiz da rampa", "alerta", "; ".join(sem[:3]) + f" (mín {RAMPA_MATIZ}°); a rampa só muda o "
                        "brilho: puxe a sombra para o frio e a luz para o quente (guia cor)")
    papel, muda = min(conferidas, key=lambda c: c[1])
    return Checagem("matiz da rampa", "ok", f"{len(conferidas)} rampa{'s' if len(conferidas) > 1 else ''} de "
                    f"{estilo.nome}, menor mudança {muda:.0f}° em {papel} (mín {RAMPA_MATIZ}°)")


def _contorno_preto(silhuetas: list[tuple[str, _Px, dict[tuple[int, int], int]]]) -> Checagem:
    """Contorno é a borda quase toda numa cor só, diferente do miolo; alerta se todos forem preto puro."""
    if not silhuetas:
        return Checagem("contorno preto", "pulada", "sem silhueta (passe camadas ou um sprite)")
    com_contorno, pretas = 0, []
    for nome, s, prof in silhuetas:
        borda = [p for p, v in prof.items() if v == 1]
        miolo = Counter(s.px[p][:3] for p, v in prof.items() if v > 1)
        if len(borda) < 8 or not miolo:
            continue
        cor, quantas = Counter(s.px[p][:3] for p in borda).most_common(1)[0]
        if quantas < CONTORNO_UMA_COR * len(borda) or miolo.most_common(1)[0][0] == cor:
            continue  # sem contorno, ou silhueta chapada
        com_contorno += 1
        if max(cor) <= PRETO:
            pretas.append((nome, next(p for p in borda if s.px[p][:3] == cor)))
    if not com_contorno:
        return Checagem("contorno preto", "ok", "nenhuma silhueta com contorno de uma cor só")
    detalhe = f"{len(pretas)} de {com_contorno} contornos em preto puro (até {rgb_para_hex((PRETO,) * 3)})"
    if pretas and len(pretas) == com_contorno:
        nome, (x, y) = pretas[0]
        return Checagem("contorno preto", "alerta", detalhe + f", o primeiro em {nome} ({x},{y}); contorno preto em "
                        "tudo achata: use a cor mais escura da rampa da forma (guia fundamentos)")
    return Checagem("contorno preto", "ok", detalhe)


def _anti_alias(silhuetas: list[tuple[str, _Px, dict[tuple[int, int], int]]], atras_de: dict[str, _Px]) -> Checagem:
    """Meio-tom na borda: alfa parcial, ou valor entre o de dentro e o de trás com um passo visível de cada lado."""
    if not silhuetas:
        return Checagem("anti-alias", "pulada", "sem silhueta (passe camadas ou um sprite)", True)
    achadas, conferidas = [], 0
    for nome, s, prof in silhuetas:
        tras = atras_de.get(nome)
        lados: dict[str, list[int]] = {lado: [0, 0] for lado in LADOS.values()}  # [meio-tom, total]
        primeiro = None
        for (x, y), v in prof.items():
            if v != 1:
                continue
            for (dx, dy), lado in LADOS.items():
                fx, fy, ix, iy = x + dx, y + dy, x - dx, y - dy
                if not s.dentro(fx, fy) or s.cheio(fx, fy):
                    continue
                if s.px[x, y][3] < 255:
                    meio = True
                elif tras is None or not tras.cheio(fx, fy) or prof.get((ix, iy), 0) < 2:
                    continue
                else:
                    dentro, fora, aqui = s.valor(ix, iy), tras.valor(fx, fy), s.valor(x, y)
                    meio = min(dentro, fora) + SOME <= aqui <= max(dentro, fora) - SOME
                lados[lado][1] += 1
                if meio:
                    lados[lado][0] += 1
                    primeiro = primeiro or (x, y)
        if any(total < 4 for _, total in lados.values()):
            continue
        conferidas += 1
        pior = min(meio / total for meio, total in lados.values())
        if pior >= AA_LADO:
            achadas.append((nome, pior, primeiro))
    if achadas:
        nome, pior, (x, y) = achadas[0]
        return Checagem("anti-alias", "alerta", f"{nome}: meio-tom em {pior:.0%}+ da borda nos 4 lados (máx {AA_LADO:.0%}"
                        f"), a partir de ({x},{y}); anti-alias em volta da forma inteira vira borrão: deixe só no "
                        "degrau longo que incomoda (guia fundamentos)", True)
    if not conferidas:
        return Checagem("anti-alias", "pulada", "nenhuma silhueta com borda nos 4 lados", True)
    return Checagem("anti-alias", "ok", f"{conferidas} silhueta{'s' if conferidas > 1 else ''}, nenhuma com meio-tom em "
                    f"{AA_LADO:.0%}+ da borda nos 4 lados", True)


def _linha_iso(silhuetas: list[tuple[str, _Px, dict[tuple[int, int], int]]]) -> Checagem:
    """Linha 2:1 é uma escada de degraus de 2; um degrau de 1 ou 3 no meio dela (2,1,2) quebra a linha."""
    if not silhuetas:
        return Checagem("linha 2:1", "pulada", "sem silhueta (passe camadas ou um sprite)", True)
    linhas, quebras = 0, []
    for nome, s, _ in silhuetas:
        for perfil in _perfis(s):
            trechos: list[list[Any]] = []  # [comprimento, distância, primeiro pixel], um por degrau
            for _, h, pixel in perfil:
                if trechos and trechos[-1][1] == h:
                    trechos[-1][0] += 1
                else:
                    trechos.append([1, h, pixel])
            i = 0
            while i < len(trechos) - 1:
                passo = trechos[i + 1][1] - trechos[i][1]
                j = i + 1
                while j + 1 < len(trechos) and trechos[j + 1][1] - trechos[j][1] == passo:
                    j += 1
                escada, meio = trechos[i:j + 1], trechos[i + 1:j]  # as pontas podem estar cortadas
                if abs(passo) == 1 and len(meio) >= ISO_DEGRAUS and sum(t[0] == 2 for t in meio) >= ISO_DOIS * len(meio):
                    linhas += 1
                    quebras += [(nome, b[0], b[2]) for a, b, c in zip(escada, escada[1:], escada[2:])
                                if a[0] == 2 == c[0] and b[0] != 2]
                i = j
    if not linhas:
        return Checagem("linha 2:1", "ok", f"nenhuma linha 2:1 ({ISO_DEGRAUS}+ degraus de 2)", True)
    if quebras:
        nome, comprimento, (x, y) = quebras[0]
        return Checagem("linha 2:1", "alerta", f"{len(quebras)} degrau{'s' if len(quebras) > 1 else ''} fora do 2 em "
                        f"{linhas} linha{'s' if linhas > 1 else ''} 2:1, o primeiro de {comprimento} em {nome} ({x},{y}); "
                        "o 2:1 é 2,2,2, nunca 2,1,2 (guia angulo)", True)
    return Checagem("linha 2:1", "ok", f"{linhas} linha{'s' if linhas > 1 else ''} 2:1, nenhuma quebrada", True)


# --- entrada -------------------------------------------------------------------------------------

def revisar(
    imagem: "str | Path | Image.Image",
    *,
    camadas: "str | Path | Sequence[str | Path | Image.Image] | None" = None,
    fundo: "str | Path | Image.Image | None" = None,
    posicao: tuple[int, int] | None = None,
    estilo: "str | Estilo | None" = None,
    laco: bool | None = None,
) -> Revisao:
    """Confere `imagem` pelas regras e devolve a `Revisao` (use `resumo()` para o texto).

    `camadas`: pasta ou lista de PNGs do fundo para a frente; sem ela, a pasta `<cena>/` ao lado
    do arquivo é usada se existir. `fundo`: cena por trás de um sprite, que vai em `posicao`
    (x, y do canto de cima; padrão: no meio). `estilo`: confere as cores contra a paleta.
    `laco`: confere a emenda no composto e em cada camada. None (padrão) segue a marca que o
    `gerar` grava no PNG (sem marca, pula); True força a conferência e False pula.
    Arquivo que não abre ou tamanhos que não batem levantam `ValueError` ou `OSError`.
    """
    nome = Path(imagem).name if isinstance(imagem, (str, Path)) else "imagem"
    original = abrir(imagem)
    marca = marca_de_laco(imagem) if laco is None and isinstance(imagem, (str, Path)) else None
    if isinstance(estilo, str):
        estilo = carregar_estilo(estilo)

    lidas: list[tuple[str, Image.Image]] = []
    if fundo is None:
        if camadas is None and isinstance(imagem, (str, Path)):
            camadas = _camadas_ao_lado(Path(imagem)) or None
        if camadas is not None:
            lidas = _ler_camadas(camadas)
    if lidas:  # as camadas dizem o tamanho real
        tamanho = lidas[0][1].size
        escala = original.width // tamanho[0] or 1
        for n, c in lidas:
            if c.size != tamanho or (c.width * escala, c.height * escala) != original.size:
                raise ValueError(f"camada {n} tem {c.width}x{c.height} e a imagem {original.width}x{original.height}")
    else:
        escala = escala_inteira(original, _indicada(imagem))
    alvo = reduzir(original, escala)

    sprite = alvo.getchannel("A").getextrema()[0] < 255 and not lidas
    # planos: (nome, a camada, o que está atrás dela)
    if fundo is not None:
        tras = abrir(fundo)
        tras = reduzir(tras, escala_inteira(tras, _indicada(fundo)))
        if alvo.width > tras.width or alvo.height > tras.height:
            raise ValueError(f"sprite {alvo.width}x{alvo.height} maior que o fundo {tras.width}x{tras.height}")
        x, y = posicao or ((tras.width - alvo.width) // 2, (tras.height - alvo.height) // 2)
        frente = Image.new("RGBA", tras.size, (0, 0, 0, 0))
        frente.paste(alvo, (x, y))
        planos = [("sprite", frente, tras)]
        tipo, cena = "sprite sobre fundo", Image.alpha_composite(tras, frente)
    else:
        planos = [(n, c, compor([c2 for _, c2 in lidas[:i]])) for i, (n, c) in enumerate(lidas) if i > 0]
        tipo, cena = ("sprite" if sprite else "cena"), alvo

    silhuetas: list[tuple[str, _Px, dict[tuple[int, int], int]]] = []
    pares: list[tuple[str, list[tuple[int, int, float]]]] = []
    fundo_px = None
    atras_de: dict[str, _Px] = {}  # o que está atrás de cada silhueta (anti-alias)
    for n, camada, atras in planos:
        f = _Px(camada)
        prof = _profundidade(f)
        if fundo is None and _atmosfera(f, prof):
            continue  # névoa e raios pontilhados são transparentes de propósito
        borda = _borda(f, atras_px := _Px(atras))
        if borda:
            pares.append((n, borda))
            silhuetas.append((n, f, prof))
            atras_de[n] = atras_px
            fundo_px = atras_px  # o da última camada com borda: o fundo da frente
    alvo_px = _Px(alvo)
    if tipo == "sprite":
        silhuetas.append(("sprite", alvo_px, _profundidade(alvo_px)))

    if tipo == "cena" and not lidas:  # só o composto: as silhuetas saem dele
        composto = _do_composto(alvo_px)
        contraste, legibilidade = _contraste_do_composto(composto), _legibilidade_do_composto(composto)
        # forma e sombreado não: no composto a silhueta se corta na que está na frente e na troca de material,
        # e a luz de contorno cai noutra família; medido assim, dá alerta em cena boa
        motivo = "sem camadas: no composto a silhueta se corta nas outras (passe camadas ou fundo)"
        pillow = Checagem("pillow shading", "pulada", motivo, True)
        serrilhado = Checagem("serrilhado", "pulada", motivo, True)
    else:
        contraste = _contraste(pares)
        legibilidade = _legibilidade(pares[-1][1] if pares else None, fundo_px,
                                     alvo_px if tipo == "sprite" else None, "sprite" if fundo is not None else "frente")
        pillow, serrilhado = _pillow(silhuetas), _serrilhado(silhuetas)

    checagens = [
        _cores(alvo, CORES_SPRITE if sprite else CORES_CENA, estilo),
        contraste,
        legibilidade,
        _soltos(alvo_px),
        pillow,
        serrilhado,
        _escala(cena),
        _repeticao(alvo),
        _laco([("composto", alvo)] + lidas, laco, marca),
        _rampa_matiz(alvo, estilo),
        _contorno_preto(silhuetas),
        _anti_alias(silhuetas, atras_de),
        _linha_iso(silhuetas),
    ]
    return Revisao(nome=nome, largura=alvo.width, altura=alvo.height, tipo=tipo, escala=escala,
                   camadas=[n for n, _ in lidas], checagens=checagens, imagem=alvo)
