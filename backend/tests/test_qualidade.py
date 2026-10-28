from datetime import UTC, datetime, timedelta

from quantofica.qualidade import monitor

AGORA = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)


def test_queda_de_cobertura_acima_de_10_por_cento():
    assert monitor.queda_de_cobertura("Giassi", 200, 179).motivo == "cobertura caiu 10% (200 → 179 preços)"
    assert monitor.queda_de_cobertura("Giassi", 200, 180) is None  # exatamente 10% ainda passa
    assert monitor.queda_de_cobertura("Giassi", 0, 0) is None  # primeira coleta não tem com o que comparar


def test_preco_fora_da_curva():
    historico = [1890, 1899, 1950, 2090]  # mediana 1924,50
    assert monitor.preco_fora_da_curva(2849, historico) is False  # +48%
    assert monitor.preco_fora_da_curva(2899, historico) is True  # +51%
    assert monitor.preco_fora_da_curva(950, historico) is True  # -51%
    assert monitor.preco_fora_da_curva(9000, [1899, 1899]) is False  # histórico curto demais para julgar


def test_tamanho_divergente_entre_redes():
    a = monitor.tamanho_divergente("07896089013405", {"Giassi": "Café Pilão 500g", "Cooper": "Café Pilão Tradicional 250g"})
    assert a is not None and a.referencia == "ean:07896089013405"
    assert monitor.tamanho_divergente("07896089013405", {"Giassi": "Café Pilão 500g", "Cooper": "CAFE PILAO 500 G"}) is None
    assert monitor.tamanho_divergente("07896089013405", {"Giassi": "Café Pilão 500g", "Cooper": "Café Pilão"}) is None


def test_coletor_parado_depois_de_26_horas():
    assert monitor.coletor_parado("Cooper", AGORA - timedelta(hours=25), AGORA) is None
    parado = monitor.coletor_parado("Cooper", AGORA - timedelta(hours=27), AGORA)
    assert parado.prioridade == 1 and "27/10 06:00" in parado.motivo
    assert "nunca rodou" in monitor.coletor_parado("Cooper", None, AGORA).motivo
