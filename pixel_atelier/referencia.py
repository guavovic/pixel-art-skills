"""`ref`: tira o estilo de uma imagem de referência e guarda como preset.

    from pixel_atelier import ref

    print(ref("referencias/floresta.png", "floresta").resumo())   # grava o preset "floresta"

A referência é vista uma vez: depois a receita usa só o preset (`"estilo": "floresta"`), e o
agente lê o resumo em texto no lugar da imagem. Tudo é determinístico e só usa Pillow.

O que sai da imagem:
- tamanho do pixel: imagem ampliada (blocos NxN) volta para o tamanho real (`imagem.escala_inteira`).
- paleta: as cores visíveis, exatas quando são até `cores` (padrão 32). Acima disso a imagem é
  quantizada pelo corte de mediana do Pillow, com aviso. Com mais de 256 cores ela não parece
  pixel art (foto, anti-aliasing): se passar de `LADO_MAX` por lado, antes é reduzida pela média
  de blocos.
- rampas: cada cor cai numa família pelo matiz (HSV) ou fica neutra (saturação abaixo de 0,2 ou
  quase preta); a neutra se divide em escura e clara (valor 0,7). Família com 2 cores ou mais vira
  rampa, do escuro ao claro (até `RAMPA_MAX` cores, espaçadas pelo valor), e vai para os papéis:
  verde → folha e grama; quente (vermelho, laranja, marrom) → terra e tronco; neutra escura →
  pedra; neutra clara → nuvem, névoa e neve; roxo → cristal. Azul fica só na paleta.
- céu: em imagem opaca, a cor mais comum de cada linha do terço de cima, de cima para baixo (do
  topo ao horizonte, até `RAMPA_MAX` cores). A última, a do horizonte, vira a atmosfera. Sprite
  (com transparência) não tem céu.
- luz: a cor mais clara da paleta; contorno: a mais escura.
- contraste: faixa de valor dos pixels (percentil 5 a 95, como no `revisar`) e o passo médio de
  valor em cada rampa. Fica no bloco `referencia` do preset, só para consulta (o estilo ignora).

O que a imagem não diz (sombreamento, contorno ligado ou não, direção da luz, largura das faixas,
forças de atmosfera e luz, papel sem família) vem do estilo `base` (padrão `snes-diurno`). Como o
preset fecha a `paleta` com as cores da referência, até o que vem do base é pintado só com elas.
O preset é gravado como o `registrar_estilo` grava: na pasta de presets do usuário, com a base já
aplicada.
"""
from __future__ import annotations

import colorsys
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

# família: (início, fim) do matiz em graus; o resto (330 a 50, dando a volta no 0) é "quente"
FAMILIAS = {"verde": (50, 170), "azul": (170, 260), "roxo": (260, 330)}
PAPEIS_DA_FAMILIA = {
    "verde": ("folha", "grama"),
    "quente": ("terra", "tronco"),
    "neutra": ("pedra",),
    "clara": ("nuvem", "nevoa", "neve"),
    "roxo": ("cristal",),
}
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
    """Corte de mediana do Pillow, só com os pixels visíveis. Devolve (quantos pixels, cor)."""
    if imagem.getchannel("A").getextrema()[0] == 255:
        rgb = imagem.convert("RGB")
    else:
        visiveis = [p[:3] for p in imagem.getdata() if p[3] > 0]
        rgb = Image.new("RGB", (len(visiveis), 1))
        rgb.putdata(visiveis)
    q = rgb.quantize(colors=cores, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    paleta = q.getpalette()
    contagem: dict[RGB, int] = {}
    for n, i in q.getcolors(maxcolors=256) or []:
        cor = tuple(paleta[i * 3:i * 3 + 3])
        contagem[cor] = contagem.get(cor, 0) + n  # type: ignore[index]
    return [(n, c) for c, n in contagem.items()]


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


def _espacar(cores: Sequence[RGB], quantas: int) -> tuple[RGB, ...]:
    """Até `quantas` cores, espaçadas pela posição na lista (já ordenada pelo valor)."""
    if len(cores) <= quantas:
        return tuple(cores)
    return tuple(cores[round(i * (len(cores) - 1) / (quantas - 1))] for i in range(quantas))


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
    rampas = [Rampa(papeis, _espacar(familias[f], RAMPA_MAX))
              for f, papeis in PAPEIS_DA_FAMILIA.items() if len(familias.get(f, ())) >= 2]
    rampas.sort(key=lambda r: ORDEM.index(r.papeis[0]))

    luz, contorno = paleta[-1], paleta[0]
    estilo: dict[str, Any] = {
        "base": str(base),
        "nome": nome,
        "descricao": f"Tirado de {arquivo}: {len(paleta)} cores, pixel {escala}x.",
        "paleta": [rgb_para_hex(c) for c in paleta],
        "luz": rgb_para_hex(luz),
        "contorno_cor": rgb_para_hex(contorno),
        "rampas": {p: [rgb_para_hex(c) for c in r.cores] for r in rampas for p in r.papeis},
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
                      estilo=estilo, avisos=avisos)


def ref(imagem: "str | Path | Image.Image", nome: str | None = None, *, base: "str | Path" = "snes-diurno",
        cores: int = CORES, sobrescrever: bool = False) -> Referencia:
    """Tira o estilo da referência e grava como preset do usuário (como `registrar_estilo`).

    Devolve a `Referencia` com `destino` preenchido; `resumo()` dá o texto para o agente.
    Nome inválido, reservado ou já usado (sem `sobrescrever`) levanta `ValueError`.
    """
    referencia = extrair_estilo(imagem, nome, base=base, cores=cores)
    referencia.destino = registrar_estilo(referencia.estilo, referencia.nome, sobrescrever=sobrescrever)
    return referencia
