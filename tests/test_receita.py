"""Receita e `gerar`: validação com erro claro, padrões, determinismo, laço, presets e linha de comando."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import ImageChops

from pixel_atelier import (
    ErroDeReceita,
    carregar_estilo,
    cores_usadas,
    dados_do_estilo,
    descrever_formas,
    gerar,
    listar_estilos,
    pasta_de_presets,
    registrar_estilo,
    validar_receita,
)
from pixel_atelier.__main__ import main

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"

MINIMA = {"camadas": [{"forma": "ceu"}, {"forma": "terreno"}]}

PEQUENA = {
    "tamanho": [96, 64],
    "estilo": "snes-diurno",
    "camadas": [
        {"forma": "ceu", "astro": "sol"},
        {"forma": "arvore", "profundidade": 0.5, "tipo": "mista"},
        {"forma": "terreno", "nome": "chao", "base": 0.85},
    ],
}


def erros_de(receita) -> list[str]:
    with pytest.raises(ErroDeReceita) as info:
        validar_receita(receita)
    return info.value.erros


# --- validação -------------------------------------------------------------------------------------

def test_receita_minima_usa_os_padroes():
    r = validar_receita(MINIMA)
    assert (r.cena, r.largura, r.altura, r.estilo.nome, r.laco, r.seed, r.ampliar, r.saida) == (
        "cena", 320, 180, "snes-diurno", True, 0, 1, "tudo")
    assert [c.arquivo for c in r.camadas] == ["01-ceu.png", "02-terreno.png"]


def test_campo_desconhecido_sugere_o_parecido():
    assert erros_de({**MINIMA, "seeed": 3}) == ["campo 'seeed' não existe em receita; quis dizer 'seed'?"]
    erros = erros_de({"camadas": [{"forma": "arvore", "profundiade": 0.5}]})
    assert erros == ["camada 1 (arvore): campo 'profundiade' não existe em arvore; quis dizer 'profundidade'?"]


def test_forma_inexistente():
    (erro,) = erros_de({"camadas": [{"forma": "arvores"}]})
    assert "forma 'arvores' não existe" in erro and "quis dizer 'arvore'?" in erro


def test_sem_camadas():
    (erro,) = erros_de({})
    assert "camadas" in erro


def test_largura_invalida_com_laco_sugere_multiplos_de_8():
    (erro,) = erros_de({**MINIMA, "tamanho": [100, 60]})
    assert "múltipla de 8" in erro and "96 ou 104" in erro


def test_largura_qualquer_sem_laco():
    assert validar_receita({**MINIMA, "tamanho": [100, 60], "laco": False}).largura == 100
    # a camada pode ligar o laço sozinha, e aí a largura volta a importar
    receita = {"tamanho": [100, 60], "laco": False, "camadas": [{"forma": "ceu", "laco": True}]}
    assert "camadas com laço: 1" in erros_de(receita)[0]


def test_tipos_e_opcoes_dos_parametros():
    erros = erros_de({"camadas": [
        {"forma": "terreno", "base": "alto", "pedrinhas": 2.5, "escurecer": 1, "superficie": "lava"},
        {"forma": "arvore", "tamanho": [0.1, 0.2, 0.3]},
    ]})
    assert erros == [
        'camada 1 (terreno): base deve ser número, veio "alto"',
        "camada 1 (terreno): pedrinhas deve ser número inteiro, veio 2.5",
        "camada 1 (terreno): escurecer deve ser true ou false, veio 1",
        'camada 1 (terreno): superficie deve ser um de "nenhuma", "grama", "neve", veio "lava"',
        "camada 2 (arvore): tamanho deve ser número ou [mínimo, máximo], veio [0.1, 0.2, 0.3]",
    ]


def test_intervalo_e_null_aceitos():
    r = validar_receita({"camadas": [{"forma": "arvore", "tamanho": [0.2, 0.3]}, {"forma": "ceu", "astro": None}]})
    assert r.camadas[0].parametros["tamanho"] == [0.2, 0.3]


def test_todos_os_erros_de_uma_vez():
    erros = erros_de({"tamanho": [0, 10], "estilo": "nao-existe", "saida": "zip", "ampliar": 0,
                      "camadas": [{"forma": "nada"}, "texto"]})
    assert len(erros) == 6
    assert str(ErroDeReceita(erros)).startswith("receita inválida:\n- ")


def test_ampliado_no_limite_passa_e_acima_falha():
    assert validar_receita({**MINIMA, "tamanho": [256, 128], "ampliar": 16}).ampliar == 16
    (erro,) = erros_de({**MINIMA, "tamanho": [264, 128], "ampliar": 16})
    assert "4224x2048" in erro and "máximo é 4096 por lado" in erro and "reduza ampliar ou tamanho" in erro
    assert "ampliada" in erros_de({**MINIMA, "tamanho": [100, 4096], "ampliar": 2})[0]


def test_json_quebrado_diz_onde():
    (erro,) = erros_de('{"camadas": [}')
    assert "linha 1, coluna" in erro


def test_cena_vira_nome_de_arquivo_seguro():
    assert "cena deve ser" in erros_de({**MINIMA, "cena": "../fora"})[0]
    assert "nome deve ser" in erros_de({"camadas": [{"forma": "ceu", "nome": "Céu Azul"}]})[0]


def test_descrever_formas_lista_toda_forma():
    texto = descrever_formas()
    for forma in ("ceu", "nuvem", "terreno", "arvore", "rocha", "cristal", "nevoa", "raios"):
        assert f"\n{forma}: " in texto
    assert '"pinheiro"|"copa"' in texto


# --- gerar -----------------------------------------------------------------------------------------

def test_mesma_receita_mesmos_bytes():
    assert gerar(PEQUENA).composto.tobytes() == gerar(PEQUENA).composto.tobytes()


def test_seed_da_receita_muda_so_as_camadas_sem_seed_fixa():
    fixa = {**PEQUENA, "camadas": [{**PEQUENA["camadas"][1], "seed": 4}, PEQUENA["camadas"][2]]}
    a, b = gerar({**fixa, "seed": 1}), gerar({**fixa, "seed": 2})
    assert a.camadas[0].imagem.tobytes() == b.camadas[0].imagem.tobytes()
    assert a.camadas[1].imagem.tobytes() != b.camadas[1].imagem.tobytes()
    assert a.camadas[0].seed == 4


def test_composto_so_com_cores_da_paleta_e_alfa_cheio():
    resultado = gerar(PEQUENA)
    assert cores_usadas(resultado.composto) <= set(resultado.receita.estilo.paleta)
    assert resultado.composto.getchannel("A").getextrema() == (255, 255)


def test_laco_sem_emenda_no_composto():
    receita = {**PEQUENA, "tamanho": [160, 96], "camadas": PEQUENA["camadas"] + [{"forma": "rocha", "quantidade": 4}]}
    girada = ImageChops.offset(gerar(receita).composto, 48, 0).load()
    andando = gerar({**receita, "camadas": [{**c, "deslocamento": 48} for c in receita["camadas"]]}).composto.load()
    # andar o mundo inteiro 48 px dá a mesma cena girada, com a folga de arredondamento do Pillow
    # que o teste das formas aceita por camada
    largura, altura = receita["tamanho"]
    diferentes = sum(1 for y in range(altura) for x in range(largura) if girada[x, y] != andando[x, y])
    assert diferentes <= len(receita["camadas"]) * largura * altura // 500


def test_laco_da_receita_chega_nas_camadas():
    r = validar_receita({**MINIMA, "laco": False, "camadas": [{"forma": "ceu"}, {"forma": "terreno", "laco": True}]})
    assert [c.parametros["laco"] for c in r.camadas] == [False, True]


def test_grava_composto_ampliado_e_camadas(tmp_path):
    resultado = gerar({**PEQUENA, "cena": "teste", "ampliar": 2}, pasta=tmp_path)
    nomes = sorted(p.relative_to(tmp_path).as_posix() for p in resultado.arquivos)
    assert nomes == ["teste-2x.png", "teste.png", "teste/01-ceu.png", "teste/02-arvore.png", "teste/03-chao.png"]
    assert all(p.is_file() for p in resultado.arquivos)
    texto = resultado.resumo()
    assert "teste: 96x64, estilo snes-diurno" in texto and "03 chao: seed" in texto


@pytest.mark.parametrize("saida, quantos", [("composto", 1), ("camadas", 3)])
def test_saida_escolhe_o_que_gravar(tmp_path, saida, quantos):
    assert len(gerar({**PEQUENA, "saida": saida}, pasta=tmp_path).arquivos) == quantos


def test_sem_pasta_nao_grava_nada():
    resultado = gerar(PEQUENA)
    assert resultado.arquivos == [] and "nada gravado" in resultado.resumo()


def test_resumo_avisa_camada_vazia_e_camada_que_tapa_tudo():
    resultado = gerar({**PEQUENA, "camadas": [
        {"forma": "ceu"},
        {"forma": "rocha", "quantidade": 0},
        {"forma": "ceu", "nome": "ceu-na-frente"},
    ]})
    assert resultado.avisos() == [
        "camada 2 (rocha) não desenhou nada",
        "camada 3 (ceu-na-frente) cobre a tela toda e esconde as de trás",
    ]
    assert json.dumps(resultado.para_dicionario())  # pronto para JSON


@pytest.mark.parametrize("nome", ["metroidvania-noturno", "snes-diurno"])
def test_exemplos_reproduzem_montar_cena(nome):
    spec = importlib.util.spec_from_file_location("montar_cena", EXEMPLOS / "montar_cena.py")
    montar_cena = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(montar_cena)
    assert gerar(EXEMPLOS / f"{nome}.json").composto.tobytes() == montar_cena.montar(nome).tobytes()


# --- presets ---------------------------------------------------------------------------------------

def test_estilo_com_base_sobrescreve_so_os_campos_dados():
    estilo = carregar_estilo({"base": "snes-diurno", "contorno": False, "rampas": {"folha": ["#203020", "#406040"]}})
    original = dados_do_estilo("snes-diurno")
    assert estilo.contorno is False and original["contorno"] is True
    assert set(estilo.rampas) == set(original["rampas"])  # as outras rampas continuam
    assert estilo.nome == "snes-diurno"


def test_receita_sobrescreve_campos_do_preset():
    base, ajustado = gerar(PEQUENA), gerar({**PEQUENA, "estilo": {"base": "snes-diurno", "sombreamento": "chapado"}})
    assert base.composto.tobytes() != ajustado.composto.tobytes()


def test_registrar_e_usar_preset_por_nome():
    destino = registrar_estilo({"base": "snes-diurno", "contorno": False}, "snes-sem-contorno")
    assert destino.parent == pasta_de_presets() and "snes-sem-contorno" in listar_estilos()
    assert carregar_estilo("snes-sem-contorno").contorno is False
    assert gerar({**PEQUENA, "estilo": "snes-sem-contorno"}).receita.estilo.nome == "snes-sem-contorno"
    with pytest.raises(ValueError, match="já existe"):
        registrar_estilo({"base": "snes-diurno"}, "snes-sem-contorno")
    registrar_estilo({"base": "snes-diurno", "contorno": True}, "snes-sem-contorno", sobrescrever=True)
    assert carregar_estilo("snes-sem-contorno").contorno is True


def test_preset_do_pacote_e_nome_ruim_sao_recusados():
    with pytest.raises(ValueError, match="vem com o pacote"):
        registrar_estilo({"base": "game-boy"}, "snes-diurno")
    with pytest.raises(ValueError, match="minúsculo"):
        registrar_estilo({"base": "game-boy"}, "Meu Estilo")
    with pytest.raises(ValueError, match="obrigatório"):
        registrar_estilo({"nome": "incompleto"})


# --- linha de comando ------------------------------------------------------------------------------

def test_linha_de_comando_gera_e_responde_em_texto(tmp_path, capsys):
    receita = tmp_path / "receita.json"
    receita.write_text(json.dumps({**PEQUENA, "cena": "cli", "saida": "composto"}), encoding="utf-8")
    assert main(["gerar", str(receita)]) == 0
    assert (tmp_path / "cli.png").is_file()
    assert "cli: 96x64" in capsys.readouterr().out


def test_linha_de_comando_receita_invalida_sai_com_2(tmp_path, capsys):
    receita = tmp_path / "ruim.json"
    receita.write_text('{"camadas": [{"forma": "arvores"}]}', encoding="utf-8")
    assert main(["gerar", str(receita)]) == 2
    assert "quis dizer 'arvore'?" in capsys.readouterr().err


def test_linha_de_comando_registra_estilo_de_arquivo_com_base(tmp_path, capsys):
    arquivo = tmp_path / "estilo.json"
    arquivo.write_text('{"base": "game-boy", "contorno": false}', encoding="utf-8")
    assert main(["registrar-estilo", str(arquivo), "--nome", "game-boy-liso"]) == 0
    assert "preset game-boy-liso gravado" in capsys.readouterr().out
    assert carregar_estilo("game-boy-liso").contorno is False
    assert main(["registrar-estilo", str(arquivo)]) == 2  # sem --nome fica o do game-boy, que é reservado
    assert "vem com o pacote" in capsys.readouterr().err
