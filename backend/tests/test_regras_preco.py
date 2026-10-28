"""R5 e R6: qual preço mostrar, frescor e conflito entre fontes."""

from datetime import datetime, timedelta

from quantofica.regras.preco import Estado, Faixa, Fonte, Observacao, preco_atual

AGORA = datetime(2026, 10, 28, 12, 0)


def obs(centavos, fonte, horas_atras, **kw):
    return Observacao(centavos, fonte, AGORA - timedelta(hours=horas_atras), **kw)


def test_mais_recente_vence():
    r = preco_atual([obs(1138, Fonte.SITE, 10), obs(1199, Fonte.CUPOM, 2)], AGORA)
    assert r.observacao.preco_centavos == 1199 and r.estado is Estado.VALIDO


def test_empate_de_data_cupom_vence_site():
    r = preco_atual([obs(1138, Fonte.SITE, 5), obs(1199, Fonte.CUPOM, 5)], AGORA)
    assert r.observacao.fonte is Fonte.CUPOM


def test_site_vence_em_24_horas_e_aparece_como_pode_ter_mudado():
    r = preco_atual([obs(1138, Fonte.SITE, 30)], AGORA)
    assert r.estado is Estado.PODE_TER_MUDADO


def test_preco_vencido_ha_mais_de_30_dias_sai_do_calculo():
    assert preco_atual([obs(1138, Fonte.SITE, 24 * 40)], AGORA) is None


def test_prioridade_da_fonte_so_desempata_mesma_hora():
    # Cupom de 3 dias e site de 1 hora, os dois válidos: vence o mais recente, mesmo sendo do site.
    r = preco_atual([obs(1199, Fonte.CUPOM, 72), obs(1138, Fonte.SITE, 1)], AGORA)
    assert r.observacao.fonte is Fonte.SITE


def test_etiqueta_nao_confirmada_e_ignorada():
    r = preco_atual([obs(1138, Fonte.SITE, 2), obs(999, Fonte.ETIQUETA, 1, confirmada=False)], AGORA)
    assert r.observacao.preco_centavos == 1138


def test_encarte_vale_ate_a_validade_impressa():
    enc = obs(2299, Fonte.ENCARTE, 24 * 3, valido_ate=AGORA + timedelta(days=1))
    assert preco_atual([enc], AGORA).estado is Estado.VALIDO


def test_preco_de_clube_nao_aparece_no_lancamento():
    clube = obs(899, Fonte.SITE, 1, faixa=Faixa.CLUBE)
    varejo = obs(999, Fonte.SITE, 1)
    assert preco_atual([clube, varejo], AGORA).observacao.preco_centavos == 999
    assert preco_atual([clube], AGORA) is None
