"""Catálogo com nome curto e grupo de equivalência de cada produto, guardado por 10 minutos (por banco)."""

import time

from psycopg import Connection

from ..regras import nome as regra_nome

VALIDADE_S = 600
_CACHE: dict[str, tuple[float, dict]] = {}


def catalogo(conn: Connection) -> dict:
    """produto_id -> dados do produto com nome curto e grupo; grupo -> produto_ids."""
    chave = conn.info.dbname
    guardado = _CACHE.get(chave)
    if guardado and time.monotonic() - guardado[0] < VALIDADE_S:
        return guardado[1]
    produtos = {}
    grupos: dict[str, list[str]] = {}
    for r in conn.execute("select id, nome_humano, marca, tamanho, unidade, categoria_id from produto").fetchall():
        pid = str(r["id"])
        g = regra_nome.grupo(r["nome_humano"], r["marca"], r["tamanho"], r["unidade"])
        produtos[pid] = {
            "id": pid,
            "nome": r["nome_humano"],
            "nome_curto": regra_nome.nome_curto(r["nome_humano"], r["marca"]),
            "marca": r["marca"],
            "tamanho": r["tamanho"],
            "unidade": r["unidade"],
            "categoria": r["categoria_id"],
            "grupo": g,
        }
        if g:
            grupos.setdefault(g, []).append(pid)
    dados = {"produtos": produtos, "grupos": grupos}
    _CACHE[chave] = (time.monotonic(), dados)
    return dados


def limpar_cache() -> None:
    _CACHE.clear()
