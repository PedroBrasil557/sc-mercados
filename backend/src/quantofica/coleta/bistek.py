"""Preços do Bistek nas lojas de Blumenau, pelas páginas da loja virtual (www.bistek.com.br).

A loja virtual é VTEX, mas o robots.txt proíbe /api/, ?map=, ?_q= e /busca/ (e os domínios
bistek.vtexcommercestable.com.br e bistek.myvtex.com proíbem tudo). As páginas de departamento e de coleção, com
?page=N e ?order=, são permitidas: esta coleta lê só essas páginas, como um visitante, identificada como
SCMercadosColetor, 1 requisição por segundo. Conferido em 05/11/2026:
- o HTML (2,5 MB descompactado) traz o estado da página num <template data-varname="__STATE__">: o cache
  normalizado do Apollo, com a busca ($ROOT_QUERY.productSearch(...): recordsFiltered, from, to), os produtos
  (Product:sp-<id>: productName, brand, categories), os SKUs (itemId, ean, measurementUnit, unitMultiplier, images)
  e a oferta de cada vendedor (commertialOffer: Price, ListPrice, AvailableQuantity);
- departamento: 18 produtos por página; coleção: 10. A busca da VTEX não passa do item 2.500 de uma mesma
  consulta: departamento maior (Mercearia tem 2.636) é lido em ordem alfabética e depois na inversa;
- um só vendedor ("1", Bistek Supermercados): o preço do site é o mesmo para todas as lojas. Como o site do Fort,
  vale para as duas lojas do Bistek em Blumenau. PriceValidUntil é sempre daqui a um ano: não é validade de oferta.

Atenção: o site tem regionalização por CEP (app avanti-regionalization: o CEP escolhe uma "franquia" com seus
vendedores). Sem CEP, o que aparece é o vendedor "1". Se um dia o preço de Blumenau for outro, os cupons fiscais
(coleta/cupom.py) mostram a diferença.

Dois modos:
- --ofertas (todo dia): as coleções de ofertas de SC (as que a página inicial mostra e as terminadas em "-sc");
- --catalogo (uma vez por semana): todos os departamentos de mercado. Cada página pesa 2,5 MB e o catálogo
  inteiro passa de 1 GB, por isso não roda todo dia. Roda no sábado à noite, antes do Catalogador (domingo 2h),
  que marca o que as redes VTEX não vendem: o produto novo que entrou aqui não vira busca diária nelas.

Para cada SKU com código de barras válido:
- produto que já está no catálogo (mesmo EAN, R1): liga o SKU (produto_na_rede) e grava o preço nas duas lojas,
  desde que o nome no site tenha o mesmo tamanho do produto (não mistura produtos entre mercados: na dúvida,
  não liga); outro tamanho desfaz a ligação de antes;
- produto novo (só no modo --catalogo): as regras do Catalogador (à venda, sem granel nem pack, tamanho no nome,
  categoria de mercado);
- vendido por quilo (granel, R4): fica de fora;
- trava por loja, como na coleta das redes VTEX: preço que mudou mais de 50% em relação ao da própria loja vai
  para revisão; a coleta seguinte vendo o mesmo preço confirma e publica.

Rodar:  python -m quantofica.coleta.bistek --ofertas | --catalogo  [--sem-banco] [--limite-paginas N]
Agenda (.github/workflows/bistek.yml): ofertas todo dia às 6h30; catálogo no sábado às 23h.
"""

import argparse
import gzip
import json
import os
import re
import sys
import urllib.error
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from ..regras import ean as ean_util
from ..regras import tamanho as tam
from . import gravar
from .catalogador import ESPACO, FORA, categoria
from .fort import lojas_da_cidade
from .gravar import Preco
from .vtex import ClienteHttp

DOMINIO = "www.bistek.com.br"
REDE = "Bistek"
ORIGEM = "bistek-site"
VENDEDOR = "1"  # Bistek Supermercados: o único vendedor do site
LIMITE_CONSULTA = 2500  # a busca da VTEX não passa do item 2.500 de uma mesma consulta
TENTATIVAS = 3  # página que falha (site lento, erro 5xx) é pedida de novo antes de dar a lista por incompleta
OFERTAS_FIXAS = ("ofertacos-da-quinzena-sc",)  # o encarte da quinzena de SC (nem sempre está na página inicial)
DEPARTAMENTOS_FORA = re.compile(r"floricultura|jardim")  # além do FORA do Catalogador
ORDEM, ORDEM_INVERSA = "OrderByNameASC", "OrderByNameDESC"  # ordem estável: a página 2 não repete a 1

_ESTADO = re.compile(r'<template data-type="json" data-varname="__STATE__">\s*<script>(.*?)</script>\s*</template>', re.S)
_ARGS_BUSCA = re.compile(r"^\$ROOT_QUERY\.productSearch\((\{.*?\})\)@")
_LOC = re.compile(r"<loc>\s*https://www\.bistek\.com\.br/([^<\s]+?)\s*</loc>")
_LINK = re.compile(r'href="/([a-z0-9-]+)"')
_INTERNO = re.compile(r"^0(300003|1000000)")  # códigos internos do Bistek (ver gtin)


class ClienteHtml(ClienteHttp):
    """O mesmo cliente das outras coletas (agente identificado, intervalo, robots.txt), lendo páginas HTML."""

    def pagina(self, url: str) -> str | None:
        self._checar_robots(url)
        try:
            bruto = self._bruto(url, cabecalhos={"Accept": "text/html,application/xml", "Accept-Encoding": "gzip"})
        except (urllib.error.URLError, TimeoutError):
            return None
        if bruto[:2] == b"\x1f\x8b":  # pedimos gzip: 2,5 MB viram ~300 kB na rede
            bruto = gzip.decompress(bruto)
        return bruto.decode("utf-8", "replace")


# ---------- leitura de uma página ----------


@dataclass(frozen=True)
class ItemDoSite:
    sku: str
    gtin: str | None  # None: sem código de barras ou código que não é GTIN de produto
    nome: str
    marca: str | None
    caminho: str  # "/Mercearia/Cafés/Em Grãos e Moídos/"
    granel: bool
    disponivel: bool
    preco_centavos: int | None
    preco_de_centavos: int | None
    imagem: str | None = None


@dataclass(frozen=True)
class Pagina:
    itens: list[ItemDoSite]
    produtos: int  # produtos nesta página (um produto pode ter mais de um SKU)
    total: int  # recordsFiltered da busca
    tamanho: int  # produtos por página (18 no departamento, 10 na coleção)


def _centavos(valor) -> int | None:
    try:
        c = int((Decimal(str(valor)) * 100).to_integral_value())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return c if c > 0 else None


def gtin(codigo: str | None) -> str | None:
    """GTIN de produto (regras/ean.py), sem os códigos internos do Bistek que passam no dígito verificador: carne,
    hortifrúti, padaria e marca própria ("3000030390307" no acém, "3000030436067" na água de coco Bistek) e
    "1000000003642" (presunto). O mesmo número em outra rede seria outro produto (R1)."""
    g = ean_util.gtin_de_produto(codigo)
    return None if g is None or _INTERNO.match(g) else g


def _valor(estado: dict, x):
    """Segue as referências do cache do Apollo ({"type": "id", "id": ...}) e abre os campos JSON."""
    if isinstance(x, dict) and x.get("type") == "id":
        return estado.get(x.get("id"), {})
    if isinstance(x, dict) and x.get("type") == "json":
        return x.get("json")
    return x


def _item(estado: dict, produto: dict, sku: dict) -> ItemDoSite:
    caminhos = _valor(estado, produto.get("categories")) or ["/"]
    oferta: dict = {}
    for v in sku.get("sellers") or []:
        vendedor = _valor(estado, v)
        if str(vendedor.get("sellerId")) == VENDEDOR:
            oferta = _valor(estado, vendedor.get("commertialOffer")) or {}
    preco = _centavos(oferta.get("Price"))
    de = _centavos(oferta.get("ListPrice"))
    imagens = [_valor(estado, i) for i in sku.get("images") or []]
    return ItemDoSite(
        sku=str(sku.get("itemId")),
        gtin=gtin(sku.get("ean")),
        nome=re.sub(r"\s+", " ", produto.get("productName") or sku.get("nameComplete") or "").strip().rstrip(".").strip(),
        marca=(produto.get("brand") or "").strip() or None,
        caminho=max(caminhos, key=len),  # o mais fundo
        granel=(sku.get("measurementUnit") or "un").lower() == "kg" or (sku.get("unitMultiplier") or 1) != 1,
        disponivel=bool(preco) and (oferta.get("AvailableQuantity") or 0) > 0,
        preco_centavos=preco,
        preco_de_centavos=de if preco and de and de > preco else None,
        imagem=imagens[0].get("imageUrl") if imagens else None,
    )


def ler_pagina(html: str) -> Pagina | None:
    """Os produtos da busca principal da página, ou None se a página não tem busca (layout mudou, página vazia)."""
    m = _ESTADO.search(html or "")
    if not m:
        return None
    try:
        estado = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    buscas = []
    for chave, valor in estado.items():
        args = _ARGS_BUSCA.match(chave)
        if args and isinstance(valor, dict) and "products" in valor:
            try:
                a = json.loads(args.group(1))
            except json.JSONDecodeError:
                continue
            buscas.append((int(valor.get("recordsFiltered") or 0), int(a.get("to", 0)) - int(a.get("from", 0)) + 1, valor))
    if not buscas:
        return None
    total, tamanho, busca = max(buscas, key=lambda b: b[0])  # a busca da página, não uma vitrine ao lado
    itens = []
    produtos = busca.get("products") or []
    for ref in produtos:
        produto = _valor(estado, ref)
        for chave, skus in produto.items():
            if chave.startswith("items"):  # items({"filter":"FIRST_AVAILABLE"}) ou ALL_AVAILABLE
                itens += [_item(estado, produto, _valor(estado, s)) for s in skus or []]
    return Pagina(itens, len(produtos), total, max(tamanho, 1))


# ---------- varredura ----------


@dataclass
class Varredura:
    itens: list[ItemDoSite] = field(default_factory=list)
    paginas: int = 0
    listas: list[str] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    _vistos: set[str] = field(default_factory=set)

    def guardar(self, itens: list[ItemDoSite]) -> None:
        for it in itens:
            if it.sku not in self._vistos:
                self._vistos.add(it.sku)
                self.itens.append(it)


def _url(caminho: str, pagina: int, ordem: str) -> str:
    return f"https://{DOMINIO}/{caminho}?order={ordem}&page={pagina}"


def _ler(http, url: str) -> Pagina | None:
    """Pede de novo só quando a requisição falhou; página que veio sem busca não melhora pedindo outra vez."""
    for _ in range(TENTATIVAS):
        texto = http.pagina(url)
        if texto is not None:
            return ler_pagina(texto)
    return None


def _paginas(http, caminho: str, ordem: str, v: Varredura, ate: int | None, limite_paginas: int | None) -> tuple[int, int] | None:
    """Lê as páginas de uma ordem até o fim, até `ate` posições ou até o limite da consulta.
    Devolve (total da busca, posições lidas) ou None se uma página falhou."""
    pagina = 1
    while True:
        if limite_paginas is not None and v.paginas >= limite_paginas:
            return None
        p = _ler(http, _url(caminho, pagina, ordem))
        v.paginas += 1
        if p is None:
            v.problemas.append(f"{caminho}: página {pagina} ({ordem}) sem produtos ou falhou")
            return None
        v.guardar(p.itens)
        lidas = pagina * p.tamanho
        alvo = min(p.total, ate + p.tamanho if ate is not None else p.total)  # uma página de folga na emenda
        if p.produtos < p.tamanho or lidas >= alvo or lidas + p.tamanho > LIMITE_CONSULTA:
            return p.total, min(lidas, p.total)
        pagina += 1


def ler_lista(http, caminho: str, v: Varredura, limite_paginas: int | None = None) -> None:
    """Uma lista inteira (departamento ou coleção), página por página, em ordem alfabética. Passando de 2.500
    produtos (o limite de uma consulta), o que faltou é lido na ordem inversa."""
    v.listas.append(caminho)
    lido = _paginas(http, caminho, ORDEM, v, None, limite_paginas)
    if lido is None or lido[0] <= lido[1]:
        return
    total, posicoes = lido
    if total > 2 * LIMITE_CONSULTA:
        v.problemas.append(f"{caminho}: {total} produtos, mais que duas consultas leem")
    _paginas(http, caminho, ORDEM_INVERSA, v, total - posicoes, limite_paginas)


def _rotas(http, sitemap: str) -> list[str]:
    return list(dict.fromkeys(_LOC.findall(http.pagina(f"https://{DOMINIO}/sitemap/{sitemap}") or "")))


def departamentos(http) -> list[str]:
    """Departamentos de mercado do sitemap (sem pet, bazar, floricultura...)."""
    return [
        d
        for d in _rotas(http, "department-0.xml")
        if "/" not in d and not FORA.search(d.replace("-", " ")) and not DEPARTAMENTOS_FORA.search(d)
    ]


def colecoes_de_oferta(http) -> list[str]:
    """Coleções de oferta de SC: as que a página inicial mostra e as do sitemap terminadas em "-sc"."""
    rotas = _rotas(http, "userRoute-0.xml")
    inicio = _LINK.findall(http.pagina(f"https://{DOMINIO}/") or "")
    escolhidas = [*OFERTAS_FIXAS, *(r for r in inicio if r in rotas), *(r for r in rotas if r.endswith("-sc"))]
    return [r for r in dict.fromkeys(escolhidas) if not r.endswith("-rs")]  # as do Rio Grande do Sul ficam de fora


def varrer(http, modo: str, limite_paginas: int | None = None) -> Varredura:
    v = Varredura()
    listas = colecoes_de_oferta(http) if modo == "ofertas" else departamentos(http)
    if not listas:
        v.problemas.append("sitemap sem listas para ler")
    for caminho in listas:
        ler_lista(http, caminho, v, limite_paginas)
        print(f"  bistek: {caminho}: {len(v.itens)} SKUs até aqui, {v.paginas} páginas", flush=True)
    return v


# ---------- gravação ----------


def gravar_varredura(conn, v: Varredura, agora: datetime, criar: bool) -> dict:
    """Liga os SKUs, cria os produtos novos (criar=True), grava os preços nas lojas de Blumenau e abre as revisões."""
    linha = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()
    if linha is None:
        raise RuntimeError(f"rede {REDE!r} não está cadastrada")
    rede_id = linha["id"]
    lojas = lojas_da_cidade(conn, rede_id)
    if not lojas:
        raise RuntimeError("nenhuma loja do Bistek em Blumenau no cadastro")

    produto_por_ean: dict[str, str] = {}
    ean_ok: set[str] = set()
    for r in conn.execute("select codigo, produto_id, status from ean").fetchall():
        produto_por_ean[r["codigo"]] = str(r["produto_id"])
        if r["status"] == "ok":
            ean_ok.add(r["codigo"])
    tamanhos = {
        str(r["id"]): (r["tamanho"], r["unidade"]) for r in conn.execute("select id, tamanho, unidade from produto").fetchall()
    }
    # Trava: o preço da própria loja (diferença entre redes é normal); a coleta seguinte com o mesmo preço confirma.
    anteriores = monitor.precos_anteriores(conn, lojas, "varejo")
    pendentes = monitor.precos_pendentes(conn)

    conta: Counter = Counter()
    novos_produtos, novos_eans = [], []
    ligacoes: dict[str, tuple[str, str, str | None]] = {}  # sku -> (produto, nome no site, imagem)
    recusados: dict[str, str] = {}  # sku -> produto: mesmo código, outra embalagem
    linhas: list[Preco] = []
    revisar: dict[str, tuple[Anomalia, dict]] = {}
    confirmados: list[str] = []
    com_preco: set[str] = set()

    for it in v.itens:
        if it.gtin is None:
            conta["sem_ean"] += 1
            continue
        if it.granel:  # preço por quilo depende da pesagem (R4)
            conta["granel"] += 1
            continue
        pid = produto_por_ean.get(it.gtin)
        if pid is None:
            if not criar:
                conta["fora_do_catalogo"] += 1
                continue
            cat, t = categoria(it.caminho, it.nome), tam.extrair(it.nome)
            motivo = (
                "indisponivel" if not it.disponivel
                else "pack" if tam.embalagem_multipla(it.nome)
                else "fora_do_mercado" if cat is None
                else "sem_tamanho" if t is None
                else None
            )  # fmt: skip
            if motivo:
                conta[motivo] += 1
                continue
            pid = str(uuid.uuid5(ESPACO, it.gtin))
            produto_por_ean[it.gtin] = pid
            ean_ok.add(it.gtin)
            tamanhos[pid] = (t.quantidade, t.unidade)
            novos_produtos.append((pid, cat, it.nome, it.marca, t.quantidade, t.unidade))
            novos_eans.append((it.gtin, pid))
            conta["novos"] += 1
        elif it.gtin not in ean_ok:
            conta["ean_em_revisao"] += 1
            continue
        elif not tam.mesmo_tamanho_no_site(it.nome, *tamanhos.get(pid, (None, None))):
            # O site mostra outra embalagem com o mesmo código: não liga, não grava preço, não compara (R1).
            conta["tamanho_diferente"] += 1
            recusados[it.sku] = pid
            continue
        ligacoes[it.sku] = (pid, it.nome, it.imagem)
        if not it.disponivel or pid in com_preco:
            continue
        com_preco.add(pid)
        evidencia = f"{ORIGEM}:{it.sku}"
        for loja in lojas:
            referencia = f"preco:{loja}:{pid}"
            if pendentes.get(referencia) == it.preco_centavos:
                confirmados.append(referencia)  # o mesmo preço de novo: não é erro do site
            elif monitor.preco_mudou_demais(it.preco_centavos, anteriores.get((loja, pid))):
                revisar[referencia] = (
                    Anomalia(referencia, "preço mudou mais de 50% em relação ao da própria loja"),
                    {"preco_centavos": it.preco_centavos, "preco_de_centavos": it.preco_de_centavos, "evidencia": evidencia},
                )
                continue
            linhas.append(Preco(pid, loja, it.preco_centavos, "varejo", "site", it.preco_de_centavos, None, evidencia))

    aceitos = {pid for pid, _, _ in ligacoes.values()}
    recusados = {sku: pid for sku, pid in recusados.items() if pid not in aceitos}
    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(
                """insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade)
                   values (%s, %s, %s, %s, %s, %s) on conflict (id) do nothing""",
                novos_produtos,
            )
            cur.executemany("insert into ean (codigo, produto_id) values (%s, %s) on conflict (codigo) do nothing", novos_eans)
            cur.executemany(
                """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site, imagem_url) values (%s, %s, %s, %s, %s)
                   on conflict (rede_id, sku) do update
                   set produto_id = excluded.produto_id, nome_no_site = excluded.nome_no_site,
                       imagem_url = coalesce(excluded.imagem_url, produto_na_rede.imagem_url)""",
                [(pid, rede_id, sku, nome, imagem) for sku, (pid, nome, imagem) in ligacoes.items()],
            )
            # Ligação e preço de antes com a embalagem errada saem (o histórico fica, imutável).
            cur.execute("delete from produto_na_rede where rede_id = %s and sku = any(%s)", (rede_id, list(recusados)))
            cur.execute(
                "delete from preco_atual where produto_id = any(%s) and loja_id = any(%s)", (list(recusados.values()), lojas)
            )
        mudaram = gravar.registrar(conn, linhas, agora)["mudaram"]
        abertas = sum(monitor.abrir_revisao(conn, "anomalia", a, proposta) for a, proposta in revisar.values())
        monitor.confirmar_precos(conn, confirmados, "coletor")
    return {
        "skus": len(v.itens),
        "paginas": v.paginas,
        "ligados": len(ligacoes),
        "novos": conta["novos"],
        "precos": len(linhas),
        "mudaram": mudaram,
        "revisao": abertas,
        "lojas": len(lojas),
        "descartes": {k: n for k, n in conta.items() if k != "novos"},
    }


def rodar(conn, http, agora: datetime, modo: str, limite_paginas: int | None = None) -> dict:
    rede = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()
    if rede is None:
        raise RuntimeError(f"rede {REDE!r} não está cadastrada")
    execucao = conn.execute(
        "insert into execucao_coleta (rede_id, iniciada_em) values (%s, %s) returning id", (rede["id"], agora)
    ).fetchone()["id"]
    try:
        v = varrer(http, modo, limite_paginas)
        if not v.itens:
            raise RuntimeError(f"a loja virtual do Bistek não respondeu: {v.problemas[:3]}")
        r = gravar_varredura(conn, v, agora, criar=modo == "catalogo")
        r["problemas"] = len(v.problemas)
    except Exception as erro:
        conn.execute(
            "update execucao_coleta set terminada_em = now(), status = 'falhou', erro = %s where id = %s",
            (repr(erro)[:2000], execucao),
        )
        raise
    conn.execute(
        """update execucao_coleta set terminada_em = now(), status = 'ok', eans_pedidos = %s, precos_gravados = %s,
           enviados_revisao = %s where id = %s""",
        (r["skus"], r["precos"], r["revisao"], execucao),
    )
    for problema in v.problemas[:20]:
        print(f"  problema: {problema}", file=sys.stderr)
    return r


def _resumo_sem_banco(v: Varredura) -> dict:
    """O que a leitura achou, sem tocar no banco (checagem do site)."""
    conta = Counter(
        "sem_ean" if it.gtin is None
        else "granel" if it.granel
        else "indisponivel" if not it.disponivel
        else "com_preco"
        for it in v.itens
    )  # fmt: skip
    return {"paginas": v.paginas, "listas": len(v.listas), "skus": len(v.itens), **conta, "problemas": v.problemas[:10]}


def main(argv: list[str] | None = None, http=None) -> int:
    p = argparse.ArgumentParser(description="Preços do Bistek (páginas da loja virtual)")
    modo = p.add_mutually_exclusive_group(required=True)
    modo.add_argument("--ofertas", action="store_const", dest="modo", const="ofertas", help="coleções de oferta (diário)")
    modo.add_argument("--catalogo", action="store_const", dest="modo", const="catalogo", help="departamentos (semanal)")
    p.add_argument("--sem-banco", action="store_true", help="só lê o site e mostra o que achou")
    p.add_argument("--limite-paginas", type=int, help="para de ler depois de N páginas (checagem)")
    args = p.parse_args(argv)
    http = http or ClienteHtml()

    if args.sem_banco:
        v = varrer(http, args.modo, args.limite_paginas)
        print(_resumo_sem_banco(v))
        for it in v.itens[:15]:
            print(f"  {it.sku} {it.gtin} {it.nome!r} {it.preco_centavos} (de {it.preco_de_centavos}) {it.caminho}")
        return 0 if v.itens else 1

    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "coletor") as resumo:
            r = rodar(conn, http, datetime.now(UTC), args.modo, args.limite_paginas)
            resumo[f"Bistek ({args.modo})"] = {k: r[k] for k in ("skus", "ligados", "novos", "precos", "revisao")}
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
