"""Normalização e validação de códigos de barras (EAN/GTIN). Base da regra R1."""

import re


def normalizar(codigo: str) -> str:
    """GTIN-14 canônico: só dígitos, completado com zeros à esquerda.

    Redes guardam o mesmo código com ou sem zeros (ex.: Monster "70847022015" no Giassi e
    "0070847022015" no Angeloni). Comparar sempre pela forma de 14 dígitos.
    """
    digitos = re.sub(r"\D", "", codigo or "")
    if not digitos or len(digitos) > 14:
        raise ValueError(f"código inválido: {codigo!r}")
    return digitos.zfill(14)


def digito_verificador_ok(codigo: str) -> bool:
    """Confere o dígito verificador GTIN (pesos 3 e 1 a partir da direita)."""
    try:
        gtin = normalizar(codigo)
    except ValueError:
        return False
    corpo, dv = gtin[:-1], int(gtin[-1])
    soma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(corpo)))
    return (10 - soma % 10) % 10 == dv


def mesmo_codigo(a: str, b: str) -> bool:
    try:
        return normalizar(a) == normalizar(b)
    except ValueError:
        return False
