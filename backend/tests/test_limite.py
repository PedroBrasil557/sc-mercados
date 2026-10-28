import pytest
from fastapi import HTTPException
from starlette.requests import Request

from quantofica.api.limite import LimiteDeTaxa


def pedido(ip: str) -> Request:
    return Request({"type": "http", "headers": [(b"fly-client-ip", ip.encode())], "client": ("10.0.0.1", 1)})


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
