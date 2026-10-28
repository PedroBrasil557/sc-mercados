"""Conexão por requisição, emprestada do pool da aplicação."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from psycopg import Connection


def conexao(request: Request) -> Iterator[Connection]:
    with request.app.state.pool.connection() as conn:
        yield conn


Conexao = Annotated[Connection, Depends(conexao)]
