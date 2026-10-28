"""Testes de integração da API contra um Postgres de verdade (ver conftest.py)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from quantofica.api.app import create_app

AGORA = datetime.now(UTC)
OBS = "insert into observacao_preco (produto_id, loja_id, preco_centavos, fonte, observado_em) values "


@pytest.fixture(scope="module")
def dados(banco_url):
    d = {
        k: uuid4()
        for k in (
            "cidade",
            "bairro",
            "giassi",
            "cooper",
            "loja_giassi",
            "cooper_perto",
            "cooper_longe",
            "arroz",
            "cafe",
            "casa",
            "ana",
            "paulo",
            "lista",
            "outra_casa",
            "intruso",
        )
    }
    with psycopg.connect(banco_url) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (d["cidade"],))
        c.execute(
            "insert into bairro (id, cidade_id, nome, lat_centro, lon_centro) "
            "values (%s, %s, 'Victor Konder', -26.9068, -49.0790)",
            (d["bairro"], d["cidade"]),
        )
        c.execute("insert into rede (id, nome) values (%s, 'Giassi'), (%s, 'Cooper')", (d["giassi"], d["cooper"]))
        lojas = [
            (d["loja_giassi"], d["giassi"], "Giassi Victor Konder", -26.9050, -49.0770),
            (d["cooper_perto"], d["cooper"], "Cooper Itoupava Seca", -26.9150, -49.0700),
            (d["cooper_longe"], d["cooper"], "Cooper Garcia", -26.9600, -49.0600),
        ]
        for loja_id, rede, nome, lat, lon in lojas:
            c.execute(
                "insert into loja (id, rede_id, cidade_id, nome, lat, lon) values (%s, %s, %s, %s, %s, %s)",
                (loja_id, rede, d["cidade"], nome, lat, lon),
            )
        c.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g'), ('cafe', 'Café', 'g')")
        c.execute(
            "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values "
            "(%s, 'graos', 'Arroz tipo 1', 'Kiarroz', 5000, 'g'), (%s, 'cafe', 'Café tradicional', 'Pilão', 500, 'g')",
            (d["arroz"], d["cafe"]),
        )
        c.execute(
            "insert into casa (id, bairro_id) values (%s, %s), (%s, %s)", (d["casa"], d["bairro"], d["outra_casa"], d["bairro"])
        )
        c.execute(
            "insert into membro (id, casa_id, apelido) values (%s, %s, 'Ana'), (%s, %s, 'Paulo'), (%s, %s, 'Intruso')",
            (d["ana"], d["casa"], d["paulo"], d["casa"], d["intruso"], d["outra_casa"]),
        )
        c.execute("insert into lista (id, casa_id, nome) values (%s, %s, 'Casa')", (d["lista"], d["casa"]))
        hora = AGORA - timedelta(hours=1)
        precos = [
            (d["loja_giassi"], d["arroz"], 2590),
            (d["loja_giassi"], d["cafe"], 1899),
            (d["cooper_perto"], d["arroz"], 2490),
            (d["cooper_perto"], d["cafe"], 2099),
            (d["cooper_longe"], d["arroz"], 1000),
            (d["cooper_longe"], d["cafe"], 1000),  # mais barata, porém longe (R13)
        ]
        for loja_id, produto, centavos in precos:
            c.execute(
                OBS + "(%s, %s, %s, 'site', %s)",
                (produto, loja_id, centavos, hora),
            )
        # Preço antigo do site (3 dias) num produto da Cooper perto: deve perder para o de 1 hora atrás.
        c.execute(
            OBS + "(%s, %s, 9999, 'site', %s)",
            (d["arroz"], d["cooper_perto"], AGORA - timedelta(days=3)),
        )
    return d


@pytest.fixture(scope="module")
def api(banco_url, dados):
    with TestClient(create_app(banco_url)) as cliente:
        yield cliente


def op(item, tipo, membro, minutos_atras=0, **extra):
    return {
        "id": str(uuid4()),
        "item_id": str(item),
        "tipo": tipo,
        "membro_id": str(membro),
        "feita_em": (AGORA - timedelta(minutes=minutos_atras)).isoformat(),
        **extra,
    }


def test_saude(api):
    assert api.get("/v1/saude").json() == {"ok": True}


def test_reenviar_o_mesmo_lote_nao_duplica(api, dados):
    lista, item = dados["lista"], uuid4()
    lote = {"operacoes": [op(item, "criar", dados["ana"], 30, produto_id=str(dados["arroz"]))]}
    primeira = api.post(f"/v1/listas/{lista}/operacoes", json=lote).json()
    segunda = api.post(f"/v1/listas/{lista}/operacoes", json=lote).json()
    assert (primeira["novas"], segunda["novas"]) == (1, 0)
    assert primeira["cursor"] == segunda["cursor"]
    itens = {i["id"]: i for i in api.get(f"/v1/listas/{lista}").json()["itens"]}
    assert itens[str(item)]["quantidade"] == 1
    assert itens[str(item)]["nome"] == "Arroz tipo 1"
    assert itens[str(item)]["adicionado_por"] == "Ana"


def test_dois_aparelhos_somando_ao_mesmo_tempo(api, dados):
    lista, item = dados["lista"], uuid4()
    api.post(
        f"/v1/listas/{lista}/operacoes", json={"operacoes": [op(item, "criar", dados["ana"], 20, produto_id=str(dados["cafe"]))]}
    )
    cursor = api.get(f"/v1/listas/{lista}/operacoes").json()["cursor"]
    api.post(f"/v1/listas/{lista}/operacoes", json={"operacoes": [op(item, "somar", dados["ana"], 5)]})
    api.post(f"/v1/listas/{lista}/operacoes", json={"operacoes": [op(item, "somar", dados["paulo"], 5)]})
    novas = api.get(f"/v1/listas/{lista}/operacoes", params={"desde": cursor}).json()
    assert [o["tipo"] for o in novas["operacoes"]] == ["somar", "somar"]
    assert novas["cursor"] > cursor
    itens = {i["id"]: i for i in api.get(f"/v1/listas/{lista}").json()["itens"]}
    assert itens[str(item)]["quantidade"] == 3


def test_item_removido_por_outro_volta_com_aviso(api, dados):
    lista, item = dados["lista"], uuid4()
    api.post(
        f"/v1/listas/{lista}/operacoes",
        json={
            "operacoes": [
                op(item, "criar", dados["ana"], 15, categoria_id="graos"),
                op(item, "remover", dados["paulo"], 10),
                op(item, "somar", dados["ana"], 5),
            ]
        },
    )
    itens = {i["id"]: i for i in api.get(f"/v1/listas/{lista}").json()["itens"]}
    assert itens[str(item)]["aviso"] == "Paulo tinha removido este item"
    assert itens[str(item)]["categoria"] == "graos"


def test_recusa_membro_de_outra_casa_e_operacao_no_futuro(api, dados):
    lista, item = dados["lista"], uuid4()
    r = api.post(f"/v1/listas/{lista}/operacoes", json={"operacoes": [op(item, "criar", dados["intruso"], categoria_id="graos")]})
    assert r.status_code == 422
    r = api.post(f"/v1/listas/{lista}/operacoes", json={"operacoes": [op(item, "somar", dados["ana"], -60)]})
    assert r.status_code == 422
    r = api.post(f"/v1/listas/{uuid4()}/operacoes", json={"operacoes": [op(item, "somar", dados["ana"])]})
    assert r.status_code == 404


def test_preco_atual_e_o_mais_recente(api, dados):
    r = api.get(
        "/v1/precos", params={"loja_id": str(dados["cooper_perto"]), "produto_id": [str(dados["arroz"]), str(dados["cafe"])]}
    )
    precos = r.json()["precos"]
    assert precos[str(dados["arroz"])]["preco_centavos"] == 2490
    assert precos[str(dados["arroz"])]["estado"] == "valido"
    assert precos[str(dados["cafe"])]["preco_centavos"] == 2099


def test_comparar_usa_a_loja_mais_proxima_de_cada_rede(api, dados):
    pedido = {"bairro_id": str(dados["bairro"]), "itens": {str(dados["arroz"]): 1, str(dados["cafe"]): 2}}
    r = api.post("/v1/comparar", json=pedido).json()
    assert [loja["nome"] for loja in r["lojas"]] == ["Giassi Victor Konder", "Cooper Itoupava Seca"]
    assert [loja["total_centavos"] for loja in r["lojas"]] == [2590 + 2 * 1899, 2490 + 2 * 2099]
    assert r["comuns"] == 2
    divisao = r["divisao"]
    assert divisao["total_centavos"] == 2490 + 2 * 1899
    assert divisao["economia_centavos"] == 100
    assert divisao["compensa"] is False  # R$1 de economia não paga a viagem extra + R$10


def test_comparar_a_partir_da_lista(api, dados):
    r = api.post("/v1/comparar", json={"bairro_id": str(dados["bairro"]), "lista_id": str(dados["lista"])})
    assert r.status_code == 200
    assert r.json()["comuns"] == 2  # arroz e café; o item genérico (só categoria) não entra na soma


def test_comparar_exige_lista_ou_itens(api, dados):
    assert api.post("/v1/comparar", json={"bairro_id": str(dados["bairro"])}).status_code == 422
