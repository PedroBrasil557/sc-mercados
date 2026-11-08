"""API do SC Mercados (FastAPI).

Rodar localmente:  uvicorn quantofica.api.app:create_app --factory --reload
Variável obrigatória: DATABASE_URL (ex.: postgresql://quantofica:local-apenas@localhost:54329/quantofica)
Opcional: PAINEL_TOKEN_SHA256 (liga o painel interno em /painel)
"""

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import catalogo, detalhes, erros, identidade, listas, mercado, painel, precos, produtos, web
from .banco import Conexao


def _aquecer(pool: ConnectionPool) -> None:
    """Catálogo e palavras de busca prontos logo que o servidor liga, em segundo plano."""
    try:
        with pool.connection() as conn:
            mercado.aquecer(conn)
    except Exception as erro:  # aquecer é só ganho de tempo: se falhar, a primeira busca faz a conta
        print(f"aquecer: {erro!r}", flush=True)


def create_app(dsn: str | None = None, aquecer_ao_ligar: bool | None = None) -> FastAPI:
    # Só no servidor de verdade (sem dsn, vindo do ambiente): nos testes o catálogo muda depois de a API ligar.
    aquecer_ao_ligar = dsn is None if aquecer_ao_ligar is None else aquecer_ao_ligar

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
        if aquecer_ao_ligar:
            catalogo.configurar(pool)  # cache vencido responde na hora e é refeito em segundo plano
            threading.Thread(target=_aquecer, args=(pool,), daemon=True).start()
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
    app.include_router(mercado.router)
    app.include_router(painel.router)
    app.include_router(erros.router)
    app.include_router(web.router)
    return app
