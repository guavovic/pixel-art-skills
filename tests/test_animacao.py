"""Cenário vivo: laço sem emenda no último quadro, folha e JSON coerentes, validação e tempo no `revisar`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from pixel_atelier import ErroDeReceita, cores_usadas, gerar, revisar, validar_receita
from pixel_atelier.__main__ import main
from pixel_atelier.animacao import Animador, deslocamento_no_quadro, fator_do_pulso, folha
from pixel_atelier.estilo import carregar_estilo
from pixel_atelier.revisao import TEMPO_MAXIMO, TEMPO_MINIMO

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
    assert "movimento: ceu parada, nuvem 1 volta" in texto and "raios pulsa e dá 1 volta" in texto


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
    assert r.animacao is not None and r.animacao.quadros == 48


# --- validação -----------------------------------------------------------------------------------

def test_animacao_vazia_usa_os_padroes():
    a = validar_receita({**VIVA, "animacao": {}}).animacao
    assert (a.quadros, a.duracao, a.voltas) == (48, 100, 2)


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


def test_folha_acima_de_4096_e_recusada():
    erros = erros_de({**VIVA, "tamanho": [1280, 720], "animacao": {"quadros": 48}})
    assert erros == ["a folha de 48 quadros ficaria com 3840x11520 pixels e o máximo é 4096 por lado; "
                     "reduza animacao.quadros ou tamanho"]
    validar_receita({**VIVA, "tamanho": [1280, 720], "animacao": {"quadros": 15}})


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
