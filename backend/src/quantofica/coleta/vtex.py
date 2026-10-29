"""Coletor de preços das lojas VTEX (Giassi, Cooper, Angeloni, Sam's).

Fluxo, validado no protótipo de 22/10/2026:
1. /api/checkout/pub/regions: quais lojas (sellers) atendem o CEP;
2. busca do produto pelo EAN (catálogo ou busca inteligente, conforme o robots.txt da rede);
3. /api/checkout/pub/orderForms/simulation: preço daquela loja física.
Respeita o robots.txt e um intervalo mínimo entre requisições. Nunca contorna bloqueios.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..regras import ean as ean_util
from ..regras import tamanho
from . import robots

# Identificação nos sites dos mercados. A URL de contato entra quando o site do SC Mercados existir.
AGENTE = "SCMercadosColetor/0.1"
LOTE_SIMULACAO = 50

Http = Callable[[str, dict | None], object | None]  # (url, corpo_json) -> json decodificado ou None


class BloqueadoPeloRobots(Exception):
    pass


@dataclass
class Rede:
    id: str
    dominio: str
    cep: str
    filtro_seller: str | None = None  # ex.: "blumenau" (o CEP da Cooper devolve lojas de outras cidades)
    nomes_sellers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PrecoColetado:
    rede: str
    seller: str
    loja: str
    ean: str  # GTIN-14
    sku: str
    nome_no_site: str
    preco_centavos: int | None
    preco_de_centavos: int | None
    origem: str  # "simulacao_loja", "catalogo", "indisponivel" ou "embalagem_diferente"


class ClienteHttp:
    """GET/POST JSON com intervalo mínimo, agente identificado e robots.txt respeitado."""

    def __init__(self, intervalo_s: float = 1.0, abrir=urllib.request.urlopen, dormir=time.sleep, relogio=time.monotonic):
        self.intervalo_s, self._abrir, self._dormir, self._relogio = intervalo_s, abrir, dormir, relogio
        self._ultima = -1e9
        self._robots: dict[str, robots.Regras] = {}

    def _bruto(self, url: str, corpo: dict | None = None) -> bytes:
        espera = self.intervalo_s - (self._relogio() - self._ultima)
        if espera > 0:
            self._dormir(espera)
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(
            url,
            data=dados,
            method="POST" if dados else "GET",
            headers={"User-Agent": AGENTE, "Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with self._abrir(req, timeout=30) as resp:
                return resp.read()
        finally:
            self._ultima = self._relogio()

    def regras(self, dominio: str) -> robots.Regras:
        if dominio not in self._robots:
            try:
                texto = self._bruto(f"https://{dominio}/robots.txt").decode("utf-8", "replace")
            except (urllib.error.URLError, TimeoutError):
                texto = ""
            self._robots[dominio] = robots.ler(texto, "SCMercadosColetor")
        return self._robots[dominio]

    def __call__(self, url: str, corpo: dict | None = None):
        u = urlparse(url)
        caminho = u.path + (f"?{u.query}" if u.query else "")
        if not self.regras(u.netloc).permitido(caminho):
            raise BloqueadoPeloRobots(url)
        try:
            return json.loads(self._bruto(url, corpo).decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None


def _variantes(codigo: str) -> list[str]:
    g = ean_util.normalizar(codigo)
    curto = g.lstrip("0")
    # Na prática as redes guardam o EAN curto ou com 13 dígitos; testar 14 e 15 dobrava as requisições.
    return list(dict.fromkeys([curto, curto.zfill(13)]))


def sellers(http: Http, rede: Rede) -> dict[str, str]:
    regioes = http(f"https://{rede.dominio}/api/checkout/pub/regions?country=BRA&postalCode={rede.cep}", None) or []
    if not regioes:
        return {}
    achados = {s["id"]: rede.nomes_sellers.get(s["id"], s["name"]) for s in regioes[0].get("sellers", [])}
    if rede.filtro_seller:
        achados = {k: v for k, v in achados.items() if rede.filtro_seller in k.lower()}
    return achados


def _preco_catalogo(item: dict) -> tuple[int | None, int | None]:
    ofertas = [s["commertialOffer"] for s in item.get("sellers", [])]
    ok = [o for o in ofertas if o.get("AvailableQuantity", 0) > 0 and o.get("Price", 0) > 0]
    if not ok:
        return None, None
    o = min(ok, key=lambda o: o["Price"])
    return round(o["Price"] * 100), round(o["ListPrice"] * 100) if o.get("ListPrice") else None


def achar_sku(http: Http, rede: Rede, codigo: str) -> tuple[str, str, int | None, int | None] | None:
    """(sku, nome no site, preço de catálogo, preço "de") do produto com este EAN, ou None.

    Tenta o catálogo e, se o robots.txt proibir ou nada for achado, a busca inteligente.
    """
    alvo = ean_util.normalizar(codigo)
    for v in _variantes(codigo):
        for url in (
            f"https://{rede.dominio}/api/catalog_system/pub/products/search?fq=alternateIds_Ean:{v}",
            f"https://{rede.dominio}/api/io/_v/api/intelligent-search/product_search/?query={v}",
        ):
            try:
                resp = http(url, None)
            except BloqueadoPeloRobots:
                continue
            produtos = resp.get("products", []) if isinstance(resp, dict) else (resp or [])
            for p in produtos:
                for item in p.get("items", []):
                    if item.get("ean") and ean_util.mesmo_codigo(item["ean"], alvo):
                        preco, preco_de = _preco_catalogo(item)
                        return item["itemId"], p["productName"], preco, preco_de
    return None


def simular(http: Http, rede: Rede, skus: list[str], ids_sellers: list[str]) -> dict[tuple[str, str], dict]:
    pedidos = [{"id": s, "quantity": 1, "seller": v} for s in skus for v in ids_sellers]
    out: dict[tuple[str, str], dict] = {}
    for i in range(0, len(pedidos), LOTE_SIMULACAO):
        corpo = {"items": pedidos[i : i + LOTE_SIMULACAO], "postalCode": rede.cep, "country": "BRA"}
        resp = http(f"https://{rede.dominio}/api/checkout/pub/orderForms/simulation?sc=1", corpo) or {}
        for it in resp.get("items", []):
            out[(it["id"], it["seller"])] = it
    return out


def coletar(
    http: Http,
    rede: Rede,
    eans: list[str],
    conhecidos: dict[str, tuple[str, str]] | None = None,
    nao_encontrados: list[str] | None = None,
) -> list[PrecoColetado]:
    """Preço de cada EAN em cada loja da rede.

    `conhecidos` (GTIN -> (sku, nome no site)) pula a busca do produto; `nao_encontrados` recebe os GTINs
    que a rede não vende, para a coleta não procurar de novo todo dia.
    """
    lojas = sellers(http, rede)
    if not lojas:
        return []
    conhecidos = conhecidos or {}
    achados = {}
    for e in eans:
        gtin = ean_util.normalizar(e)
        if gtin in conhecidos:
            sku, nome = conhecidos[gtin]
            achados[gtin] = (sku, nome, None, None)
            continue
        r = achar_sku(http, rede, e)
        if r:
            achados[gtin] = r
        elif nao_encontrados is not None:
            nao_encontrados.append(gtin)
    sim = simular(http, rede, [a[0] for a in achados.values()], list(lojas))
    saida = []
    for gtin, (sku, nome, p_cat, p_de_cat) in achados.items():
        for seller, loja in lojas.items():
            s = sim.get((sku, seller))
            if tamanho.embalagem_multipla(nome):
                preco, preco_de, origem = None, None, "embalagem_diferente"  # R1: vai para revisão
            elif s and s.get("availability") == "available" and s.get("sellingPrice"):
                preco, preco_de, origem = s["sellingPrice"], s.get("listPrice") or None, "simulacao_loja"
            elif s is None and p_cat:
                preco, preco_de, origem = p_cat, p_de_cat, "catalogo"
            else:
                preco, preco_de, origem = None, None, "indisponivel"
            saida.append(PrecoColetado(rede.id, seller, loja, gtin, sku, nome, preco, preco_de, origem))
    return saida
