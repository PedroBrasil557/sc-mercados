"""Regra R12: economia de uma compra, sempre com a base de cálculo visível."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Economia:
    pago_centavos: int
    media_centavos: int
    economia_centavos: int  # nunca negativa
    base: str  # texto mostrado ao lado do valor


def calcular(pago_centavos: int, totais_mesmos_itens: dict[str, int]) -> Economia:
    """Média do preço dos mesmos itens nos mercados comparados menos o valor pago.

    Economia negativa vira zero e não é somada ao mês.
    """
    if not totais_mesmos_itens:
        raise ValueError("sem mercados para comparar")
    media = Decimal(sum(totais_mesmos_itens.values())) / len(totais_mesmos_itens)
    media_centavos = int(media.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    economia = max(0, media_centavos - pago_centavos)
    base = "comparado à média de " + _juntar(sorted(totais_mesmos_itens))
    return Economia(pago_centavos, media_centavos, economia, base)


def _juntar(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
