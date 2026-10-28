"""R15: sincronização da lista por operações."""

from datetime import datetime, timedelta
from decimal import Decimal
from itertools import permutations

from quantofica.regras.lista import Operacao, Tipo, aplicar

T0 = datetime(2026, 10, 28, 9, 0)


def op(id_, tipo, segundos, membro="ana", item="leite", valor=None):
    return Operacao(id_, item, tipo, T0 + timedelta(seconds=segundos), membro, Decimal(valor) if valor else None)


def test_dois_mais_um_ao_mesmo_tempo_viram_dois():
    # Critério de aceite: duas pessoas somam +1 no mesmo item ao mesmo tempo → soma das duas
    ops = [op("1", Tipo.CRIAR, 0), op("2", Tipo.SOMAR, 10, "ana"), op("3", Tipo.SOMAR, 10, "paulo")]
    assert aplicar(ops)["leite"].quantidade == 3


def test_ordem_de_chegada_nao_muda_o_resultado():
    ops = [op("1", Tipo.CRIAR, 0, valor=12), op("2", Tipo.TIRAR, 5), op("3", Tipo.SOMAR, 6, "paulo"), op("4", Tipo.MARCAR, 9)]
    resultados = {(it.quantidade, it.comprado, it.removido) for p in permutations(ops) for it in [aplicar(list(p))["leite"]]}
    assert resultados == {(Decimal(12), True, False)}


def test_remover_e_somar_ao_mesmo_tempo_o_item_fica_com_aviso():
    ops = [op("1", Tipo.CRIAR, 0), op("2", Tipo.REMOVER, 20, "paulo"), op("3", Tipo.SOMAR, 21, "ana")]
    it = aplicar(ops, {"paulo": "Paulo"})["leite"]
    assert not it.removido and it.quantidade == 1
    assert it.aviso == "Paulo tinha removido este item"


def test_remover_por_ultimo_remove():
    it = aplicar([op("1", Tipo.CRIAR, 0), op("2", Tipo.SOMAR, 5), op("3", Tipo.REMOVER, 9, "paulo")])["leite"]
    assert it.removido


def test_tirar_ate_zero_remove_e_nao_fica_negativo():
    it = aplicar([op("1", Tipo.CRIAR, 0), op("2", Tipo.TIRAR, 1), op("3", Tipo.TIRAR, 2)])["leite"]
    assert it.quantidade == 0 and it.removido


def test_readicionar_o_proprio_item_nao_gera_aviso():
    it = aplicar([op("1", Tipo.CRIAR, 0), op("2", Tipo.REMOVER, 1), op("3", Tipo.SOMAR, 2)])["leite"]
    assert not it.removido and it.aviso is None


def test_quantidade_fracionada_banana_em_kg():
    it = aplicar([op("1", Tipo.CRIAR, 0, item="banana", valor="1.5"), op("2", Tipo.SOMAR, 1, item="banana", valor="0.5")])[
        "banana"
    ]
    assert it.quantidade == Decimal("2.0")
