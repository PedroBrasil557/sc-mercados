"""O catálogo vencido responde na hora e é refeito em segundo plano (no servidor ninguém espera os ~10 s)."""

import time

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from quantofica.api import catalogo as cat


def test_catalogo_vencido_responde_na_hora_e_atualiza_em_segundo_plano(banco_url):
    cat.limpar_cache()
    with psycopg.connect(banco_url, row_factory=dict_row) as conn:
        cat.catalogo(conn)
        chave = conn.info.dbname
        cat._CACHE[chave] = (time.monotonic() - cat.VALIDADE_S - 1, {"produtos": {}, "grupos": {}, "velho": True})
        pool = ConnectionPool(banco_url, min_size=1, max_size=2, kwargs={"row_factory": dict_row}, open=True)
        cat.configurar(pool)
        try:
            assert cat.catalogo(conn).get("velho") is True  # quem pediu não espera: recebe o de antes
            for _ in range(100):
                if "velho" not in cat.catalogo(conn):
                    break
                time.sleep(0.05)
            assert "velho" not in cat.catalogo(conn)  # o novo ficou pronto em segundo plano
        finally:
            cat.configurar(None)
            pool.close()
            cat.limpar_cache()


def test_sem_pool_o_catalogo_vencido_e_refeito_na_hora(banco_url):
    cat.limpar_cache()
    with psycopg.connect(banco_url, row_factory=dict_row) as conn:
        cat.catalogo(conn)
        cat._CACHE[conn.info.dbname] = (time.monotonic() - cat.VALIDADE_S - 1, {"produtos": {}, "grupos": {}, "velho": True})
        assert "velho" not in cat.catalogo(conn)
    cat.limpar_cache()
