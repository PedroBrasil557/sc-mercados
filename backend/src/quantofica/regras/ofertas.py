"""Regra R9: quando um preço é oferta real."""

from statistics import median

DESCONTO_MINIMO = 0.05
DIAS_HISTORICO_MINIMO = 30


def oferta_real(
    preco_centavos: int,
    historico_30d: list[int],
    historico_60d: list[int],
    dias_de_historico: int,
    preco_de_centavos: int | None = None,
    precos_outras_lojas: list[int] | None = None,
) -> bool:
    """Com 30 dias de histórico: pelo menos 5% abaixo da mediana dos últimos 30 dias na mesma loja,
    ou o menor preço dos últimos 60 dias.

    Antes disso (regra provisória): o "de/por" da loja precisa dar 5% ou mais de desconto e o preço
    não pode estar acima da mediana das outras lojas, porque o "de" sozinho pode estar inflado.
    """
    if dias_de_historico >= DIAS_HISTORICO_MINIMO and historico_30d:
        if preco_centavos <= median(historico_30d) * (1 - DESCONTO_MINIMO):
            return True
        return bool(historico_60d) and preco_centavos < min(historico_60d)
    if not preco_de_centavos or preco_centavos > preco_de_centavos * (1 - DESCONTO_MINIMO):
        return False
    return not precos_outras_lojas or preco_centavos <= median(precos_outras_lojas)


def percentual_desconto(preco_centavos: int, referencia_centavos: int) -> int:
    """Desconto exibido no selo, arredondado para o inteiro mais próximo (−23,7% → −24%)."""
    return int((1 - preco_centavos / referencia_centavos) * 100 + 0.5)
