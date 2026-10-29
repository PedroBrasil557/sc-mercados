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


def gtin_de_produto(codigo: str | None) -> str | None:
    """GTIN-14 de um código de barras de verdade, ou None.

    Fora: código interno da loja (curto: "93" passaria no dígito verificador), faixas de uso restrito do GS1
    (02x, 04x e 2xx no EAN-13: peso variável e numeração interna, o mesmo número é outro produto em outra
    rede) e dígito verificador errado.
    """
    digitos = re.sub(r"\D", "", codigo or "")
    if len(digitos) not in (8, 12, 13, 14):
        return None
    gtin = normalizar(digitos)
    if not digito_verificador_ok(gtin):
        return None
    if len(digitos) != 8 and gtin[0] == "0" and (gtin[1] == "2" or gtin[1:3] in ("02", "04")):
        return None
    return gtin


def mesmo_codigo(a: str, b: str) -> bool:
    try:
        return normalizar(a) == normalizar(b)
    except ValueError:
        return False
