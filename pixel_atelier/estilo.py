"""Estilo: paleta, rampas por papel e o jeito de sombrear. É o que muda de um visual para outro.

Um estilo é só dado (um dicionário ou um JSON em `pixel_atelier/estilos/`). As formas pedem cores
por papel (`folha`, `pedra`, `terra`...) e por profundidade, e o estilo responde com cores da
paleta dele. Trocar de estilo não muda nenhuma forma.

Formato do dicionário (só `nome`, `ceu`, `atmosfera`, `luz` e `rampas` são obrigatórios):

    {
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
      "paleta": ["#..."],              # opcional: paleta fechada; sem ela, a paleta sai das rampas
      "extras": ["#..."],              # opcional: cores a mais na paleta derivada
      "niveis_profundidade": [0.4, 0.7],  # opcional: rampas já misturadas com a atmosfera
      "forca_atmosfera": 0.7,          # quanto a profundidade 1 puxa para a atmosfera
      "forca_luz": 0.5,                # quanto a luz de contorno puxa para a cor da luz
      "sombreamento": "faixas",        # "chapado", "faixas" ou "pontilhado"
      "contorno": false,               # contorno escuro de 1 pixel em volta das formas
      "luz_contorno": true,            # borda clara do lado da luz
      "direcao_luz": [-1, -1],         # de onde vem a luz (x, y): -1, -1 é de cima à esquerda
      "largura_faixa": 2,              # espessura das faixas de luz e sombra, em pixels
      "tom_base": 0.5                  # posição do tom médio na rampa, de 0 a 1
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from .cor import RGB, cor_mais_proxima, gerar_rampa, hex_para_rgb, luminancia, misturar, rgb_para_hex, sem_repetir

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
        """Rampa do papel (escuro ao claro) já na profundidade, só com cores da paleta."""
        chave = ("rampa", papel, round(profundidade, 4))
        if chave not in self._cache:
            base = self._rampa_crua(papel)
            self._cache[chave] = tuple(self.cor(c, profundidade) for c in base)
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
        sombreamento = dados.get("sombreamento", "faixas")
        if sombreamento not in SOMBREAMENTOS:
            raise ValueError(f"sombreamento deve ser um de {SOMBREAMENTOS}, veio {sombreamento!r}")

        ceu = [hex_para_rgb(c) for c in dados["ceu"]]
        atmosfera = hex_para_rgb(dados["atmosfera"])
        luz = hex_para_rgb(dados["luz"])
        rampas = {papel: _ler_rampa(valor) for papel, valor in dados["rampas"].items()}
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
            paleta = sem_repetir(cores)
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
            origem=dict(dados),
        )

    def para_dicionario(self) -> dict[str, Any]:
        """Dicionário pronto para JSON, já resolvido (paleta fechada, rampas em hex)."""
        return {
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


# --- presets ---------------------------------------------------------------------------------

def _pasta_de_estilos():
    return resources.files("pixel_atelier") / "estilos"


def listar_estilos() -> list[str]:
    """Nomes dos estilos que vêm com o pacote, em ordem alfabética."""
    return sorted(p.name[:-5] for p in _pasta_de_estilos().iterdir() if p.name.endswith(".json"))


def carregar_estilo(estilo: "str | Path | dict[str, Any] | Estilo") -> Estilo:
    """Aceita o nome de um preset, o caminho de um JSON, um dicionário ou um `Estilo` pronto."""
    if isinstance(estilo, Estilo):
        return estilo
    if isinstance(estilo, dict):
        return Estilo.de_dicionario(estilo)
    caminho = Path(estilo)
    if caminho.suffix == ".json" and caminho.exists():
        return Estilo.de_dicionario(json.loads(caminho.read_text(encoding="utf-8")))
    arquivo = _pasta_de_estilos() / f"{estilo}.json"
    if not arquivo.is_file():
        raise KeyError(f"estilo {estilo!r} não existe; os que existem: {', '.join(listar_estilos())}")
    return Estilo.de_dicionario(json.loads(arquivo.read_text(encoding="utf-8")))


def salvar_estilo(estilo: Estilo, caminho: str | Path) -> Path:
    """Grava o estilo resolvido em JSON (UTF-8, LF)."""
    destino = Path(caminho)
    with open(destino, "w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(estilo.para_dicionario(), arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")
    return destino
