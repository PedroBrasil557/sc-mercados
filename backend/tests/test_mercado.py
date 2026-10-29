"""Seu mercado, busca inteligente, "qualquer marca" e o resumo do Início."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from quantofica.api import catalogo as cache_catalogo
from quantofica.api.app import create_app
from quantofica.regras.nome import grupo, nome_curto

AGORA = datetime.now(UTC)


class TestNome:
    @pytest.mark.parametrize(
        ("nome", "marca", "curto"),
        [
            ("Leite UHT Integral Tirol Caixa com Tampa 1l", "Tirol", "Leite integral"),
            ("Feijão Carioca Tipo 1 Kicaldo Pacote 1kg", "Kicaldo", "Feijão carioca"),
            ("Açúcar Refinado União Pacote 1kg", "União", "Açúcar refinado"),
            ("Creme de Leite Nestlé Caixa 200g", "Nestlé", "Creme de leite"),
            ("Sabão em pó Omo 2,2kg", "Omo", "Sabão em pó"),
            ("Lava-Roupas Líquido Omo Galão 3l", "Omo", "Lava roupas líquido"),
        ],
    )
    def test_nome_curto(self, nome, marca, curto):
        assert nome_curto(nome, marca) == curto

    def test_mesmo_grupo_marcas_diferentes_e_tamanho_igual(self):
        assert grupo("Feijão Carioca Tipo 1 Kicaldo 1kg", "Kicaldo") == grupo("Feijão Carioca Caldo Bom Pacote 1kg", "Caldo Bom")
        assert grupo("Feijão Carioca Kicaldo 1kg", "Kicaldo") != grupo("Feijão Preto Kicaldo 1kg", "Kicaldo")
        assert grupo("Feijão Carioca Kicaldo 1kg", "Kicaldo") != grupo("Feijão Carioca Kicaldo 2kg", "Kicaldo")
        assert grupo("Cerveja Pack com 12 Unidades 350ml Cada", "X") is None  # pacote de vários fica fora


@pytest.fixture(scope="module")
def dados(banco_url):
    d = {
        k: uuid4()
        for k in ("cidade", "bairro", "cooper", "giassi", "loja_c", "loja_g", "uniao", "caravelas", "zero", "kicaldo", "caldo")
    }
    with psycopg.connect(banco_url, autocommit=True) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (d["cidade"],))
        c.execute(
            "insert into bairro (id, cidade_id, nome, lat_centro, lon_centro) values (%s, %s, 'Itoupavazinha', -26.86, -49.09)",
            (d["bairro"], d["cidade"]),
        )
        c.execute("insert into rede (id, nome) values (%s, 'Cooper'), (%s, 'Giassi')", (d["cooper"], d["giassi"]))
        for lid, rede, nome, lat, lon in [
            (d["loja_c"], d["cooper"], "Cooper Itoupavazinha", -26.865, -49.09),
            (d["loja_g"], d["giassi"], "Giassi Victor Konder", -26.905, -49.077),
        ]:
            c.execute(
                "insert into loja (id, rede_id, cidade_id, nome, lat, lon) values (%s, %s, %s, %s, %s, %s)",
                (lid, rede, d["cidade"], nome, lat, lon),
            )
        c.execute(
            "insert into categoria (id, nome, unidade_medida) values "
            "('mercearia', 'Mercearia', 'g'), ('bebidas', 'Bebidas', 'ml'), ('graos', 'Grãos', 'g')"
        )
        prods = [
            (d["uniao"], "mercearia", "Açúcar Refinado União Pacote 1kg", "União", 1000, "g"),
            (d["caravelas"], "mercearia", "Açúcar Refinado Caravelas Pacote 1kg", "Caravelas", 1000, "g"),
            (d["zero"], "bebidas", "Refrigerante Guaraná Zero Açúcar Lata 350ml", "Antarctica", 350, "ml"),
            (d["kicaldo"], "graos", "Feijão Carioca Tipo 1 Kicaldo Pacote 1kg", "Kicaldo", 1000, "g"),
            (d["caldo"], "graos", "Feijão Carioca Caldo Bom Pacote 1kg", "Caldo Bom", 1000, "g"),
        ]
        for pid, cat, nome, marca, q, u in prods:
            c.execute(
                "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values (%s, %s, %s, %s, %s, %s)",
                (pid, cat, nome, marca, q, u),
            )
        hora = AGORA - timedelta(hours=1)
        obs = (
            "insert into observacao_preco (produto_id, loja_id, preco_centavos, preco_de_centavos, fonte, observado_em) "
            "values (%s, %s, %s, %s, 'site', %s)"
        )
        for pid, loja, preco, de in [
            (d["uniao"], d["loja_c"], 263, 529), (d["caravelas"], d["loja_c"], 449, None), (d["zero"], d["loja_c"], 450, None),
            (d["kicaldo"], d["loja_c"], 899, None), (d["caldo"], d["loja_c"], 1149, None),
            (d["uniao"], d["loja_g"], 399, None), (d["kicaldo"], d["loja_g"], 999, None), (d["caldo"], d["loja_g"], 1068, None),
        ]:  # fmt: skip
            c.execute(obs, (pid, loja, preco, de, hora))
    cache_catalogo.limpar_cache()
    return d


@pytest.fixture(scope="module")
def api(banco_url, dados):
    with TestClient(create_app(banco_url)) as cliente:
        yield cliente


@pytest.fixture(scope="module")
def eu(api, dados):
    r = api.post("/v1/aparelhos", json={"apelido": "Pedro", "bairro_id": str(dados["bairro"])}).json()
    return {"h": {"Authorization": f"Bearer {r['token']}"}, "lista": r["lista_id"]}


def test_seu_mercado_e_o_mais_perto_com_preco_e_pode_ser_trocado(api, dados, eu):
    r = api.get("/v1/mercados", headers=eu["h"]).json()
    assert (r["seu_mercado"]["nome"], r["automatico"]) == ("Cooper Itoupavazinha", True)
    r = api.put("/v1/casa/mercado", headers=eu["h"], json={"loja_id": str(dados["loja_g"])}).json()
    assert (r["seu_mercado"]["nome"], r["automatico"]) == ("Giassi Victor Konder", False)
    r = api.put("/v1/casa/mercado", headers=eu["h"], json={"loja_id": None}).json()
    assert r["automatico"] is True


def test_busca_acucar_traz_acucar_e_esconde_o_zero_acucar(api, eu):
    r = api.get("/v1/busca", headers=eu["h"], params={"q": "açúcar"}).json()
    assert r["escondidos_zero"] == 1
    assert {p["marca"] for p in r["produtos"]} == {"União", "Caravelas"}
    primeiro = r["produtos"][0]
    assert (primeiro["nome_curto"], primeiro["preco_centavos"], primeiro["no_seu_mercado"], primeiro["desconto_pct"]) == (
        "Açúcar refinado",
        263,
        True,
        50,
    )
    assert primeiro["preco_por_unidade"] == "R$ 2,63/kg"
    [g] = r["grupos"]
    assert (g["nome"], g["marcas"], g["a_partir_centavos"], g["marca_mais_barata"]) == ("Açúcar refinado · 1 kg", 2, 263, "União")
    assert {m["valor"]: m["n"] for m in r["filtros"]["marcas"]} == {"União": 1, "Caravelas": 1}
    # mostrar mesmo assim
    assert api.get("/v1/busca", headers=eu["h"], params={"q": "açúcar", "mostrar_zero": True}).json()["total"] == 3


def test_busca_mostra_quando_e_mais_barato_longe(api, eu):
    r = api.get("/v1/busca", headers=eu["h"], params={"q": "feijão carioca", "ordem": "preco"}).json()
    caldo = next(p for p in r["produtos"] if p["marca"] == "Caldo Bom")
    assert caldo["preco_centavos"] == 1149 and caldo["mais_barato_longe"]["rede"] == "Giassi"
    assert [
        p["marca"] for p in api.get("/v1/busca", headers=eu["h"], params={"q": "feijão", "marca": "Kicaldo"}).json()["produtos"]
    ] == ["Kicaldo"]


def test_qualquer_marca_pega_a_mais_barata_de_cada_mercado(api, dados, eu):
    pedido = {
        "bairro_id": str(dados["bairro"]),
        "itens": {str(dados["caldo"]): 1},
        "qualquer_marca": [str(dados["caldo"])],
        "custo_km_centavos": 0,
    }
    lojas = {lj["rede"]: lj for lj in api.post("/v1/comparar", headers=eu["h"], json=pedido).json()["lojas"]}
    assert lojas["Cooper"]["total_centavos"] == 899 and lojas["Giassi"]["total_centavos"] == 999  # Kicaldo nos dois
    assert lojas["Cooper"]["escolhas"][0]["marca"] == "Kicaldo"
    # sem "qualquer marca", vale a marca pedida
    pedido |= {"qualquer_marca": []}
    lojas = {lj["rede"]: lj for lj in api.post("/v1/comparar", headers=eu["h"], json=pedido).json()["lojas"]}
    assert lojas["Cooper"]["total_centavos"] == 1149


def test_item_qualquer_marca_na_lista(api, dados, eu):
    op = {
        "id": str(uuid4()),
        "item_id": str(uuid4()),
        "tipo": "criar",
        "feita_em": AGORA.isoformat(),
        "produto_id": str(dados["caldo"]),
        "qualquer_marca": True,
    }
    assert api.post(f"/v1/listas/{eu['lista']}/operacoes", headers=eu["h"], json={"operacoes": [op]}).status_code == 200
    [item] = api.get(f"/v1/listas/{eu['lista']}", headers=eu["h"]).json()["itens"]
    assert (item["qualquer_marca"], item["nome_curto"]) == (True, "Feijão carioca")
    r = api.post(
        "/v1/comparar", headers=eu["h"], json={"bairro_id": str(dados["bairro"]), "lista_id": eu["lista"], "custo_km_centavos": 0}
    ).json()
    assert {lj["rede"]: lj["total_centavos"] for lj in r["lojas"]} == {"Cooper": 899, "Giassi": 999}


def test_produto_mostra_equivalente_mais_barato_no_seu_mercado(api, dados, eu):
    r = api.get(f"/v1/produtos/{dados['caldo']}", headers=eu["h"]).json()
    assert r["seu_mercado"]["preco_centavos"] == 1149
    assert [(e["marca"], e["economia_centavos"]) for e in r["equivalentes"]] == [("Kicaldo", 250)]


def test_ofertas_comecam_pelo_seu_mercado(api, eu):
    r = api.get("/v1/ofertas", headers=eu["h"]).json()
    uniao = next(o for o in r["ofertas"] if o["produto"]["marca"] == "União")
    assert uniao["seu_mercado"] is True and uniao["preco_por_unidade"] == "R$ 2,63/kg"


def test_inicio_resume_a_casa(api, eu):
    r = api.get("/v1/inicio", headers=eu["h"]).json()
    assert r["seu_mercado"]["nome"] == "Cooper Itoupavazinha"
    assert r["status"]["produtos"] == 5
    assert any(b["nome"].startswith("Feijão carioca") for b in r["basicos"])
    assert r["atividade"] == []  # só aparece o que os outros da casa fizeram
