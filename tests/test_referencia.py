"""`ref`: estilo tirado de imagens feitas no teste, com paleta e rampas conhecidas."""
from __future__ import annotations

import json

import pytest
from PIL import Image

from pixel_atelier import (ampliar, carregar_estilo, cores_usadas, descrever_estilos, extrair_estilo, gerar, listar_estilos,
                           pasta_de_presets, ref)
from pixel_atelier.cor import luminancia, rgb_para_hex
from pixel_atelier.estilo import validar_nome_de_estilo
from pixel_atelier.__main__ import main

CEU = [(40, 80, 180), (80, 130, 220), (140, 180, 240)]  # do topo ao horizonte
VERDE = [(20, 60, 30), (40, 110, 40), (80, 160, 60), (150, 210, 100)]
QUENTE = [(70, 40, 20), (130, 80, 40), (190, 130, 70)]
CINZA = [(60, 60, 64), (110, 110, 115), (160, 160, 165)]
CLARO = [(235, 240, 245), (255, 255, 255)]
TODAS = CEU + VERDE + QUENTE + CINZA + CLARO


def hexes(cores) -> list[str]:
    return [rgb_para_hex(c) for c in cores]


def cena() -> Image.Image:
    """64x48 opaca: céu em faixas de 5, 5 e 6 linhas no terço de cima, verdes no meio, o resto embaixo."""
    imagem = Image.new("RGBA", (64, 48))
    for i, (y0, y1) in enumerate(((0, 5), (5, 10), (10, 16))):
        imagem.paste(CEU[i] + (255,), (0, y0, 64, y1))
    for i, cor in enumerate(VERDE):
        imagem.paste(cor + (255,), (i * 16, 16, i * 16 + 16, 32))
    for i, cor in enumerate(QUENTE + CINZA + CLARO):
        imagem.paste(cor + (255,), (i * 8, 32, i * 8 + 8, 48))
    return imagem


def foto() -> Image.Image:
    """Degradê com centenas de milhares de cores: nada de pixel art."""
    imagem = Image.new("RGB", (600, 400))
    imagem.putdata([(x * 255 // 600, y * 255 // 400, (x * y) % 256) for y in range(400) for x in range(600)])
    return imagem


# --- paleta, rampas e pixel ------------------------------------------------------------------------

def test_paleta_conhecida_volta_exata():
    r = extrair_estilo(cena(), "sintetica")
    assert set(r.paleta) == set(TODAS) and r.cores_na_imagem == len(TODAS)
    assert r.paleta == sorted(TODAS, key=lambda c: (luminancia(c), c))  # do escuro ao claro
    assert sorted(r.estilo["paleta"]) == sorted(hexes(TODAS))
    assert r.escala == 1 and r.tamanho == (64, 48) and not r.avisos


def test_rampas_vao_para_os_papeis_ordenadas_por_valor():
    r = extrair_estilo(cena(), "sintetica")
    rampas = r.estilo["rampas"]
    assert rampas["folha"] == rampas["grama"] == hexes(VERDE)
    assert rampas["terra"] == rampas["tronco"] == hexes(QUENTE)
    assert rampas["pedra"] == hexes(CINZA)
    assert rampas["nuvem"] == rampas["nevoa"] == rampas["neve"] == hexes(CLARO)
    for rampa in r.rampas:
        if rampa.papeis != ("ceu",):
            valores = [luminancia(c) for c in rampa.cores]
            assert valores == sorted(valores) and len(set(valores)) == len(valores)
    assert r.estilo["ceu"] == hexes(CEU) and r.estilo["atmosfera"] == rgb_para_hex(CEU[-1])
    assert r.luz == (255, 255, 255) and r.contorno == min(TODAS, key=luminancia)
    assert r.da_base == ["cristal"]  # sem roxo na imagem


def test_rampa_longa_fica_com_seis_cores_espacadas():
    verdes = [(10 + 8 * i, 60 + 15 * i, 20 + 6 * i) for i in range(10)]
    imagem = Image.new("RGBA", (40, 40), (255, 255, 255, 255))
    for i, cor in enumerate(verdes):
        imagem.paste(cor + (255,), (i * 4, 0, i * 4 + 4, 40))
    imagem.putpixel((0, 0), (255, 255, 255, 255))  # bloco 1x
    folha = extrair_estilo(imagem, "verdes").estilo["rampas"]["folha"]
    assert len(folha) == 6 and folha[0] == rgb_para_hex(verdes[0]) and folha[-1] == rgb_para_hex(verdes[-1])


def test_pixel_ampliado_detectado_e_lido_no_tamanho_real():
    r = extrair_estilo(ampliar(cena(), 3), "ampliada")
    assert r.escala == 3 and r.tamanho == (64, 48) and r.tamanho_original == (192, 144)
    assert set(r.paleta) == set(TODAS)
    assert r.estilo["referencia"]["pixel"] == 3
    assert "ampliada 3x (pixel real 64x48)" in r.resumo()


def test_sprite_sem_ceu_e_sem_contar_o_transparente():
    sprite = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for i, cor in enumerate(VERDE):
        sprite.paste(cor + (255,), (2 + i * 4, 3, 6 + i * 4, 17))
    r = extrair_estilo(sprite, "sprite")
    assert set(r.paleta) == set(VERDE)
    assert "ceu" not in r.estilo and r.atmosfera is None
    assert r.da_base[-2:] == ["ceu", "atmosfera"]


def test_pixel_art_com_cores_demais_reduz_para_o_limite():
    r = extrair_estilo(cena(), "oito", cores=8)
    assert len(r.paleta) <= 8 and r.cores_na_imagem == len(TODAS)
    assert any("paleta reduzida" in a for a in r.avisos)


def test_foto_e_reduzida_e_quantizada_com_aviso():
    r = extrair_estilo(foto(), "foto")
    assert len(r.paleta) <= 32 and max(r.tamanho) <= 256
    assert r.avisos and "não parece pixel art" in r.avisos[0] and "reduzida para" in r.avisos[0]
    assert extrair_estilo(foto(), "foto").estilo == r.estilo  # determinístico


def test_resumo_curto_em_texto():
    texto = ref(cena(), "resumo-teste").resumo()
    linhas = texto.splitlines()
    assert linhas[0].startswith("preset resumo-teste gravado em ") and linhas[0].endswith(", base snes-diurno")
    assert linhas[1:4] == ["referência imagem: 64x48",
                           "paleta: 15 cores (exatas da imagem)",
                           "valor: 0.18 a 1.00, faixa 0.74 (p5 a p95)"]
    assert "  folha, grama: 4 cores #143c1e > #96d264, valor 0.19 a 0.74, passo 0.18" in linhas
    assert "da base, só com cores da paleta: cristal" in linhas
    assert len(linhas) < 15


# --- preset ----------------------------------------------------------------------------------------

def test_preset_salvo_funciona_no_gerar():
    r = ref(cena(), "ref-cena")
    assert r.destino == pasta_de_presets() / "ref-cena.json"
    dados = json.loads(r.destino.read_text(encoding="utf-8"))
    assert "base" not in dados and dados["sombreamento"] == "faixas"  # o que a imagem não diz veio do base
    assert set(carregar_estilo("ref-cena").paleta) == set(TODAS)
    resultado = gerar({"tamanho": [96, 64], "estilo": "ref-cena",
                       "camadas": [{"forma": "ceu"}, {"forma": "arvore", "profundidade": 0.5},
                                   {"forma": "cristal"}, {"forma": "terreno", "base": 0.85}]})
    assert cores_usadas(resultado.composto) <= set(TODAS)  # até o cristal, que veio do base


def test_base_escolhida_completa_o_que_falta():
    ref(cena(), "ref-gb", base="game-boy")
    estilo = carregar_estilo("ref-gb")
    assert estilo.sombreamento == "pontilhado" and estilo.largura_faixa == 1


def test_nome_invalido_reservado_ou_repetido_e_recusado():
    with pytest.raises(ValueError, match="minúsculo"):
        ref(cena(), "Meu Estilo")
    with pytest.raises(ValueError, match="vem com o pacote"):
        ref(cena(), "snes-diurno")
    with pytest.raises(KeyError, match="não existe"):
        ref(cena(), "sem-base", base="nada")
    ref(cena(), "repetido")
    with pytest.raises(ValueError, match="já existe"):
        ref(cena(), "repetido")
    ref(cena(), "repetido", sobrescrever=True)


def test_preset_copiado_com_nome_fora_do_padrao_diz_como_renomear():
    copiado = pasta_de_presets() / "Meu_Estilo.json"
    pasta_de_presets().mkdir(parents=True, exist_ok=True)
    copiado.write_text(json.dumps({"base": "snes-diurno", "nome": "Meu_Estilo"}), encoding="utf-8")
    try:
        dica = "renomeie o arquivo para meu-estilo.json e use \"meu-estilo\""
        with pytest.raises(ValueError, match="Meu_Estilo.json .* tem nome fora do padrão") as erro:
            carregar_estilo("Meu_Estilo")
        assert dica in str(erro.value)
        with pytest.raises(KeyError) as erro:
            carregar_estilo("meu-estilo")  # o nome certo, antes de renomear
        assert dica in str(erro.value)
        assert "Meu_Estilo" not in listar_estilos()
        assert f"aviso: o preset Meu_Estilo.json em {pasta_de_presets().as_posix()}" in descrever_estilos()
        with pytest.raises(ValueError) as erro:
            carregar_estilo("../Meu_Estilo")  # nome com caminho nem é procurado na pasta
        assert "renomeie" not in str(erro.value)
        copiado.rename(pasta_de_presets() / "meu-estilo.json")
        assert carregar_estilo("meu-estilo").nome == "Meu_Estilo" and "meu-estilo" in listar_estilos()
    finally:
        for arquivo in (copiado, pasta_de_presets() / "meu-estilo.json"):
            arquivo.unlink(missing_ok=True)


def test_base_invalida_tem_a_mesma_mensagem_do_gerar_e_do_revisar():
    for base in ("../fora", "Snes_Diurno", "pasta/estilo"):
        with pytest.raises(ValueError) as erro_ref:
            extrair_estilo(cena(), "x", base=base)
        with pytest.raises(ValueError) as erro_estilo:
            validar_nome_de_estilo(base, "base")
        assert str(erro_ref.value) == str(erro_estilo.value)
        assert str(erro_ref.value).startswith(f"nome de base {base!r} inválido: use o nome de um preset")


def test_preset_copiado_com_nome_fora_do_padrao_diz_como_renomear():
    copiado = pasta_de_presets() / "Meu_Estilo.json"
    pasta_de_presets().mkdir(parents=True, exist_ok=True)
    copiado.write_text(json.dumps({"base": "snes-diurno", "nome": "Meu_Estilo"}), encoding="utf-8")
    try:
        dica = "renomeie o arquivo para meu-estilo.json e use \"meu-estilo\""
        with pytest.raises(ValueError, match="Meu_Estilo.json .* tem nome fora do padrão") as erro:
            carregar_estilo("Meu_Estilo")
        assert dica in str(erro.value)
        with pytest.raises(KeyError) as erro:
            carregar_estilo("meu-estilo")  # o nome certo, antes de renomear
        assert dica in str(erro.value)
        assert "Meu_Estilo" not in listar_estilos()
        assert f"aviso: o preset Meu_Estilo.json em {pasta_de_presets().as_posix()}" in descrever_estilos()
        with pytest.raises(ValueError) as erro:
            carregar_estilo("../Meu_Estilo")  # nome com caminho nem é procurado na pasta
        assert "renomeie" not in str(erro.value)
        copiado.rename(pasta_de_presets() / "meu-estilo.json")
        assert carregar_estilo("meu-estilo").nome == "Meu_Estilo" and "meu-estilo" in listar_estilos()
    finally:
        for arquivo in (copiado, pasta_de_presets() / "meu-estilo.json"):
            arquivo.unlink(missing_ok=True)


def test_imagem_sem_pixel_visivel():
    with pytest.raises(ValueError, match="nenhum pixel visível"):
        extrair_estilo(Image.new("RGBA", (16, 16)), "vazia")


# --- linha de comando ------------------------------------------------------------------------------

def test_linha_de_comando_grava_e_responde_em_texto(tmp_path, capsys):
    arquivo = tmp_path / "Floresta Úmida-3x.png"
    ampliar(cena(), 3).save(arquivo)
    assert main(["ref", str(arquivo)]) == 0  # sem --nome: o do arquivo
    saida = capsys.readouterr().out
    assert saida.startswith("preset floresta-umida-3x gravado em ") and "ampliada 3x" in saida
    assert main(["ref", str(arquivo), "--nome", "cli-ref", "--cores", "8"]) == 0
    assert "paleta reduzida" in capsys.readouterr().out
    assert main(["ref", str(arquivo), "--nome", "Ruim"]) == 2
    assert "preset não gravado: nome de preset" in capsys.readouterr().err
    assert main(["ref", str(tmp_path / "nada.png"), "--nome", "nada"]) == 2
