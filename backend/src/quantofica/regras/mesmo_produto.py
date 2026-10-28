"""Regra R1: quando dois itens de redes diferentes são o mesmo produto."""

from dataclasses import dataclass
from enum import StrEnum

from . import ean, tamanho


class Veredito(StrEnum):
    MESMO = "mesmo"
    REVISAR = "revisar"  # mesmo EAN, mas tamanho ou embalagem divergem: vai para a fila humana
    DIFERENTE = "diferente"


@dataclass(frozen=True)
class ItemNaRede:
    ean: str
    nome: str


def comparar(a: ItemNaRede, b: ItemNaRede) -> Veredito:
    if not ean.mesmo_codigo(a.ean, b.ean):
        return Veredito.DIFERENTE
    if tamanho.embalagem_multipla(a.nome) != tamanho.embalagem_multipla(b.nome):
        return Veredito.REVISAR
    ta, tb = tamanho.extrair(a.nome), tamanho.extrair(b.nome)
    if ta and tb and not ta.mesmo_que(tb):
        return Veredito.REVISAR
    return Veredito.MESMO
