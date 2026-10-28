import pytest
from fastapi import HTTPException
from starlette.requests import Request

from quantofica.api.limite import LimiteDeTaxa, ip_do_cliente


def pedido(encaminhado: str | None = None) -> Request:
    cabecalhos = [(b"x-forwarded-for", encaminhado.encode())] if encaminhado else []
    return Request({"type": "http", "headers": cabecalhos, "client": ("10.0.0.1", 1)})


def test_bloqueia_depois_do_maximo_e_libera_quando_a_janela_passa():
    agora = [0.0]
    limite = LimiteDeTaxa(maximo=3, janela_s=600, relogio=lambda: agora[0])
    for _ in range(3):
        limite(pedido("200.1.1.1"))
    with pytest.raises(HTTPException) as erro:
        limite(pedido("200.1.1.1"))
    assert erro.value.status_code == 429
    limite(pedido("200.2.2.2"))  # outro IP não é afetado
    agora[0] = 601
    limite(pedido("200.1.1.1"))


def test_ip_inventado_pelo_cliente_nao_dribla_o_limite():
    # O cliente manda um IP diferente a cada tentativa; o proxy acrescenta o verdadeiro no fim.
    limite = LimiteDeTaxa(maximo=2, janela_s=600, relogio=lambda: 0.0)
    limite(pedido("1.1.1.1, 200.9.9.9"))
    limite(pedido("2.2.2.2, 200.9.9.9"))
    with pytest.raises(HTTPException):
        limite(pedido("3.3.3.3, 200.9.9.9"))


def test_sem_proxy_usa_o_ip_da_conexao():
    assert ip_do_cliente(pedido()) == "10.0.0.1"
