"""Gerações: números das âncoras e do meio, receita com geração, limites no desenho e no `revisar`."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PIL import Image

from pixel_atelier import carregar_estilo, gerar, revisar
from pixel_atelier.__main__ import main
from pixel_atelier.cor import hex_para_rgb, luminancia, mudanca_de_matiz
from pixel_atelier.geracao import (ANCORAS, CORES_NES, MODERNO, geracao, ler_geracao, matiz_na_grade, na_grade,
                                   valor_na_grade)
from pixel_atelier.guia import capitulo
from pixel_atelier.imagem import gravar_png, marca_de_geracao
from pixel_atelier.revisao import COPIAS, COPIAS_LADRILHOS, JANELA, _copias_minimas, _lado_da_janela

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"

CENA = {
    "camadas": [
        {"forma": "ceu", "astro": "sol"},
        {"forma": "arvore", "profundidade": 0.5, "tipo": "mista"},
        {"forma": "terreno", "nome": "chao", "base": 0.85},
    ],
}


def regra(revisao, nome: str):
    return next(c for c in revisao.checagens if c.regra == nome)


def cores_rgb(imagem: Image.Image) -> set[tuple[int, int, int]]:
    contagem = imagem.convert("RGBA").getcolors(maxcolors=imagem.width * imagem.height)
    return {cor[:3] for _, cor in contagem if cor[3] > 0}


@pytest.mark.parametrize("valor, numero", [(8, 8), ("16", 16), ("16-bits", 16), ("Moderno", MODERNO), ("hd", MODERNO),
                                           (128, MODERNO)])
def test_le_numero_e_nome(valor, numero):
    assert ler_geracao(valor) == numero


@pytest.mark.parametrize("valor", [4, 0, "bits", True, None, 12.5])
def test_geracao_invalida_diz_o_que_vale(valor):
    with pytest.raises(ValueError, match="a partir de 8"):
        ler_geracao(valor)


def test_meio_interpola_e_pega_a_tecnica_mais_perto():
    doze, dez = geracao(12), geracao(10)
    assert (doze.tamanho, doze.cores_cena, doze.cores_camada) == ((256, 230), 63, 14)
    assert (doze.grade, doze.sombreamento) == ("15-bits", "faixas")
    assert (dez.grade, dez.sombreamento, dez.passos) == ("nes", "pontilhado", 4)
    assert geracao(48).cores_camada is None
    assert (geracao(20).textura, geracao(20).ladrilhos, geracao(24).textura, geracao(24).ladrilhos) == (0.0, True, 0.7, False)


def test_rampa_sem_tom_repetido_quando_a_grade_junta_tons():
    estilo = carregar_estilo({"base": "16-bits", "geracao": 10})
    for papel in estilo.rampas:
        rampa = estilo.rampa(papel, 0.65)
        assert all(a != b for a, b in zip(rampa, rampa[1:])), papel


def test_cor_da_grade_guarda_o_matiz_da_rampa():
    estilo = carregar_estilo({"base": "metroidvania-noturno", "nome": "noite-8", "geracao": 8})
    tema, na_grade_ = mudanca_de_matiz(estilo.rampas_do_tema["cristal"]), mudanca_de_matiz(estilo.rampas["cristal"])
    assert set(estilo.rampas["cristal"]) <= set(CORES_NES) and set(estilo.rampas["cristal"]) <= set(estilo.paleta)
    assert abs(na_grade_[0]) >= 3 and na_grade_[0] * tema[0] > 0  # o NES punha os 3 tons numa coluna só: 0°

    folha = carregar_estilo("snes-diurno").rampas["folha"]
    assert matiz_na_grade(list(folha), "nes") == list(folha)  # a cor mais perto já guarda: a paleta decide


@pytest.mark.parametrize("grade, rampa, perto_do_tema", [
    ("15-bits", ["#a8b8d8", "#becde5", "#d5e2f2", "#e6f0f9", "#f3f7fc", "#ffffff"], 1),  # neve diurna em 32 bits
    ("nes", ["#002e1c", "#068c40", "#3beb6a"], 32),  # a de menor distância ia a -78°
])
def test_grade_escolhe_o_matiz_mais_perto_do_tema(grade, rampa, perto_do_tema):
    cores = [hex_para_rgb(c) for c in rampa]
    tema = mudanca_de_matiz(cores)[0]
    escolhida = matiz_na_grade(cores, grade)
    assert all(na_grade(c, grade) == c for c in escolhida)
    assert abs(mudanca_de_matiz(escolhida)[0] - tema) < perto_do_tema


def test_neve_diurna_em_32_bits_fica_no_matiz_do_tema():
    neve = carregar_estilo({"base": "snes-diurno", "nome": "dia-32", "geracao": 32}).rampas["neve"]
    assert -10 < mudanca_de_matiz(neve)[0] < -4  # o tema anda -7°; a grade dava -21°


def test_paleta_fechada_guarda_o_degrau_de_valor_na_grade():
    verdes = [hex_para_rgb(c) for c in ("#0f380f", "#306230", "#8bac0f", "#9bbc0f")]
    trocas = valor_na_grade(verdes, "nes")
    escuros = sorted({trocas[verdes[0]], trocas[verdes[1]]}, key=luminancia)
    assert len(escuros) == 2 and luminancia(escuros[1]) - luminancia(escuros[0]) > 0.05
    assert all(na_grade(c, "nes") == c for c in trocas.values())


def test_contorno_preto_entra_na_paleta_fechada():
    estilo = carregar_estilo({"base": "game-boy", "nome": "gb-8", "geracao": 8})
    assert estilo.contorno_cor == (0, 0, 0) and (0, 0, 0) in estilo.paleta


def test_paleta_menor_que_a_rampa_nao_usa_selout():
    assert not carregar_estilo({"base": "game-boy", "nome": "gb-32", "geracao": 32}).selout
    assert carregar_estilo({"base": "snes-diurno", "nome": "dia-32", "geracao": 32}).selout


def test_receita_sem_tamanho_usa_o_da_geracao():
    assert gerar({**CENA, "estilo": "16-bits"}).composto.size == (256, 224)
    assert gerar({**CENA, "geracao": 8}).composto.size == (256, 240)
    assert gerar({**CENA, "geracao": 8, "tamanho": [96, 64]}).composto.size == (96, 64)


def test_geracao_vale_com_qualquer_tema():
    resultado = gerar({**CENA, "tamanho": [96, 64], "estilo": "metroidvania-noturno", "geracao": 8})
    assert resultado.cores <= set(CORES_NES)
    assert all(c.cores <= ANCORAS[8].cores_camada for c in resultado.camadas)


def test_16_bits_fica_na_grade_de_15_bits():
    cores = cores_rgb(gerar({**CENA, "tamanho": [96, 64], "estilo": "16-bits"}).composto)
    assert all(na_grade(c, "15-bits") == c for c in cores)


def test_geracao_errada_na_receita_e_erro_de_estilo():
    with pytest.raises(ValueError, match="estilo: geracao deve ser"):
        gerar({**CENA, "geracao": 3})


def test_preset_de_geracao_ida_e_volta():
    estilo = carregar_estilo("32-bits")
    assert estilo.geracao == ANCORAS[32] and estilo.para_dicionario()["geracao"] == 32
    assert "geracao" not in carregar_estilo("snes-diurno").para_dicionario()


@pytest.mark.parametrize("nome", ["snes-diurno", "metroidvania-noturno", "game-boy"])
def test_receitas_antigas_desenham_igual_ao_png_do_pacote(nome):
    receita = json.loads((EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
    novo = gerar(receita).composto.convert("RGBA")
    with Image.open(EXEMPLOS / f"{nome}.png") as guardado:
        assert novo.tobytes() == guardado.convert("RGBA").tobytes()


def test_png_guarda_a_geracao(tmp_path):
    gerar({**CENA, "cena": "nes", "estilo": "8-bits", "ampliar": 2, "saida": "tudo"}, pasta=tmp_path)
    assert marca_de_geracao(tmp_path / "nes.png") == 8
    assert marca_de_geracao(tmp_path / "nes-2x.png") == 8
    gerar({**CENA, "cena": "antiga", "tamanho": [96, 64]}, pasta=tmp_path)
    assert marca_de_geracao(tmp_path / "antiga.png") is None


def _cena_com_cores(quantas: int) -> Image.Image:
    imagem = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    for i in range(quantas):
        imagem.paste((i * 7 % 256, i * 3 % 256, 200, 255), (i % 8 * 8, i // 8 * 8, i % 8 * 8 + 8, i // 8 * 8 + 8))
    return imagem


def test_revisar_usa_o_limite_de_cores_da_geracao():
    cena = _cena_com_cores(40)
    assert regra(revisar(cena), "cores").estado == "ok"
    assert regra(revisar(cena, geracao=8), "cores").estado == "alerta"
    assert regra(revisar(cena, geracao="16-bits"), "cores").estado == "ok"


def test_revisar_le_a_geracao_do_png(tmp_path):
    cena = tmp_path / "cena.png"
    gravar_png(_cena_com_cores(40), cena, laco=False, geracao=8)
    assert regra(revisar(cena), "cores").estado == "alerta"
    assert regra(revisar(cena, geracao=32), "cores").estado == "ok"


def test_cores_por_camada():
    fundo, frente = _cena_com_cores(20), Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    assert not any(c.regra == "cores por camada" for c in revisar(fundo, camadas=[fundo, frente]).checagens)
    assert regra(revisar(fundo, camadas=[fundo, frente], geracao=8), "cores por camada").estado == "alerta"
    assert regra(revisar(fundo, camadas=[fundo, frente], geracao=32), "cores por camada").estado == "ok"
    assert regra(revisar(fundo, camadas=[fundo, frente], geracao="moderno"), "cores por camada").estado == "pulada"


def test_repeticao_por_geracao():
    assert _copias_minimas(None) == COPIAS and _copias_minimas(ANCORAS[32]) == COPIAS
    assert _copias_minimas(ANCORAS[8]) == _copias_minimas(geracao(16)) == COPIAS_LADRILHOS
    assert _lado_da_janela(None) == _lado_da_janela(ANCORAS[16]) == JANELA
    assert _lado_da_janela(ANCORAS[MODERNO]) == 2 * JANELA
    assert _copias_minimas(geracao(20)) == COPIAS_LADRILHOS and _copias_minimas(geracao(24)) == COPIAS
    assert _lado_da_janela(geracao(48)) == 18


def test_tabela_do_guia_bate_com_as_ancoras():
    guia = capitulo("geracoes")
    for numero, epoca in ANCORAS.items():
        rotulo = "moderno" if numero == MODERNO else str(numero)
        linha = re.search(rf"^\| {rotulo} \|[^\n]*", guia, re.MULTILINE).group(0)
        camada = "livre" if epoca.cores_camada is None else str(epoca.cores_camada)
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        assert celulas[1:5] == [f"{epoca.tamanho[0]}x{epoca.tamanho[1]}", str(epoca.passos), str(epoca.cores_cena),
                                camada], linha


def test_linha_de_comando_revisar_com_geracao(tmp_path, capsys):
    cena = tmp_path / "cena.png"
    _cena_com_cores(40).save(cena)
    main(["revisar", str(cena), "--geracao", "8"])
    assert "(limite 25)" in capsys.readouterr().out
