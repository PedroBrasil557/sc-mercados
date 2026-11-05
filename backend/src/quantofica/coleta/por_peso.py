"""Itens por quilo nas redes VTEX (fase 1): liga os itens de cada rede aos genéricos e grava o preço do quilo.

- Ligar: o Catalogador, ao percorrer a rede toda (toda semana), passa os itens vendidos por quilo para `ligar`, que
  usa a regra estrita de regras/por_peso.py. `--descobrir` faz o mesmo só nos departamentos de comida fresca, para a
  primeira carga sem esperar a semana.
- Coletar: todo dia, junto da coleta de preços, `coletar` simula na loja os itens ligados e grava, por loja e
  genérico, o quilo mais barato entre os que casam ("qualquer marca"). A simulação devolve o preço do quilo (`price`)
  e o do passo de venda (`sellingPrice`, ex.: 0,25 kg); com desconto, o quilo sai do passo.
- A trava é a mesma da coleta: preço que mudou mais de 50% na própria loja espera a coleta seguinte confirmar.

Rodar:  python -m quantofica.coleta.por_peso --descobrir [--rede giassi]
        python -m quantofica.coleta.por_peso --coletar [--rede giassi]
"""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from ..regras import por_peso
from ..regras.preco import Faixa
from . import gravar
from . import redes as config
from .gravar import Preco
from .vtex import ClienteHttp, Http, Rede, sellers, simular

# Departamentos com itens por quilo, para a descoberta rápida (o Catalogador semanal lê a rede inteira).
FRESCOS = re.compile(r"padaria|hortifruti|fruta|verdura|legume|acougue|carne|aves|peixe|frios|laticin|frigorif|resfriad|congelad")


def garantir_genericos(conn: psycopg.Connection) -> None:
    """Os genéricos existem no catálogo como produtos de 1 kg (tamanho 1000 g), marcados como por_kg."""
    with conn.cursor() as cur:
        cur.executemany(
            "insert into categoria (id, nome, unidade_medida) values (%s, %s, 'g') on conflict (id) do nothing",
            [("carnes", "Carnes e aves"), ("padaria", "Padaria"), ("hortifruti", "Hortifrúti"), ("laticinios", "Laticínios")],
        )
    with conn.cursor() as cur:
        cur.executemany(
            """insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade, atributos)
               values (%s, %s, %s, null, 1000, 'g', %s)
               on conflict (id) do update set categoria_id = excluded.categoria_id, nome_humano = excluded.nome_humano,
                 atributos = produto.atributos || excluded.atributos""",
            [(g.produto_id, g.categoria, g.nome, json.dumps({"por_kg": True, "generico": g.slug})) for g in por_peso.GENERICOS],
        )


def _rede_id(conn: psycopg.Connection, rede: Rede) -> str:
    nome = config.NOME_NO_BANCO[rede.id]
    linha = conn.execute("select id from rede where nome = %s", (nome,)).fetchone()
    if linha is None:
        raise RuntimeError(f"rede {nome!r} não está cadastrada")
    return str(linha["id"])


def ligar(conn: psycopg.Connection, rede: Rede, itens: list, completa: bool = False) -> dict:
    """Liga os itens por quilo da rede (catalogador.ItemDoSite) aos genéricos. Devolve genérico -> SKUs ligados.

    Com a rede lida inteira (`completa`), desfaz as ligações de genérico que a regra não reconhece mais
    (item que saiu do site ou regra que ficou mais estrita)."""
    garantir_genericos(conn)
    rede_id = _rede_id(conn, rede)
    genericos = [g.produto_id for g in por_peso.GENERICOS]
    ligacoes: dict[str, tuple[str, str, str | None]] = {}  # sku -> (produto, nome no site, foto)
    for it in itens:
        if not getattr(it, "por_kg", False):
            continue
        g = por_peso.generico_do_item(it.nome, it.marca)
        if g:
            ligacoes[it.sku] = (g.produto_id, it.nome, it.imagem)
    with conn.transaction():
        with conn.cursor() as cur:
            # Um SKU já ligado a um produto com código de barras não é trocado (só os de genérico).
            cur.executemany(
                """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site, imagem_url) values (%s, %s, %s, %s, %s)
                   on conflict (rede_id, sku) do update set produto_id = excluded.produto_id,
                     nome_no_site = excluded.nome_no_site, imagem_url = coalesce(excluded.imagem_url, produto_na_rede.imagem_url)
                   where produto_na_rede.produto_id = any(%s::uuid[])""",
                [(p, rede_id, sku, nome, foto, genericos) for sku, (p, nome, foto) in ligacoes.items()],
            )
        desligados = 0
        if completa and ligacoes:  # rede sem nenhum item por quilo lido é sinal de leitura ruim: não desliga nada
            desligados = conn.execute(
                """delete from produto_na_rede where rede_id = %s and produto_id = any(%s::uuid[]) and not (sku = any(%s))""",
                (rede_id, genericos, list(ligacoes)),
            ).rowcount
    por_generico: dict[str, list[str]] = {}
    for sku, (p, _, _) in ligacoes.items():
        por_generico.setdefault(por_peso.POR_PRODUTO[p].slug, []).append(sku)
    return {"ligados": len(ligacoes), "genericos": len(por_generico), "desligados": desligados, "por_generico": por_generico}


def preco_do_quilo(item: dict) -> tuple[int, int | None] | None:
    """(preço do quilo, preço "de" do quilo) da simulação de um item vendido por quilo, ou None."""
    if item.get("availability") != "available" or (item.get("measurementUnit") or "").lower() != "kg":
        return None
    passo, venda, cheio = item.get("unitMultiplier") or 0, item.get("sellingPrice"), item.get("price")
    if passo <= 0 or not venda:
        return None
    # Sem desconto, o passo é o quilo vezes o passo (com arredondamento): vale o preço do quilo, exato.
    quilo = cheio if cheio and abs(venda - cheio * passo) <= 1 else round(venda / passo)
    de = item.get("listPrice")
    return quilo, (de if de and de > quilo else None)


def coletar(conn: psycopg.Connection, http: Http, rede: Rede, agora: datetime) -> dict:
    """Preço do quilo de cada genérico em cada loja da rede: o mais barato entre os itens ligados."""
    rede_id = _rede_id(conn, rede)
    faixa = config.FAIXA.get(rede.id, Faixa.VAREJO)
    ligados = conn.execute(
        """select pr.sku, pr.produto_id from produto_na_rede pr
           where pr.rede_id = %s and pr.produto_id = any(%s::uuid[])""",
        (rede_id, [g.produto_id for g in por_peso.GENERICOS]),
    ).fetchall()
    if not ligados:
        return {"rede": config.NOME_NO_BANCO[rede.id], "precos": 0, "revisao": 0}
    produto_do_sku = {r["sku"]: str(r["produto_id"]) for r in ligados}
    loja_por_seller = {
        r["seller_id"]: str(r["id"])
        for r in conn.execute(
            "select id, seller_id from loja where rede_id = %s and seller_id is not null", (rede_id,)
        ).fetchall()
    }
    vendedores = [s for s in sellers(http, rede) if s in loja_por_seller]
    sim = simular(http, rede, list(produto_do_sku), vendedores)

    melhor: dict[tuple[str, str], tuple[int, int | None, str]] = {}  # (loja, produto) -> (quilo, de, evidência)
    for (sku, seller), item in sim.items():
        p = preco_do_quilo(item)
        loja, produto = loja_por_seller.get(seller), produto_do_sku.get(sku)
        if p is None or loja is None or produto is None:
            continue
        chave = (loja, produto)
        if chave not in melhor or p[0] < melhor[chave][0]:
            melhor[chave] = (p[0], p[1], f"vtex:{rede.id}:{seller}:{sku}")

    anteriores = monitor.precos_anteriores(conn, list(loja_por_seller.values()), faixa)
    pendentes = monitor.precos_pendentes(conn)
    gravacoes, revisar, confirmados = [], [], []
    for (loja, produto), (quilo, de, evidencia) in melhor.items():
        referencia = f"preco:{loja}:{produto}"
        if pendentes.get(referencia) == quilo:
            confirmados.append(referencia)
        elif monitor.preco_mudou_demais(quilo, anteriores.get((loja, produto))):
            revisar.append(
                (
                    Anomalia(referencia, "preço mudou mais de 50% em relação ao da própria loja"),
                    {"preco_centavos": quilo, "preco_de_centavos": de, "evidencia": evidencia},
                )
            )
            continue
        gravacoes.append(Preco(produto, loja, quilo, faixa, "site", de, None, evidencia))
    with conn.transaction():
        r = gravar.registrar(conn, gravacoes, agora)
        abertas = sum(monitor.abrir_revisao(conn, "anomalia", a, prop) for a, prop in revisar)
        monitor.confirmar_precos(conn, confirmados, "coletor")
    return {"rede": config.NOME_NO_BANCO[rede.id], "precos": len(gravacoes), "mudaram": r["mudaram"], "revisao": abertas}


def main(argv: list[str] | None = None, http: Http | None = None) -> int:
    from . import catalogador  # aqui dentro: o catalogador importa este módulo

    p = argparse.ArgumentParser(description="Itens por quilo: ligar aos genéricos e coletar o preço do quilo")
    p.add_argument("--rede", choices=[r.id for r in config.REDES_VTEX])
    modo = p.add_mutually_exclusive_group(required=True)
    modo.add_argument("--descobrir", action="store_true", help="lê os departamentos de comida fresca e liga os itens")
    modo.add_argument("--coletar", action="store_true", help="grava o preço do quilo nas lojas")
    args = p.parse_args(argv)
    http = http or ClienteHttp()
    falhas = 0
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        garantir_genericos(conn)
        for rede in config.REDES_VTEX:
            if args.rede and rede.id != args.rede:
                continue
            try:
                if args.descobrir:
                    v = catalogador.varrer(http, rede, departamentos=FRESCOS)
                    r = ligar(conn, rede, v.itens)
                    print(f"{rede.id}: {r['ligados']} itens em {r['genericos']} genéricos ({v.paginas} páginas)")
                else:
                    print(coletar(conn, http, rede, datetime.now(UTC)))
            except Exception as erro:  # uma rede fora do ar não impede as outras
                falhas += 1
                print(f"{rede.id}: falhou: {erro!r}", file=sys.stderr)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
