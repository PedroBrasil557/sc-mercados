"""Banco de teste para os testes de integração.

Cada módulo de teste recebe o banco `quantofica_teste` recriado do zero no Postgres local
(db/docker-compose.yml) ou no do CI, com as migrações aplicadas pelo mesmo executor da produção. Sem Postgres disponível,
os testes que pedem o banco são pulados.
"""

import os
from pathlib import Path

import psycopg
import pytest

from quantofica.banco.migrar import migrar

PASTA_DB = Path(__file__).resolve().parents[2] / "db"
ADMIN = os.environ.get("TEST_ADMIN_DATABASE_URL", "postgresql://quantofica:local-apenas@localhost:54329/postgres")
NOME = "quantofica_teste"


@pytest.fixture(scope="module")
def banco_url() -> str:
    try:
        admin = psycopg.connect(ADMIN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("Postgres de teste indisponível (suba com: docker compose -p quantofica up -d --wait)")
    with admin:
        admin.execute(f"drop database if exists {NOME} with (force)")
        admin.execute(f"create database {NOME}")
    url = psycopg.conninfo.make_conninfo(ADMIN, dbname=NOME)
    migrar(url, PASTA_DB)
    return url
