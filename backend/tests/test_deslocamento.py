"""Deslocamento: só muda a sugestão de mercado, nunca os valores; cada meio de transporte cobra de um jeito."""

from quantofica.regras import deslocamento, totais
from quantofica.regras.deslocamento import Modo


def test_cada_meio_cobra_de_um_jeito():
    assert deslocamento.ida_e_volta(Modo.CARRO, 3) == 540  # 3 km x R$ 0,90 x 2
    assert deslocamento.ida_e_volta(Modo.ONIBUS, 0.8) == 0  # perto: vai a pé
    assert deslocamento.ida_e_volta(Modo.ONIBUS, 2) == deslocamento.ida_e_volta(Modo.ONIBUS, 9) == 1100  # duas passagens
    assert deslocamento.perna(Modo.APLICATIVO, 1) == 750  # corrida curta: a tarifa mínima
    assert deslocamento.perna(Modo.TAXI, 2) == round(535 + 436 * 2 * 1.3)  # bandeirada + km pelas ruas
    assert deslocamento.ida_e_volta(Modo.A_PE, 5) == 0


def test_sugestao_muda_com_o_meio_de_transporte():
    # Caso real (28/10/2026): Angeloni 122,77 a 7,1 km; Cooper Mafisa 135,49 a 2,3 km (seu mercado).
    precos, dist = {"angeloni": 12277, "cooper": 13549}, {"angeloni": 7.1, "cooper": 2.3}

    def sugere(m):
        return totais.recomendar(precos, dist, lambda km: deslocamento.ida_e_volta(m, km), "cooper").loja

    assert sugere(Modo.CARRO) == "cooper"  # 12,72 a menos não paga 8,64 de viagem a mais + 10 de folga
    assert sugere(Modo.ONIBUS) == "angeloni"  # de ônibus a viagem custa o mesmo: vale o mais barato no caixa
    assert sugere(Modo.APLICATIVO) == "cooper"  # de aplicativo a viagem pesa ainda mais
    assert totais.recomendar(precos, dist, 90, "cooper").loja == "cooper"  # o jeito antigo (custo por km) continua
