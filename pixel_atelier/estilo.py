"""Estilo: paleta, rampas por papel e o jeito de sombrear. É o que muda de um visual para outro.

Um estilo é só dado (um dicionário ou um JSON em `pixel_atelier/estilos/`). As formas pedem cores
por papel (`folha`, `pedra`, `terra`...) e por profundidade, e o estilo responde com cores da
paleta dele. Trocar de estilo não muda nenhuma forma.

Formato do dicionário (sem `base`, só `nome`, `ceu`, `atmosfera`, `luz` e `rampas` são obrigatórios):

    {
      "base": "snes-diurno",           # opcional: parte de um preset e troca só os campos dados
      "nome": "meu-estilo",
      "descricao": "texto curto",
      "ceu": ["#topo", "...", "#horizonte"],
      "atmosfera": "#cor que o longe puxa",
      "luz": "#cor da luz de contorno e dos raios",
      "contorno_cor": "#cor do contorno (padrão: a mais escura da paleta)",
      "rampas": {
        "folha": ["#escuro", "...", "#claro"],
        "pedra": {"base": "#8a8a96", "passos": 5, "matiz": 20}
      },
      "paleta": ["#..."],              # opcional: paleta fechada; sem ela, a paleta sai das rampas, sem par quase igual
      "extras": ["#..."],              # opcional: cores a mais na paleta derivada
      "niveis_profundidade": [0.4, 0.7],  # opcional: rampas já misturadas com a atmosfera
      "forca_atmosfera": 0.7,          # quanto a profundidade 1 puxa para a atmosfera
      "forca_luz": 0.5,                # quanto a luz de contorno puxa para a cor da luz
      "sombreamento": "faixas",        # "chapado", "faixas" ou "pontilhado"
      "contorno": false,               # contorno escuro de 1 pixel em volta das formas
      "luz_contorno": true,            # borda clara do lado da luz
      "direcao_luz": [-1, -1],         # de onde vem a luz (x, y): -1, -1 é de cima à esquerda
      "largura_faixa": 2,              # espessura das faixas de luz e sombra, em pixels
      "tom_base": 0.5,                 # posição do tom médio na rampa, de 0 a 1
      "geracao": 16                    # opcional: técnica de uma época (8, 16, 32, "moderno"); ver geracao.py
    }

Com `geracao`, a época manda na técnica (passos das rampas, grade e limite de cores, sombreamento,
largura e degraus das faixas, contorno e textura) e o tema continua mandando nas cores.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterator

from .cor import (RGB, cor_mais_proxima, gerar_rampa, hex_para_rgb, luminancia, misturar, rgb_para_hex, sem_quase_iguais,
                  sem_repetir)
from .geracao import Geracao, geracao as ler_geracao, matiz_na_grade, na_grade, reduzir_paleta

PAPEIS = ("folha", "tronco", "pedra", "terra", "grama", "cristal", "nuvem", "nevoa", "neve")

# Papel que falta no estilo usa o primeiro destes que existir.
RESERVA = {
    "tronco": ("terra", "pedra"),
    "grama": ("folha", "terra"),
    "terra": ("pedra",),
    "pedra": ("terra",),
    "folha": ("grama", "pedra"),
    "cristal": ("pedra",),
    "nevoa": ("nuvem",),
    "nuvem": ("nevoa",),
    "neve": ("nuvem", "nevoa"),
}

SOMBREAMENTOS = ("chapado", "faixas", "pontilhado")


def _ler_rampa(valor: Any) -> list[RGB]:
    if isinstance(valor, dict):
        argumentos = {k: v for k, v in valor.items() if k != "base"}
        return gerar_rampa(hex_para_rgb(valor["base"]), **argumentos)
    if isinstance(valor, (list, tuple)) and valor:
        return [hex_para_rgb(c) for c in valor]
    raise ValueError(f"rampa inválida: {valor!r}")


def _rampa_da_geracao(valor: Any, passos: int) -> Any:
    """A rampa com `passos` tons: a gerada ganha os passos, a lista é reamostrada de ponta a ponta."""
    if isinstance(valor, dict):
        return {**valor, "passos": passos}
    cores = _ler_rampa(valor)
    if len(cores) < 2 or len(cores) == passos:
        return valor
    saida = []
    for i in range(passos):
        posicao = i * (len(cores) - 1) / (passos - 1)
        antes = int(posicao)
        depois = min(antes + 1, len(cores) - 1)
        saida.append(rgb_para_hex(misturar(cores[antes], cores[depois], posicao - antes)))
    return saida


@dataclass
class Estilo:
    nome: str
    ceu: tuple[RGB, ...]
    atmosfera: RGB
    luz: RGB
    rampas: dict[str, tuple[RGB, ...]]
    paleta: tuple[RGB, ...]
    contorno_cor: RGB
    descricao: str = ""
    forca_atmosfera: float = 0.7
    forca_luz: float = 0.5
    sombreamento: str = "faixas"
    contorno: bool = False
    luz_contorno: bool = True
    direcao_luz: tuple[int, int] = (-1, -1)
    largura_faixa: int = 2
    tom_base: float = 0.5
    degraus: int = 1
    textura: float = 0.0
    selout: bool = False
    geracao: Geracao | None = None
    rampas_do_tema: dict[str, tuple[RGB, ...]] = field(default_factory=dict)  # com geração: as rampas antes da grade
    origem: dict[str, Any] = field(default_factory=dict, repr=False)
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    # --- cores ---------------------------------------------------------------------------

    def cor(self, cor: RGB, profundidade: float = 0.0) -> RGB:
        """Cor da paleta para `cor` vista a `profundidade` (0 perto, 1 no fundo).

        O longe mistura com a cor da atmosfera, o que dá contraste entre as camadas.
        """
        chave = ("cor", cor, round(profundidade, 4))
        if chave not in self._cache:
            t = max(0.0, min(1.0, profundidade)) * self.forca_atmosfera
            self._cache[chave] = cor_mais_proxima(misturar(cor, self.atmosfera, t), self.paleta)
        return self._cache[chave]

    def rampa(self, papel: str, profundidade: float = 0.0) -> tuple[RGB, ...]:
        """Rampa do papel (escuro ao claro) já na profundidade, só com cores da paleta.

        Com geração, tons vizinhos que a grade da época junta numa cor só viram um tom: a rampa
        fica mais curta em vez de repetir a cor (o meio dela cairia no tom mais claro).
        """
        chave = ("rampa", papel, round(profundidade, 4))
        if chave not in self._cache:
            tons = [self.cor(c, profundidade) for c in self._rampa_crua(papel)]
            if self.geracao is not None:
                tons = [c for i, c in enumerate(tons) if i == 0 or c != tons[i - 1]]
            self._cache[chave] = tuple(tons)
        return self._cache[chave]

    def _rampa_crua(self, papel: str) -> tuple[RGB, ...]:
        if papel in self.rampas:
            return self.rampas[papel]
        for reserva in RESERVA.get(papel, ()):
            if reserva in self.rampas:
                return self.rampas[reserva]
        return next(iter(self.rampas.values()))

    def cor_da_luz(self, profundidade: float = 0.0) -> RGB:
        return self.cor(self.luz, profundidade)

    # --- dicionário e JSON ---------------------------------------------------------------

    @classmethod
    def de_dicionario(cls, dados: dict[str, Any]) -> "Estilo":
        for chave in ("nome", "ceu", "atmosfera", "luz", "rampas"):
            if chave not in dados:
                raise ValueError(f"estilo sem o campo obrigatório {chave!r}")
        epoca = None
        rampas_do_tema = {}
        if "geracao" in dados:
            epoca = ler_geracao(dados["geracao"])
            rampas_do_tema = {papel: tuple(_ler_rampa(valor)) for papel, valor in dados["rampas"].items()}
            dados = _com_a_tecnica(dados, epoca)
        sombreamento = dados.get("sombreamento", "faixas")
        if sombreamento not in SOMBREAMENTOS:
            raise ValueError(f"sombreamento deve ser um de {SOMBREAMENTOS}, veio {sombreamento!r}")

        ceu = [hex_para_rgb(c) for c in dados["ceu"]]
        atmosfera = hex_para_rgb(dados["atmosfera"])
        luz = hex_para_rgb(dados["luz"])
        rampas = {papel: _ler_rampa(valor) for papel, valor in dados["rampas"].items()}
        if epoca is not None:
            rampas = {p: matiz_na_grade(r, epoca.grade) for p, r in rampas.items()}
        forca_atmosfera = float(dados.get("forca_atmosfera", 0.7))

        if "paleta" in dados:
            paleta = sem_repetir(hex_para_rgb(c) for c in dados["paleta"])
        else:
            cores = list(ceu) + [atmosfera, luz]
            for rampa in rampas.values():
                cores.extend(rampa)
            for nivel in dados.get("niveis_profundidade", ()):
                t = float(nivel) * forca_atmosfera
                for rampa in rampas.values():
                    cores.extend(misturar(c, atmosfera, t) for c in rampa)
                cores.append(misturar(luz, atmosfera, t))
            cores.extend(hex_para_rgb(c) for c in dados.get("extras", ()))
            if "contorno_cor" in dados:
                cores.append(hex_para_rgb(dados["contorno_cor"]))
            paleta = sem_quase_iguais(cores)  # rampa misturada com a atmosfera cai a 1 ou 2 de outra cor
        if epoca is not None:
            paleta = reduzir_paleta(sem_repetir(na_grade(c, epoca.grade) for c in paleta), epoca.cores_cena)
        if len(paleta) > 256:
            raise ValueError(f"paleta com {len(paleta)} cores; o limite é 256")

        # rampas e céu também passam pela paleta, para uma paleta fechada valer em tudo
        rampas = {p: tuple(cor_mais_proxima(c, paleta) for c in r) for p, r in rampas.items()}
        ceu = [cor_mais_proxima(c, paleta) for c in ceu]
        if "contorno_cor" in dados:
            contorno_cor = cor_mais_proxima(hex_para_rgb(dados["contorno_cor"]), paleta)
        else:
            contorno_cor = min(paleta, key=luminancia)
        direcao = tuple(int(v) for v in dados.get("direcao_luz", (-1, -1)))
        if len(direcao) != 2 or direcao == (0, 0) or any(abs(v) > 1 for v in direcao):
            raise ValueError("direcao_luz deve ser [x, y] com valores -1, 0 ou 1, sem ser [0, 0]")

        return cls(
            nome=str(dados["nome"]),
            descricao=str(dados.get("descricao", "")),
            ceu=tuple(ceu),
            atmosfera=atmosfera,
            luz=luz,
            rampas=rampas,
            paleta=tuple(paleta),
            contorno_cor=contorno_cor,
            forca_atmosfera=forca_atmosfera,
            forca_luz=float(dados.get("forca_luz", 0.5)),
            sombreamento=sombreamento,
            contorno=bool(dados.get("contorno", False)),
            luz_contorno=bool(dados.get("luz_contorno", True)),
            direcao_luz=direcao,  # type: ignore[arg-type]
            largura_faixa=max(1, int(dados.get("largura_faixa", 2))),
            tom_base=float(dados.get("tom_base", 0.5)),
            degraus=epoca.degraus if epoca else 1,
            textura=epoca.textura if epoca else 0.0,
            selout=epoca is not None and epoca.contorno == "selout",
            geracao=epoca,
            rampas_do_tema=rampas_do_tema,
            origem=dict(dados),
        )

    def para_dicionario(self) -> dict[str, Any]:
        """Dicionário pronto para JSON, já resolvido (paleta fechada, rampas em hex)."""
        dados = {
            "nome": self.nome,
            "descricao": self.descricao,
            "ceu": [rgb_para_hex(c) for c in self.ceu],
            "atmosfera": rgb_para_hex(self.atmosfera),
            "luz": rgb_para_hex(self.luz),
            "contorno_cor": rgb_para_hex(self.contorno_cor),
            "rampas": {p: [rgb_para_hex(c) for c in r] for p, r in self.rampas.items()},
            "paleta": [rgb_para_hex(c) for c in self.paleta],
            "forca_atmosfera": self.forca_atmosfera,
            "forca_luz": self.forca_luz,
            "sombreamento": self.sombreamento,
            "contorno": self.contorno,
            "luz_contorno": self.luz_contorno,
            "direcao_luz": list(self.direcao_luz),
            "largura_faixa": self.largura_faixa,
            "tom_base": self.tom_base,
        }
        if self.geracao is not None:
            dados["geracao"] = self.geracao.numero
        return dados


def _com_a_tecnica(dados: dict[str, Any], epoca: Geracao) -> dict[str, Any]:
    """Os campos de técnica do estilo trocados pelos da geração; as cores do tema ficam."""
    novos = {
        **dados,
        "rampas": {papel: _rampa_da_geracao(valor, epoca.passos) for papel, valor in dados["rampas"].items()},
        "sombreamento": epoca.sombreamento,
        "largura_faixa": epoca.largura_faixa,
        "contorno": True,
    }
    if epoca.contorno == "preto":
        novos["contorno_cor"] = "#000000"
    return novos


# --- presets ---------------------------------------------------------------------------------
#
# Preset é um estilo com nome. Os do pacote ficam em `pixel_atelier/estilos/`; os registrados com
# `registrar_estilo` ficam na pasta de presets do usuário (variável PIXEL_ATELIER_ESTILOS ou
# ~/.pixel-atelier/estilos). Onde se aceita um dicionário de estilo, vale `"base": "nome"` para
# partir de um preset e mudar só alguns campos (as rampas se juntam papel a papel).

VARIAVEL_PRESETS = "PIXEL_ATELIER_ESTILOS"
NOME_VALIDO = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# Dentro de `estilos_so_em`, estilo dado como caminho .json só vale se cair na raiz (é o que o MCP usa).
_RAIZ_DOS_JSON: ContextVar[Path | None] = ContextVar("raiz_dos_json_de_estilo", default=None)


@contextmanager
def estilos_so_em(raiz: Path) -> Iterator[None]:
    """Durante o bloco, caminho .json de estilo (e de `base`) relativo parte da raiz e fora dela é recusado."""
    marca = _RAIZ_DOS_JSON.set(Path(raiz).resolve())
    try:
        yield
    finally:
        _RAIZ_DOS_JSON.reset(marca)


def sugerir_nome(texto: str) -> str:
    """Nome de preset parecido com o texto: `Floresta Nublada_3x` vira `floresta-nublada-3x`."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def validar_nome_de_estilo(nome: object, o_que: str = "estilo") -> str:
    """O nome de um preset: minúsculo com hífens, sem barra nem `..` (nunca vira caminho).

    Se o nome inválido for o de um JSON copiado à mão para a pasta de presets, o erro diz como renomear.
    """
    if isinstance(nome, str) and NOME_VALIDO.match(nome):
        return nome
    mensagem = (f"nome de {o_que} {nome!r} inválido: use o nome de um preset (minúsculo com hífens, "
                f"ex.: snes-diurno) ou o caminho de um arquivo .json")
    copiado = _preset_fora_do_padrao(nome)
    if copiado is not None:
        mensagem += f"; {_renomeie(copiado)}"
    raise ValueError(mensagem)


def _preset_fora_do_padrao(nome: object) -> Path | None:
    """O JSON da pasta de presets do usuário com esse nome fora do padrão, se existir.

    Nome com barra ou `..` nem é procurado: o nome nunca vira caminho."""
    if not isinstance(nome, str) or not nome or ".." in nome or any(c in nome for c in "/\\:"):
        return None
    arquivo = pasta_de_presets() / f"{nome}.json"
    return arquivo if arquivo.is_file() else None


def _renomeie(arquivo: Path) -> str:
    sugestao = sugerir_nome(arquivo.stem) or "meu-estilo"
    return (f"o preset {arquivo.name} em {arquivo.parent.as_posix()} tem nome fora do padrão e não carrega por nome: "
            f"renomeie o arquivo para {sugestao}.json e use \"{sugestao}\"")


def _arquivo_json_do_estilo(caminho: Path) -> Path:
    raiz = _RAIZ_DOS_JSON.get()
    if raiz is not None:
        caminho = (raiz / caminho).resolve()
        if not caminho.is_relative_to(raiz):
            raise ValueError(f"o estilo {caminho.name!r} fica fora da raiz {raiz.as_posix()}; use um caminho dentro dela")
    if not caminho.is_file():
        raise KeyError(f"o arquivo de estilo {caminho.as_posix()!r} não existe")
    return caminho


def _pasta_de_estilos():
    return resources.files("pixel_atelier") / "estilos"


def pasta_de_presets() -> Path:
    """Pasta dos presets registrados pelo usuário."""
    return Path(os.environ.get(VARIAVEL_PRESETS) or Path.home() / ".pixel-atelier" / "estilos")


def _arquivo_do_preset(nome: str):
    for pasta in (_pasta_de_estilos(), pasta_de_presets()):
        arquivo = pasta / f"{nome}.json"
        if arquivo.is_file():
            return arquivo
    return None


def listar_estilos() -> list[str]:
    """Nomes dos presets (do pacote e do usuário), em ordem alfabética."""
    nomes = {p.name[:-5] for p in _pasta_de_estilos().iterdir() if p.name.endswith(".json")}
    nomes.update(p.stem for p in _presets_do_usuario() if NOME_VALIDO.match(p.stem))
    return sorted(nomes)


def _presets_do_usuario() -> list[Path]:
    pasta = pasta_de_presets()
    return sorted(pasta.glob("*.json")) if pasta.is_dir() else []


def descrever_estilos() -> str:
    """Uma linha por preset: o nome e, quando tem, a descrição. JSON com nome fora do padrão vira aviso."""
    linhas = []
    for nome in listar_estilos():
        descricao = dados_do_estilo(nome).get("descricao")
        linhas.append(f"{nome}: {descricao}" if descricao else nome)
    linhas.extend(f"aviso: {_renomeie(p)}" for p in _presets_do_usuario() if not NOME_VALIDO.match(p.stem))
    return "\n".join(linhas)


def dados_do_estilo(estilo: "str | Path | dict[str, Any] | Estilo", _nivel: int = 0) -> dict[str, Any]:
    """Dicionário cru do estilo (antes de resolver a paleta), já com a `base` aplicada.

    Aceita o nome de um preset, o caminho de um JSON, um dicionário ou um `Estilo`.
    """
    if _nivel > 8:
        raise ValueError("estilo com base em ciclo (uma base aponta de volta para outra)")
    if isinstance(estilo, Estilo):
        return dict(estilo.origem) if estilo.origem else estilo.para_dicionario()
    if isinstance(estilo, dict):
        if "base" not in estilo:
            return dict(estilo)
        dados = dados_do_estilo(estilo["base"], _nivel + 1)
        for chave, valor in estilo.items():
            if chave == "base":
                continue
            if chave == "rampas" and isinstance(valor, dict) and isinstance(dados.get("rampas"), dict):
                dados["rampas"] = {**dados["rampas"], **valor}
            else:
                dados[chave] = valor
        return dados
    if not isinstance(estilo, (str, Path)):
        raise TypeError(f"estilo deve ser nome, caminho, dicionário ou Estilo, veio {type(estilo).__name__}")
    if Path(estilo).suffix == ".json":
        arquivo = _arquivo_json_do_estilo(Path(estilo))
    else:
        arquivo = _arquivo_do_preset(validar_nome_de_estilo(str(estilo)))
    if arquivo is None:
        mensagem = f"estilo {str(estilo)!r} não existe; os que existem: {', '.join(listar_estilos())}"
        parecidos = [p for p in _presets_do_usuario()
                     if not NOME_VALIDO.match(p.stem) and sugerir_nome(p.stem) == estilo]
        if parecidos:
            mensagem += f"; {_renomeie(parecidos[0])}"
        raise KeyError(mensagem)
    return dados_do_estilo(json.loads(arquivo.read_text(encoding="utf-8")), _nivel + 1)


def carregar_estilo(estilo: "str | Path | dict[str, Any] | Estilo") -> Estilo:
    """Aceita o nome de um preset, o caminho de um JSON, um dicionário (com ou sem `base`) ou um `Estilo` pronto."""
    if isinstance(estilo, Estilo):
        return estilo
    return Estilo.de_dicionario(dados_do_estilo(estilo))


def registrar_estilo(estilo: "str | Path | dict[str, Any] | Estilo", nome: str | None = None, *,
                     sobrescrever: bool = False) -> Path:
    """Guarda o estilo como preset com nome, na pasta de presets do usuário. Devolve o arquivo gravado.

    Grava o dicionário cru (com a `base` já aplicada), para o preset continuar fácil de ajustar.
    Os nomes do pacote são reservados; um preset do usuário só é trocado com `sobrescrever=True`.
    """
    dados = dados_do_estilo(estilo)
    nome = nome or dados.get("nome")
    if not isinstance(nome, str) or not NOME_VALIDO.match(nome):
        raise ValueError(f"nome de preset deve ser minúsculo com hífens (ex.: floresta-nublada), veio {nome!r}")
    dados["nome"] = nome
    Estilo.de_dicionario(dados)  # valida antes de gravar
    if (_pasta_de_estilos() / f"{nome}.json").is_file():
        raise ValueError(f"o preset {nome!r} vem com o pacote; escolha outro nome")
    destino = pasta_de_presets() / f"{nome}.json"
    if destino.exists() and not sobrescrever:
        raise ValueError(f"o preset {nome!r} já existe em {destino}; use sobrescrever para trocar")
    destino.parent.mkdir(parents=True, exist_ok=True)
    _gravar_json(dados, destino)
    return destino


def salvar_estilo(estilo: Estilo, caminho: str | Path) -> Path:
    """Grava o estilo resolvido em JSON (UTF-8, LF)."""
    return _gravar_json(estilo.para_dicionario(), Path(caminho))


def _gravar_json(dados: dict[str, Any], destino: Path) -> Path:
    with open(destino, "w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")
    return destino
