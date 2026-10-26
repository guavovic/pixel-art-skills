"""`gerar`: desenha a receita inteira e responde em texto curto, sem precisar olhar a imagem.

    from pixel_atelier import gerar

    resultado = gerar("exemplos/snes-diurno.json", pasta="saida")
    print(resultado.resumo())

Sem `pasta`, nada é gravado: as imagens ficam em `resultado.composto` e `resultado.camadas` (e,
com `animacao` na receita, os quadros em `resultado.quadros`).
`resultado.para_dicionario()` devolve o mesmo resumo em dicionário pronto para JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from .animacao import Animador, Movimento, folha, gravar_gif, gravar_tempo, tempo
from .cor import RGB, cores_usadas, rgb_para_hex
from .formas import desenhar
from .imagem import ampliar, compor, gravar_png
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
    quadros: list[Image.Image] = field(default_factory=list, repr=False)
    movimentos: list[Movimento] = field(default_factory=list)
    arquivos_da_animacao: list[Path] = field(default_factory=list)
    gif_exato: bool = True

    def avisos(self) -> list[str]:
        """Problemas que só aparecem depois de desenhar: camada vazia, camada que esconde as de trás."""
        avisos = []
        for c in self.camadas:
            if c.cobertura == 0:
                avisos.append(f"camada {c.indice + 1} ({c.nome}) não desenhou nada")
            elif c.cobertura == 1 and c.indice > 0:
                avisos.append(f"camada {c.indice + 1} ({c.nome}) cobre a tela toda e esconde as de trás")
        nada_se_mexe = self.movimentos and not any(m.voltas or m.pulsa for m in self.movimentos)
        if nada_se_mexe:
            avisos.append("animação sem movimento: nenhuma camada anda nem pulsa "
                          "(sem laço, ou voltas 0 sem nuvem, névoa ou raios)")
        if not self.gif_exato:
            avisos.append("o GIF passou de 256 cores e saiu com a paleta reduzida; a folha PNG tem as cores exatas")
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
            "animacao": self._animacao_em_dicionario(),
            "avisos": self.avisos(),
        }

    def _animacao_em_dicionario(self) -> dict[str, Any] | None:
        a = self.receita.animacao
        if a is None:
            return None
        return {"quadros": a.quadros, "duracao": a.duracao, "voltas": a.voltas,
                "arquivos": [p.as_posix() for p in self.arquivos_da_animacao],
                "movimento": {c.nome: m.descrever() for c, m in zip(self.camadas, self.movimentos)}}

    def resumo(self, base: Path | None = None) -> str:
        """Resumo em poucas linhas: arquivos, tamanho, cores e o que cada camada fez.

        Com `base`, os caminhos que ficam dentro dela aparecem relativos a ela (texto mais curto).
        """
        def caminho(p: Path) -> str:
            return (p.relative_to(base) if base and p.is_relative_to(base) else p).as_posix()

        r = self.receita
        linhas = [f"{r.cena}: {r.largura}x{r.altura}, estilo {r.estilo.nome}, "
                  f"{'com laço' if r.laco else 'sem laço'}, seed {r.seed}, {len(self.camadas)} camadas"]
        if not self.arquivos:
            linhas.append("nada gravado (sem pasta)")
        de_fora = {c.arquivo for c in self.camadas} | set(self.arquivos_da_animacao)
        compostos = [caminho(p) for p in self.arquivos if p not in de_fora]
        if compostos:
            linhas.append("composto: " + ", ".join(compostos))
        cores = f"cores: {len(self.cores)} de {len(r.estilo.paleta)} da paleta"
        if len(self.cores) <= CORES_LISTADAS:
            cores += " (" + " ".join(sorted(rgb_para_hex(c) for c in self.cores)) + ")"
        linhas.append(cores)
        a = r.animacao
        if a is not None:
            segundos = f"{a.quadros * a.duracao / 1000:g}".replace(".", ",")
            texto = f"animação: {a.quadros} quadros de {a.duracao} ms ({segundos} s por laço), voltas {a.voltas}"
            if self.arquivos_da_animacao:
                texto += ": " + ", ".join(caminho(p) for p in self.arquivos_da_animacao)
            linhas.append(texto)
            linhas.append("movimento: " + ", ".join(f"{c.nome} {m.descrever()}" for c, m in zip(self.camadas, self.movimentos)))
        pasta = next((caminho(c.arquivo.parent) for c in self.camadas if c.arquivo), None)
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
    if r.animacao is not None:
        animador = Animador(r, [c.imagem for c in geradas])
        resultado.movimentos = animador.movimentos
        resultado.quadros = animador.quadros()
    if pasta is not None:
        _gravar(resultado, Path(pasta))
    return resultado


def _gravar(resultado: Resultado, pasta: Path) -> None:
    r = resultado.receita
    pasta.mkdir(parents=True, exist_ok=True)
    if r.saida in ("tudo", "composto"):
        destino = pasta / f"{r.cena}.png"
        gravar_png(resultado.composto, destino, r.laco)
        resultado.arquivos.append(destino)
        if r.ampliar > 1:
            destino = pasta / f"{r.cena}-{r.ampliar}x.png"
            gravar_png(ampliar(resultado.composto, r.ampliar), destino, r.laco, escala=r.ampliar)
            resultado.arquivos.append(destino)
        if r.animacao is not None:
            _gravar_animacao(resultado, pasta)
    if r.saida in ("tudo", "camadas"):
        (pasta / r.cena).mkdir(exist_ok=True)
        for receita_camada, c in zip(r.camadas, resultado.camadas):
            c.arquivo = pasta / r.cena / receita_camada.arquivo
            gravar_png(c.imagem, c.arquivo, receita_camada.parametros["laco"])
            resultado.arquivos.append(c.arquivo)


def _gravar_animacao(resultado: Resultado, pasta: Path) -> None:
    """`<cena>.gif` (ou `<cena>-Nx.gif`, ampliado), `<cena>-quadros.png` e `<cena>-quadros.json`."""
    r = resultado.receita
    a = r.animacao
    gif = pasta / (f"{r.cena}-{r.ampliar}x.gif" if r.ampliar > 1 else f"{r.cena}.gif")
    resultado.gif_exato = gravar_gif(resultado.quadros, gif, a.duracao, r.laco, escala=r.ampliar)
    dados = tempo(r.cena, a, (r.largura, r.altura), r.laco, f"{r.cena}-quadros.png")
    arquivo_folha = pasta / dados["folha"]
    gravar_png(folha(resultado.quadros, dados["colunas"]), arquivo_folha, r.laco)
    arquivo_tempo = pasta / f"{r.cena}-quadros.json"
    gravar_tempo(dados, arquivo_tempo)
    resultado.arquivos_da_animacao = [gif, arquivo_folha, arquivo_tempo]
    resultado.arquivos.extend(resultado.arquivos_da_animacao)
