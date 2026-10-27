"""Cenário vivo: laço sem emenda no último quadro, folha e JSON coerentes, validação e tempo no `revisar`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from pixel_atelier import ErroDeReceita, cores_usadas, gerar, revisar, validar_receita
from pixel_atelier.__main__ import main
from pixel_atelier.animacao import (Animador, deslocamento_no_quadro, fator_do_pulso, folha, gravar_gif, movimentos,
                                    voltas_por_profundidade)
from pixel_atelier.estilo import carregar_estilo
from pixel_atelier.revisao import LACO_QUADROS, TEMPO_MAXIMO, TEMPO_MINIMO

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"

VIVA = {
    "cena": "viva",
    "tamanho": [96, 64],
    "estilo": "metroidvania-noturno",
    "animacao": {"quadros": 8, "duracao": 100, "voltas": 2},
    "camadas": [
        {"forma": "ceu"},
        {"forma": "nuvem", "tipo": "fiapo"},
        {"forma": "terreno", "nome": "longe", "profundidade": 0.7, "base": 0.6},
        {"forma": "raios", "intensidade": 0.5},
        {"forma": "nevoa", "centro": 0.7},
        {"forma": "terreno", "nome": "chao", "base": 0.85},
    ],
}


def erros_de(receita) -> list[str]:
    with pytest.raises(ErroDeReceita) as info:
        validar_receita(receita)
    return info.value.erros


def _sem_cor_no_vazio(imagem: Image.Image) -> bytes:
    """Bytes RGBA com o pixel transparente zerado: a cor dele não aparece."""
    imagem = imagem.convert("RGBA")
    zerada = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
    zerada.paste(imagem, mask=imagem.getchannel("A"))
    return zerada.tobytes()


# --- motor ---------------------------------------------------------------------------------------

def test_quadro_depois_do_ultimo_e_o_primeiro():
    r = validar_receita(VIVA)
    resultado = gerar(r)
    animador = Animador(r, [c.imagem for c in resultado.camadas])
    assert animador.quadro(r.animacao.quadros).tobytes() == resultado.quadros[0].tobytes()


def test_passo_do_ultimo_para_o_primeiro_e_igual_aos_outros():
    for voltas, largura, quadros in ((1, 96, 8), (3, 320, 48), (2, 640, 7)):
        posicoes = [deslocamento_no_quadro(voltas, largura, q, quadros) for q in range(quadros + 1)]
        passos = {(posicoes[q] - posicoes[q + 1]) % largura for q in range(quadros)}
        assert max(passos) - min(passos) <= 1, (voltas, largura, quadros)
        assert posicoes[quadros] == posicoes[0] == 0


def test_quadro_zero_e_o_composto_parado_e_todos_mudam():
    resultado = gerar(VIVA)
    assert resultado.quadros[0].tobytes() == resultado.composto.tobytes()
    assert len({q.tobytes() for q in resultado.quadros}) == len(resultado.quadros)


def test_quadros_na_paleta_e_com_alfa_cheio():
    resultado = gerar(VIVA)
    paleta = set(carregar_estilo("metroidvania-noturno").paleta)
    for q in resultado.quadros:
        assert cores_usadas(q) <= paleta
        assert set(q.getchannel("A").getextrema()) <= {0, 255}


def test_movimento_pela_profundidade_vento_e_pulso():
    resultado = gerar(VIVA)
    movimento = {c.nome: m for c, m in zip(resultado.camadas, resultado.movimentos)}
    assert movimento["ceu"].voltas == 0
    assert movimento["nuvem"].voltas == round(2 * (1 - 0.9)) + 1
    assert movimento["longe"].voltas == 1 and movimento["chao"].voltas == 2
    assert movimento["chao"].passo == 2 * 96 / 8
    assert movimento["raios"].pulsa and not movimento["chao"].pulsa
    assert fator_do_pulso(0, 8) == 1 and fator_do_pulso(8, 8) == 1 and fator_do_pulso(2, 8) < 1


def test_camada_sem_laco_fica_parada_e_sem_movimento_avisa():
    parada = {**VIVA, "laco": False, "camadas": [{"forma": "ceu"}, {"forma": "terreno"}]}
    resultado = gerar(parada)
    assert len({q.tobytes() for q in resultado.quadros}) == 1
    assert any("sem movimento" in a for a in resultado.avisos())


@pytest.mark.parametrize("nome", ["snes-diurno", "game-boy", "metroidvania-noturno"])
@pytest.mark.parametrize("tamanho", [[96, 64], [640, 360]])
def test_anima_em_qualquer_estilo_e_tamanho(nome, tamanho):
    receita = json.loads((EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
    r = validar_receita({**receita, "tamanho": tamanho, "ampliar": 1, "animacao": {"quadros": 4, "voltas": 1}})
    resultado = gerar(r)
    assert [q.size for q in resultado.quadros] == [tuple(tamanho)] * 4
    animador = Animador(r, [c.imagem for c in resultado.camadas])
    assert animador.quadro(4).tobytes() == resultado.quadros[0].tobytes()


PARALLAX = {**VIVA, "tamanho": [320, 180], "animacao": {"quadros": 96, "voltas": 4}, "camadas": [
    {"forma": "ceu"},
    {"forma": "terreno", "nome": "montanhas", "profundidade": 0.85, "base": 0.6},
    {"forma": "arvore", "nome": "pinheiros", "profundidade": 0.65, "base": 0.7},
    {"forma": "arvore", "nome": "mata", "profundidade": 0.35, "base": 0.8},
    {"forma": "terreno", "nome": "chao", "base": 0.9},
]}


def _voltas(receita) -> dict[str, int]:
    r = validar_receita(receita)
    return {c.nome: m.voltas for c, m in zip(r.camadas, movimentos(r.camadas, r.animacao, r.largura))}


def test_profundidades_diferentes_andam_em_velocidades_diferentes():
    assert _voltas(PARALLAX) == {"ceu": 0, "montanhas": 1, "pinheiros": 2, "mata": 3, "chao": 4}


def test_mais_profundidades_que_voltas_arredonda_e_nao_para_ninguem():
    assert voltas_por_profundidade([1.0, 0.95, 0.85, 0.65, 0.35, 0.0], 4) == {
        1.0: 0, 0.95: 1, 0.85: 1, 0.65: 1, 0.35: 3, 0.0: 4}
    assert voltas_por_profundidade([0.9, 0.0], 0) == {0.9: 0, 0.0: 0}


def test_profundidades_distintas_respeitam_a_ordem_e_o_teto():
    for voltas in range(1, 9):
        for quantas in range(1, voltas + 1):
            profundidades = [round(0.99 * i / quantas, 3) for i in range(quantas)]
            saida = voltas_por_profundidade(profundidades, voltas)
            em_ordem = [saida[p] for p in sorted(profundidades, reverse=True)]
            assert em_ordem == sorted(set(em_ordem)) and 1 <= em_ordem[0] and em_ordem[-1] <= voltas


def test_voltas_proprias_da_camada():
    camadas = [*PARALLAX["camadas"][:2], {**PARALLAX["camadas"][2], "voltas": 3}, *PARALLAX["camadas"][3:]]
    voltas = _voltas({**PARALLAX, "camadas": camadas})
    assert voltas["pinheiros"] == 3 and voltas["montanhas"] == 1 and voltas["mata"] == 3 and voltas["chao"] == 4
    parada = _voltas({**PARALLAX, "camadas": [{**c, "voltas": 0} for c in PARALLAX["camadas"]]})
    assert set(parada.values()) == {0}


def test_voltas_da_camada_invalidas():
    erros = erros_de({**VIVA, "camadas": [{"forma": "terreno", "voltas": 1.5}, {"forma": "terreno", "voltas": 17},
                                          {"forma": "terreno", "voltas": 2, "laco": False}]})
    assert any(e.startswith("camada 1 (terreno): voltas deve ser inteiro de 0 a 16, veio 1.5") for e in erros)
    assert any(e.startswith("camada 2 (terreno): voltas deve ser inteiro de 0 a 16, veio 17") for e in erros)
    assert any(e.startswith("camada 3 (terreno): voltas 2 pede laço") for e in erros)
    validar_receita({**VIVA, "camadas": [{"forma": "terreno", "voltas": 0, "laco": False}]})


def test_passo_por_quadro_suave_no_padrao():
    """No padrão, a camada mais perto anda 1/24 da largura por quadro e a mais lenta 1/96."""
    for tamanho in ([320, 180], [640, 360]):
        r = validar_receita({**PARALLAX, "tamanho": tamanho, "animacao": {}})
        passos = [m.passo for m in movimentos(r.camadas, r.animacao, r.largura) if m.voltas]
        assert max(passos) <= tamanho[0] / 24 + 1e-9


# --- saída ---------------------------------------------------------------------------------------

def test_grava_gif_folha_e_tempo_coerentes(tmp_path):
    resultado = gerar({**VIVA, "ampliar": 2}, pasta=tmp_path)
    dados = json.loads((tmp_path / "viva-quadros.json").read_text(encoding="utf-8"))
    assert dados == {"cena": "viva", "folha": "viva-quadros.png", "quadros": 8, "duracao": 100, "quadro": [96, 64],
                     "colunas": 8, "linhas": 1, "laco": True}
    with Image.open(tmp_path / dados["folha"]) as aberta:
        lida = aberta.convert("RGBA")
    assert lida.size == (96 * 8, 64)
    assert lida.tobytes() == folha(resultado.quadros, dados["colunas"]).tobytes()
    with Image.open(tmp_path / "viva-2x.gif") as gif:
        quadros_gif = [(_sem_cor_no_vazio(q), q.info["duration"]) for q in ImageSequence.Iterator(gif)]
    assert [d for _, d in quadros_gif] == [100] * 8
    assert [q for q, _ in quadros_gif] == [_sem_cor_no_vazio(q.resize((192, 128), Image.Resampling.NEAREST))
                                          for q in resultado.quadros]
    texto = resultado.resumo()
    assert "animação: 8 quadros de 100 ms (0,8 s por laço), voltas 2" in texto
    assert "movimento: ceu parada, nuvem 1 volta (12,0 px/quadro)" in texto
    assert "raios pulsa e dá 1 volta (12,0 px/quadro)" in texto


def test_gif_com_transparencia_guarda_o_alfa(tmp_path):
    sem_ceu = {**VIVA, "camadas": VIVA["camadas"][1:]}
    resultado = gerar(sem_ceu, pasta=tmp_path)
    with Image.open(tmp_path / "viva.gif") as gif:
        lidos = [_sem_cor_no_vazio(q) for q in ImageSequence.Iterator(gif)]
    assert lidos == [_sem_cor_no_vazio(q) for q in resultado.quadros]


def test_folha_quebra_linha_em_4096():
    r = validar_receita({**VIVA, "tamanho": [640, 360], "animacao": {"quadros": 20}})
    resultado = gerar(r)
    imagem = folha(resultado.quadros, 6)
    assert imagem.size == (640 * 6, 360 * 4)


def test_receita_sem_animacao_nao_grava_animacao(tmp_path):
    sem = {k: v for k, v in VIVA.items() if k != "animacao"}
    resultado = gerar(sem, pasta=tmp_path)
    assert resultado.quadros == [] and resultado.para_dicionario()["animacao"] is None
    assert not list(tmp_path.glob("*.gif")) and not list(tmp_path.glob("*-quadros.*"))


def test_exemplo_animado_valida():
    r = validar_receita(EXEMPLOS / "snes-diurno-animado.json")
    assert r.animacao is not None and r.animacao.quadros == 96


# --- validação -----------------------------------------------------------------------------------

def test_animacao_vazia_usa_os_padroes():
    a = validar_receita({**VIVA, "animacao": {}}).animacao
    assert (a.quadros, a.duracao, a.voltas) == (96, 100, 4)


@pytest.mark.parametrize("tamanho, quadros, voltas", [([320, 180], 96, 4), ([640, 360], 96, 4), ([1280, 720], 96, 4),
                                                     ([1920, 1080], 42, 1)])
def test_padrao_cabe_na_memoria_e_voltas_seguem_os_quadros(tamanho, quadros, voltas):
    a = validar_receita({**VIVA, "tamanho": tamanho, "animacao": {}}).animacao
    assert (a.quadros, a.voltas) == (quadros, voltas)
    assert validar_receita({**VIVA, "animacao": {"quadros": 48}}).animacao.voltas == 2
    assert validar_receita({**VIVA, "animacao": {"quadros": 240}}).animacao.voltas == 4


def test_animacao_invalida_junta_os_erros():
    erros = erros_de({**VIVA, "animacao": {"quadros": 1, "duracao": "rapido", "voltas": -1, "velocidade": 2}})
    assert any("'velocidade' não existe em animacao" in e for e in erros)
    assert any(e.startswith("animacao.quadros deve ser inteiro de 2 a 256") for e in erros)
    assert any(e.startswith("animacao.duracao deve ser inteiro") for e in erros)
    assert any(e.startswith("animacao.voltas deve ser inteiro de 0 a 16") for e in erros)
    assert any("animacao deve ser um objeto" in e for e in erros_de({**VIVA, "animacao": 12}))


def test_duracao_anda_de_10_em_10():
    erros = erros_de({**VIVA, "animacao": {"duracao": 85}})
    assert erros == ["animacao.duracao anda de 10 em 10 ms (o GIF guarda centésimos), veio 85; use 80 ou 90"]


def test_quadros_acima_do_limite_de_memoria_sao_recusados():
    erros = erros_de({**VIVA, "tamanho": [1920, 1080], "animacao": {"quadros": 48}})
    assert erros == ["48 quadros de 1920x1080 passam do limite de memória da animação (42 quadros nesse tamanho); "
                     "reduza animacao.quadros ou tamanho"]
    validar_receita({**VIVA, "tamanho": [1280, 720], "animacao": {"quadros": 96}})


def test_folha_que_passa_do_lado_maximo_segue_em_paginas(tmp_path, monkeypatch):
    monkeypatch.setattr("pixel_atelier.receita.AMPLIADO_MAXIMO", 200)
    resultado = gerar(VIVA, pasta=tmp_path)
    dados = json.loads((tmp_path / "viva-quadros.json").read_text(encoding="utf-8"))
    assert dados == {"cena": "viva", "quadros": 8, "duracao": 100, "quadro": [96, 64], "colunas": 2, "linhas": 3,
                     "laco": True, "folhas": ["viva-quadros-1.png", "viva-quadros-2.png"], "quadros_por_folha": 6}
    assert not (tmp_path / "viva-quadros.png").exists()
    with Image.open(tmp_path / "viva-quadros-1.png") as primeira, Image.open(tmp_path / "viva-quadros-2.png") as segunda:
        assert primeira.size == (192, 192) and segunda.size == (192, 64)
        assert primeira.convert("RGBA").tobytes() == folha(resultado.quadros[:6], 2).tobytes()
        assert segunda.convert("RGBA").tobytes() == folha(resultado.quadros[6:], 2).tobytes()
    for pagina in ("viva-quadros-1.png", "viva-quadros-2.png"):
        revisao = revisar(tmp_path / pagina)
        tempo = next(c for c in revisao.checagens if c.regra == "tempo")
        assert tempo.estado == "ok" and tempo.detalhe.startswith("8 quadros de 100 ms"), pagina
        laco = next(c for c in revisao.checagens if c.regra == "laço dos quadros")
        assert laco.estado == "ok", pagina


# --- revisar e linha de comando ------------------------------------------------------------------

def test_revisar_confere_o_tempo_no_gif_e_na_folha(tmp_path):
    gerar({**VIVA, "saida": "tudo"}, pasta=tmp_path)
    for arquivo in ("viva.gif", "viva-quadros.png"):
        revisao = revisar(tmp_path / arquivo)
        tempo = next(c for c in revisao.checagens if c.regra == "tempo")
        assert tempo.estado == "ok" and tempo.detalhe.startswith("8 quadros de 100 ms"), arquivo
        assert (revisao.largura, revisao.altura) == (96, 64) and len(revisao.camadas) == 6
    parada = next(c for c in revisar(tmp_path / "viva.png").checagens if c.regra == "tempo")
    assert parada.estado == "pulada"


@pytest.mark.parametrize("duracao, alerta", [(TEMPO_MINIMO - 10, "abaixo de 20 ms"),
                                              (TEMPO_MAXIMO + 10, "acima de 300 ms"),
                                              (TEMPO_MINIMO, None), (TEMPO_MAXIMO, None)])
def test_revisar_alerta_tempo_fora_da_faixa(tmp_path, duracao, alerta):
    gerar({**VIVA, "animacao": {"quadros": 4, "duracao": duracao}}, pasta=tmp_path)
    tempo = next(c for c in revisar(tmp_path / "viva.gif").checagens if c.regra == "tempo")
    if alerta is None:
        assert tempo.estado == "ok"
    else:
        assert tempo.estado == "alerta" and alerta in tempo.detalhe and "guia animacao" in tempo.detalhe


def test_linha_de_comando_gera_animacao(tmp_path, capsys):
    receita = tmp_path / "viva.json"
    receita.write_text(json.dumps(VIVA), encoding="utf-8")
    assert main(["gerar", str(receita)]) == 0
    saida = capsys.readouterr().out
    assert "animação: 8 quadros" in saida and "viva-quadros.json" in saida
    assert main(["revisar", str(tmp_path / "viva.gif")]) == 0
    assert "ok tempo: 8 quadros de 100 ms" in capsys.readouterr().out


def _laco_dos_quadros(arquivo):
    return next(c for c in revisar(arquivo).checagens if c.regra == "laço dos quadros")


def test_revisar_confere_a_volta_do_ultimo_quadro_para_o_primeiro(tmp_path):
    receita = json.loads((EXEMPLOS / "snes-diurno-animado.json").read_text(encoding="utf-8"))
    resultado = gerar({**receita, "ampliar": 1, "saida": "tudo"}, pasta=tmp_path)
    for arquivo in ("snes-diurno-animado.gif", "snes-diurno-animado-quadros.png"):
        laco = _laco_dos_quadros(tmp_path / arquivo)
        assert laco.estado == "ok" and f"máx {LACO_QUADROS:g}x" in laco.detalhe, arquivo
    de_fora = tmp_path / "de-fora.gif"
    resultado.quadros[0].save(de_fora, save_all=True, append_images=resultado.quadros[1:], duration=100, loop=0)
    assert _laco_dos_quadros(de_fora).estado == "ok"
    cortado = tmp_path / "cortado.gif"
    gravar_gif(resultado.quadros[:24], cortado, 100, True)
    laco = _laco_dos_quadros(cortado)
    assert laco.estado == "alerta" and "pula no fim do laço" in laco.detalhe


def test_revisar_pula_a_volta_no_gif_que_toca_uma_vez(tmp_path):
    resultado = gerar({**VIVA, "animacao": {"quadros": 8}})
    uma_vez = tmp_path / "uma-vez.gif"
    resultado.quadros[0].save(uma_vez, save_all=True, append_images=resultado.quadros[1:4], duration=100)
    assert _laco_dos_quadros(uma_vez).estado == "pulada"
    gerar(VIVA, pasta=tmp_path)
    assert all(c.regra != "laço dos quadros" for c in revisar(tmp_path / "viva.png").checagens)
