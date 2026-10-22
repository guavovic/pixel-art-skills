"""`gerar`: desenha a receita inteira e responde em texto curto, sem precisar olhar a imagem.

    from pixel_atelier import gerar

    resultado = gerar("exemplos/snes-diurno.json", pasta="saida")
    print(resultado.resumo())

Sem `pasta`, nada é gravado: as imagens ficam em `resultado.composto` e `resultado.camadas`.
`resultado.para_dicionario()` devolve o mesmo resumo em dicionário pronto para JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from .cor import RGB, cores_usadas, rgb_para_hex
from .formas import desenhar
from .imagem import ampliar, compor
from .receita import Receita, validar_receita

CORES_LISTADAS = 16  # até quantas cores o resumo lista em hex


@dataclass
class CamadaGerada:
    indice: int
    nome: str
    forma: str
    seed: int
    imagem: Image.Image = field(repr=False)
    cobertura: float  # fração dos pixels visíveis, de 0 a 1
    cores: int
    arquivo: Path | None = None


@dataclass
class Resultado:
    receita: Receita
    composto: Image.Image = field(repr=False)
    camadas: list[CamadaGerada]
    cores: set[RGB]
    arquivos: list[Path] = field(default_factory=list)

    def avisos(self) -> list[str]:
        """Problemas que só aparecem depois de desenhar: camada vazia, camada que esconde as de trás."""
        avisos = []
        for c in self.camadas:
            if c.cobertura == 0:
                avisos.append(f"camada {c.indice + 1} ({c.nome}) não desenhou nada")
            elif c.cobertura == 1 and c.indice > 0:
                avisos.append(f"camada {c.indice + 1} ({c.nome}) cobre a tela toda e esconde as de trás")
        return avisos

    def para_dicionario(self) -> dict[str, Any]:
        r = self.receita
        return {
            "cena": r.cena,
            "tamanho": [r.largura, r.altura],
            "estilo": r.estilo.nome,
            "laco": r.laco,
            "seed": r.seed,
            "cores": len(self.cores),
            "cores_na_paleta": len(r.estilo.paleta),
            "paleta_usada": sorted(rgb_para_hex(c) for c in self.cores),
            "arquivos": [p.as_posix() for p in self.arquivos],
            "camadas": [
                {"nome": c.nome, "forma": c.forma, "seed": c.seed, "cobertura": round(c.cobertura, 3),
                 "cores": c.cores, "arquivo": c.arquivo.as_posix() if c.arquivo else None}
                for c in self.camadas
            ],
            "avisos": self.avisos(),
        }

    def resumo(self) -> str:
        """Resumo em poucas linhas: arquivos, tamanho, cores e o que cada camada fez."""
        r = self.receita
        linhas = [f"{r.cena}: {r.largura}x{r.altura}, estilo {r.estilo.nome}, "
                  f"{'com laço' if r.laco else 'sem laço'}, seed {r.seed}, {len(self.camadas)} camadas"]
        if not self.arquivos:
            linhas.append("nada gravado (sem pasta)")
        de_camada = {c.arquivo for c in self.camadas}
        compostos = [p.as_posix() for p in self.arquivos if p not in de_camada]
        if compostos:
            linhas.append("composto: " + ", ".join(compostos))
        cores = f"cores: {len(self.cores)} de {len(r.estilo.paleta)} da paleta"
        if len(self.cores) <= CORES_LISTADAS:
            cores += " (" + " ".join(sorted(rgb_para_hex(c) for c in self.cores)) + ")"
        linhas.append(cores)
        pasta = next((c.arquivo.parent.as_posix() for c in self.camadas if c.arquivo), None)
        linhas.append(f"camadas{' em ' + pasta if pasta else ''} (seed, área coberta, cores):")
        for c in self.camadas:
            arquivo = f" {c.arquivo.name}" if c.arquivo else ""
            cores_camada = "1 cor" if c.cores == 1 else f"{c.cores} cores"
            linhas.append(f"  {c.indice + 1:02d} {c.nome}: seed {c.seed}, {c.cobertura:.0%}, {cores_camada}{arquivo}")
        linhas.extend(f"aviso: {a}" for a in self.avisos())
        return "\n".join(linhas)


def _cobertura(imagem: Image.Image) -> float:
    alfa = imagem.getchannel("A")
    return alfa.histogram()[255] / (imagem.width * imagem.height)


def gerar(receita: "str | Path | dict[str, Any] | Receita", pasta: str | Path | None = None) -> Resultado:
    """Valida e desenha a receita. Com `pasta`, grava os PNGs conforme o campo `saida` da receita.

    Arquivos: `<pasta>/<cena>.png` (composto), `<pasta>/<cena>-<N>x.png` (composto ampliado, se
    `ampliar` > 1) e `<pasta>/<cena>/<NN>-<nome>.png` (cada camada no tamanho real).
    Erro na receita levanta `ErroDeReceita` com todos os problemas em texto.
    """
    r = receita if isinstance(receita, Receita) else validar_receita(receita)
    geradas = []
    for c in r.camadas:
        imagem = desenhar(c.forma, r.estilo, r.largura, r.altura, **c.parametros)
        geradas.append(CamadaGerada(indice=c.indice, nome=c.nome, forma=c.forma, seed=c.parametros["seed"],
                                    imagem=imagem, cobertura=_cobertura(imagem), cores=len(cores_usadas(imagem))))
    composto = compor(c.imagem for c in geradas)
    resultado = Resultado(receita=r, composto=composto, camadas=geradas, cores=cores_usadas(composto))
    if pasta is not None:
        _gravar(resultado, Path(pasta))
    return resultado


def _gravar(resultado: Resultado, pasta: Path) -> None:
    r = resultado.receita
    pasta.mkdir(parents=True, exist_ok=True)
    if r.saida in ("tudo", "composto"):
        destino = pasta / f"{r.cena}.png"
        resultado.composto.save(destino)
        resultado.arquivos.append(destino)
        if r.ampliar > 1:
            destino = pasta / f"{r.cena}-{r.ampliar}x.png"
            ampliar(resultado.composto, r.ampliar).save(destino)
            resultado.arquivos.append(destino)
    if r.saida in ("tudo", "camadas"):
        (pasta / r.cena).mkdir(exist_ok=True)
        for receita_camada, c in zip(r.camadas, resultado.camadas):
            c.arquivo = pasta / r.cena / receita_camada.arquivo
            c.imagem.save(c.arquivo)
            resultado.arquivos.append(c.arquivo)
