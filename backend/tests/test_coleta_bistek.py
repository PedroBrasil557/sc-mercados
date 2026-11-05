"""Coleta do Bistek pelas páginas da loja virtual: leitura do estado da página, paginação, robots.txt e gravação
(ligação pelo EAN, recusa por tamanho diferente, produto novo, preço nas duas lojas de Blumenau e trava)."""

import gzip
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from quantofica.coleta import bistek
from quantofica.coleta.bistek import ClienteHtml, ItemDoSite, Varredura
from quantofica.coleta.vtex import BloqueadoPeloRobots

# Códigos de barras de verdade, vistos no site do Bistek em 05/11/2026.
TIROL = "7896256600780"  # Creme De Leite Tirol 200g
ARROZ = "7896084700027"  # Arroz Parboilizado Kiarroz 1kg
CAFE = "7896045101665"  # Café Em Pó 3 Corações Gourmet Sul De Minas 250g
DORI = "7896058500219"  # Bala Gelatina Dori Urso 60g
PAPEL = "7891172432026"  # Papel Higiênico Neve Leve 16 Pague 15
FRANGO = "7893000005945"  # Filé de peito de frango Sadia 1kg
MAGGI = "7891000502105"  # Tempero Fondor Maggi 120g


def produto(sku, ean, nome, preco, de=None, caminho="/Mercearia/", estoque=10000, unidade="un", mult=1, vendedor="1"):
    return {"sku": sku, "ean": ean, "nome": nome, "preco": preco, "de": de if de is not None else preco,
            "caminho": caminho, "estoque": estoque, "unidade": unidade, "mult": mult, "vendedor": vendedor}  # fmt: skip


def ref(chave):
    return {"type": "id", "generated": True, "id": chave, "typename": "x"}


def html(produtos, total, de=0, tamanho=18, filtro="FIRST_AVAILABLE"):
    """Uma página como a do Bistek: o cache normalizado do Apollo num <template data-varname="__STATE__">."""
    estado = {}
    for p in produtos:
        chave = f"Product:sp-{p['sku']}"
        sku = f'{chave}.items({{"filter":"{filtro}"}}).0'
        vendedor, oferta, imagem = f"{sku}.sellers.0", f"${sku}.sellers.0.commertialOffer", f"Image:{p['sku']}"
        estado[oferta] = {
            "Price": p["preco"],
            "ListPrice": p["de"],
            "AvailableQuantity": p["estoque"],
            "PriceValidUntil": "2027-11-05T18:39:50Z",
        }
        estado[vendedor] = {"sellerId": p["vendedor"], "sellerName": "Bistek Supermercados", "commertialOffer": ref(oferta)}
        estado[imagem] = {"imageId": p["sku"], "imageUrl": f"https://bistek.vtexassets.com/arquivos/ids/{p['sku']}.jpg"}
        estado[sku] = {
            "itemId": p["sku"],
            "ean": p["ean"],
            "measurementUnit": p["unidade"],
            "unitMultiplier": p["mult"],
            "images": [ref(imagem)],
            "sellers": [ref(vendedor)],
        }
        caminhos = [p["caminho"], "/" + p["caminho"].strip("/").split("/")[0] + "/"]
        estado[chave] = {
            "productId": p["sku"],
            "productName": p["nome"],
            "brand": "Marca",
            "categories": {"type": "json", "json": caminhos},
            f'items({{"filter":"{filtro}"}})': [ref(sku)],
        }
    facetas = [{"key": "c", "value": "mercearia"}]
    args = {"from": de, "orderBy": "OrderByNameASC", "query": "mercearia", "selectedFacets": facetas, "to": de + tamanho - 1}
    args = json.dumps(args, separators=(",", ":"))
    busca = f'$ROOT_QUERY.productSearch({args})@context({{"provider":"vtex.search-graphql"}})@runtimeMeta({{"hash":"a9"}})'
    estado[busca] = {"products": [ref(f"Product:sp-{p['sku']}") for p in produtos], "recordsFiltered": total}
    estado[f"{busca}.correction"] = {"misspelled": True}
    corpo = json.dumps(estado, ensure_ascii=False)
    return (
        f'<html><body><template data-type="json" data-varname="__STATE__">\n<script>{corpo}</script>\n</template></body></html>'
    )


def test_le_os_produtos_do_estado_da_pagina():
    pagina = bistek.ler_pagina(
        html(
            [
                produto(
                    "1273418", TIROL, "Creme De Leite Tirol 200g", 3.29, caminho="/Mercearia/Cremes de Leite/Cremes de Leite/"
                ),
                produto("2126427", "8028630011021", "Farinha Grano Duro Agugiaro 1kg", 23.6, de=30.89),
                produto("1293044", "2700006916289", "Amido De Milho Maizena Caixa 200g", 7.41),  # faixa de uso interno
                produto("4004254", "1000000003642", "Presunto Perdigão 200g", 9.24),  # código interno do Bistek
                produto("3039021", "3000030390215", "Acém Frescal 1,5 Kg", 97.41),  # código interno (carnes)
                produto("9", FRANGO, "Filé de Frango kg", 29.9, unidade="kg"),
                produto("10", MAGGI, "Tempero Fondor Maggi 120g", 12.35, estoque=0),
                produto("11", DORI, "Bala Dori 60g", 3.59, vendedor="outro"),  # só o vendedor "1" vale
            ],
            total=2636,
            de=36,
        )
    )
    assert (pagina.total, pagina.tamanho, pagina.produtos) == (2636, 18, 8)
    tirol, farinha, maizena, presunto, acem, frango, maggi, dori = pagina.itens
    assert acem.gtin is None
    assert tirol.sku == "1273418" and tirol.gtin == "0" + TIROL and tirol.nome == "Creme De Leite Tirol 200g"
    assert tirol.caminho == "/Mercearia/Cremes de Leite/Cremes de Leite/"  # a categoria mais funda
    assert (tirol.preco_centavos, tirol.preco_de_centavos, tirol.disponivel) == (329, None, True)
    assert tirol.imagem == "https://bistek.vtexassets.com/arquivos/ids/1273418.jpg"
    assert (farinha.preco_centavos, farinha.preco_de_centavos) == (2360, 3089)
    assert maizena.gtin is None and presunto.gtin is None
    assert frango.granel and not maggi.disponivel
    assert dori.preco_centavos is None and not dori.disponivel
    assert bistek.ler_pagina("<html>sem estado</html>") is None


class SiteDoBistek:
    """As páginas da loja virtual, sem rede: departamentos e coleções em ordem de nome, N produtos por página."""

    def __init__(self, listas, departamentos=(), rotas=(), links_inicio=(), tamanho=18, categorias=()):
        self.listas, self.departamentos, self.rotas, self.categorias = listas, departamentos, rotas, categorias
        self.links_inicio, self.tamanho = links_inicio, tamanho
        self.chamadas: list[str] = []

    def pagina(self, url):
        self.chamadas.append(url)
        u = urlparse(url)
        caminho = u.path.strip("/")
        if caminho.startswith("sitemap/"):
            rotas = self.departamentos if "department" in caminho else self.categorias if "category" in caminho else self.rotas
            return "<urlset>" + "".join(f"<url><loc>https://www.bistek.com.br/{r}</loc></url>" for r in rotas) + "</urlset>"
        if caminho == "":
            return "<html>" + "".join(f'<a href="/{r}">oferta</a>' for r in self.links_inicio) + "</html>"
        if caminho not in self.listas:
            return "<html>página sem produtos</html>"
        q = parse_qs(u.query)
        pagina, ordem = int(q["page"][0]), q["order"][0]
        todos = sorted(self.listas[caminho], key=lambda p: p["nome"], reverse=ordem.endswith("DESC"))
        de = (pagina - 1) * self.tamanho
        if pagina > bistek.MAX_PAGINAS:
            return "<html>o site não serve esta página</html>"
        return html(todos[de : de + self.tamanho], len(todos), de, self.tamanho)


def muitos(n, prefixo="Produto"):
    return [produto(str(i), TIROL, f"{prefixo} {i:04d} 200g", 1.0) for i in range(n)]


def test_le_departamento_maior_que_uma_consulta_nas_duas_ordens(monkeypatch):
    monkeypatch.setattr(bistek, "MAX_PAGINAS", 5)
    site = SiteDoBistek({"mercearia": muitos(64), "bebidas": muitos(25)}, tamanho=10)
    v = Varredura()
    bistek.ler_lista(site, "mercearia", v)
    assert len(v.itens) == 64 and not v.problemas  # 50 na ordem alfabética, o resto na inversa
    assert all("order=OrderByName" in u for u in site.chamadas)  # ordem estável: a página 2 não repete a 1
    assert sum("DESC" in u for u in site.chamadas) == 3
    bistek.ler_lista(site, "bebidas", v)
    assert len(v.itens) == 64 + 0  # mesmos SKUs: não duplica
    assert site.chamadas[-1].endswith("order=OrderByNameASC&page=3")


def test_departamento_maior_que_as_duas_ordens_e_lido_pelas_subcategorias(monkeypatch):
    monkeypatch.setattr(bistek, "MAX_PAGINAS", 2)  # 20 produtos por ordem, 40 nas duas
    cafes, massas = muitos(30, "Cafe"), [produto(str(100 + i), TIROL, f"Massa {i:04d} 500g", 1.0) for i in range(25)]
    site = SiteDoBistek(
        {"mercearia": cafes + massas, "mercearia/cafes": cafes, "mercearia/massas": massas},
        departamentos=["mercearia"],
        categorias=["mercearia/cafes", "mercearia/massas", "bebidas/sucos"],
        tamanho=10,
    )
    v = bistek.varrer(site, "catalogo")
    assert len(v.itens) == 55 and not v.problemas
    assert v.listas == ["mercearia", "mercearia/cafes", "mercearia/massas"]
    # Sem subcategorias para descer, o que sobrou vira problema (a varredura não finge que leu tudo).
    site.categorias = []
    v = bistek.varrer(site, "catalogo")
    assert v.problemas == ["mercearia: 15 produtos além do que as duas ordens alcançam, sem subcategorias"]


def test_varre_departamentos_de_mercado_e_colecoes_de_oferta_de_sc():
    site = SiteDoBistek(
        {
            "mercearia": muitos(20),
            "bistek": muitos(3, "Outro"),
            "ofertacos-da-quinzena-sc": muitos(2),
            "ofertas-sadia": muitos(1),
        },
        departamentos=["mercearia", "pet-shop", "bazar", "floricultura-e-jardim", "bistek"],
        rotas=["ofertas-sadia", "ofertacos-da-quinzena-sc", "ofertacos-da-quinzena-rs", "especial-natal", "biscoitos-sc"],
        links_inicio=["ofertas-sadia", "fale-conosco", "ofertacos-da-quinzena-rs"],
    )
    v = bistek.varrer(site, "catalogo")
    assert v.listas == ["mercearia", "bistek"]  # sem pet, bazar e floricultura
    assert not any("pet-shop" in u or "bazar" in u for u in site.chamadas)
    o = bistek.varrer(site, "ofertas")
    assert o.listas == ["ofertacos-da-quinzena-sc", "ofertas-sadia", "biscoitos-sc"]  # sem as do RS nem as antigas
    assert o.problemas == ["biscoitos-sc: página 1 (OrderByNameASC) sem produtos ou falhou"]


class Resposta:
    def __init__(self, corpo):
        self.corpo = corpo

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def read(self):
        return self.corpo


def test_cliente_respeita_o_robots_e_descompacta():
    robots = "User-agent: *\nDisallow: /busca/\nDisallow: /*?map=\nDisallow: /*&map=\nDisallow: /api/\n"
    pedidos = []

    def abrir(req, timeout):
        pedidos.append(req)
        if req.full_url.endswith("/robots.txt"):
            return Resposta(robots.encode())
        return Resposta(gzip.compress("<html>Café</html>".encode()))

    cliente = ClienteHtml(abrir=abrir, dormir=lambda s: None)
    assert cliente.pagina("https://www.bistek.com.br/mercearia?order=OrderByNameASC&page=2") == "<html>Café</html>"
    for proibida in ("/api/catalog_system/pub/products/search", "/mercearia?map=c", "/busca/?ft=arroz"):
        with pytest.raises(BloqueadoPeloRobots):
            cliente.pagina(f"https://www.bistek.com.br{proibida}")
    pagina = pedidos[-1]
    assert pagina.get_header("User-agent") == "SCMercadosColetor/0.1"  # identificado, sem fingir ser navegador
    assert pagina.get_header("Accept-encoding") == "gzip"
    assert len(pedidos) == 2  # robots.txt uma vez e a página; as proibidas nem saem


def item(sku, ean, nome, preco, de=None, caminho="/Mercearia/", granel=False, disponivel=True):
    gtin = bistek.gtin(ean)
    return ItemDoSite(sku, gtin, nome, "Marca", caminho, granel, disponivel, preco if disponivel else None, de, f"img-{sku}")


def test_grava_liga_recusa_cria_e_trava(banco_url):
    agora = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)
    ids = {k: uuid4() for k in ("blumenau", "brusque", "rede", "garcia", "itoupava", "fora", "arroz", "tirol", "dori")}
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC'), (%s, 'Brusque', 'SC')",
                  (ids["blumenau"], ids["brusque"]))  # fmt: skip
        c.execute("insert into rede (id, nome, site, tem_api) values (%s, 'Bistek', 'www.bistek.com.br', true)", (ids["rede"],))
        for loja, cidade in (("garcia", "blumenau"), ("itoupava", "blumenau"), ("fora", "brusque")):
            c.execute(
                "insert into loja (id, rede_id, cidade_id, nome) values (%s, %s, %s, %s)",
                (ids[loja], ids["rede"], ids[cidade], f"Bistek {loja}"),
            )
        c.execute(
            "insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g'), ('laticinios', 'Lat.', 'g'),"
            " ('doces', 'Doces', 'g'), ('cafe', 'Café', 'g'), ('mercearia', 'Merc.', 'un'), ('higiene', 'Hig.', 'un')"
        )
        for chave, cat, nome, q, ean in (
            ("arroz", "graos", "Arroz Parboilizado Kiarroz 1kg", 1000, ARROZ),
            ("tirol", "laticinios", "Creme de Leite Tirol 200g", 200, TIROL),
            ("dori", "doces", "Bala de Gelatina Dori Ursinhos 100g", 100, DORI),  # no Bistek o mesmo código é o de 60 g
        ):
            c.execute(
                "insert into produto (id, categoria_id, nome_humano, tamanho, unidade) values (%s, %s, %s, %s, 'g')",
                (ids[chave], cat, nome, q),
            )
            c.execute("insert into ean (codigo, produto_id) values (%s, %s)", ("0" + ean, ids[chave]))
        # Antes: o arroz custava R$ 10,00 no Garcia e a bala estava ligada (errado) com preço.
        for produto_id, centavos in ((ids["arroz"], 1000), (ids["dori"], 359)):
            c.execute(
                "insert into observacao_preco (produto_id, loja_id, preco_centavos, fonte, observado_em) "
                "values (%s, %s, %s, 'site', %s)",
                (produto_id, ids["garcia"], centavos, agora - timedelta(days=1)),
            )
        c.execute(
            "insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, '2190010', 'Bala Dori')",
            (ids["dori"], ids["rede"]),
        )

        v = Varredura()
        v.guardar([
            item("1002678", ARROZ, "Arroz Parboilizado Kiarroz 1kg", 411),  # caiu 59%: trava no Garcia
            item("1273418", TIROL, "Creme De Leite Tirol 200g", 329, de=399),
            item("2190010", DORI, "Bala Gelatina Dori Urso 60g", 359),  # outro tamanho: não liga
            item("2002590", CAFE, "Café Em Pó 3 Corações Gourmet Sul De Minas 250g", 2677, caminho="/Mercearia/Cafés/Especiais/"),
            item("1408178", PAPEL, "Papel Higiênico Neve 30m Pacote Leve 16 Pague 15 Unidades", 2881),
            item("730882", FRANGO, "Filé De Peito De Frango Sadia kg", 1851, granel=True),
            item("1014420", MAGGI, "Tempero Em Pó Fondor Maggi 120g", 1235, disponivel=False),
            item("1", None, "Sem código 1kg", 100),
        ])  # fmt: skip
        r = bistek.gravar_varredura(c, v, agora, criar=True)
        assert (r["lojas"], r["ligados"], r["novos"], r["revisao"]) == (2, 3, 1, 1)
        assert r["descartes"] == {"tamanho_diferente": 1, "pack": 1, "granel": 1, "indisponivel": 1, "sem_ean": 1}

        def precos(produto_id):
            linhas = c.execute(
                "select loja_id, preco_centavos, preco_de_centavos from preco_atual where produto_id = %s", (produto_id,)
            ).fetchall()
            return {str(x["loja_id"]): (x["preco_centavos"], x["preco_de_centavos"]) for x in linhas}

        garcia, itoupava = str(ids["garcia"]), str(ids["itoupava"])
        assert precos(ids["tirol"]) == {garcia: (329, 399), itoupava: (329, 399)}  # as duas lojas; nada em Brusque
        assert precos(ids["arroz"]) == {garcia: (1000, None), itoupava: (411, None)}  # o Garcia esperou a confirmação
        assert precos(ids["dori"]) == {}  # ligação errada desfeita: preço sai
        cafe = c.execute(
            "select p.id, p.categoria_id, p.tamanho, p.unidade from produto p join ean e on e.produto_id = p.id "
            "where e.codigo = %s",
            ("0" + CAFE,),
        ).fetchone()
        assert (cafe["categoria_id"], float(cafe["tamanho"]), cafe["unidade"]) == ("cafe", 250.0, "g")
        assert len(precos(cafe["id"])) == 2
        ligados = c.execute("select sku, nome_no_site, imagem_url from produto_na_rede order by sku").fetchall()
        assert [x["sku"] for x in ligados] == ["1002678", "1273418", "2002590"]
        assert ligados[1]["nome_no_site"] == "Creme De Leite Tirol 200g" and ligados[1]["imagem_url"] == "img-1273418"
        alerta = c.execute("select referencia_id, status, proposta_agente from fila_revisao").fetchone()
        assert alerta["referencia_id"] == f"preco:{garcia}:{ids['arroz']}" and alerta["proposta_agente"]["preco_centavos"] == 411

        # No dia seguinte (ofertas): o mesmo preço confirma e publica; produto novo não entra fora da varredura semanal.
        amanha = agora + timedelta(days=1)
        v = Varredura()
        v.guardar([item("1002678", ARROZ, "Arroz Parboilizado Kiarroz 1kg", 411),
                   item("2337207", "7898700060041", "Tomate Grape Vidagro Orgânicos 180g", 617)])  # fmt: skip
        r = bistek.gravar_varredura(c, v, amanha, criar=False)
        assert r["descartes"] == {"fora_do_catalogo": 1} and r["novos"] == 0
        assert precos(ids["arroz"]) == {garcia: (411, None), itoupava: (411, None)}
        assert c.execute("select status from fila_revisao").fetchone()["status"] == "resolvida"

        # A rodada inteira, do site ao banco, registra a execução para o Vigia.
        site = SiteDoBistek(
            {"ofertacos-da-quinzena-sc": [produto("1273418", TIROL, "Creme De Leite Tirol 200g", 3.19, de=3.99)]},
            rotas=["ofertacos-da-quinzena-sc"],
            tamanho=10,
        )
        r = bistek.rodar(c, site, amanha, "ofertas")
        assert (r["skus"], r["precos"]) == (1, 2)
        assert precos(ids["tirol"]) == {garcia: (319, 399), itoupava: (319, 399)}
        e = c.execute("select status, eans_pedidos, precos_gravados from execucao_coleta").fetchone()
        assert (e["status"], e["eans_pedidos"], e["precos_gravados"]) == ("ok", 1, 2)

        # Site fora do ar: a execução fica como falhou (o Vigia e o Revisor veem).
        with pytest.raises(RuntimeError):
            bistek.rodar(c, SiteDoBistek({}), amanha, "ofertas")
        assert c.execute("select count(*) as n from execucao_coleta where status = 'falhou'").fetchone()["n"] == 1
