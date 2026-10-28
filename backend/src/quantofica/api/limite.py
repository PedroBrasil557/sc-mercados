"""Limite de tentativas por IP nas rotas públicas (cadastro do aparelho e uso de convite).

Janela deslizante em memória: basta para uma instância. Com várias máquinas, cada uma conta a sua parte,
o que ainda deixa a força bruta nos códigos de convite (31^8 combinações, 48 h de validade) inviável.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request


def ip_do_cliente(request: Request) -> str:
    """IP de quem chamou, atrás do proxy do Render.

    O proxy acrescenta ao FIM do X-Forwarded-For o IP que ele viu. O começo da lista é escrito pelo próprio
    cliente e pode ser inventado a cada tentativa, então nunca é usado (o --proxy-headers do uvicorn com
    "*" usa justamente o primeiro: por isso ele não está ligado no Dockerfile).
    """
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[-1].strip()
    return request.client.host if request.client else "?"


class LimiteDeTaxa:
    def __init__(self, maximo: int, janela_s: float, relogio: Callable[[], float] = time.monotonic):
        self.maximo, self.janela_s, self._relogio = maximo, janela_s, relogio
        self._chamadas: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        ip = ip_do_cliente(request)
        agora = self._relogio()
        fila = self._chamadas[ip]
        while fila and agora - fila[0] > self.janela_s:
            fila.popleft()
        if len(fila) >= self.maximo:
            raise HTTPException(429, "muitas tentativas; espere alguns minutos", headers={"Retry-After": str(int(self.janela_s))})
        fila.append(agora)
