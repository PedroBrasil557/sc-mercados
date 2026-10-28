"""R15 contra os casos compartilhados com o app (compartilhado/r15_casos.json), em todas as ordens de chegada."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import pytest

from quantofica.regras.lista import Operacao, Tipo, aplicar

CASOS = json.loads((Path(__file__).resolve().parents[2] / "compartilhado" / "r15_casos.json").read_text(encoding="utf-8"))[
    "casos"
]
T0 = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def operacao(o: dict) -> Operacao:
    valor = Decimal(str(o["valor"])) if "valor" in o else None
    return Operacao(o["id"], o["item"], Tipo(o["tipo"]), T0 + timedelta(seconds=o["segundos"]), o["membro"], valor)


@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def test_caso_compartilhado(caso):
    ops = [operacao(o) for o in caso["operacoes"]]
    for ordem in permutations(ops):
        itens = aplicar(list(ordem), caso.get("nomes"))
        obtido = {
            k: {"quantidade": float(i.quantidade), "comprado": i.comprado, "removido": i.removido, "aviso": i.aviso}
            for k, i in itens.items()
        }
        assert obtido == caso["esperado"]
