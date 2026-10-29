"""Catalogador v2: percorre as seções de mercado das redes, cria os produtos novos e liga os SKUs."""

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from quantofica.coleta import catalogador
from quantofica.coleta.catalogador import ItemDoSite, Varredura, categoria
from quantofica.coleta.vtex import Rede

ARROZ, FEIJAO, PANELA, PACK, SEM_TAMANHO, GRANEL = (
    "7896084700119",
    "7896006744115",
    "7891000000011",
    "7622210592750",
    "7891000100103",
    "7891000055502",
)


def produto(sku, ean, nome, caminho, marca="Marca", disponivel=True, unidade="un"):
    return {
        "productName": nome,
        "brand": marca,
        "categories": [caminho, "/" + caminho.strip("/").split("/")[0] + "/"],
        "items": [
            {
                "itemId": sku,
                "ean": ean,
                "nameComplete": nome + " UNIDADE",
                "measurementUnit": unidade,
                "unitMultiplier": 1,
                "sellers": [{"commertialOffer": {"AvailableQuantity": 10 if disponivel else 0, "Price": 9.9}}],
            }
        ],
    }


def test_categoria_pelo_nome_e_pela_secao():
    assert categoria("/Mercearia/Padaria/", "Requeijão Cremoso Tirol 200g") == "laticinios"
    assert categoria("/Vida e Saúde/Sem Lactose/", "Leite UHT Integral Zero Lactose Tirol 1l") == "laticinios"
    assert categoria("/Mercearia/Chocolates/Tabletes/", "Chocolate ao Leite Lacta 80g") == "doces"
    assert categoria("/Mercearia/Arroz/", "Arroz Branco Tio João 1kg") == "graos"
    assert categoria("/Limpeza/Água Sanitária/", "Alvejante Qboa 1l") == "limpeza"
    assert categoria("/Bebidas não alcoólicas/Águas/", "Água Mineral Crystal 500ml") == "bebidas"
    assert categoria("/Cantinho do Bebê/Alimentação Infantil/", "Papinha Nestlé Banana 120g") == "mercearia"
    assert categoria("/Congelados/Pratos Prontos/", "Lasanha Seara Bolonhesa 600g") == "mercearia"
    assert categoria("/Utensílios/Panelas/", "Panela Tramontina 20cm") is None
    assert categoria("/Pet Shop/Rações/", "Ração Whiskas Carne 1kg") is None


class Site:
    """Uma rede VTEX falsa: árvore de categorias, catálogo por categoria (fq=C:) e busca inteligente."""

    ARVORE = [
        {
            "id": 11,
            "name": "Mercearia",
            "url": "https://x/mercearia",
            "children": [
                {"id": 84, "name": "Arroz e Feijão", "url": "https://x/mercearia/arroz-e-feijao", "children": []},
                {"id": 85, "name": "Massas", "url": "https://x/mercearia/massas", "children": []},
            ],
        },
        {"id": 16, "name": "Utensílios", "url": "https://x/utensilios", "children": []},
    ]

    def __init__(self, por_categoria):
        self.por_categoria = por_categoria
        self.chamadas = []

    def __call__(self, url, corpo):
        self.chamadas.append(url)
        if "/category/tree/" in url:
            return self.ARVORE
        if "fq=C:/" in url:
            cat = url.split("fq=C:/")[1].split("/&")[0]
            inicio = int(url.split("_from=")[1].split("&")[0])
            fim = int(url.split("_to=")[1])
            return self.por_categoria.get(cat, [])[inicio : fim + 1]
        if "intelligent-search" in url:
            caminho = url.split("product_search/")[1].split("?")[0]
            slug = caminho.rsplit("/", 1)[1]
            todos = self.por_categoria.get(slug, [])
            pagina = int(url.split("page=")[1].split("&")[0])
            n = catalogador.POR_PAGINA
            return {"products": todos[(pagina - 1) * n : pagina * n], "recordsFiltered": len(todos)}
        return None


def test_varre_pagina_a_pagina_e_pula_o_que_nao_e_mercado(monkeypatch):
    monkeypatch.setattr(catalogador, "POR_PAGINA", 2)
    arroz = [produto(str(i), ARROZ if i == 1 else FEIJAO, f"Arroz {i} 1kg", "/Mercearia/Arroz e Feijão/") for i in (1, 2, 3)]
    site = Site({"11/84": arroz, "11/85": [], "16": [produto("9", PANELA, "Panela 20cm", "/Utensílios/")]})
    v = catalogador.varrer(site, Rede("giassi", "www.giassi.com.br", "89010000"))
    assert [i.sku for i in v.itens] == ["1", "2", "3"]
    assert v.completa and v.departamentos == ["Mercearia"]
    assert not any("fq=C:/16/" in u for u in site.chamadas)
    assert v.itens[0].nome == "Arroz 1 1kg"  # o nome do produto, sem o "UNIDADE" que a Cooper põe no nome do item


def test_angeloni_vai_pela_busca_inteligente(monkeypatch):
    monkeypatch.setattr(catalogador, "POR_PAGINA", 2)
    arroz = [produto(str(i), ARROZ, f"Arroz {i} 1kg", "/Mercearia/Arroz e Feijão/", marca="TIO JOÃO") for i in (1, 2, 3)]
    site = Site({"arroz-e-feijao": arroz})
    v = catalogador.varrer(site, Rede("angeloni", "super.angeloni.com.br", "89010000"))
    assert len(v.itens) == 3 and v.completa
    assert all("fq=" not in u for u in site.chamadas)  # o robots.txt do Angeloni proíbe fq=


def test_grava_produto_novo_liga_sku_e_marca_ausente(banco_url):
    agora = datetime(2026, 10, 30, 5, tzinfo=UTC)
    existente, sumido = uuid4(), uuid4()
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as c:
        for nome in ("Giassi", "Sam's Club"):
            c.execute("insert into rede (nome) values (%s)", (nome,))
        c.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g'), ('mercearia', 'Merc.', 'un')")
        c.execute("insert into produto (id, categoria_id, nome_humano) values (%s, 'graos', 'Arroz antigo 5kg')", (existente,))
        c.execute("insert into produto (id, categoria_id, nome_humano) values (%s, 'graos', 'Saiu de linha 1kg')", (sumido,))
        c.execute("insert into ean (codigo, produto_id) values ('07896084700119', %s)", (existente,))
        c.execute("insert into ean (codigo, produto_id) values ('07891000000011', %s)", (sumido,))

        def item(sku, ean, nome, granel=False, disponivel=True):
            gtin = ean.zfill(14) if ean else None
            return ItemDoSite("giassi", sku, gtin, nome, "Marca", "/Mercearia/Arroz e Feijão/", granel, disponivel)

        v = Varredura(
            [
                item("1", ARROZ, "Arroz Tio João 5kg"),
                item("2", FEIJAO, "Feijão Carioca Camil 1kg"),
                item("3", PACK, "Biscoito Pack com 3 unidades de 126g"),
                item("4", SEM_TAMANHO, "Feijão Preto Especial"),
                item("5", GRANEL, "Feijão a granel kg", granel=True),
                item("6", "7891000200100", "Arroz Integral 1kg", disponivel=False),
                item("7", None, "Sem código 1kg"),
            ],
            True,
            1,
            ["Mercearia"],
        )
        r = catalogador.gravar(c, Rede("giassi", "www.giassi.com.br", "89010000"), v, agora)
        assert r["novos"] == 1 and r["ligados"] == 2
        assert r["descartes"] == {"pack": 1, "sem_tamanho": 1, "granel": 1, "indisponivel": 1, "sem_ean": 1}
        feijao = c.execute(
            "select p.nome_humano, p.categoria_id, p.tamanho, p.unidade from produto p join ean e on e.produto_id = p.id "
            "where e.codigo = '07896006744115'"
        ).fetchone()
        assert (feijao["nome_humano"], feijao["categoria_id"], float(feijao["tamanho"]), feijao["unidade"]) == (
            "Feijão Carioca Camil 1kg",
            "graos",
            1000.0,
            "g",
        )
        ligados = c.execute("select sku, produto_id from produto_na_rede order by sku").fetchall()
        assert [x["sku"] for x in ligados] == ["1", "2"] and ligados[0]["produto_id"] == existente
        ausentes = c.execute("select codigo from ean_ausente").fetchall()
        assert [a["codigo"] for a in ausentes] == ["07891000000011"]  # o catálogo tem, o Giassi não vende mais

        # Sam's: só liga o que já existe, não cria produto.
        arroz_sams = ItemDoSite("sams", "50", "07899999999994", "Arroz Member's 5kg", None, "/Mercearia/", False, True)
        sams = Varredura([arroz_sams], True, 1, [])
        r = catalogador.gravar(c, Rede("sams", "www.samsclub.com.br", "89010000"), sams, agora)
        assert r["novos"] == 0 and r["descartes"] == {"fora_do_catalogo": 1}

        # Varredura incompleta (página que falhou): não marca nada como ausente.
        c.execute("delete from ean_ausente")
        catalogador.gravar(c, Rede("giassi", "www.giassi.com.br", "89010000"), Varredura([], False, 1, []), agora)
        assert c.execute("select count(*) as n from ean_ausente").fetchone()["n"] == 0
