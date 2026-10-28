"""Limite de tentativas por IP nas rotas públicas (cadastro do aparelho e uso de convite).

Janela deslizante em memória: basta para uma instância. Com várias máquinas, cada uma conta a sua parte,
o que ainda deixa a força bruta nos códigos de convite (31^8 combinações, 48 h de validade) inviável.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request


class LimiteDeTaxa:
    def __init__(self, maximo: int, janela_s: float, relogio: Callable[[], float] = time.monotonic):
        self.maximo, self.janela_s, self._relogio = maximo, janela_s, relogio
        self._chamadas: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        # Atrás do proxy do Fly.io o IP real vem no cabeçalho Fly-Client-IP.
        ip = request.headers.get("fly-client-ip") or (request.client.host if request.client else "?")
        agora = self._relogio()
        fila = self._chamadas[ip]
        while fila and agora - fila[0] > self.janela_s:
            fila.popleft()
        if len(fila) >= self.maximo:
            raise HTTPException(429, "muitas tentativas; espere alguns minutos", headers={"Retry-After": str(int(self.janela_s))})
        fila.append(agora)
