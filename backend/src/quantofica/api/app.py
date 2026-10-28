"""API do Quanto Fica (FastAPI).

Rodar localmente:  uvicorn quantofica.api.app:create_app --factory --reload
Variável obrigatória: DATABASE_URL (ex.: postgresql://quantofica:local-apenas@localhost:54329/quantofica)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import listas, precos


def create_app(dsn: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI):
        pool = ConnectionPool(
            dsn or os.environ["DATABASE_URL"], min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=True
        )
        app.state.pool = pool
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(title="Quanto Fica", version="0.1.0", lifespan=ciclo)

    @app.get("/v1/saude")
    def saude():
        return {"ok": True}

    app.include_router(listas.router)
    app.include_router(precos.router)
    return app
