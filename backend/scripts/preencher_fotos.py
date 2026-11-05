"""Preenche produto_na_rede.imagem_url (foto do produto no site da rede) para os SKUs já ligados.

Só para teste no app (modo de desenvolvimento); exibir no app publicado depende de autorização das redes.
Daqui em diante o Catalogador grava a foto sozinho; isto é a carga inicial.

- Giassi, Cooper e Sam's: API de catálogo, 50 SKUs por consulta (fq=skuId:...);
- Angeloni (robots.txt proíbe fq=): busca inteligente pelo código de barras, só para produto ainda sem foto.

Rodar:  python scripts/preencher_fotos.py      (1 requisição por segundo, respeitando o robots.txt)
"""

import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantofica.coleta.redes import NOME_NO_BANCO, REDES_VTEX  # noqa: E402
from quantofica.coleta.vtex import BloqueadoPeloRobots, ClienteHttp  # noqa: E402

LOTE = 50


def _imagem(item: dict) -> str | None:
    imagens = item.get("images") or []
    return imagens[0].get("imageUrl") if imagens else None


def por_sku(conn, http, rede) -> int:
    nome = NOME_NO_BANCO[rede.id]
    skus = [
        r["sku"]
        for r in conn.execute(
            """select pr.sku from produto_na_rede pr join rede r on r.id = pr.rede_id
               where r.nome = %s and pr.imagem_url is null""",
            (nome,),
        ).fetchall()
    ]
    gravadas = 0
    for i in range(0, len(skus), LOTE):
        lote = skus[i : i + LOTE]
        url = (
            f"https://{rede.dominio}/api/catalog_system/pub/products/search?"
            + "&".join(f"fq=skuId:{s}" for s in lote)
            + f"&_from=0&_to={LOTE - 1}"
        )
        achadas = {}
        for p in http(url, None) or []:
            for it in p.get("items") or []:
                if (img := _imagem(it)) and it.get("itemId") in lote:
                    achadas[it["itemId"]] = img
        with conn.cursor() as cur:
            cur.executemany(
                """update produto_na_rede set imagem_url = %s
                   where sku = %s and rede_id = (select id from rede where nome = %s)""",
                [(img, sku, nome) for sku, img in achadas.items()],
            )
        gravadas += len(achadas)
        if i % 2000 == 0:
            print(f"  {nome}: {i + len(lote)}/{len(skus)} SKUs, {gravadas} fotos", flush=True)
    return gravadas


def angeloni_sem_foto(conn, http, rede) -> int:
    """Produtos ligados ao Angeloni que ainda não têm foto em rede nenhuma: busca pelo código de barras."""
    linhas = conn.execute(
        """select pr.sku, min(e.codigo) as codigo from produto_na_rede pr join rede r on r.id = pr.rede_id
           join ean e on e.produto_id = pr.produto_id
           where r.nome = 'Angeloni' and pr.imagem_url is null
             and not exists (select 1 from produto_na_rede o where o.produto_id = pr.produto_id and o.imagem_url is not null)
           group by pr.sku"""
    ).fetchall()
    gravadas = 0
    for n, r in enumerate(linhas):
        url = f"https://{rede.dominio}/api/io/_v/api/intelligent-search/product_search/?query={r['codigo'].lstrip('0')}"
        try:
            resp = http(url, None) or {}
        except BloqueadoPeloRobots:
            break
        for p in resp.get("products") or []:
            for it in p.get("items") or []:
                if it.get("itemId") == r["sku"] and (img := _imagem(it)):
                    conn.execute(
                        """update produto_na_rede set imagem_url = %s
                           where sku = %s and rede_id = (select id from rede where nome = 'Angeloni')""",
                        (img, r["sku"]),
                    )
                    gravadas += 1
        if n % 500 == 0:
            print(f"  Angeloni: {n}/{len(linhas)}, {gravadas} fotos", flush=True)
    return gravadas


def main() -> int:
    http = ClienteHttp()
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        for rede in REDES_VTEX:
            if rede.id == "angeloni":
                continue
            print(rede.id, por_sku(conn, http, rede), "fotos", flush=True)
        angeloni = next(r for r in REDES_VTEX if r.id == "angeloni")
        print("angeloni", angeloni_sem_foto(conn, http, angeloni), "fotos", flush=True)
        total = conn.execute(
            """select count(distinct p.id) filter (where pr.imagem_url is not null) as com, count(distinct p.id) as todos
               from produto p left join produto_na_rede pr on pr.produto_id = p.id"""
        ).fetchone()
        print(f"produtos com foto: {total['com']} de {total['todos']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
