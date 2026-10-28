"""Coletor VTEX e robots.txt, sem internet: respostas gravadas no formato visto em 22/10/2026."""

import pytest

from quantofica.coleta import robots, vtex

ROBOTS_ANGELONI = """
User-agent: *
User-agent: *
Disallow: /busca
Disallow: /*ft=*
Disallow: /checkout
Disallow: *?fq=*
Disallow: /*map=*
"""
ROBOTS_GIASSI = """
# Disallow all crawlers access to certain pages.
User-agent: *
Disallow: /checkout/*
Disallow: /busca/*
"""


class TestRobots:
    def test_curinga_no_inicio_bloqueia_fq(self):
        r = robots.ler(ROBOTS_ANGELONI)
        assert not r.permitido("/api/catalog_system/pub/products/search?fq=alternateIds_Ean:7894900027013")
        assert not r.permitido("/api/catalog_system/pub/products/search?ft=coca")

    def test_api_de_checkout_nao_e_o_checkout_do_site(self):
        # "/checkout" bloqueia o carrinho do site, não "/api/checkout/..."
        assert robots.ler(ROBOTS_ANGELONI).permitido("/api/checkout/pub/regions?country=BRA&postalCode=89010000")
        assert robots.ler(ROBOTS_GIASSI).permitido("/api/checkout/pub/orderForms/simulation?sc=1")

    def test_busca_inteligente_e_permitida(self):
        assert robots.ler(ROBOTS_ANGELONI).permitido("/api/io/_v/api/intelligent-search/product_search/?query=7894900027013")

    def test_prefixo_e_ancora(self):
        r = robots.Regras(proibir=["/busca", "/*.pdf$"], permitir=["/busca/ofertas"])
        assert not r.permitido("/busca/arroz")
        assert r.permitido("/busca/ofertas")  # regra mais específica vence
        assert not r.permitido("/encarte.pdf") and r.permitido("/encarte.pdf?v=2")

    def test_sem_robots_tudo_permitido(self):
        assert robots.ler("").permitido("/qualquer")


def item(ean, sku, preco=11.38, de=11.38, qtd=100):
    return {
        "itemId": sku,
        "ean": ean,
        "sellers": [{"sellerId": "1", "commertialOffer": {"Price": preco, "ListPrice": de, "AvailableQuantity": qtd}}],
    }


class FakeHttp:
    """Responde por trecho de URL e aplica um robots.txt, como o ClienteHttp real."""

    def __init__(self, rotas: dict, robots_txt: str = ""):
        self.rotas, self.regras, self.chamadas = rotas, robots.ler(robots_txt), []

    def __call__(self, url, corpo=None):
        caminho = url.split("://", 1)[1].split("/", 1)[1]
        if not self.regras.permitido("/" + caminho):
            raise vtex.BloqueadoPeloRobots(url)
        self.chamadas.append(url)
        for trecho, resp in self.rotas.items():
            if trecho in url:
                return resp(corpo) if callable(resp) else resp
        return None


REGIOES = [{"id": "v2.x", "sellers": [{"id": "giassi09", "name": "giassi09"}]}]


def simulacao(precos: dict):
    def responder(corpo):
        return {
            "items": [
                {"id": i["id"], "seller": i["seller"], **precos.get(i["id"], {"availability": "cannotBeDelivered"})}
                for i in corpo["items"]
            ]
        }

    return responder


class TestColetaVtex:
    def test_preco_da_loja_vem_da_simulacao(self):
        http = FakeHttp(
            {
                "regions": REGIOES,
                "alternateIds_Ean:7894900027013": [
                    {"productName": "Refrigerante Coca-Cola Garrafa 2l", "items": [item("7894900027013", "4828")]}
                ],
                "simulation": simulacao({"4828": {"availability": "available", "sellingPrice": 1138, "listPrice": 1138}}),
            },
            ROBOTS_GIASSI,
        )
        rede = vtex.Rede("giassi", "www.giassi.com.br", "89010000", nomes_sellers={"giassi09": "Giassi Victor Konder"})
        [p] = vtex.coletar(http, rede, ["7894900027013"])
        assert (p.preco_centavos, p.origem, p.loja, p.ean) == (1138, "simulacao_loja", "Giassi Victor Konder", "07894900027013")

    def test_angeloni_usa_busca_inteligente_e_ean_com_zeros(self):
        # O robots do Angeloni proíbe "?fq=": o coletor cai na busca inteligente e acha "0070847022015"
        http = FakeHttp(
            {
                "regions": [{"id": "v2.y", "sellers": [{"id": "superangeloni15", "name": "Angeloni Velha"}]}],
                "intelligent-search": {
                    "products": [{"productName": "Energético MONSTER Green 473ml", "items": [item("0070847022015", "359")]}]
                },
                "simulation": simulacao({"359": {"availability": "available", "sellingPrice": 849, "listPrice": 999}}),
            },
            ROBOTS_ANGELONI,
        )
        [p] = vtex.coletar(http, vtex.Rede("angeloni", "super.angeloni.com.br", "89010000"), ["70847022015"])
        assert p.preco_centavos == 849 and p.preco_de_centavos == 999
        assert not any("fq=" in u for u in http.chamadas)

    def test_pack_com_mesmo_ean_nao_vira_preco(self):
        http = FakeHttp(
            {
                "regions": [{"id": "v", "sellers": [{"id": "samsclub4001", "name": "Sam´s Blumenau"}]}],
                "alternateIds_Ean:": [
                    {
                        "productName": "Macarrão de Sêmola Espaguete 5 Barilla Pack com 3 Unidades 500g Cada",
                        "items": [item("8076800195057", "76602")],
                    }
                ],
                "simulation": simulacao({"76602": {"availability": "available", "sellingPrice": 4198}}),
            }
        )
        [p] = vtex.coletar(http, vtex.Rede("sams", "www.samsclub.com.br", "89010000"), ["8076800195057"])
        assert p.preco_centavos is None and p.origem == "embalagem_diferente"

    def test_indisponivel_na_loja(self):
        http = FakeHttp(
            {
                "regions": REGIOES,
                "alternateIds_Ean:": [{"productName": "Macarrão Barilla 500g", "items": [item("8076800195057", "3636")]}],
                "simulation": simulacao({"3636": {"availability": "withoutStock", "sellingPrice": 0}}),
            }
        )
        [p] = vtex.coletar(http, vtex.Rede("giassi", "www.giassi.com.br", "89010000"), ["8076800195057"])
        assert p.preco_centavos is None and p.origem == "indisponivel"

    def test_filtra_lojas_de_outras_cidades(self):
        http = FakeHttp(
            {
                "regions": [
                    {
                        "id": "v",
                        "sellers": [
                            {"id": "minhacoopersuperaguaverdeblumenau", "name": "x"},
                            {"id": "minhacoopersupercentroindaial", "name": "y"},
                        ],
                    }
                ]
            }
        )
        rede = vtex.Rede(
            "cooper",
            "www.minhacooper.com.br",
            "89010000",
            filtro_seller="blumenau",
            nomes_sellers={"minhacoopersuperaguaverdeblumenau": "Água Verde"},
        )
        assert vtex.sellers(http, rede) == {"minhacoopersuperaguaverdeblumenau": "Água Verde"}


class TestClienteHttp:
    def test_respeita_intervalo_e_robots(self):
        dormiu = []
        relogio = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])

        class Resp:
            def __init__(self, dados):
                self.dados = dados

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self.dados

        def abrir(req, timeout):
            return Resp(b"User-agent: *\nDisallow: /proibido" if req.full_url.endswith("robots.txt") else b'{"ok": true}')

        c = vtex.ClienteHttp(intervalo_s=1.0, abrir=abrir, dormir=dormiu.append, relogio=lambda: next(relogio))
        assert c("https://loja.test/api/ok") == {"ok": True}
        assert dormiu and dormiu[0] > 0  # esperou entre o robots.txt e a chamada
        with pytest.raises(vtex.BloqueadoPeloRobots):
            c("https://loja.test/proibido/x")
