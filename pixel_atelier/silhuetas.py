"""Silhuetas tiradas só do composto, para o `revisar` medir contraste e forma sem as camadas.

Numa cena sem a pasta de camadas (o `gerar` com `"saida": "composto"`, ou uma imagem de fora), não
dá para saber o que está na frente de quê. Mas cada silhueta pinta com a rampa dela: as cores de
uma rampa se tocam o tempo todo (faixas de luz e sombra, pontilhado entre dois tons), e as cores
de duas silhuetas só se tocam na beira. Então:

1. duas cores ficam na mesma família quando cada uma tem pelo menos `LIGA` da própria borda
   encostada na outra e elas não são distantes demais (`LIGA_DISTANCIA` em RGB);
2. silhueta é um pedaço contínuo (4 vizinhos) de uma família, com pelo menos `SILHUETA_MIN` pixels;
3. furo de 1 pixel (pontilhado de outra família por cima) é fechado antes de medir a borda.

Isso separa material de material (céu, nuvem, mata, tronco, chão). Duas camadas pintadas com
cores quase iguais viram uma silhueta só, então o que falta em contraste ali não aparece: a
separação erra para o lado de não acusar. Por isso tudo que sai daqui é heurística, e só serve
para valor (contraste e legibilidade): a forma de cada silhueta se corta na que está na frente e
na troca de material, então pillow shading e serrilhado continuam pedindo as camadas.
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass

from PIL import Image, ImageChops

from .cor import distancia2
from .imagem import vizinho

LIGA = 0.15  # fração da borda de cada cor encostada na outra para as duas serem da mesma família
LIGA_DISTANCIA = 80  # distância RGB acima disso não liga: verde da mata e azul do céu nunca juntam
SILHUETA_MIN = 32  # pixels; menos que isso é detalhe (estrela, pedrinha, ponto de pontilhado)


@dataclass
class Silhueta:
    imagem: Image.Image  # RGBA do tamanho do composto, só com os pixels da silhueta (furos fechados)
    pixels: int
    caixa: tuple[int, int, int, int]


def familias(imagem: Image.Image) -> tuple[list[int], dict[int, int]]:
    """Cada pixel como número (os 4 bytes RGBA) e a família de cada cor."""
    largura, altura = imagem.size
    cores = memoryview(imagem.tobytes()).cast("I").tolist()
    toques: Counter[tuple[int, int]] = Counter()
    for y in range(altura):
        linha = cores[y * largura:(y + 1) * largura]
        for a, b in zip(linha, linha[1:]):
            if a != b:
                toques[(a, b) if a < b else (b, a)] += 1
        if y + 1 < altura:
            for a, b in zip(linha, cores[(y + 1) * largura:(y + 2) * largura]):
                if a != b:
                    toques[(a, b) if a < b else (b, a)] += 1
    borda: Counter[int] = Counter()
    for (a, b), n in toques.items():
        borda[a] += n
        borda[b] += n
    pai = {c: c for c in set(cores)}

    def raiz(c: int) -> int:
        while pai[c] != c:
            pai[c] = pai[pai[c]]
            c = pai[c]
        return c

    limite = LIGA_DISTANCIA ** 2
    for (a, b), n in sorted(toques.items()):
        if n >= LIGA * borda[a] and n >= LIGA * borda[b] and distancia2(_rgb(a), _rgb(b)) <= limite:
            pai[raiz(a)] = raiz(b)
    return cores, {c: raiz(c) for c in pai}


def separar(imagem: Image.Image) -> list[Silhueta]:
    """As silhuetas do composto, maiores primeiro."""
    largura, altura = imagem.size
    cores, familia = familias(imagem)
    rotulo = [familia[c] for c in cores]
    visto = bytearray(largura * altura)
    pedacos: list[list[int]] = []
    for inicio in range(largura * altura):
        if visto[inicio]:
            continue
        visto[inicio] = 1
        f = rotulo[inicio]
        pilha, pedaco = [inicio], []
        while pilha:
            i = pilha.pop()
            pedaco.append(i)
            x = i % largura
            for j, dentro in ((i - 1, x > 0), (i + 1, x + 1 < largura), (i - largura, i >= largura),
                              (i + largura, i + largura < largura * altura)):
                if dentro and not visto[j] and rotulo[j] == f:
                    visto[j] = 1
                    pilha.append(j)
        if len(pedaco) >= SILHUETA_MIN:
            pedacos.append(pedaco)
    pedacos.sort(key=len, reverse=True)
    silhuetas = []
    for pedaco in pedacos:
        mascara = bytearray(largura * altura)
        for i in pedaco:
            mascara[i] = 255
        m = _fechar_furos(Image.frombytes("L", (largura, altura), bytes(mascara)))
        recorte = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
        recorte.paste(imagem, mask=m)
        silhuetas.append(Silhueta(recorte, len(pedaco), m.getbbox() or (0, 0, 0, 0)))
    return silhuetas


def _fechar_furos(mascara: Image.Image) -> Image.Image:
    """Fecha o pixel vazio com os 4 vizinhos cheios (ponto de pontilhado de outra família por cima)."""
    cercado = mascara.point(lambda v: 255 - v)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cercado = ImageChops.multiply(cercado, vizinho(mascara, dx, dy))
    return ImageChops.lighter(mascara, cercado)


def _rgb(c: int) -> bytes:
    return c.to_bytes(4, sys.byteorder)[:3]
