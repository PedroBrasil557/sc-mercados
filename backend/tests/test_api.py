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
    assert divisao["distancia_extra_km"] >= 0
    assert r["itens"] == 2
    assert r["redes_sem_preco"] == []  # as duas redes do teste têm preço


def test_comparar_recomenda_a_mais_perto_quando_ir_longe_nao_compensa(api, dados, casa):
    # Giassi (0,4 km) 25,90 x Cooper Itoupava Seca (1,1 km) 24,90: 1 real não paga a viagem nem a folga de 10
    pedido = {"bairro_id": str(dados["bairro"]), "itens": {str(dados["arroz"]): 1}}
    lojas = api.post("/v1/comparar", headers=casa["ana"], json=pedido).json()["lojas"]
    assert [(lj["nome"], lj["recomendada"]) for lj in lojas] == [("Giassi Victor Konder", True), ("Cooper Itoupava Seca", False)]
    assert lojas[1]["nota"].startswith("R$\u00a01,00 mais barato na prateleira")
    assert 0 < lojas[0]["custo_viagem_centavos"] < lojas[1]["custo_viagem_centavos"]


def test_comparar_com_a_loja_preferida_da_rede(api, dados, casa):
    pedido = {"bairro_id": str(dados["bairro"]), "itens": {str(dados["arroz"]): 1}, "preferidas": [str(dados["cooper_longe"])]}
    lojas = api.post("/v1/comparar", headers=casa["ana"], json=pedido).json()["lojas"]
    # A Cooper usada é a preferida (Garcia), não a mais perto; a recomendada continua sendo a melhor para a casa
    assert {lj["nome"] for lj in lojas} == {"Cooper Garcia", "Giassi Victor Konder"}


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
    cafe = api.get("/v1/produtos", headers=casa["ana"], params={"busca": "cafe"}).json()[0]
    # Giassi 18,99 x Cooper perto 20,99 x Cooper longe 10,00: o menor da cidade, com a rede
    assert (cafe["menor_preco_centavos"], cafe["menor_preco_rede"]) == (1000, "Cooper")
    assert nomes("PILÃO") == ["Café tradicional"]  # pela marca
    assert nomes("arroz kiarroz") == ["Arroz tipo 1"]  # todas as palavras
    assert nomes("feijão") == []
    assert len(nomes("")) == 2  # sem busca: o catálogo
    assert api.get("/v1/produtos").status_code == 401


def test_trocar_apelido_e_bairro(api, dados, casa):
    r = api.patch("/v1/eu", headers=casa["paulo"], json={"apelido": "Paulão", "bairro_id": str(dados["bairro"])})
    assert r.status_code == 200
    assert r.json()["membro"]["apelido"] == "Paulão"
    assert r.json()["casa"]["bairro_id"] == str(dados["bairro"])
    assert api.patch("/v1/eu", headers=casa["paulo"], json={"bairro_id": str(uuid4())}).status_code == 422
    api.patch("/v1/eu", headers=casa["paulo"], json={"apelido": "Paulo"})


def test_detalhe_do_produto_mostra_o_preco_em_cada_loja(api, dados, casa):
    api.patch("/v1/eu", headers=casa["ana"], json={"bairro_id": str(dados["bairro"])})
    r = api.get(f"/v1/produtos/{dados['arroz']}", headers=casa["ana"]).json()
    assert r["produto"]["nome"] == "Arroz tipo 1"
    assert [p["preco_centavos"] for p in r["precos"]] == [1000, 2490, 2590]  # todas as lojas, do mais barato
    assert r["precos"][0]["nome"] == "Cooper Garcia"
    # O seu mercado (sem escolha: o mais perto com preço do site) vem primeiro, com o histórico dele
    assert (r["seu_mercado"]["nome"], r["seu_mercado"]["preco_centavos"]) == ("Giassi Victor Konder", 2590)
    assert [h["preco_centavos"] for h in r["historico"]] == [2590]
    # A Cooper aparece uma vez só (pela loja mais barata dela) e o veredito diz se vale ir até lá
    assert [linha["rede"] for linha in r["por_rede"]].count("Cooper") == 1
    assert r["veredito"]["rede"] == "Cooper" and r["veredito"]["economia_centavos"] == 2590 - 1000


def test_outras_lojas_da_rede(api, dados, casa):
    pedido = {"rede": "Cooper", "itens": {str(dados["arroz"]): 1, str(dados["cafe"]): 2}}
    lojas = api.post("/v1/comparar/rede", headers=casa["ana"], json=pedido).json()["lojas"]
    assert [(lj["nome"], lj["total_centavos"]) for lj in lojas] == [
        ("Cooper Itoupava Seca", 2490 + 2 * 2099),
        ("Cooper Garcia", 1000 + 2 * 1000),
    ]


def test_oferta_provisoria_pelo_de_por_conferido_com_as_outras_lojas(api, banco_url, dados, casa):
    with psycopg.connect(banco_url) as c:
        # Giassi anuncia café de 24,90 por 17,90: 28% abaixo do "de" e abaixo da mediana das outras lojas
        c.execute(
            "insert into observacao_preco (produto_id, loja_id, preco_centavos, preco_de_centavos, fonte, observado_em) "
            "values (%s, %s, 1790, 2490, 'site', %s)",
            (dados["cafe"], dados["loja_giassi"], AGORA - timedelta(minutes=30)),
        )
    ofertas = api.get("/v1/ofertas", headers=casa["ana"]).json()["ofertas"]
    assert [(o["produto"]["nome"], o["rede"], o["desconto_pct"]) for o in ofertas] == [("Café tradicional", "Giassi", 28)]


def test_reporte_de_preco_vai_para_a_revisao(api, banco_url, dados, casa):
    r = api.post(
        "/v1/reportes",
        headers=casa["ana"],
        json={"produto_id": str(dados["arroz"]), "loja_id": str(dados["loja_giassi"]), "preco_centavos": 2390},
    )
    assert r.status_code == 201
    with psycopg.connect(banco_url) as c:
        assert c.execute("select count(*) from fila_revisao where tipo = 'reporte'").fetchone()[0] == 1


def test_busca_por_codigo_de_barras(api, banco_url, dados, casa):
    with psycopg.connect(banco_url) as c:
        c.execute("insert into ean (codigo, produto_id) values ('07896084700119', %s)", (dados["arroz"],))
    assert api.get("/v1/produtos/ean/7896084700119", headers=casa["ana"]).json()["nome"] == "Arroz tipo 1"
    assert api.get("/v1/produtos/ean/7890000000000", headers=casa["ana"]).status_code == 404


def test_cupom_calcula_a_economia_so_com_os_itens_reconhecidos(api, banco_url, casa):
    cupom = {
        "chave": "4226 1012 3456 7800 0199 6500 1000 0012 3410 0012 3456",
        "emitente": "Mercado Exemplo",
        "emitido_em": AGORA.date().isoformat(),
        "total_centavos": 4290,
        "itens": [
            {"descricao": "ARROZ KIARROZ T1 5KG", "codigo": "7896084700119", "quantidade": 1, "valor_total_centavos": 2290},
            {"descricao": "PAO FRANCES KG", "codigo": "1234", "quantidade": 0.5, "valor_total_centavos": 2000},
        ],
    }
    r = api.post("/v1/cupons", headers=casa["ana"], json=cupom)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert (corpo["itens"], corpo["itens_reconhecidos"]) == (2, 1)
    # Arroz: pagou 22,90; média da loja mais perto de cada rede = (25,90 + 24,90) / 2 = 25,40
    assert corpo["economia"]["economia_centavos"] == 250
    assert corpo["economia"]["base"] == "comparado à média de Cooper e Giassi"
    assert api.post("/v1/cupons", headers=casa["ana"], json=cupom).status_code == 409  # o mesmo cupom não conta duas vezes
    assert api.get("/v1/economia", headers=casa["ana"]).json()["economia_centavos"] == 250
    with psycopg.connect(banco_url) as c:
        assert c.execute("select count(*) from codigo_item_loja where codigo_interno = '1234'").fetchone()[0] == 1


def test_codigo_de_recuperacao_leva_a_mesma_lista_para_outro_celular(api, casa):
    codigo = api.post("/v1/eu/recuperacao", headers=casa["paulo"]).json()["codigo"]
    assert len(codigo) == 14 and codigo.count("-") == 2
    novo = api.post("/v1/recuperar", json={"codigo": codigo.lower()}).json()
    assert str(novo["lista_id"]) == casa["lista"]
    eu = api.get("/v1/eu", headers=com_token(novo["token"])).json()
    assert eu["membro"]["apelido"] == "Paulo"
    assert api.post("/v1/recuperar", json={"codigo": "ZZZZ-ZZZZ-ZZZZ"}).status_code == 404


def test_lista_na_web_com_politica_de_seguranca(api):
    r = api.get("/c/ABCD2345")
    assert r.status_code == 200 and "Lista da casa" in r.text
    politica = r.headers["content-security-policy"]
    nonce = politica.split("'nonce-")[1].split("'")[0]
    assert f'nonce="{nonce}"' in r.text and "unsafe-inline" not in politica and "frame-ancestors 'none'" in politica
    assert api.get("/c/ABCD2345").headers["content-security-policy"] != politica  # nonce novo a cada resposta


def test_bairros_sao_publicos(api):
    bairros = api.get("/v1/bairros").json()
    assert [b["nome"] for b in bairros] == ["Victor Konder"]
    assert round(bairros[0]["lat"], 4) == -26.9068


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


def test_loja_so_com_itens_do_encarte_aparece_a_parte(api, dados, banco_url):
    # Fort perto, com só o café no encarte: não pode encolher o total justo das outras para 1 item.
    fort, loja = uuid4(), uuid4()
    with psycopg.connect(banco_url) as c:
        c.execute("insert into rede (id, nome) values (%s, 'Fort Atacadista')", (fort,))
        c.execute(
            "insert into loja (id, rede_id, cidade_id, nome, lat, lon) values (%s, %s, %s, 'Fort Itoupava Norte', %s, %s)",
            (loja, fort, dados["cidade"], -26.9060, -49.0780),
        )
        c.execute(
            "insert into observacao_preco (produto_id, loja_id, preco_centavos, fonte, observado_em, valido_ate) "
            "values (%s, %s, 1590, 'encarte', %s, %s)",
            (dados["cafe"], loja, AGORA - timedelta(hours=2), AGORA + timedelta(days=2)),
        )
    pedido = {"bairro_id": str(dados["bairro"]), "itens": {str(dados["arroz"]): 1, str(dados["cafe"]): 2}}
    eu = api.post("/v1/aparelhos", json={"apelido": "Bia", "bairro_id": str(dados["bairro"])}).json()
    r = api.post("/v1/comparar", headers=com_token(eu["token"]), json=pedido).json()
    assert r["comuns"] == 2
    assert "Fort Atacadista" not in [lj["rede"] for lj in r["lojas"]]
    [poucos] = r["lojas_com_poucos_itens"]
    assert (poucos["rede"], poucos["itens"], poucos["total_centavos"]) == ("Fort Atacadista", [str(dados["cafe"])], 2 * 1590)
    # Os mesmos itens (o café) também na recomendada, para comparar
    assert poucos["mesmos_itens"] == 1 and poucos["mesmos_itens_na_recomendada_centavos"] > 0
    assert poucos["valido_ate"] is not None


@pytest.mark.parametrize("caminho", ["/privacidade", "/termos", "/excluir-conta"])
def test_paginas_legais_com_csp_e_dados_do_responsavel(api, caminho, monkeypatch):
    monkeypatch.setenv("RESPONSAVEL_NOME", "Fulano <b>de Tal</b>")
    monkeypatch.setenv("CONTATO_EMAIL", "contato@exemplo.com")
    r = api.get(caminho)
    assert r.status_code == 200
    assert "script-src 'nonce-" in r.headers["content-security-policy"]
    assert "{{" not in r.text
    assert "contato@exemplo.com" in r.text
    assert "<b>de Tal</b>" not in r.text  # nome entra como texto, nunca como HTML
