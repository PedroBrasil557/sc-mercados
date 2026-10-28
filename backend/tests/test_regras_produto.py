"""R1 e R2: código de barras, tamanho e mesmo produto. Casos reais da coleta de 22/10/2026."""

import pytest

from quantofica.regras import ean, tamanho
from quantofica.regras.mesmo_produto import ItemNaRede, Veredito, comparar


class TestEan:
    def test_zeros_a_esquerda_nao_mudam_o_produto(self):
        # Monster: "70847022015" no Giassi e "0070847022015" no Angeloni
        assert ean.mesmo_codigo("70847022015", "0070847022015")
        assert ean.normalizar("70847022015") == "00070847022015"

    @pytest.mark.parametrize("codigo", ["7894900027013", "7891000100103", "7896089013405", "70847022015"])
    def test_digito_verificador_de_produtos_reais(self, codigo):
        assert ean.digito_verificador_ok(codigo)

    def test_digito_verificador_errado(self):
        assert not ean.digito_verificador_ok("7894900027014")

    @pytest.mark.parametrize("codigo", ["", "abc", "123456789012345"])
    def test_codigo_invalido(self, codigo):
        with pytest.raises(ValueError):
            ean.normalizar(codigo)


class TestTamanho:
    @pytest.mark.parametrize(
        "nome, qtd, unidade",
        [
            ("Café Torrado e Moído Extraforte Pilão Pacote 500g", 500, "g"),
            ("Arroz Branco Tipo 1 Tio Urbano Pacote 5kg", 5000, "g"),
            ("Leite UHT Integral Tirol 1\u00a0L", 1000, "ml"),
            ("Sabão em pó Omo 2,2 kg", 2200, "g"),
            ("Detergente Ypê Neutro 500 Ml", 500, "ml"),
            ("Papel Higiênico Duetto 12 rolos", 12, "un"),
        ],
    )
    def test_extrai_tamanho(self, nome, qtd, unidade):
        t = tamanho.extrair(nome)
        assert t is not None and t.quantidade == qtd and t.unidade == unidade

    def test_sem_tamanho(self):
        assert tamanho.extrair("Banana prata") is None

    @pytest.mark.parametrize(
        "nome, esperado",
        [
            ("Macarrão de Sêmola Espaguete 5 Barilla Pack com 3 Unidades 500g Cada", True),
            ("Pack Biscoito Original Oreo Pacote 270g 3 Unidades Leve Mais Pague Menos", True),
            ("Kit Shampoo + Condicionador", True),
            ("Papel Higiênico Folha Dupla Neutro Duetto 30m Pacote 12 Unidades", False),
            ("Macarrão de Sêmola Espaguete 8 Galo Pacote 500g", False),
            # Coleta de 28/10/2026: "KitKat" não é kit (os três foram parar na revisão à toa)
            ("Wafer Kitkat Pacote 41,5g", False),
            ("Mini Chocolate ao Leite Kit Kat Nestle 41,5g", False),
            ("Chocolate KITKAT 4 Fingers ao Leite 41,5g NESTLÉ", False),
            ("Kit Kat Pack com 3 Unidades 41,5g Cada", True),
            ("Leite Condensado Moça 3 x 395g", True),
            ("Kit de Panelas", True),
        ],
    )
    def test_embalagem_multipla(self, nome, esperado):
        assert tamanho.embalagem_multipla(nome) is esperado


class TestMesmoProduto:
    def test_mesmo_ean_e_tamanho(self):
        a = ItemNaRede("7894900027013", "Refrigerante Coca-Cola Garrafa 2l")
        b = ItemNaRede("7894900027013", "Refrigerante COCA COLA Original 2L")
        assert comparar(a, b) is Veredito.MESMO

    def test_mesmo_ean_em_pack_vai_para_revisao(self):
        # Caso real: o Sam's cadastrou o EAN do Barilla 500 g num pacote com 3 unidades
        a = ItemNaRede("8076800195057", "Macarrão Spaghetti n5 Grano Duro BARILLA 500g")
        b = ItemNaRede("8076800195057", "Macarrão de Sêmola Espaguete 5 Barilla Pack com 3 Unidades 500g Cada")
        assert comparar(a, b) is Veredito.REVISAR

    def test_mesmo_ean_com_tamanho_diferente_vai_para_revisao(self):
        a = ItemNaRede("7891000100103", "Leite Condensado Moça 395g")
        b = ItemNaRede("7891000100103", "Leite Condensado Moça 270g")
        assert comparar(a, b) is Veredito.REVISAR

    def test_ean_diferente(self):
        a, b = ItemNaRede("7894900027013", "Coca 2L"), ItemNaRede("7894900010015", "Coca lata 350ml")
        assert comparar(a, b) is Veredito.DIFERENTE
