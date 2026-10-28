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
        for k in ("cidade", "bairro", "giassi", "cooper", "loja_giassi", "cooper_perto", "cooper_longe", "arroz", "cafe")
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
            c.execute(OBS + "(%s, %s, %s, 'site', %s)", (produto, loja_id, centavos, hora))
        # Preço antigo do site (3 dias) num produto da Cooper perto: deve perder para o de 1 hora atrás.
        c.execute(OBS + "(%s, %s, 9999, 'site', %s)", (d["arroz"], d["cooper_perto"], AGORA - timedelta(days=3)))
    return d


@pytest.fixture(scope="module")
def api(banco_url, dados):
    with TestClient(create_app(banco_url)) as cliente:
        yield cliente


def com_token(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def casa(api, dados):
    """Ana abre o app e convida o Paulo pelo código; o Intruso tem uma casa só dele."""
    ana = api.post("/v1/aparelhos", json={"apelido": "Ana", "bairro_id": str(dados["bairro"])}).json()
    codigo = api.post("/v1/casa/convites", headers=com_token(ana["token"])).json()["codigo"]
    paulo = api.post(f"/v1/convites/{codigo.lower()}", json={"apelido": "Paulo"}).json()
    intruso = api.post("/v1/aparelhos", json={"apelido": "Intruso"}).json()
    return {
        "lista": ana["lista_id"],
        "ana": com_token(ana["token"]),
        "paulo": com_token(paulo["token"]),
        "intruso": com_token(intruso["token"]),
    }


def op(item, tipo, minutos_atras=0, **extra):
    return {
        "id": str(uuid4()),
        "item_id": str(item),
        "tipo": tipo,
        "feita_em": (AGORA - timedelta(minutes=minutos_atras)).isoformat(),
        **extra,
    }


def enviar(api, quem, lista, *operacoes):
    return api.post(f"/v1/listas/{lista}/operacoes", headers=quem, json={"operacoes": list(operacoes)})


def itens(api, quem, lista) -> dict:
    return {i["id"]: i for i in api.get(f"/v1/listas/{lista}", headers=quem).json()["itens"]}


def test_saude(api):
    assert api.get("/v1/saude").json() == {"ok": True}


def test_sem_token_nao_entra(api, casa):
    assert api.get(f"/v1/listas/{casa['lista']}").status_code == 401
    assert api.get(f"/v1/listas/{casa['lista']}", headers=com_token("inventado")).status_code == 401


def test_paulo_entrou_na_casa_da_ana_pelo_convite(api, casa):
    eu = api.get("/v1/eu", headers=casa["paulo"]).json()
    assert [m["apelido"] for m in eu["casa"]["membros"]] == ["Ana", "Paulo"]
    assert str(eu["listas"][0]["id"]) == casa["lista"]
    assert api.post("/v1/convites/ZZZZ2222", json={"apelido": "X"}).status_code == 404


def test_lista_de_outra_casa_responde_como_inexistente(api, casa):
    assert enviar(api, casa["intruso"], casa["lista"], op(uuid4(), "criar")).status_code == 404
    assert api.get(f"/v1/listas/{casa['lista']}", headers=casa["intruso"]).status_code == 404


def test_reenviar_o_mesmo_lote_nao_duplica(api, dados, casa):
    lista, item = casa["lista"], uuid4()
    operacao = op(item, "criar", 30, produto_id=str(dados["arroz"]))
    primeira = enviar(api, casa["ana"], lista, operacao).json()
    segunda = enviar(api, casa["ana"], lista, operacao).json()
    assert (primeira["novas"], segunda["novas"]) == (1, 0)
    assert primeira["cursor"] == segunda["cursor"]
    item_visto = itens(api, casa["paulo"], lista)[str(item)]
    assert (item_visto["quantidade"], item_visto["nome"], item_visto["adicionado_por"]) == (1, "Arroz tipo 1", "Ana")


def test_dois_aparelhos_somando_ao_mesmo_tempo(api, dados, casa):
    lista, item, ana, paulo = casa["lista"], uuid4(), casa["ana"], casa["paulo"]
    enviar(api, ana, lista, op(item, "criar", 20, produto_id=str(dados["cafe"])))
    cursor = api.get(f"/v1/listas/{lista}/operacoes", headers=paulo).json()["cursor"]
    enviar(api, ana, lista, op(item, "somar", 5))
    enviar(api, paulo, lista, op(item, "somar", 5))
    novas = api.get(f"/v1/listas/{lista}/operacoes", headers=paulo, params={"desde": cursor}).json()
    assert [o["tipo"] for o in novas["operacoes"]] == ["somar", "somar"]
    assert novas["cursor"] > cursor
    assert itens(api, ana, lista)[str(item)]["quantidade"] == 3


def test_item_removido_por_outro_volta_com_aviso(api, casa):
    lista, item = casa["lista"], uuid4()
    enviar(api, casa["ana"], lista, op(item, "criar", 15, categoria_id="graos"))
    enviar(api, casa["paulo"], lista, op(item, "remover", 10))
    enviar(api, casa["ana"], lista, op(item, "somar", 5))
    item_visto = itens(api, casa["ana"], lista)[str(item)]
    assert item_visto["aviso"] == "Paulo tinha removido este item"
    assert item_visto["categoria"] == "graos"


def test_recusa_operacao_no_futuro(api, casa):
    assert enviar(api, casa["ana"], casa["lista"], op(uuid4(), "somar", -60)).status_code == 422


def test_preco_atual_e_o_mais_recente(api, dados, casa):
    r = api.get(
        "/v1/precos",
        headers=casa["ana"],
        params={"loja_id": str(dados["cooper_perto"]), "produto_id": [str(dados["arroz"]), str(dados["cafe"])]},
    )
    precos = r.json()["precos"]
    assert precos[str(dados["arroz"])]["preco_centavos"] == 2490
    assert precos[str(dados["arroz"])]["estado"] == "valido"
    assert precos[str(dados["cafe"])]["preco_centavos"] == 2099


def test_comparar_usa_a_loja_mais_proxima_de_cada_rede(api, dados, casa):
    pedido = {"bairro_id": str(dados["bairro"]), "itens": {str(dados["arroz"]): 1, str(dados["cafe"]): 2}}
    r = api.post("/v1/comparar", headers=casa["ana"], json=pedido).json()
    assert [loja["nome"] for loja in r["lojas"]] == ["Giassi Victor Konder", "Cooper Itoupava Seca"]
    assert [loja["total_centavos"] for loja in r["lojas"]] == [2590 + 2 * 1899, 2490 + 2 * 2099]
    assert r["comuns"] == 2
    divisao = r["divisao"]
    assert divisao["total_centavos"] == 2490 + 2 * 1899
    assert divisao["economia_centavos"] == 100
    assert divisao["compensa"] is False  # R$1 de economia não paga a viagem extra + R$10


def test_comparar_a_partir_da_lista(api, dados, casa):
    pedido = {"bairro_id": str(dados["bairro"]), "lista_id": casa["lista"]}
    r = api.post("/v1/comparar", headers=casa["ana"], json=pedido)
    assert r.status_code == 200
    assert r.json()["comuns"] == 2  # arroz e café; o item genérico (só categoria) não entra na soma
    assert api.post("/v1/comparar", headers=casa["intruso"], json=pedido).status_code == 404


def test_comparar_exige_lista_ou_itens(api, dados, casa):
    assert api.post("/v1/comparar", headers=casa["ana"], json={"bairro_id": str(dados["bairro"])}).status_code == 422


def test_busca_no_catalogo_ignora_acento_e_maiuscula(api, casa):
    def nomes(busca):
        return [p["nome"] for p in api.get("/v1/produtos", headers=casa["ana"], params={"busca": busca}).json()]

    assert nomes("cafe") == ["Café tradicional"]
    assert nomes("PILÃO") == ["Café tradicional"]  # pela marca
    assert nomes("arroz kiarroz") == ["Arroz tipo 1"]  # todas as palavras
    assert nomes("feijão") == []
    assert len(nomes("")) == 2  # sem busca: o catálogo
    assert api.get("/v1/produtos").status_code == 401


def test_bairros_sao_publicos(api):
    assert [b["nome"] for b in api.get("/v1/bairros").json()] == ["Victor Konder"]


def test_exclusao_de_conta(api, banco_url, casa):
    """A dona apaga a conta: a casa passa para o Paulo e a lista fica igual. Quando o Paulo apaga, a casa some."""
    lista = casa["lista"]
    antes = {k: v["quantidade"] for k, v in itens(api, casa["paulo"], lista).items()}
    assert api.delete("/v1/eu", headers=casa["ana"]).status_code == 204
    assert api.get("/v1/eu", headers=casa["ana"]).status_code == 401
    eu = api.get("/v1/eu", headers=casa["paulo"]).json()
    assert [(m["apelido"], m["papel"]) for m in eu["casa"]["membros"]] == [("Paulo", "dono")]
    assert {k: v["quantidade"] for k, v in itens(api, casa["paulo"], lista).items()} == antes

    assert api.delete("/v1/eu", headers=casa["paulo"]).status_code == 204
    with psycopg.connect(banco_url) as c:
        assert c.execute("select count(*) from lista where id = %s", (lista,)).fetchone()[0] == 0
        assert c.execute("select count(*) from operacao_lista where lista_id = %s", (lista,)).fetchone()[0] == 0
