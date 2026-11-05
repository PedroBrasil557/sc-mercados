"""Itens por quilo (fase 1): regra estrita de genérico, preço do quilo e gravação no banco."""

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from quantofica.coleta import por_peso as coleta
from quantofica.coleta import redes as config
from quantofica.coleta.catalogador import ItemDoSite
from quantofica.regras import por_peso


@pytest.mark.parametrize(
    ("nome", "marca", "esperado"),
    [
        ("Pão Francês Giassi Kg", "Giassi", "pao-frances"),
        ("Pão Francês Tradicional Sr.Pão Kg", "SR PAO", "pao-frances"),
        ("Pão Angeloni Francês kg", "ANGELONI", "pao-frances"),
        ("Banana Caturra Kg", "RENKAWIECKI", "banana-caturra"),
        ("Limão Tahiti Kg", "LUCELMAR", "limao-taiti"),
        ("Carne Bovina Patinho em Pedaço Verdi Kg", "SAO JOAO", "patinho"),
        ("Patinho Bovino Moído Friboi Kg", "FRIBOI", "patinho-moido"),
        ("Patinho Bovino em Bifes Resfriado sem Osso Giassi Kg", "Giassi", "patinho-bife"),
        ("Contra Filé Bovino Resfriado Friboi a Vácuo Kg", "FRIBOI", "contrafile"),
        ("Coxa com Sobrecoxa de Frango sem Dorso Congelada Copacol Kg", "COPACOL", "coxa-sobrecoxa"),
        ("Coxa Sobrecoxa Frango Macedo Resfriada Kg", "MACEDO", "coxa-sobrecoxa"),
        ("Presunto Cozido Fatiado sem Capa de Gordura Sadia Kg", "Sadia", "presunto-fatiado"),
        ("Queijo Minas Padrão Fracionado Verde Campo Kg", "Verde Campo", "minas-padrao"),
    ],
)
def test_liga_ao_generico(nome, marca, esperado):
    g = por_peso.generico_do_item(nome, marca)
    assert g is not None and g.slug == esperado


@pytest.mark.parametrize(
    ("nome", "marca"),
    [
        ("Pão Francês Crocante Giassi Kg", "Giassi"),  # outro pão
        ("Mini Pão Francês Tradicional Superpan kg", "SUPERPAN"),
        ("Banana Branca Orgânica Kg", "Vida Nova"),  # orgânica não é a comum
        ("Picanha Suína Temperada Pamplona Kg", "PAMPLONA"),  # suína não é a bovina
        ("Alcatra Bovino Miolo para Grelha Central de Carnes Cooper Kg", "COOPER"),  # corte diferente
        ("Bacon Defumado em Cubos Guinther Pacote Kg", "GUINTHER"),
        ("Queijo Minas Frescal Light Holandês Kg", "Holandes"),
        ("Coxa e Sobrecoxa de Frango Resfriado Desossada na Mostarda Temperados Cooper Kg", "COOPER"),
        ("Mortadela em Fatias Excelsior Bandeja 180g Kg", "Excelsior"),  # peso fixo: embalagem
        ("Patinho Bovino Marca Desconhecida Kg", None),  # palavra que a regra não conhece: na dúvida, não liga
    ],
)
def test_na_duvida_nao_liga(nome, marca):
    assert por_peso.generico_do_item(nome, marca) is None


def test_genericos_tem_ids_estaveis_e_unicos():
    assert len({g.slug for g in por_peso.GENERICOS}) == len(por_peso.GENERICOS)
    assert por_peso.POR_SLUG["pao-frances"].produto_id == por_peso.POR_SLUG["pao-frances"].produto_id
    assert len(por_peso.POR_PRODUTO) == len(por_peso.GENERICOS)


def test_preco_do_quilo_da_simulacao():
    base = {"availability": "available", "measurementUnit": "kg", "unitMultiplier": 0.25}
    # Sem desconto: o passo de 0,25 kg custa 4,22 e o quilo 16,90 (exato, sem o erro do arredondamento).
    assert coleta.preco_do_quilo(base | {"price": 1690, "listPrice": 1690, "sellingPrice": 422}) == (1690, None)
    # Com desconto no passo: o quilo sai do passo; o "de" é o preço cheio.
    assert coleta.preco_do_quilo(base | {"price": 1690, "listPrice": 1990, "sellingPrice": 375}) == (1500, 1990)
    assert coleta.preco_do_quilo(base | {"availability": "withoutStock", "sellingPrice": None}) is None
    assert coleta.preco_do_quilo(base | {"measurementUnit": "un", "price": 500, "sellingPrice": 500}) is None


class SiteFalso:
    """Simulação VTEX do Giassi com itens por quilo, sem rede."""

    def __init__(self, precos):
        self.precos = precos  # sku -> (preço do quilo, passo)

    def __call__(self, url, corpo):
        if "/regions" in url:
            return [{"sellers": [{"id": "giassi01", "name": "Giassi Victor Konder"}]}]
        if "/simulation" in url:
            itens = []
            for i in corpo["items"]:
                quilo, passo = self.precos[i["id"]]
                itens.append(
                    {
                        "id": i["id"],
                        "seller": i["seller"],
                        "availability": "available",
                        "measurementUnit": "kg",
                        "unitMultiplier": passo,
                        "price": quilo,
                        "listPrice": quilo,
                        "sellingPrice": round(quilo * passo),
                    }
                )
            return {"items": itens}
        return None


def _item(sku, nome, marca="Giassi", por_kg=True):
    return ItemDoSite("giassi", sku, None, nome, marca, "/Padaria/", True, True, f"https://x/{sku}.jpg", por_kg)


def test_liga_e_coleta_o_quilo_mais_barato(banco_url):
    giassi = next(r for r in config.REDES_VTEX if r.id == "giassi")
    ids = {k: uuid4() for k in ("cidade", "rede", "loja")}
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (ids["cidade"],))
        c.execute("insert into rede (id, nome, tem_api) values (%s, 'Giassi', true)", (ids["rede"],))
        c.execute(
            "insert into loja (id, rede_id, cidade_id, nome, seller_id) values (%s, %s, %s, 'Giassi Victor Konder', 'giassi01')",
            (ids["loja"], ids["rede"], ids["cidade"]),
        )
        itens = [
            _item("1", "Pão Francês Giassi Kg"),
            _item("2", "Pão Francês Marquespan Kg", "Marquespan"),
            _item("3", "Pão Francês Crocante Giassi Kg"),  # não casa
            _item("4", "Banana Caturra Kg", por_kg=False),  # vendida por unidade: fica de fora
        ]
        r = coleta.ligar(c, giassi, itens, completa=True)
        assert r["ligados"] == 2 and r["por_generico"] == {"pao-frances": ["1", "2"]}

        pao = por_peso.POR_SLUG["pao-frances"].produto_id
        site = SiteFalso({"1": (1690, 0.25), "2": (1590, 0.25)})
        agora = datetime.now(UTC)
        assert coleta.coletar(c, site, giassi, agora)["precos"] == 1
        atual = c.execute("select preco_centavos, evidencia_id from preco_atual where produto_id = %s", (pao,)).fetchone()
        assert atual["preco_centavos"] == 1590 and atual["evidencia_id"] == "vtex:giassi:giassi01:2"
        produto = c.execute("select tamanho, unidade, atributos from produto where id = %s", (pao,)).fetchone()
        assert (float(produto["tamanho"]), produto["unidade"], produto["atributos"]["por_kg"]) == (1000.0, "g", True)

        # Quilo que dispara na própria loja espera a coleta seguinte confirmar.
        site.precos = {"1": (4990, 0.25), "2": (4990, 0.25)}
        assert coleta.coletar(c, site, giassi, agora)["revisao"] == 1
        assert (
            c.execute("select preco_centavos from preco_atual where produto_id = %s", (pao,)).fetchone()["preco_centavos"] == 1590
        )
        coleta.coletar(c, site, giassi, agora)
        assert (
            c.execute("select preco_centavos from preco_atual where produto_id = %s", (pao,)).fetchone()["preco_centavos"] == 4990
        )

        # A rede lida inteira sem o item 2: a ligação dele sai.
        r = coleta.ligar(c, giassi, itens[:1], completa=True)
        assert r["desligados"] == 1
        skus = [x["sku"] for x in c.execute("select sku from produto_na_rede where produto_id = %s", (pao,)).fetchall()]
        assert skus == ["1"]
