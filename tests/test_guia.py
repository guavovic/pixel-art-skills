"""Guia de pixel art: índice e capítulos curtos, e todo limiar do `revisar` explicado no guia."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pixel_atelier import gerar, revisao, revisar
from pixel_atelier.__main__ import main
from pixel_atelier.guia import capitulo, capitulos


EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"
CAPITULOS = {"fundamentos", "cor", "angulo", "escala", "luz", "pontilhado", "animacao", "composicao", "estilos",
             "erros"}


def test_indice_aponta_para_cada_capitulo():
    assert set(capitulos()) == CAPITULOS
    indice = capitulo()
    assert all(f"`{nome}`" in indice for nome in CAPITULOS)


def test_capitulos_curtos_com_titulo():
    for nome in CAPITULOS:
        texto = capitulo(nome)
        assert texto.startswith("# ") and len(texto) < 4500, nome  # barato em token: um capítulo por vez


def test_nome_desconhecido_lista_os_que_existem():
    assert capitulo("COR.md") == capitulo("cor")
    with pytest.raises(KeyError, match="há: angulo, animacao"):
        capitulo("../indice")


LIMIARES = ("CORES_SPRITE", "CORES_CENA", "QUASE_IGUAL", "CONTRASTE_CAMADAS", "CONTRASTE_FRENTE", "SOME", "SOME_MAX",
            "FAIXA_FUNDO", "FAIXA_SPRITE", "SOLTOS_MAX", "PILLOW_MIOLO", "PILLOW_LADOS", "SERRILHADO_MAX", "LADRILHO",
            "LADRILHOS_FORA", "JANELA", "COPIAS", "ATMOSFERA", "LACO_EMENDA")


def _escrito(nome: str, valor: float) -> set[str]:
    """Como o número aparece no guia: inteiro, porcentagem ou decimal com vírgula."""
    if isinstance(valor, int):
        return {str(valor)}
    if nome.endswith("_MAX"):
        return {f"{valor * 100:g}%".replace(".", ",")}
    return {f"{valor:.2f}".replace(".", ","), f"{valor:g}".replace(".", ",")}


def test_cada_limiar_do_revisar_esta_no_guia():
    """Mudou o número no revisar, muda no guia: toda linha que cita a constante traz o valor."""
    guia = "\n".join(capitulo(nome) for nome in sorted(CAPITULOS))
    for nome in LIMIARES:
        linhas = re.findall(rf"[^\n]*`{nome}`[^\n]*", guia)
        assert linhas, f"{nome} não aparece no guia"
        for linha in linhas:
            assert any(re.search(rf"(?<![\d,]){re.escape(n)}(?![\d,]\d)", linha)
                       for n in _escrito(nome, getattr(revisao, nome))), (nome, linha)


@pytest.mark.parametrize("nome", ["metroidvania-noturno", "snes-diurno"])
def test_exemplos_do_pacote_passam_sem_alerta(nome, tmp_path):
    receita = json.loads((EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
    gerar({**receita, "saida": "tudo", "ampliar": 1}, pasta=tmp_path)
    resultado = revisar(tmp_path / f"{nome}.png", laco=True)  # as cenas do pacote dão a volta
    assert len(resultado.camadas) == len(receita["camadas"])
    assert not resultado.alertas(), resultado.resumo()


def test_linha_de_comando_guia(capsys):
    assert main(["guia"]) == 0 and capsys.readouterr().out.startswith("# Guia de pixel art")
    assert main(["guia", "luz"]) == 0 and "Pillow shading" in capsys.readouterr().out
    assert main(["guia", "nada"]) == 2 and "não existe" in capsys.readouterr().err
