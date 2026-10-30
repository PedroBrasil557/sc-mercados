"""Preços do Fort Atacadista pela loja virtual (não só os do encarte).

A loja virtual (fortatacadista.com.br, robots.txt libera /produtos/) usa a mesma API pública dos encartes
(coleta/fort.py): o preço de cada produto na loja online de Blumenau (1645). A rede usa preço regional, então,
como no encarte, ele vale para as duas lojas de Blumenau.

O site não mostra código de barras (nem a API: conferido no JavaScript público em 30/10/2026). Para não
misturar produtos entre mercados:
- só liga sozinho o que passa no casador estrito (mesma marca e tamanho; só palavras neutras de diferença);
- o que só o casador de encarte liga vira sugestão no painel (uma pessoa confirma);
- trava de preço: preço mais de 40% longe da mediana do mesmo produto nos outros mercados não é publicado.

Rodar:  python -m quantofica.coleta.fort_site
Agenda (.github/workflows/encartes.yml): todo dia às 7h, antes do Revisor.
"""

import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from ..regras import tamanho as tam
from . import gravar
from .casamento import casar, casar_estrito, palavras
from .fort import API, CABECALHOS, REDE, carregar_catalogo, lojas_da_cidade
from .gravar import Preco
from .vtex import ClienteHttp

SITEMAP = "https://fortatacadista.com.br/sitemap.xml"
LOJA_ONLINE = "1645"  # "blumenau" na loja virtual
POR_CONSULTA = 40
TRAVA = 0.4  # preço mais de 40% longe da mediana dos outros mercados: provável ligação errada, não publica
ORIGEM = "fort-site"


def ids_do_sitemap(http) -> list[str]:
    bruto = http.binario(SITEMAP) or b""
    return list(dict.fromkeys(re.findall(r"/produtos/(\d+)/", bruto.decode("utf-8", "replace"))))


def _centavos(valor) -> int | None:
    return round(float(valor) * 100) if valor else None


def produtos(http, ids: list[str]) -> dict[str, dict]:
    """Nome, marca e preço na loja de Blumenau, 40 produtos por consulta. Produto fora de linha volta nulo."""
    saida: dict[str, dict] = {}
    for i in range(0, len(ids), POR_CONSULTA):
        corpo = " ".join(
            f'p{x}: product(id: "{x}", storeId: "{LOJA_ONLINE}") {{ id name brand {{ name }} '
            f'pricing(storeId: "{LOJA_ONLINE}") {{ price promotionalPrice promotion }} }}'
            for x in ids[i : i + POR_CONSULTA]
            if x.isdigit()
        )
        r = http(API, {"query": f'query {{ publicViewer(storeId: "{LOJA_ONLINE}") {{ id {corpo} }} }}'}, CABECALHOS) or {}
        for chave, p in ((r.get("data") or {}).get("publicViewer") or {}).items():
            if not chave.startswith("p") or not p or not p.get("pricing"):
                continue
            preco = _centavos(p["pricing"].get("price"))
            promo = _centavos(p["pricing"].get("promotionalPrice"))
            if not preco:
                continue
            em_oferta = bool(p["pricing"].get("promotion")) and promo and promo < preco
            saida[p["id"]] = {
                "nome": re.sub(r"\s+", " ", p["name"] or "").strip(),
                "marca": ((p.get("brand") or {}).get("name") or "").strip() or None,
                "preco_centavos": promo if em_oferta else preco,
                "preco_de_centavos": preco if em_oferta else None,
            }
    return saida


def _grupos(catalogo) -> dict[tuple, list]:
    g: dict[tuple, list] = defaultdict(list)
    for c in catalogo.candidatos:
        if c.tamanho and c.marca:
            g[(" ".join(palavras(c.marca)), c.tamanho.unidade, round(c.tamanho.quantidade))].append(c)
    return g


def ligar(nome: str, marca: str | None, grupos: dict[tuple, list]) -> tuple[list[str], str | None]:
    """(produtos ligados com certeza, produto sugerido para uma pessoa confirmar)."""
    t = tam.extrair(nome)
    if t is None or not marca:
        return [], None
    grupo = grupos.get((" ".join(palavras(marca)), t.unidade, round(t.quantidade)), [])
    if not grupo:
        return [], None
    certos = casar_estrito(nome, marca, grupo)
    if certos:
        return [c.chave for c in certos], None
    provavel = casar(nome if " ".join(palavras(marca)) in " ".join(palavras(nome)) else f"{nome} {marca}", grupo)
    return [], (provavel[0].chave if len(provavel) == 1 else None)


def medianas_nos_outros(conn, rede_id, produtos_ids: list[str], agora: datetime) -> dict[str, int]:
    """Mediana do preço de varejo de cada produto nos outros mercados (preço atual, últimos 3 dias)."""
    por: dict[str, list[int]] = defaultdict(list)
    for r in conn.execute(
        """select a.produto_id, a.preco_centavos from preco_atual a join loja l on l.id = a.loja_id
           where a.produto_id = any(%s) and l.rede_id <> %s and a.faixa = 'varejo' and a.observado_em >= %s""",
        (produtos_ids, rede_id, agora - timedelta(days=3)),
    ).fetchall():
        por[str(r["produto_id"])].append(r["preco_centavos"])
    return {p: int(statistics.median(v)) for p, v in por.items()}


def fora_da_trava(preco: int, mediana: int | None) -> bool:
    return mediana is not None and abs(preco - mediana) > TRAVA * mediana


def rodar(conn, http, agora: datetime) -> dict:
    rede_id = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()["id"]
    execucao = conn.execute(
        "insert into execucao_coleta (rede_id, iniciada_em) values (%s, %s) returning id", (rede_id, agora)
    ).fetchone()["id"]
    try:
        resumo = _rodar(conn, http, agora, rede_id)
    except Exception as erro:
        conn.execute(
            "update execucao_coleta set terminada_em = now(), status = 'falhou', erro = %s where id = %s",
            (repr(erro)[:2000], execucao),
        )
        raise
    conn.execute(
        """update execucao_coleta set terminada_em = now(), status = 'ok', eans_pedidos = %s, precos_gravados = %s,
           enviados_revisao = %s where id = %s""",
        (resumo["no_site"], resumo["precos"], resumo["revisao"] + resumo["sugestoes"], execucao),
    )
    return resumo


def _rodar(conn, http, agora: datetime, rede_id) -> dict:
    resumo: Counter = Counter()
    lojas = lojas_da_cidade(conn, rede_id)
    if not lojas:
        raise RuntimeError("nenhuma loja do Fort em Blumenau no cadastro")
    no_site = produtos(http, ids_do_sitemap(http))
    if not no_site:
        raise RuntimeError("a loja virtual do Fort não respondeu")
    resumo["no_site"] = len(no_site)

    ligados: dict[str, list[str]] = defaultdict(list)
    for r in conn.execute("select sku, produto_id from produto_na_rede where rede_id = %s", (rede_id,)).fetchall():
        ligados[r["sku"]].append(str(r["produto_id"]))
    grupos = _grupos(carregar_catalogo(conn))
    novos, sugestoes = [], []
    for sku, p in no_site.items():
        if sku in ligados:
            continue
        certos, sugerido = ligar(p["nome"], p["marca"], grupos)
        if certos:
            ligados[sku] = certos
            novos += [(c, sku, p["nome"]) for c in certos]
        elif sugerido:
            sugestoes.append((sku, p, sugerido))

    precos_ids = sorted({pid for sku in no_site if sku in ligados for pid in ligados[sku]})
    medianas = medianas_nos_outros(conn, rede_id, precos_ids, agora)
    linhas, travados = [], []
    for sku, p in no_site.items():
        for produto in ligados.get(sku, []):
            if fora_da_trava(p["preco_centavos"], medianas.get(produto)):
                travados.append((sku, produto, p))
                continue
            linhas += [
                Preco(produto, loja, p["preco_centavos"], "varejo", "site", p["preco_de_centavos"], None, f"{ORIGEM}:{sku}")
                for loja in lojas
            ]

    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(
                """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, %s, %s)
                   on conflict (rede_id, sku) do nothing""",
                [(produto, rede_id, sku, nome) for produto, sku, nome in novos],
            )
        resumo["mudaram"] = gravar.registrar(conn, linhas, agora)["mudaram"]
        for sku, p, sugerido in sugestoes:
            resumo["sugestoes"] += monitor.abrir_revisao(
                conn,
                "ean",
                Anomalia(f"{ORIGEM}:{sku}", f"produto do site do Fort sem código de barras: {p['nome']!r}", 4),
                {"origem": ORIGEM, "rede": REDE, "sku": sku, "nome": p["nome"], "marca": p["marca"],
                 "preco_centavos": p["preco_centavos"], "produtos": [sugerido]},
            )  # fmt: skip
        for sku, produto, p in travados:
            resumo["revisao"] += monitor.abrir_revisao(
                conn,
                "anomalia",
                Anomalia(
                    f"preco:{lojas[0]}:{produto}",
                    f"preço do site do Fort mais de 40% longe da mediana dos outros mercados ({p['nome']!r}): "
                    "confira se a ligação pelo nome está certa",
                ),
                {"preco_centavos": p["preco_centavos"], "evidencia": f"{ORIGEM}:{sku}", "sku": sku},
            )
    resumo["ligados_agora"] = len({sku for _, sku, _ in novos})
    resumo["ligados"] = sum(1 for sku in no_site if sku in ligados)
    resumo["precos"] = len(linhas)
    resumo["travados"] = len(travados)
    return dict(resumo)


def ligar_sugestao(conn, item_id: str, proposta: dict, produtos_ids: list[str], quem: str, agora: datetime) -> int:
    """Painel ou Revisor confirmou a ligação: lembra o SKU do Fort e publica o preço (com a trava). Resolve o item."""
    rede_id = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()["id"]
    lojas = lojas_da_cidade(conn, rede_id)
    medianas = medianas_nos_outros(conn, rede_id, produtos_ids, agora)
    linhas = []
    for produto in produtos_ids:
        conn.execute(
            """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, %s, %s)
               on conflict (rede_id, sku) do update set produto_id = excluded.produto_id""",
            (produto, rede_id, proposta["sku"], proposta["nome"]),
        )
        if not fora_da_trava(proposta["preco_centavos"], medianas.get(produto)):
            linhas += [
                Preco(produto, loja, proposta["preco_centavos"], "varejo", "site", None, None, f"{ORIGEM}:{proposta['sku']}")
                for loja in lojas
            ]
    gravar.registrar(conn, linhas, agora)
    conn.execute(
        "update fila_revisao set status = 'resolvida', revisado_por = %s, decidido_em = now() where id = %s", (quem, item_id)
    )
    return len(linhas)


def main(http=None) -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "coletor") as resumo:
            r = rodar(conn, http or ClienteHttp(), datetime.now(UTC))
            resumo["Fort (site)"] = {k: r.get(k, 0) for k in ("no_site", "ligados", "precos", "sugestoes", "travados")}
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
