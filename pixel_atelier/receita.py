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
      "camadas": [                     # do fundo para a frente
        {"forma": "ceu", "astro": "sol"},
        {"forma": "arvore", "nome": "mata-longe", "seed": 4, "profundidade": 0.6, "tipo": "pinheiro"}
      ]
    }

Cada camada tem `forma` (obrigatório), `nome` (opcional, entra no nome do arquivo) e os parâmetros
da forma (`python -m pixel_atelier formas` lista todos, com o padrão). `seed`, `profundidade`,
`laco` e `deslocamento` valem em qualquer forma. Sem `seed`, a camada usa uma seed derivada da
seed da receita e da posição dela; com `seed`, fica fixa mesmo quando a receita muda de seed.

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

CAMPOS = ("cena", "descricao", "tamanho", "estilo", "laco", "seed", "ampliar", "saida", "camadas")
SAIDAS = ("tudo", "composto", "camadas")
COMUNS = ("seed", "laco", "deslocamento")  # parâmetros que toda forma aceita e a receita resolve
TAMANHO_MAXIMO = 4096
SEED_DERIVADA = 100_000  # seeds derivadas ficam curtas, fáceis de copiar para fixar uma camada
AMPLIAR_MAXIMO = 16
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

    @property
    def arquivo(self) -> str:
        return f"{self.indice + 1:02d}-{self.nome}.png"


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
    original: dict[str, Any] = field(default_factory=dict, repr=False)


# --- parâmetros das formas ----------------------------------------------------------------------

def parametros_da_forma(forma: str) -> dict[str, inspect.Parameter]:
    """Parâmetros que a receita pode passar para a forma (tudo depois de estilo, largura e altura)."""
    return dict(list(inspect.signature(FORMAS[forma]).parameters.items())[3:])


def descrever_formas() -> str:
    """Uma linha por forma com os parâmetros e o padrão de cada um. Serve de cola para escrever receitas."""
    linhas = ["todas: seed (padrão: derivada da seed da receita), laco (padrão: o da receita), deslocamento=0"]
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
    if r["saida"] not in SAIDAS:
        erros.append(f"saida deve ser um de {', '.join(SAIDAS)}, veio {r['saida']!r}")
    if not isinstance(r.get("descricao", ""), str):
        erros.append("descricao deve ser texto")

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
                   original=dados)


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
    for campo, valor in item.items():
        if campo in ("forma", "nome"):
            continue
        if campo not in aceitos:
            erros.append(f"{onde}: " + _desconhecido(campo, forma, [*aceitos, "nome"]))
        elif problema := _conferir_valor(forma, campo, aceitos[campo], valor):
            erros.append(f"{onde}: {problema}")
        else:
            parametros[campo] = valor
    # com qualquer erro a receita inteira é recusada, então a camada pode voltar mesmo incompleta
    return Camada(indice=i, forma=forma, nome=nome, parametros=parametros)
