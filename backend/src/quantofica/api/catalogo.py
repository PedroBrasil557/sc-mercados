"""Catálogo com nome curto e grupo de equivalência de cada produto, guardado na memória (por banco).

Montar o catálogo (23 mil produtos) leva uns 10 s no servidor grátis. No servidor, com o pool configurado
(configurar), o cache vencido continua respondendo na hora e o catálogo novo é montado em segundo plano: ninguém
espera. Sem pool (testes, scripts), o cache vencido é refeito na hora, como antes.
"""

import threading
import time

from psycopg import Connection

from ..regras import nome as regra_nome

VALIDADE_S = 1800  # o catálogo só muda com as coletas (poucas vezes por dia)
_CACHE: dict[str, tuple[float, dict]] = {}
_POOL = None
_ATUALIZANDO: set[str] = set()
_TRAVA = threading.Lock()


def configurar(pool) -> None:
    """Liga a atualização em segundo plano (servidor de verdade)."""
    global _POOL
    _POOL = pool


def catalogo(conn: Connection) -> dict:
    """produto_id -> dados do produto com nome curto e grupo; grupo -> produto_ids."""
    chave = conn.info.dbname
    guardado = _CACHE.get(chave)
    if guardado:
        if time.monotonic() - guardado[0] < VALIDADE_S:
            return guardado[1]
        if _POOL is not None:
            _atualizar_em_segundo_plano(chave)
            return guardado[1]
    return _montar(conn, chave)


def _atualizar_em_segundo_plano(chave: str) -> None:
    with _TRAVA:
        if chave in _ATUALIZANDO:
            return
        _ATUALIZANDO.add(chave)

    def rodar() -> None:
        try:
            with _POOL.connection() as c:
                _montar(c, chave)
        except Exception as erro:  # fica o catálogo de antes; a próxima vez tenta de novo
            print(f"catálogo: atualização falhou: {erro!r}", flush=True)
        finally:
            with _TRAVA:
                _ATUALIZANDO.discard(chave)

    threading.Thread(target=rodar, daemon=True).start()


def _montar(conn: Connection, chave: str) -> dict:
    produtos = {}
    grupos: dict[str, list[str]] = {}
    for r in conn.execute(
        """select id, nome_humano, marca, tamanho, unidade, categoria_id,
                  coalesce((atributos->>'por_kg')::boolean, false) as por_kg from produto"""
    ).fetchall():
        pid = str(r["id"])
        # Item por quilo já é "qualquer marca" (regras/por_peso.py): não entra em grupo com os embalados de 1 kg.
        g = None if r["por_kg"] else regra_nome.grupo(r["nome_humano"], r["marca"], r["tamanho"], r["unidade"])
        produtos[pid] = {
            "id": pid,
            "nome": r["nome_humano"],
            "nome_curto": regra_nome.nome_curto(r["nome_humano"], r["marca"]),
            "marca": r["marca"],
            "tamanho": r["tamanho"],
            "unidade": r["unidade"],
            "categoria": r["categoria_id"],
            "grupo": g,
            "por_kg": r["por_kg"],
        }
        if g:
            grupos.setdefault(g, []).append(pid)
    dados = {"produtos": produtos, "grupos": grupos}
    _CACHE[chave] = (time.monotonic(), dados)
    return dados


def limpar_cache() -> None:
    _CACHE.clear()
