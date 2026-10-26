"""`ref`: estilo tirado de imagens feitas no teste, com paleta e rampas conhecidas."""
from __future__ import annotations

import json

import pytest
from PIL import Image

from pixel_atelier import (PAPEIS, ampliar, carregar_estilo, cores_usadas, descrever_estilos, extrair_estilo, gerar,
                           listar_estilos, pasta_de_presets, ref)
from pixel_atelier.cor import hex_para_rgb, luminancia, rgb_para_hex
from pixel_atelier.estilo import validar_nome_de_estilo
from pixel_atelier.referencia import DIVIDIR_PAR, ORDEM
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
    rampas = extrair_estilo(imagem, "verdes").estilo["rampas"]
    assert len(rampas["folha"]) == len(rampas["grama"]) == 6
    assert rampas["folha"][0] == rgb_para_hex(verdes[0]) and rampas["grama"][-1] == rgb_para_hex(verdes[-1])


def colunas(cores, altura=32, largura=4) -> Image.Image:
    """Uma coluna de cada cor; a 1ª tem um pixel da 2ª, para a imagem ficar em bloco 1x."""
    imagem = Image.new("RGBA", (len(cores) * largura, altura))
    for i, cor in enumerate(cores):
        imagem.paste(cor + (255,), (i * largura, 0, (i + 1) * largura, altura))
    imagem.putpixel((0, 0), cores[1] + (255,))
    return imagem


def media_de_valor(rampa) -> float:
    return sum(luminancia(hex_para_rgb(c)) for c in rampa) / len(rampa)


def test_familia_dominante_reparte_pelo_valor_os_papeis_vazios():
    # quase tudo azul, do quase preto ao claro (como uma cena noturna), e um branco só
    azuis = [(8 + 12 * i, 16 + 16 * i, 40 + 18 * i) for i in range(12)]
    r = extrair_estilo(colunas(azuis + [(250, 252, 255)]), "noite")
    rampas = r.estilo["rampas"]
    assert set(rampas) == set(PAPEIS) and not set(PAPEIS) & set(r.da_base)  # nada vem da base
    assert r.dominante == ("azul", 12, list(ORDEM))
    for papel, rampa in rampas.items():
        assert len(rampa) >= 2 and {hex_para_rgb(c) for c in rampa} <= set(azuis), papel
    # cada papel num trecho de valor: tronco no escuro, neve no claro
    assert media_de_valor(rampas["tronco"]) < media_de_valor(rampas["pedra"]) < media_de_valor(rampas["neve"])
    assert rampas["folha"] != rampas["grama"] and rampas["terra"] != rampas["tronco"]
    assert "família azul domina (12 de 13 cores), repartida pelo valor em: folha, grama" in r.resumo()


def test_familia_dominante_tira_o_tom_fora_do_matiz_papel_a_papel():
    # noite azul com um verde-água no meio dos valores (o da grama da metroidvania-noturno)
    azuis = [(8 + 12 * i, 16 + 16 * i, 40 + 18 * i) for i in range(12)]
    verde_agua = (44, 138, 132)
    r = extrair_estilo(colunas(azuis[:6] + [verde_agua] + azuis[6:]), "noite")
    assert r.dominante is not None and r.dominante[0] == "azul"
    assert rgb_para_hex(verde_agua) not in r.estilo["rampas"]["pedra"]
    em_alguma = any(rgb_para_hex(verde_agua) in rampa for rampa in r.estilo["rampas"].values())
    assert em_alguma or r.fora_do_matiz == [verde_agua]


def test_familia_dominante_centra_a_terra_na_cor_do_chao():
    # noite azul com o chão quase preto na faixa de baixo, como a metroidvania-noturno
    azuis = [(8 + 12 * i, 16 + 16 * i, 40 + 18 * i) for i in range(12)]
    imagem = colunas(azuis + [(250, 252, 255)])
    imagem.paste(azuis[2] + (255,), (0, 28, imagem.width, 32))
    r = extrair_estilo(imagem, "noite")
    terra = r.estilo["rampas"]["terra"]
    assert terra == hexes(azuis[:5])  # o chão bem no meio, que é o tom base
    assert media_de_valor(terra) < media_de_valor(r.estilo["rampas"]["pedra"])


def test_terra_centrada_no_chao_tambem_fora_da_familia_dominante():
    marrons = [(70, 35, 20), (100, 55, 30), (130, 85, 45), (160, 115, 65), (190, 150, 90)]
    imagem = colunas(marrons + VERDE + CINZA + [(255, 255, 255)])
    imagem.paste(marrons[1] + (255,), (0, 28, imagem.width, 32))
    r = extrair_estilo(imagem, "chao")
    assert r.dominante is None and r.estilo["rampas"]["terra"] == hexes(marrons[:3])


def test_paleta_reduzida_guarda_cores_de_cada_familia():
    # muitos verdes e poucos marrons escuros: o corte de mediana da imagem toda juntava os marrons
    verdes = [(20 + 4 * i, 60 + 5 * i, 30 + 2 * i) for i in range(30)]
    marrons = [(90, 50, 30), (105, 60, 35), (120, 72, 42)]
    preto, branco = (10, 10, 12), (255, 255, 255)
    r = extrair_estilo(colunas(verdes + marrons + CINZA + [preto, branco]), "familias", cores=12)
    assert len(r.paleta) <= 12
    assert r.estilo["rampas"]["terra"] == hexes(marrons)
    assert r.contorno == preto and r.luz == branco  # o contorno e a luz ficam exatos


def test_sem_familia_dominante_papel_vazio_continua_vindo_da_base():
    r = extrair_estilo(cena(), "sintetica")
    assert r.dominante is None and r.da_base == ["cristal"]


def test_par_de_papeis_ganha_rampas_diferentes_com_cores_suficientes():
    verdes = [(20 + 14 * i, 60 + 18 * i, 30 + 10 * i) for i in range(DIVIDIR_PAR)]
    vermelhos = [(120, 30, 20), (200, 60, 40)]  # para o verde não dominar
    rampas = extrair_estilo(colunas(verdes + vermelhos + [(255, 255, 255)]), "par").estilo["rampas"]
    assert rampas["folha"] != rampas["grama"]
    assert rampas["folha"][0] == rgb_para_hex(verdes[0]) and rampas["grama"][-1] == rgb_para_hex(verdes[-1])
    assert media_de_valor(rampas["folha"]) < media_de_valor(rampas["grama"])  # folha no trecho mais escuro
    assert all(len(rampas[p]) >= 2 for p in ("folha", "grama"))
    poucos = extrair_estilo(colunas(verdes[:DIVIDIR_PAR - 1] + vermelhos + [(255, 255, 255)]), "par").estilo["rampas"]
    assert poucos["folha"] == poucos["grama"]  # com poucas cores, a mesma rampa


def test_tom_fora_do_matiz_sai_da_rampa_e_fica_na_paleta():
    # o caso da quantização da snes-diurno: marrons e um rosa caídos na família quente
    marrons, rosa = [(110, 70, 35), (130, 85, 45), (146, 106, 60)], (193, 126, 149)
    r = extrair_estilo(colunas(marrons + [rosa] + VERDE[:2] + CINZA[:2] + [(255, 255, 255)]), "rosa")
    assert r.dominante is None
    assert rgb_para_hex(rosa) not in r.estilo["rampas"]["terra"] + r.estilo["rampas"]["tronco"]
    assert r.estilo["rampas"]["terra"] == hexes(marrons)
    assert rgb_para_hex(rosa) in r.estilo["paleta"] and r.fora_do_matiz == [rosa]
    assert f"fora do matiz da família, só na paleta: {rgb_para_hex(rosa)}" in r.resumo()


def test_rampa_que_muda_de_matiz_aos_poucos_fica_inteira():
    # verdes do escuro ao verde-amarelo (os da snes-diurno) e os quatro do game-boy
    snes = ["#245a31", "#3f7852", "#3c8c34", "#639380", "#589c5f", "#72b182", "#7bc064", "#91c69a", "#b9e1ae",
            "#bae884"]
    game_boy = ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"]
    for cores in (snes, game_boy):
        r = extrair_estilo(colunas([hex_para_rgb(c) for c in cores]), "verdes")
        verdes = r.estilo["rampas"]["folha"] + r.estilo["rampas"]["grama"]
        assert not r.fora_do_matiz and set(verdes) <= set(cores)
        por_valor = sorted(cores, key=lambda c: luminancia(hex_para_rgb(c)))
        assert por_valor[0] in verdes and por_valor[-1] in verdes  # do mais escuro ao mais claro


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
