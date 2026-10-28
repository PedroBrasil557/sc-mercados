"""Regra R15: estado da lista a partir das operações de todos os aparelhos da casa.

O app nunca envia "a quantidade é 3"; envia "somei 1". Assim dois "+1" feitos ao mesmo tempo viram 2.
As operações são aplicadas na ordem em que foram feitas (e pelo id, para empates), então todos os
aparelhos chegam ao mesmo estado com as mesmas operações, não importa a ordem em que as receberam.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Tipo(StrEnum):
    CRIAR = "criar"
    SOMAR = "somar"
    TIRAR = "tirar"
    MARCAR = "marcar"
    DESMARCAR = "desmarcar"
    REMOVER = "remover"


@dataclass(frozen=True)
class Operacao:
    id: str
    item_id: str
    tipo: Tipo
    feita_em: datetime
    membro_id: str | None = None
    valor: Decimal | None = None


@dataclass
class Item:
    id: str
    quantidade: Decimal = Decimal(0)
    comprado: bool = False
    removido: bool = False
    removido_por: str | None = None
    aviso: str | None = None  # "Paulo tinha removido este item"
    adicionado_por: str | None = None
    historico: list[str] = field(default_factory=list)


def aplicar(operacoes: list[Operacao], nomes: dict[str, str] | None = None) -> dict[str, Item]:
    """Estado final de cada item. Itens removidos ficam no resultado com `removido=True`."""
    nomes = nomes or {}
    itens: dict[str, Item] = {}
    for op in sorted(operacoes, key=lambda o: (o.feita_em, o.id)):
        it = itens.setdefault(op.item_id, Item(op.item_id))
        it.historico.append(op.id)
        valor = op.valor if op.valor is not None else Decimal(1)
        if op.tipo in (Tipo.CRIAR, Tipo.SOMAR):
            if it.removido and it.removido_por and it.removido_por != op.membro_id:
                quem = nomes.get(it.removido_por, "Alguém da casa")
                it.aviso = f"{quem} tinha removido este item"
            if it.removido:
                it.quantidade, it.removido, it.removido_por = Decimal(0), False, None
            it.quantidade += valor
            it.adicionado_por = it.adicionado_por or op.membro_id
        elif op.tipo is Tipo.TIRAR:
            it.quantidade = max(Decimal(0), it.quantidade - valor)
            if it.quantidade == 0:
                it.removido, it.removido_por = True, op.membro_id
        elif op.tipo is Tipo.REMOVER:
            it.removido, it.removido_por, it.aviso = True, op.membro_id, None
        elif op.tipo is Tipo.MARCAR:
            it.comprado = True
        elif op.tipo is Tipo.DESMARCAR:
            it.comprado = False
    return itens
