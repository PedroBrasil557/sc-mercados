"""R7, R8, R9, R12 e R14 com preços reais da coleta de 22/10/2026."""

import pytest

from quantofica.regras import economia, ofertas, totais

# Preços reais (centavos) de Giassi Victor Konder, Angeloni Velha e Cooper Água Verde.
PRECOS = {
    "Giassi": {"cafe": 2298, "leite": 478, "omo": 2647, "sal": 518},
    "Angeloni": {"cafe": 2599, "leite": 479, "omo": 2499, "sal": 519},
    "Cooper": {"cafe": 2799, "leite": 519, "omo": 3799},  # a Cooper não vendia sal no site
}
LISTA = {"cafe": 2, "leite": 12, "omo": 1, "sal": 1}


class TestTotalJusto:
    def test_so_soma_itens_vendidos_em_todas(self):
        c = totais.comparar(LISTA, PRECOS)
        assert c.comuns == ["cafe", "leite", "omo"]
        assert c.totais == {"Giassi": 12979, "Angeloni": 13445, "Cooper": 15625}
        assert c.ordem == ["Giassi", "Angeloni", "Cooper"]

    def test_fora_da_soma_e_comparacao_parcial(self):
        c = totais.comparar(LISTA, PRECOS)
        assert c.fora_da_soma["Cooper"] == ["sal"]
        assert c.parcial == {"Giassi": False, "Angeloni": False, "Cooper": True}  # 1 de 4 > 20%

    def test_empate_desempata_pela_distancia(self):
        precos = {"A": {"x": 100}, "B": {"x": 100}}
        assert totais.comparar({"x": 1}, precos, {"A": 5.0, "B": 1.0}).ordem == ["B", "A"]


class TestMelhorDivisao:
    def test_escolhe_o_par_mais_barato_e_diz_se_compensa(self):
        d = totais.melhor_divisao(LISTA, PRECOS, {("Angeloni", "Giassi"): 900})
        assert d.lojas == ("Angeloni", "Giassi")
        assert d.total_centavos == 12831 and d.economia_centavos == 148
        assert not d.compensa  # 1,48 não paga 9,00 de deslocamento + 10,00

    def test_compensa_quando_economia_supera_deslocamento_mais_10_reais(self):
        precos = {"A": {"x": 5000, "y": 1000}, "B": {"x": 3000, "y": 3000}}
        d = totais.melhor_divisao({"x": 1, "y": 1}, precos, {("A", "B"): 500})
        assert d.economia_centavos == 2000 and d.compensa


class TestDistancia:
    def test_haversine_em_blumenau(self):
        # Centro de Blumenau até a Itoupava Norte: alguns quilômetros
        d = totais.distancia_km(-26.9194, -49.0661, -26.8781, -49.0828)
        assert 4 < d < 6

    def test_custo_ida_e_volta(self):
        assert totais.custo_deslocamento_centavos(5, 90) == 900


class TestOfertaReal:
    def test_cinco_por_cento_abaixo_da_mediana(self):
        assert ofertas.oferta_real(2298, [2998] * 30, [2998] * 60, dias_de_historico=45)

    def test_desconto_pequeno_nao_e_oferta(self):
        assert not ofertas.oferta_real(2900, [2998] * 30, [2800] * 60, dias_de_historico=45)

    def test_menor_preco_dos_60_dias_e_oferta(self):
        assert ofertas.oferta_real(2790, [2800] * 30, [2800, 2850] * 30, dias_de_historico=60)

    def test_provisoria_de_por_inflado_nao_passa(self):
        # Sem histórico: "de" de 37,79 mas o preço fica acima da mediana das outras lojas
        assert not ofertas.oferta_real(
            3000, [], [], dias_de_historico=0, preco_de_centavos=3779, precos_outras_lojas=[1997, 2798]
        )

    def test_provisoria_omo_no_giassi(self):
        assert ofertas.oferta_real(2647, [], [], dias_de_historico=0, preco_de_centavos=3468, precos_outras_lojas=[2499, 3799])

    @pytest.mark.parametrize("por, de, pct", [(2647, 3468, 24), (2298, 2998, 23), (2245, 2689, 17)])
    def test_percentual_do_selo(self, por, de, pct):
        assert ofertas.percentual_desconto(por, de) == pct


class TestEconomia:
    def test_economia_do_cupom_lido(self):
        # Tela "Cupom lido": pago no Giassi 398,40; média dos 3 mercados 408,67; economia 10,27
        e = economia.calcular(39840, {"Giassi": 39840, "Angeloni": 39846, "Cooper": 42914})
        assert e.media_centavos == 40867 and e.economia_centavos == 1027
        assert e.base == "comparado à média de Angeloni, Cooper e Giassi"

    def test_economia_negativa_vira_zero(self):
        assert economia.calcular(50000, {"A": 40000, "B": 41000}).economia_centavos == 0


class TestRecomendar:
    DIST = {"angeloni": 7.1, "giassi": 6.8, "mafisa": 2.3}

    def test_itoupavazinha_fica_na_cooper_mafisa(self):
        # Caso relatado pelo Pedro: o mais barato na prateleira ficava a 7,1 km
        r = totais.recomendar({"angeloni": 12277, "giassi": 12748, "mafisa": 13549}, self.DIST, 90)
        assert (r.loja, r.mais_perto, r.economia_na_prateleira_centavos) == ("mafisa", "mafisa", 0)

    def test_longe_vale_quando_a_economia_paga_a_viagem_e_sobra(self):
        # 40 reais mais barato: paga os ~8,64 da viagem a mais e sobra bem mais que 10
        r = totais.recomendar({"angeloni": 9549, "mafisa": 13549}, self.DIST, 90)
        assert (r.loja, r.economia_na_prateleira_centavos) == ("angeloni", 4000)

    def test_sem_custo_de_viagem_ainda_exige_a_folga(self):
        # A pé/ônibus (custo 0): 12,72 mais barato passa da folga de 10
        assert totais.recomendar({"angeloni": 12277, "mafisa": 13549}, self.DIST, 0).loja == "angeloni"
        assert totais.recomendar({"angeloni": 12949, "mafisa": 13549}, self.DIST, 0).loja == "mafisa"

    def test_lista_vazia(self):
        assert totais.recomendar({}, {}, 90) is None
