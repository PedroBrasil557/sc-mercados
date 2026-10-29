"""API do SC Mercados (FastAPI).

Rodar localmente:  uvicorn quantofica.api.app:create_app --factory --reload
Variável obrigatória: DATABASE_URL (ex.: postgresql://quantofica:local-apenas@localhost:54329/quantofica)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import detalhes, identidade, listas, precos, produtos, web
from .banco import Conexao


def create_app(dsn: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI):
        # prepare_threshold=None: o pooler do Supabase (modo transação) não aceita prepared statements.
        pool = ConnectionPool(
            dsn or os.environ["DATABASE_URL"],
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )
        app.state.pool = pool
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(title="SC Mercados", version="0.1.0", lifespan=ciclo)

    @app.get("/v1/saude")
    def saude(conn: Conexao):
        """Usada pela checagem de saúde da Fly.io: só responde ok se o banco também responder."""
        conn.execute("select 1")
        return {"ok": True}

    app.include_router(identidade.router)
    app.include_router(listas.router)
    app.include_router(precos.router)
    app.include_router(produtos.router)
    app.include_router(detalhes.router)
    app.include_router(web.router)
    return app
