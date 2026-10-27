"""Formas: determinismo, paleta respeitada, laço sem emenda e desenho dentro do tamanho."""
from __future__ import annotations

import pytest
from PIL import Image, ImageChops

from pixel_atelier import FORMAS, carregar_estilo, cores_usadas, desenhar, listar_estilos

LARGURA, ALTURA = 160, 96

# parâmetros que garantem que cada forma desenhe algo visível no tamanho pequeno dos testes
PARAMETROS = {
    "ceu": dict(estrelas=20, astro="lua"),
    "nuvem": dict(quantidade=3),
    "terreno": dict(),
    "arvore": dict(tipo="mista"),
    "rocha": dict(quantidade=3, tamanho=(0.12, 0.2)),
    "cristal": dict(quantidade=2),
    "nevoa": dict(densidade=0.7),
    "raios": dict(intensidade=0.6),
}


def gerar(forma: str, estilo="snes-diurno", seed: int = 7, **extra) -> Image.Image:
    return desenhar(forma, estilo, LARGURA, ALTURA, seed=seed, **{**PARAMETROS[forma], **extra})


def test_toda_forma_tem_parametros_de_teste():
    assert set(PARAMETROS) == set(FORMAS)


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_mesma_seed_mesmos_bytes(forma):
    assert gerar(forma).tobytes() == gerar(forma).tobytes()


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_seed_diferente_muda_a_arte(forma):
    assert gerar(forma, seed=1).tobytes() != gerar(forma, seed=2).tobytes()


@pytest.mark.parametrize("nome_estilo", listar_estilos())
@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_nenhuma_cor_fora_da_paleta(forma, nome_estilo):
    estilo = carregar_estilo(nome_estilo)
    imagem = gerar(forma, estilo, profundidade=0.4) if forma != "ceu" else gerar(forma, estilo)
    fora = cores_usadas(imagem) - set(estilo.paleta)
    assert not fora, f"cores fora da paleta: {sorted(fora)[:5]}"


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_alfa_so_cheio_ou_vazio(forma):
    alfas = {a for _, a in gerar(forma).getchannel("A").getcolors()}
    assert alfas <= {0, 255}


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_desenha_algo_dentro_do_tamanho(forma):
    imagem = gerar(forma)
    assert imagem.mode == "RGBA"
    assert imagem.size == (LARGURA, ALTURA)
    caixa = imagem.getchannel("A").getbbox()
    assert caixa is not None, "a forma não desenhou nada"
    x0, y0, x1, y1 = caixa
    assert 0 <= x0 < x1 <= LARGURA and 0 <= y0 < y1 <= ALTURA
    opacos = imagem.getchannel("A").histogram()[255]
    assert opacos >= 20


def _diferencas(imagem: Image.Image, a: int, b: int) -> int:
    px = imagem.load()
    return sum(1 for y in range(imagem.height) if px[a, y] != px[b, y])


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_laco_sem_emenda(forma):
    """A coluna 0 continua a última: a emenda não muda mais que a maior troca entre colunas vizinhas."""
    imagem = gerar(forma)
    emenda = _diferencas(imagem, LARGURA - 1, 0)
    maior_interna = max(_diferencas(imagem, x, x + 1) for x in range(LARGURA - 1))
    assert emenda <= maior_interna


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_laco_e_um_anel(forma):
    """Andar o mundo 48 pixels dá exatamente a mesma imagem girada: nada é cortado na borda.

    Se alguma parte da forma fosse desenhada sem as cópias do laço, ela não daria a volta e
    centenas de pixels mudariam. Junto com o ruído periódico, é o que garante a emenda invisível.
    A folga de poucos pixels é do arredondamento do Pillow ao rasterizar polígono em outra posição.
    """
    girada = ImageChops.offset(gerar(forma), 48, 0).load()
    andando = gerar(forma, deslocamento=48).load()
    diferentes = sum(1 for y in range(ALTURA) for x in range(LARGURA) if girada[x, y] != andando[x, y])
    assert diferentes <= LARGURA * ALTURA // 500


def test_laco_do_terreno_fecha_o_perfil():
    """No terreno o perfil de cima tem que fechar: a altura na coluna 0 e na última quase igual."""
    imagem = gerar("terreno", amplitude=0.3, superficie="nenhuma", pedrinhas=0)
    alfa = imagem.getchannel("A").load()

    def topo(x: int) -> int:
        return next(y for y in range(ALTURA) if alfa[x, y])

    passos = [abs(topo(x + 1) - topo(x)) for x in range(LARGURA - 1)]
    assert abs(topo(LARGURA - 1) - topo(0)) <= max(passos)


def test_sem_laco_aceita_qualquer_largura():
    imagem = desenhar("arvore", "game-boy", 100, 60, laco=False, seed=3)
    assert imagem.size == (100, 60)


def test_laco_pede_largura_multipla_de_8():
    with pytest.raises(ValueError):
        desenhar("arvore", "game-boy", 100, 60, seed=3)


@pytest.mark.parametrize("forma, extra", [
    ("arvore", dict(tipo="copa", base=1.02)),
    ("arvore", dict(tipo="mista", base=1.3)),
    ("nuvem", dict(faixa=(0.9, 1.4))),
])
def test_base_abaixo_da_tela_nao_quebra(forma, extra):
    imagem = gerar(forma, **extra)
    assert imagem.size == (LARGURA, ALTURA)


def test_forma_desconhecida():
    with pytest.raises(KeyError):
        desenhar("castelo", "game-boy", 64, 64)


def test_profundidade_aproxima_da_atmosfera():
    """Longe fica mais perto da cor da atmosfera do que perto (contraste entre camadas)."""
    estilo = carregar_estilo("metroidvania-noturno")

    def distancia_media(profundidade: float) -> float:
        imagem = desenhar("rocha", estilo, LARGURA, ALTURA, seed=4, profundidade=profundidade, quantidade=3,
                          tamanho=(0.15, 0.2))
        cores = [(n, c) for n, c in imagem.getcolors() if c[3]]
        alvo = estilo.atmosfera
        total = sum(n for n, _ in cores)
        return sum(n * sum((c[i] - alvo[i]) ** 2 for i in range(3)) ** 0.5 for n, c in cores) / total

    assert distancia_media(0.9) < distancia_media(0.0)


@pytest.mark.parametrize("densidade", [0.1, 0.2, 0.3])
@pytest.mark.parametrize("seed", range(12))
def test_nuvem_em_fiapo_rala_desenha_em_qualquer_seed(seed, densidade):
    imagem = gerar("nuvem", seed=seed, tipo="fiapo", densidade=densidade)
    assert imagem.getchannel("A").getbbox() is not None


def test_nuvem_em_fiapo_enche_mais_com_mais_densidade():
    def acesos(densidade: float) -> int:
        alfa = gerar("nuvem", seed=2, tipo="fiapo", densidade=densidade).getchannel("A")
        return alfa.histogram()[255]

    assert 0 < acesos(0.1) < acesos(0.3) < acesos(0.6)


@pytest.mark.parametrize("densidade", [0.02, 0.05, 0.1])
@pytest.mark.parametrize("seed", range(12))
def test_nevoa_rala_desenha_em_qualquer_seed(seed, densidade):
    imagem = desenhar("nevoa", "snes-diurno", 160, 144, seed=seed, densidade=densidade)
    assert imagem.getchannel("A").getbbox() is not None


def test_nevoa_enche_mais_com_mais_densidade():
    def acesos(densidade: float) -> int:
        alfa = gerar("nevoa", seed=2, densidade=densidade).getchannel("A")
        return alfa.histogram()[255]

    assert 0 < acesos(0.05) < acesos(0.3) < acesos(0.6)
