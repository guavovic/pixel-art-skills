"""`ref`: tira o estilo de uma imagem de referência e guarda como preset.

    from pixel_atelier import ref

    print(ref("referencias/floresta.png", "floresta").resumo())   # grava o preset "floresta"

A referência é vista uma vez: depois a receita usa só o preset (`"estilo": "floresta"`), e o
agente lê o resumo em texto no lugar da imagem. Tudo é determinístico e só usa Pillow.

O que sai da imagem:
- tamanho do pixel: imagem ampliada (blocos NxN) volta para o tamanho real (`imagem.escala_inteira`).
- paleta: as cores visíveis, exatas quando são até `cores` (padrão 32). Acima disso, com aviso,
  a mais escura e a mais clara ficam exatas (contorno e luz) e o resto é quantizado família a
  família pelo corte de mediana do Pillow: cada família guarda `PISO_DA_FAMILIA` cores (se
  couber) e a sobra vai pelo tamanho, para a família pequena não virar 2 tons. Com mais famílias
  que cores, a imagem toda é quantizada de uma vez. Com mais de 256 cores ela não parece
  pixel art (foto, anti-aliasing): se passar de `LADO_MAX` por lado, antes é reduzida pela média
  de blocos.
- rampas: cada cor cai numa família pelo matiz (HSV) ou fica neutra (saturação abaixo de 0,2 ou
  quase preta); a neutra se divide em escura e clara (valor 0,7). Família com 2 cores ou mais vira
  rampa, do escuro ao claro (até `RAMPA_MAX` cores, espaçadas pelo valor), e vai para os papéis:
  verde → folha e grama; quente (vermelho, laranja, marrom) → terra e tronco; neutra escura →
  pedra; neutra clara → nuvem, névoa e neve; roxo → cristal. Azul fica só na paleta.
- par de papéis: família com `DIVIDIR_PAR` cores ou mais dá rampas diferentes para folha e grama
  (e para tronco e terra): folha e tronco no trecho mais escuro, grama e terra no mais claro.
- tom fora do matiz: numa família cromática, o tom cujo croma de lado (CIELAB, em relação ao matiz
  médio da família pesado pelos pixels) passa de `DESVIO_DE_MATIZ` sai da rampa e fica só na paleta,
  como o rosa que a quantização põe entre os marrons. Rampa que muda de matiz aos poucos fica inteira.
- família dominante: com `DOMINANTE` da paleta ou mais numa família só (cena noturna toda azul,
  game-boy todo verde), os papéis sem família vão para ela, cada um num trecho de valor (`JANELAS`:
  tronco no escuro, neve no claro), e o tom fora do matiz sai papel a papel.
- chão: em imagem opaca, a cor mais comum da faixa de baixo (`FAIXA_DO_CHAO` da altura). Se ela
  está na família da terra, a rampa da terra é centrada nela, porque a pintura usa o tom do meio:
  assim o chão gerado sai na cor do chão da referência.
- céu: em imagem opaca, a cor mais comum de cada linha do terço de cima, de cima para baixo (do
  topo ao horizonte, até `RAMPA_MAX` cores). A última, a do horizonte, vira a atmosfera. Sprite
  (com transparência) não tem céu.
- luz: a cor mais clara da paleta; contorno: a mais escura.
- contraste: faixa de valor dos pixels (percentil 5 a 95, como no `revisar`) e o passo médio de
  valor em cada rampa. Fica no bloco `referencia` do preset, só para consulta (o estilo ignora).

O que a imagem não diz (sombreamento, contorno ligado ou não, direção da luz, largura das faixas,
forças de atmosfera e luz, papel sem família quando nenhuma domina) vem do estilo `base` (padrão
`snes-diurno`, mesma validação de nome do gerar e do revisar). Como o preset fecha a `paleta` com
as cores da referência, até o que vem do base é pintado só com elas. O preset é gravado como o
`registrar_estilo` grava: na pasta de presets do usuário, com a base já aplicada.
"""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from .cor import RGB, cor_mais_proxima, limpar_alfa, luminancia, rgb_para_hex, sem_repetir
from .estilo import NOME_VALIDO, dados_do_estilo, registrar_estilo, sugerir_nome, validar_nome_de_estilo
from .imagem import abrir, escala_inteira, reduzir

CORES = 32  # paleta padrão do preset; dá para pedir de 2 a 256
CORES_PIXEL_ART = 256  # acima disso a referência não parece pixel art
LADO_MAX = 256  # foto maior que isso é reduzida pela média antes de quantizar
SATURACAO_NEUTRA = 0.2
VALOR_ESCURO = 0.1  # cor quase preta: o matiz dela não quer dizer nada
NEUTRA_CLARA = 0.7  # valor (luminância) a partir do qual a neutra é nuvem, névoa ou neve
RAMPA_MAX = 6
PISO_DA_FAMILIA = 3  # cores que cada família guarda quando a paleta é reduzida (se couber): rampa de 3 tons

# família: (início, fim) do matiz em graus; o resto (330 a 50, dando a volta no 0) é "quente"
FAMILIAS = {"verde": (50, 170), "azul": (170, 260), "roxo": (260, 330)}
PAPEIS_DA_FAMILIA = {
    "verde": ("folha", "grama"),
    "quente": ("terra", "tronco"),
    "neutra": ("pedra",),
    "clara": ("nuvem", "nevoa", "neve"),
    "roxo": ("cristal",),
}
CINZAS = ("neutra", "clara")  # famílias sem matiz que conte
# Tom de família cromática cujo croma de lado (no CIELAB, em relação ao matiz médio da família) passa
# disso é tom estranho: sai da rampa e fica só na paleta. Na família dominante, vale em cada papel.
DESVIO_DE_MATIZ = 20
# Família com essas cores ou mais dá uma rampa para cada papel do par; abaixo, os dois dividem a rampa.
DIVIDIR_PAR = 5
JANELA_DO_PAR = {"folha": (0, 0.65), "tronco": (0, 0.65), "grama": (0.35, 1), "terra": (0.35, 1)}
# Família com essa fração da paleta ou mais é repartida pelos papéis vazios, cada papel num trecho de
# valor dela (0 a cor mais escura da família, 1 a mais clara).
DOMINANTE = 0.6
JANELAS = {"tronco": (0, 0.45), "terra": (0.1, 0.55), "folha": (0.15, 0.65), "pedra": (0.25, 0.7),
           "grama": (0.35, 0.85), "cristal": (0.5, 1), "nuvem": (0.55, 1), "nevoa": (0.65, 1), "neve": (0.75, 1)}
FAIXA_DO_CHAO = 0.1  # fração de baixo da imagem cuja cor mais comum é o chão
ORDEM = ("folha", "grama", "terra", "tronco", "pedra", "cristal", "nuvem", "nevoa", "neve")


@dataclass
class Rampa:
    papeis: tuple[str, ...]
    cores: tuple[RGB, ...]  # do escuro ao claro; o céu, do topo ao horizonte

    def linha(self) -> str:
        valores = [luminancia(c) for c in self.cores]
        passo = (valores[-1] - valores[0]) / (len(valores) - 1)
        return (f"{', '.join(self.papeis)}: {len(self.cores)} cores {rgb_para_hex(self.cores[0])} > "
                f"{rgb_para_hex(self.cores[-1])}, valor {valores[0]:.2f} a {valores[-1]:.2f}, passo {passo:.2f}")


@dataclass
class Referencia:
    nome: str
    arquivo: str
    tamanho_original: tuple[int, int]
    escala: int  # 1, ou N quando a imagem veio ampliada N vezes
    tamanho: tuple[int, int]  # tamanho real, onde as cores foram contadas
    cores_na_imagem: int
    paleta: list[RGB]  # do escuro ao claro
    rampas: list[Rampa]
    da_base: list[str]  # papéis que vieram do estilo base
    luz: RGB
    contorno: RGB
    atmosfera: RGB | None
    valor: tuple[float, float]  # mínimo e máximo
    faixa: float  # percentil 5 a 95
    base: str
    estilo: dict[str, Any]  # o que vai para registrar_estilo
    avisos: list[str] = field(default_factory=list)
    destino: Path | None = None
    fora_do_matiz: list[RGB] = field(default_factory=list)  # tom longe do matiz da família: só na paleta
    dominante: tuple[str, int, list[str]] | None = None  # família, quantas cores, papéis repartidos pelo valor

    def resumo(self) -> str:
        """Texto curto para o agente: o preset, a paleta, as rampas e o contraste."""
        w, h = self.tamanho_original
        linhas = []
        if self.destino is not None:
            linhas.append(f"preset {self.nome} gravado em {self.destino.as_posix()}, base {self.base}")
        cabecalho = f"referência {self.arquivo}: {w}x{h}"
        if self.escala > 1:
            cabecalho += f", ampliada {self.escala}x (pixel real {self.tamanho[0]}x{self.tamanho[1]})"
        elif self.tamanho != self.tamanho_original:
            cabecalho += f", reduzida para {self.tamanho[0]}x{self.tamanho[1]}"
        linhas.append(cabecalho)
        exatas = len(self.paleta) == self.cores_na_imagem
        linhas.append(f"paleta: {len(self.paleta)} cores" + (" (exatas da imagem)" if exatas
                                                             else f" (de {self.cores_na_imagem} na imagem)"))
        linhas.append(f"valor: {self.valor[0]:.2f} a {self.valor[1]:.2f}, faixa {self.faixa:.2f} (p5 a p95)")
        linhas.append("rampas, do escuro ao claro (céu: do topo ao horizonte):")
        linhas.extend(f"  {r.linha()}" for r in self.rampas)
        if self.dominante:
            familia, quantas, papeis = self.dominante
            linhas.append(f"família {familia} domina ({quantas} de {len(self.paleta)} cores), "
                          f"repartida pelo valor em: {', '.join(papeis)}")
        if self.fora_do_matiz:
            tons = ", ".join(map(rgb_para_hex, self.fora_do_matiz[:6]))
            resto = len(self.fora_do_matiz) - 6
            tons += f" e mais {resto}" if resto > 0 else ""
            linhas.append(f"fora do matiz da família, só na paleta: {tons}")
        if self.da_base:
            linhas.append(f"da base, só com cores da paleta: {', '.join(self.da_base)}")
        extra = f", atmosfera {rgb_para_hex(self.atmosfera)}" if self.atmosfera else ""
        linhas.append(f"luz {rgb_para_hex(self.luz)}, contorno {rgb_para_hex(self.contorno)}{extra}")
        linhas.extend(f"aviso: {a}" for a in self.avisos)
        return "\n".join(linhas)


# --- extração -------------------------------------------------------------------------------------

def _contar(imagem: Image.Image) -> list[tuple[int, RGB]]:
    """(quantos pixels, cor) das cores visíveis."""
    contagem = imagem.getcolors(maxcolors=imagem.width * imagem.height) or []
    return [(n, (r, g, b)) for n, (r, g, b, a) in contagem if a > 0]


def _quantizar(imagem: Image.Image, cores: int) -> list[tuple[int, RGB]]:
    """Corte de mediana do Pillow, só com os pixels visíveis, família a família. Devolve (quantos pixels, cor).

    O corte da imagem inteira junta o marrom escuro de pouco pixel com o cinza vizinho e a família fica com
    2 cores (rampa curta). Por isso cada família (`_familia`) é quantizada sozinha, com uma parte das `cores`
    (`_repartir`). A cor mais escura e a mais clara ficam exatas: são o contorno e a luz do preset. Com mais
    famílias do que cores, vale o corte da imagem inteira."""
    contagem = _contar(imagem)
    escura = min(contagem, key=lambda par: luminancia(par[1]))
    clara = max(contagem, key=lambda par: luminancia(par[1]))
    por_familia: dict[str, list[tuple[int, RGB]]] = {}
    for par in contagem:
        if par is not escura and par is not clara:
            por_familia.setdefault(_familia(par[1]), []).append(par)
    sobra = cores - 2
    if len(por_familia) > sobra:
        return _mediana_de_cores(contagem, cores)
    cotas = _repartir({f: len(pares) for f, pares in por_familia.items()}, sobra)
    juntas = [escura, clara] + [par for f, pares in por_familia.items() for par in _mediana_de_cores(pares, cotas[f])]
    pixels: dict[RGB, int] = {}
    for n, cor in juntas:
        pixels[cor] = pixels.get(cor, 0) + n
    return [(n, c) for c, n in pixels.items()]


def _repartir(tamanhos: dict[str, int], total: int) -> dict[str, int]:
    """Divide `total` entre as famílias: cada uma com até `PISO_DA_FAMILIA` cores (se couber, senão 1) e o
    resto pelo tamanho (D'Hondt), nunca mais que o tamanho dela."""
    pisos = {f: min(n, PISO_DA_FAMILIA) for f, n in tamanhos.items()}
    cotas = pisos if sum(pisos.values()) <= total else {f: 1 for f in tamanhos}
    livres = [f for f in tamanhos if cotas[f] < tamanhos[f]]
    while livres and sum(cotas.values()) < total:
        f = max(livres, key=lambda f: tamanhos[f] / (cotas[f] + 1))
        cotas[f] += 1
        livres = [f for f in livres if cotas[f] < tamanhos[f]]
    return cotas


def _mediana_de_cores(contagem: Sequence[tuple[int, RGB]], cores: int) -> list[tuple[int, RGB]]:
    """Corte de mediana do Pillow nas cores dadas, cada uma com o peso dos pixels dela."""
    if len(contagem) <= cores:
        return list(contagem)
    pixels = [cor for n, cor in contagem for _ in range(n)]
    rgb = Image.new("RGB", (len(pixels), 1))
    rgb.putdata(pixels)
    q = rgb.quantize(colors=cores, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    paleta = q.getpalette()
    juntas: dict[RGB, int] = {}
    for n, i in q.getcolors(maxcolors=256) or []:
        cor = tuple(paleta[i * 3:i * 3 + 3])
        juntas[cor] = juntas.get(cor, 0) + n  # type: ignore[index]
    return [(n, c) for c, n in juntas.items()]


def _familia(cor: RGB) -> str:
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in cor))
    if s < SATURACAO_NEUTRA or v < VALOR_ESCURO:
        return "clara" if luminancia(cor) >= NEUTRA_CLARA else "neutra"
    graus = h * 360
    return next((nome for nome, (inicio, fim) in FAMILIAS.items() if inicio <= graus < fim), "quente")


def _ceu(imagem: Image.Image, paleta: Sequence[RGB]) -> list[RGB]:
    """Cor mais comum de cada linha do terço de cima, já na paleta, do topo ao horizonte. Só em imagem opaca."""
    if imagem.getchannel("A").getextrema()[0] < 255:
        return []
    cores = []
    for y in range(max(1, imagem.height // 3)):
        linha = imagem.crop((0, y, imagem.width, y + 1))
        _, cor = max(linha.getcolors(maxcolors=imagem.width))
        cores.append(cor_mais_proxima(cor[:3], paleta))
    return sem_repetir(cores)


def _chao(imagem: Image.Image, paleta: Sequence[RGB]) -> RGB | None:
    """Cor mais comum da faixa de baixo (`FAIXA_DO_CHAO` da altura), já na paleta. Só em imagem opaca: na
    vista lateral é o chão."""
    if imagem.getchannel("A").getextrema()[0] < 255:
        return None
    faixa = imagem.crop((0, imagem.height - max(1, round(imagem.height * FAIXA_DO_CHAO)), imagem.width, imagem.height))
    _, cor = max(faixa.getcolors(maxcolors=faixa.width * faixa.height))
    return cor_mais_proxima(cor[:3], paleta)


def _centrar(cores: Sequence[RGB], cor: RGB, largura: float) -> tuple[float, float]:
    """Trecho de até `largura` com `cor` bem no meio (o tom base da rampa), sem pular cor: encolhe perto da
    ponta e fica com até `RAMPA_MAX` cores."""
    i, ultimo = cores.index(cor), len(cores) - 1
    lado = min(round(largura / 2 * ultimo), i, ultimo - i, (RAMPA_MAX - 1) // 2)
    return (i - lado) / ultimo, (i + lado) / ultimo


def _espacar(cores: Sequence[RGB], quantas: int) -> tuple[RGB, ...]:
    """Até `quantas` cores, espaçadas pela posição na lista (já ordenada pelo valor)."""
    if len(cores) <= quantas:
        return tuple(cores)
    return tuple(cores[round(i * (len(cores) - 1) / (quantas - 1))] for i in range(quantas))


def _ab(cor: RGB) -> tuple[float, float]:
    """Os eixos a e b do CIELAB (D65): o plano da cor sem o valor, onde o ângulo é o matiz como o olho vê."""
    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    r, g, b = (linear(c / 255) for c in cor)
    x = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047)
    y = f(0.2126 * r + 0.7152 * g + 0.0722 * b)
    z = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883)
    return 500 * (x - y), 200 * (y - z)


def _separar_fora_do_matiz(cores: Sequence[RGB], pixels: dict[RGB, int]) -> tuple[list[RGB], list[RGB]]:
    """Separa (dentro, fora). Sai o tom que se afasta do matiz médio das cores (pesado pelos pixels) mais
    que `DESVIO_DE_MATIZ`, medido no CIELAB como a parte do croma de lado (croma vezes o seno da diferença
    de matiz): o rosa que a quantização põe entre os marrons, o brilho de cristal no meio da terra. Rampa
    que muda de matiz aos poucos (verde escuro ao verde-amarelo) fica inteira, e tom quase cinza também,
    porque o matiz dele quase não aparece. Com menos de 3 cores nada sai; sobram sempre 2 ou mais."""
    if len(cores) < 3:
        return list(cores), []
    planos = {c: _ab(c) for c in cores}
    a = sum(pixels[c] * planos[c][0] for c in cores)
    b = sum(pixels[c] * planos[c][1] for c in cores)
    norma = math.hypot(a, b)
    if norma == 0:
        return list(cores), []
    a, b = a / norma, b / norma
    fora = []
    for cor in cores:
        ca, cb = planos[cor]
        de_lado = abs(ca * b - cb * a)  # croma vezes o seno da diferença de matiz
        if ca * a + cb * b < 0:  # matiz do lado oposto: todo o croma conta
            de_lado = math.hypot(ca, cb)
        if de_lado > DESVIO_DE_MATIZ:
            fora.append(cor)
    dentro = [c for c in cores if c not in fora]
    return (dentro, fora) if len(dentro) >= 2 else (list(cores), [])


def _janela(cores: Sequence[RGB], inicio: float, fim: float,
            pixels: dict[RGB, int] | None = None) -> tuple[tuple[RGB, ...], list[RGB]]:
    """(rampa, tons tirados). O trecho da família (já ordenada pelo valor) entre `inicio` e `fim` (0 a mais
    escura, 1 a mais clara), com pelo menos 2 cores, espaçado até `RAMPA_MAX`. Com `pixels`, sem o tom fora
    do matiz do trecho."""
    ultimo = len(cores) - 1
    baixo, alto = round(inicio * ultimo), round(fim * ultimo)
    while alto - baixo + 1 < min(2, len(cores)):
        if alto < ultimo:
            alto += 1
        else:
            baixo -= 1
    trecho, fora = list(cores[baixo:alto + 1]), []
    if pixels is not None:
        trecho, fora = _separar_fora_do_matiz(trecho, pixels)
    return _espacar(trecho, RAMPA_MAX), fora


def _rampas_por_papel(familias: dict[str, list[RGB]], dominante: str | None, pixels: dict[RGB, int],
                      chao: RGB | None = None) -> tuple[dict[str, tuple[RGB, ...]], list[RGB]]:
    """(rampa de cada papel, tons tirados por estarem fora do matiz).

    Cada família com 2 cores ou mais vai para os papéis dela. O par (folha e grama, tronco e terra) de
    família com `DIVIDIR_PAR` cores ou mais ganha duas rampas: folha e tronco no trecho mais escuro. A
    família dominante, quando há, vai também para os papéis que ficaram vazios, cada um no seu trecho de
    valor (`JANELAS`), e o tom fora do matiz sai papel a papel (o verde-água sai da pedra azul, mas fica
    no cristal). Se a cor do `chao` é da família que dá a terra, a rampa da terra fica centrada nela: o
    chão quase preto da cena noturna, e não o trecho do meio da família."""
    por_papel: dict[str, tuple[RGB, ...]] = {}
    tirados: list[RGB] = []

    def rampa(familia: str, papel: str, inicio: float, fim: float) -> None:
        filtro = pixels if familia == dominante and familia not in CINZAS else None
        if papel == "terra" and chao in familias[familia]:
            inicio, fim = _centrar(familias[familia], chao, fim - inicio)
        por_papel[papel], fora = _janela(familias[familia], inicio, fim, filtro)
        tirados.extend(fora)

    for familia, papeis in PAPEIS_DA_FAMILIA.items():
        if len(familias.get(familia, ())) < 2:
            continue
        dividir = len(familias[familia]) >= DIVIDIR_PAR
        for papel in papeis:
            rampa(familia, papel, *(JANELA_DO_PAR[papel] if dividir and papel in JANELA_DO_PAR else (0, 1)))
    if dominante:
        for papel in ORDEM:
            if papel not in por_papel:
                rampa(dominante, papel, *JANELAS[papel])
    return por_papel, tirados


def _familia_dominante(familias: dict[str, list[RGB]], total: int) -> str | None:
    """A família com `DOMINANTE` da paleta ou mais: referência quase toda de um matiz só."""
    nome, cores = max(familias.items(), key=lambda par: len(par[1]))
    return nome if len(cores) >= 3 and len(cores) >= DOMINANTE * total else None


def _agrupar(por_papel: dict[str, tuple[RGB, ...]]) -> list[Rampa]:
    """Papéis com a mesma rampa numa linha só, na ordem de `ORDEM`."""
    grupos: dict[tuple[RGB, ...], list[str]] = {}
    for papel in ORDEM:
        if papel in por_papel:
            grupos.setdefault(por_papel[papel], []).append(papel)
    return [Rampa(tuple(papeis), cores) for cores, papeis in grupos.items()]


def _percentil(contagem: Sequence[tuple[int, float]], p: float) -> float:
    """Percentil de valores com peso, na mesma regra do `revisar` (índice int(p * n))."""
    ordenados = sorted(contagem, key=lambda par: par[1])
    total = sum(n for n, _ in ordenados)
    alvo = min(total - 1, int(p * total))
    for n, valor in ordenados:
        if alvo < n:
            return valor
        alvo -= n
    return ordenados[-1][1]


def extrair_estilo(imagem: "str | Path | Image.Image", nome: str | None = None, *, base: "str | Path" = "snes-diurno",
                   cores: int = CORES) -> Referencia:
    """Lê a referência e monta o preset (sem gravar). Use `ref` para gravar.

    `nome`: nome do preset (padrão: o do arquivo, em minúsculas com hífens). `base`: preset ou JSON
    que dá o que a imagem não diz. `cores`: tamanho máximo da paleta, de 2 a 256.
    """
    arquivo = Path(imagem).name if isinstance(imagem, (str, Path)) else "imagem"
    nome = nome or sugerir_nome(Path(arquivo).stem)
    if not NOME_VALIDO.match(nome):
        raise ValueError(f"nome de preset deve ser minúsculo com hífens (ex.: floresta-nublada), veio {nome!r}")
    if not 2 <= cores <= 256:
        raise ValueError(f"cores deve ir de 2 a 256, veio {cores}")
    if Path(base).suffix != ".json":
        validar_nome_de_estilo(str(base), "base")  # a mesma mensagem do gerar e do revisar
    dados_do_estilo(base)  # base que não existe falha antes de ler a imagem

    original = limpar_alfa(abrir(imagem))
    escala = escala_inteira(original)
    alvo = reduzir(original, escala)
    contagem = _contar(alvo)
    if not contagem:
        raise ValueError(f"{arquivo} não tem nenhum pixel visível")
    na_imagem = len(contagem)
    avisos = []
    if na_imagem > CORES_PIXEL_ART:
        aviso = f"{na_imagem} cores, não parece pixel art (foto ou anti-aliasing)"
        if max(alvo.size) > LADO_MAX:
            fator = -(-max(alvo.size) // LADO_MAX)
            alvo = limpar_alfa(alvo.reduce(fator))
            aviso += f"; reduzida para {alvo.width}x{alvo.height} pela média"
        contagem = _quantizar(alvo, cores)
        avisos.append(f"{aviso}; quantizada para {len(contagem)} cores. Confira as rampas antes de usar")
    elif na_imagem > cores:
        contagem = _quantizar(alvo, cores)
        avisos.append(f"{na_imagem} cores na referência; paleta reduzida para {len(contagem)} (cores sobe o limite)")

    paleta = sorted((c for _, c in contagem), key=lambda c: (luminancia(c), c))
    valores = [(n, luminancia(c)) for n, c in contagem]

    familias: dict[str, list[RGB]] = {}
    for cor in paleta:
        familias.setdefault(_familia(cor), []).append(cor)
    pixels = {c: n for n, c in contagem}
    dominante = _familia_dominante(familias, len(paleta))
    fora_do_matiz = []
    for nome_da_familia, cores_da_familia in familias.items():
        if nome_da_familia not in CINZAS and nome_da_familia != dominante:  # a dominante se filtra em cada papel
            familias[nome_da_familia], longe = _separar_fora_do_matiz(cores_da_familia, pixels)
            fora_do_matiz.extend(longe)
    por_papel, tirados = _rampas_por_papel(familias, dominante, pixels, _chao(alvo, paleta))
    usadas = {c for r in por_papel.values() for c in r}
    fora_do_matiz.extend(sem_repetir(c for c in tirados if c not in usadas))
    proprios = {p for f, papeis in PAPEIS_DA_FAMILIA.items() if len(familias.get(f, ())) >= 2 for p in papeis}
    repartidos = [p for p in ORDEM if p not in proprios] if dominante else []
    rampas = _agrupar(por_papel)

    luz, contorno = paleta[-1], paleta[0]
    estilo: dict[str, Any] = {
        "base": str(base),
        "nome": nome,
        "descricao": f"Tirado de {arquivo}: {len(paleta)} cores, pixel {escala}x.",
        "paleta": [rgb_para_hex(c) for c in paleta],
        "luz": rgb_para_hex(luz),
        "contorno_cor": rgb_para_hex(contorno),
        "rampas": {p: [rgb_para_hex(c) for c in por_papel[p]] for p in ORDEM if p in por_papel},
    }
    atmosfera = None
    ceu = _espacar(_ceu(alvo, paleta), RAMPA_MAX)
    if len(ceu) >= 2:
        atmosfera = ceu[-1]
        estilo["ceu"] = [rgb_para_hex(c) for c in ceu]
        estilo["atmosfera"] = rgb_para_hex(atmosfera)
        rampas.append(Rampa(("ceu",), ceu))
    faixa = _percentil(valores, 0.95) - _percentil(valores, 0.05)
    valor = (min(v for _, v in valores), max(v for _, v in valores))
    estilo["referencia"] = {
        "arquivo": arquivo, "base": str(base), "tamanho_real": list(alvo.size), "pixel": escala,
        "cores_na_imagem": na_imagem, "valor": [round(valor[0], 3), round(valor[1], 3)], "faixa_valor": round(faixa, 3),
    }
    da_base = [p for p in ORDEM if p not in estilo["rampas"]] + ([] if atmosfera else ["ceu", "atmosfera"])
    return Referencia(nome=nome, arquivo=arquivo, tamanho_original=original.size, escala=escala, tamanho=alvo.size,
                      cores_na_imagem=na_imagem, paleta=paleta, rampas=rampas, da_base=da_base, luz=luz,
                      contorno=contorno, atmosfera=atmosfera, valor=valor, faixa=faixa, base=str(base),
                      estilo=estilo, avisos=avisos, fora_do_matiz=sorted(fora_do_matiz, key=luminancia),
                      dominante=(dominante, len(familias[dominante]), repartidos) if repartidos else None)


def ref(imagem: "str | Path | Image.Image", nome: str | None = None, *, base: "str | Path" = "snes-diurno",
        cores: int = CORES, sobrescrever: bool = False) -> Referencia:
    """Tira o estilo da referência e grava como preset do usuário (como `registrar_estilo`).

    Devolve a `Referencia` com `destino` preenchido; `resumo()` dá o texto para o agente.
    Nome inválido, reservado ou já usado (sem `sobrescrever`) levanta `ValueError`.
    """
    referencia = extrair_estilo(imagem, nome, base=base, cores=cores)
    referencia.destino = registrar_estilo(referencia.estilo, referencia.nome, sobrescrever=sobrescrever)
    return referencia
