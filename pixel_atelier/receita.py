"""Receita: a cena inteira descrita em JSON curto, validada antes de desenhar.

Formato (só `camadas` é obrigatório; o resto tem padrão):

    {
      "cena": "floresta",              # nome dos arquivos de saída (minúsculo, hífen ou sublinhado)
      "descricao": "texto livre",
      "tamanho": [320, 180],           # largura e altura reais, em pixels
      "estilo": "snes-diurno",         # nome de preset, caminho de JSON ou dicionário de estilo;
                                       # {"base": "snes-diurno", "contorno": true} parte do preset
      "laco": true,                    # laço horizontal sem emenda (largura múltipla de 8)
      "seed": 0,                       # sorteia as camadas que não fixam a própria seed
      "ampliar": 1,                    # grava também o composto ampliado N vezes, para olhar
      "saida": "tudo",                 # "tudo", "composto" ou "camadas"
      "animacao": {"quadros": 96, "duracao": 100, "voltas": 4},  # opcional: GIF, folha e JSON de tempo
      "camadas": [                     # do fundo para a frente
        {"forma": "ceu", "astro": "sol"},
        {"forma": "arvore", "nome": "mata-longe", "seed": 4, "profundidade": 0.6, "tipo": "pinheiro"}
      ]
    }

Cada camada tem `forma` (obrigatório), `nome` (opcional, entra no nome do arquivo) e os parâmetros
da forma (`python -m pixel_atelier formas` lista todos, com o padrão). `seed`, `profundidade`,
`laco` e `deslocamento` valem em qualquer forma. Sem `seed`, a camada usa uma seed derivada da
seed da receita e da posição dela; com `seed`, fica fixa mesmo quando a receita muda de seed.
Com `animacao`, `voltas` (opcional) fixa as voltas da camada no laço no lugar da profundidade.

Erros saem todos de uma vez, em texto, num `ErroDeReceita`.
"""
from __future__ import annotations

import difflib
import inspect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .estilo import Estilo, carregar_estilo, PAPEIS
from .formas import FORMAS
from .formas._base import semente
from .formas.arvore import TIPOS as TIPOS_ARVORE
from .formas.ceu import ASTROS
from .formas.nuvem import TIPOS as TIPOS_NUVEM
from .formas.terreno import SUPERFICIES

CAMPOS = ("cena", "descricao", "tamanho", "estilo", "laco", "seed", "ampliar", "saida", "animacao", "camadas")
SAIDAS = ("tudo", "composto", "camadas")
COMUNS = ("seed", "laco", "deslocamento")  # parâmetros que toda forma aceita e a receita resolve
TAMANHO_MAXIMO = 4096
SEED_DERIVADA = 100_000  # seeds derivadas ficam curtas, fáceis de copiar para fixar uma camada
AMPLIAR_MAXIMO = 16
AMPLIADO_MAXIMO = 4096  # lado máximo do composto depois de `ampliar`, para não estourar a memória
ANIMACAO_PADRAO = {"quadros": 96, "duracao": 100, "voltas": 4}
QUADROS_POR_VOLTA = 24  # sem `voltas`, 1 volta a cada 24 quadros (até 4): a camada mais perto anda 1/24 da largura por quadro
QUADROS_MAXIMO = 256
PIXELS_DA_ANIMACAO = 96 * 1280 * 720  # quadros vezes área: 96 quadros cabem até 1280x720 sem estourar a memória
DURACAO_MAXIMA = 2000  # ms por quadro; o GIF guarda o tempo em centésimos, então a duração anda de 10 em 10
VOLTAS_MAXIMO = 16
NOME_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PADRAO = {"cena": "cena", "tamanho": [320, 180], "estilo": "snes-diurno", "laco": True, "seed": 0,
          "ampliar": 1, "saida": "tudo"}

# valores aceitos nos parâmetros de texto
OPCOES: dict[tuple[str, str], tuple] = {
    ("arvore", "tipo"): TIPOS_ARVORE,
    ("ceu", "astro"): ASTROS,
    ("nuvem", "tipo"): TIPOS_NUVEM,
    ("terreno", "superficie"): SUPERFICIES,
    ("terreno", "papel"): PAPEIS,
    ("nevoa", "papel"): PAPEIS,
}


class ErroDeReceita(ValueError):
    """Receita inválida. `erros` tem uma mensagem por problema; `str()` junta todas."""

    def __init__(self, erros: list[str]):
        self.erros = list(erros)
        super().__init__("receita inválida:\n" + "\n".join(f"- {e}" for e in self.erros))


@dataclass
class Camada:
    indice: int
    forma: str
    nome: str
    parametros: dict[str, Any]  # já com seed, profundidade, laco e deslocamento resolvidos
    voltas: int | None = None  # voltas próprias no laço da animação; None segue a profundidade

    @property
    def arquivo(self) -> str:
        return f"{self.indice + 1:02d}-{self.nome}.png"


@dataclass
class Animacao:
    quadros: int
    duracao: int  # ms por quadro
    voltas: int  # voltas da camada mais perto (profundidade 0) no laço inteiro


@dataclass
class Receita:
    cena: str
    largura: int
    altura: int
    estilo: Estilo
    laco: bool
    seed: int
    ampliar: int
    saida: str
    camadas: list[Camada]
    descricao: str = ""
    animacao: Animacao | None = None
    original: dict[str, Any] = field(default_factory=dict, repr=False)


# --- parâmetros das formas ----------------------------------------------------------------------

def parametros_da_forma(forma: str) -> dict[str, inspect.Parameter]:
    """Parâmetros que a receita pode passar para a forma (tudo depois de estilo, largura e altura)."""
    return dict(list(inspect.signature(FORMAS[forma]).parameters.items())[3:])


def descrever_campos() -> str:
    """Linha com os campos do topo da receita e o padrão de cada um."""
    partes = [f"{campo}={json.dumps(valor, ensure_ascii=False)}" for campo, valor in PADRAO.items()]
    partes[list(PADRAO).index("saida")] += " (" + "|".join(json.dumps(s) for s in SAIDAS) + ")"
    animacao = json.dumps(ANIMACAO_PADRAO)
    return ("receita: " + ", ".join(partes) + ", descricao (texto livre), "
            f"animacao={animacao} (opcional: grava GIF, folha de quadros e JSON de tempo), "
            'camadas=[{"forma": ..., "nome": ..., parâmetros}] (obrigatório, do fundo para a frente)')


def descrever_formas() -> str:
    """Campos da receita e uma linha por forma com os parâmetros e o padrão. Serve de cola para escrever receitas."""
    linhas = [descrever_campos(),
              "todas: seed (padrão: derivada da seed da receita), laco (padrão: o da receita), deslocamento=0, "
              "voltas (com animacao; padrão: pela profundidade)"]
    for forma in FORMAS:
        partes = []
        for nome, p in parametros_da_forma(forma).items():
            if nome in COMUNS:
                continue
            padrao = list(p.default) if isinstance(p.default, tuple) else p.default
            texto = f"{nome}={json.dumps(padrao, ensure_ascii=False)}"
            if (forma, nome) in OPCOES:
                texto += " (" + "|".join(json.dumps(o) for o in OPCOES[(forma, nome)]) + ")"
            partes.append(texto)
        linhas.append(f"{forma}: " + ", ".join(partes))
    return "\n".join(linhas)


def _numero(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _conferir_valor(forma: str, nome: str, p: inspect.Parameter, valor: Any) -> str | None:
    """Mensagem de erro se `valor` não serve para o parâmetro, ou None."""
    tipos = {t.strip() for t in str(p.annotation).split("|")}
    if valor is None and "None" in tipos:
        return None
    if "bool" in tipos and isinstance(valor, bool):
        return None
    if "int" in tipos and isinstance(valor, int) and not isinstance(valor, bool):
        return None
    if "float" in tipos and _numero(valor):
        return None
    if tipos & {"list", "tuple"} and isinstance(valor, (list, tuple)) and len(valor) == 2 and all(map(_numero, valor)):
        return None
    if "str" in tipos and isinstance(valor, str):
        opcoes = OPCOES.get((forma, nome))
        if opcoes is None or valor in opcoes:
            return None
        return f"{nome} deve ser um de {', '.join(json.dumps(o) for o in opcoes)}, veio {json.dumps(valor)}"
    esperado = {
        "bool": "true ou false", "int": "número inteiro", "float": "número", "str": "texto", "None": "null",
        "list": "[mínimo, máximo]", "tuple": "[mínimo, máximo]",
    }
    descricao = " ou ".join(dict.fromkeys(esperado[t] for t in sorted(tipos) if t in esperado))
    return f"{nome} deve ser {descricao}, veio {json.dumps(valor, ensure_ascii=False)}"


def _desconhecido(campo: str, onde: str, validos) -> str:
    texto = f"campo {campo!r} não existe em {onde}"
    parecido = difflib.get_close_matches(campo, list(validos), n=1)
    if parecido:
        texto += f"; quis dizer {parecido[0]!r}?"
    return texto


# --- leitura e validação ------------------------------------------------------------------------

def ler_receita(fonte: "str | Path | dict[str, Any]") -> dict[str, Any]:
    """Dicionário da receita a partir de um dicionário, de texto JSON ou do caminho de um arquivo."""
    if isinstance(fonte, dict):
        return fonte
    texto = str(fonte)
    if isinstance(fonte, str) and texto.lstrip().startswith("{"):
        origem = "receita"
    else:
        caminho = Path(fonte)
        if not caminho.is_file():
            raise ErroDeReceita([f"arquivo {texto!r} não existe"])
        texto, origem = caminho.read_text(encoding="utf-8"), caminho.name
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise ErroDeReceita([f"{origem}: JSON inválido na linha {erro.lineno}, coluna {erro.colno}: {erro.msg}"]) from None
    if not isinstance(dados, dict):
        raise ErroDeReceita(["a receita deve ser um objeto JSON ({...})"])
    return dados


def validar_receita(fonte: "str | Path | dict[str, Any]") -> Receita:
    """Lê, confere e completa a receita com os padrões. Junta todos os problemas num só `ErroDeReceita`."""
    dados = ler_receita(fonte)
    erros: list[str] = []
    for campo in dados:
        if campo not in CAMPOS:
            erros.append(_desconhecido(campo, "receita", CAMPOS))
    r = {**PADRAO, **dados}

    cena = r["cena"]
    if not isinstance(cena, str) or not NOME_VALIDO.match(cena):
        erros.append(f"cena deve ser texto minúsculo com hífen ou sublinhado (vira nome de arquivo), veio {cena!r}")

    largura = altura = 0
    tamanho = r["tamanho"]
    if (isinstance(tamanho, (list, tuple)) and len(tamanho) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 < v <= TAMANHO_MAXIMO for v in tamanho)):
        largura, altura = tamanho
    else:
        erros.append(f"tamanho deve ser [largura, altura] com inteiros de 1 a {TAMANHO_MAXIMO}, veio {tamanho!r}")

    estilo = None
    try:
        estilo = carregar_estilo(r["estilo"])
    except (KeyError, ValueError, TypeError) as erro:
        erros.append(f"estilo: {erro.args[0] if erro.args else erro}")

    for campo, tipo, nome_tipo in (("laco", bool, "true ou false"), ("seed", int, "número inteiro")):
        if not isinstance(r[campo], tipo) or (tipo is int and isinstance(r[campo], bool)):
            erros.append(f"{campo} deve ser {nome_tipo}, veio {r[campo]!r}")
    ampliar = r["ampliar"]
    if not isinstance(ampliar, int) or isinstance(ampliar, bool) or not 1 <= ampliar <= AMPLIAR_MAXIMO:
        erros.append(f"ampliar deve ser inteiro de 1 a {AMPLIAR_MAXIMO}, veio {ampliar!r}")
    elif largura and max(largura, altura) * ampliar > AMPLIADO_MAXIMO:
        erros.append(f"a imagem ampliada ficaria com {largura * ampliar}x{altura * ampliar} pixels e o máximo é "
                     f"{AMPLIADO_MAXIMO} por lado; reduza ampliar ou tamanho")
    if r["saida"] not in SAIDAS:
        erros.append(f"saida deve ser um de {', '.join(SAIDAS)}, veio {r['saida']!r}")
    if not isinstance(r.get("descricao", ""), str):
        erros.append("descricao deve ser texto")

    animacao = _validar_animacao(dados.get("animacao"), largura, altura, erros) if "animacao" in dados else None

    camadas: list[Camada] = []
    lista = dados.get("camadas")
    if not isinstance(lista, list) or not lista:
        erros.append('a receita precisa de "camadas": uma lista com pelo menos uma camada, do fundo para a frente')
        lista = []
    seed_receita = r["seed"] if isinstance(r["seed"], int) else 0
    for i, item in enumerate(lista):
        if camada := _validar_camada(i, item, r, seed_receita, erros):
            camadas.append(camada)
    com_laco = [str(i + 1) for i, item in enumerate(lista) if isinstance(item, dict) and item.get("laco", r["laco"]) is True]
    if com_laco and largura % 8:
        abaixo = largura // 8 * 8
        sugestao = f"{abaixo} ou {abaixo + 8}" if abaixo else str(abaixo + 8)
        erros.append(f"com laço a largura precisa ser múltipla de 8, veio {largura} (camadas com laço: "
                     f"{', '.join(com_laco)}); use {sugestao}, ou \"laco\": false")

    if erros:
        raise ErroDeReceita(erros)
    return Receita(cena=cena, largura=largura, altura=altura, estilo=estilo, laco=r["laco"], seed=r["seed"],
                   ampliar=ampliar, saida=r["saida"], camadas=camadas, descricao=r.get("descricao", ""),
                   animacao=animacao, original=dados)


def colunas_da_folha(quadros: int, largura: int) -> int:
    """Quadros por linha da folha: o máximo que cabe em `AMPLIADO_MAXIMO` de largura."""
    return max(1, min(quadros, AMPLIADO_MAXIMO // max(1, largura)))


def quadros_por_folha(quadros: int, largura: int, altura: int) -> int:
    """Quadros numa página da folha de até `AMPLIADO_MAXIMO` por lado; o resto vai para as páginas seguintes."""
    colunas = colunas_da_folha(quadros, largura)
    return min(quadros, colunas * max(1, AMPLIADO_MAXIMO // max(1, altura)))


def _quadros_que_cabem(largura: int, altura: int) -> int:
    return max(2, min(QUADROS_MAXIMO, PIXELS_DA_ANIMACAO // max(1, largura * altura)))


def _quadros_padrao(largura: int, altura: int) -> int:
    """96 quadros, ou os que couberem em `PIXELS_DA_ANIMACAO`."""
    if not largura:
        return ANIMACAO_PADRAO["quadros"]
    return min(ANIMACAO_PADRAO["quadros"], _quadros_que_cabem(largura, altura))


def _inteiro_entre(v: Any, minimo: int, maximo: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and minimo <= v <= maximo


def _validar_animacao(valor: Any, largura: int, altura: int, erros: list[str]) -> Animacao | None:
    if not isinstance(valor, dict):
        erros.append(f"animacao deve ser um objeto como {json.dumps(ANIMACAO_PADRAO)}, veio {valor!r}")
        return None
    for campo in valor:
        if campo not in ANIMACAO_PADRAO:
            erros.append(_desconhecido(campo, "animacao", ANIMACAO_PADRAO))
    a = {**ANIMACAO_PADRAO, "quadros": _quadros_padrao(largura, altura), **valor}
    quadros_valido = _inteiro_entre(a["quadros"], 2, QUADROS_MAXIMO)
    if "voltas" not in valor and quadros_valido:
        a["voltas"] = min(ANIMACAO_PADRAO["voltas"], max(1, a["quadros"] // QUADROS_POR_VOLTA))
    limites = {"quadros": (2, QUADROS_MAXIMO), "duracao": (10, DURACAO_MAXIMA), "voltas": (0, VOLTAS_MAXIMO)}
    validos = True
    for campo, (minimo, maximo) in limites.items():
        v = a[campo]
        if not _inteiro_entre(v, minimo, maximo):
            erros.append(f"animacao.{campo} deve ser inteiro de {minimo} a {maximo}, veio {v!r}")
            validos = False
    if not validos:
        return None
    if a["duracao"] % 10:
        erros.append(f"animacao.duracao anda de 10 em 10 ms (o GIF guarda centésimos), veio {a['duracao']}; "
                     f"use {a['duracao'] // 10 * 10 or 10} ou {a['duracao'] // 10 * 10 + 10}")
    if largura and a["quadros"] > _quadros_que_cabem(largura, altura):
        erros.append(f"{a['quadros']} quadros de {largura}x{altura} passam do limite de memória da animação "
                     f"({_quadros_que_cabem(largura, altura)} quadros nesse tamanho); reduza animacao.quadros ou tamanho")
    return Animacao(quadros=a["quadros"], duracao=a["duracao"], voltas=a["voltas"])


def _validar_camada(i: int, item: Any, r: dict[str, Any], seed_receita: int, erros: list[str]) -> Camada | None:
    onde = f"camada {i + 1}"
    if not isinstance(item, dict):
        erros.append(f"{onde}: deve ser um objeto com \"forma\" e os parâmetros")
        return None
    forma = item.get("forma")
    if not isinstance(forma, str) or forma not in FORMAS:
        texto = f"{onde}: forma {forma!r} não existe; as que existem: {', '.join(FORMAS)}"
        parecido = difflib.get_close_matches(str(forma), list(FORMAS), n=1)
        erros.append(texto + (f"; quis dizer {parecido[0]!r}?" if parecido else ""))
        return None
    onde = f"camada {i + 1} ({forma})"
    aceitos = parametros_da_forma(forma)
    nome = item.get("nome", forma)
    if not isinstance(nome, str) or not NOME_VALIDO.match(nome):
        erros.append(f"{onde}: nome deve ser texto minúsculo com hífen ou sublinhado, veio {nome!r}")

    parametros: dict[str, Any] = {"seed": semente(seed_receita, i + 1) % SEED_DERIVADA, "laco": r["laco"]}
    voltas = item.get("voltas")
    if "voltas" in item and not _inteiro_entre(voltas, 0, VOLTAS_MAXIMO):
        erros.append(f"{onde}: voltas deve ser inteiro de 0 a {VOLTAS_MAXIMO}, veio {json.dumps(voltas)}")
        voltas = None
    sem_laco = not item.get("laco", r["laco"])
    if voltas and sem_laco:
        erros.append(f"{onde}: voltas {voltas} pede laço (sem laço a borda abriria um buraco ao andar); "
                     "tire voltas ou use \"laco\": true")
    for campo, valor in item.items():
        if campo in ("forma", "nome", "voltas"):
            continue
        if campo not in aceitos:
            erros.append(f"{onde}: " + _desconhecido(campo, forma, [*aceitos, "nome"]))
        elif problema := _conferir_valor(forma, campo, aceitos[campo], valor):
            erros.append(f"{onde}: {problema}")
        else:
            parametros[campo] = valor
    # com qualquer erro a receita inteira é recusada, então a camada pode voltar mesmo incompleta
    return Camada(indice=i, forma=forma, nome=nome, parametros=parametros, voltas=voltas)
