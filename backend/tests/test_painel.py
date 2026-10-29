"""Painel interno: acesso por token, fila de revisão, ligar item de encarte e confirmar loja."""

import hashlib
import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from quantofica.api import painel
from quantofica.api.app import create_app
from quantofica.coleta import fort
from quantofica.coleta.encarte_pdf import Encarte, ItemDoEncarte

TOKEN = "token-de-teste-do-painel"
ADMIN = {"Authorization": f"Bearer {TOKEN}"}
FILA = "insert into fila_revisao (id, tipo, referencia_id, proposta_agente, motivo) values "


@pytest.fixture(scope="module")
def dados(banco_url):
    d = {k: uuid4() for k in ("cidade", "fort", "loja1", "loja2", "osm", "arroz", "item", "ean_item")}
    hoje = datetime.now(UTC).astimezone(fort.FUSO).date()
    with psycopg.connect(banco_url, autocommit=True) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (d["cidade"],))
        c.execute("insert into rede (id, nome) values (%s, 'Fort Atacadista')", (d["fort"],))
        for loja, origem in ((d["loja1"], "rede"), (d["loja2"], "rede"), (d["osm"], "openstreetmap")):
            c.execute(
                "insert into loja (id, rede_id, cidade_id, nome, origem, lat, lon) values (%s, %s, %s, 'Fort', %s, %s, %s)",
                (loja, d["fort"], d["cidade"], origem, -26.9, -49.07),
            )
        c.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g')")
        c.execute(
            "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) "
            "values (%s, 'graos', 'Arroz Parboilizado Tipo 1 Urbano Pacote 5kg', 'Urbano', 5000, 'g')",
            (d["arroz"],),
        )
        proposta = {
            "nome": "Arroz Urbano Parb. 5 Quilos",
            "preco_centavos": 1990,
            "condicional_centavos": 1890,
            "encarte": "Semanal",
            "encarte_id": "1",
            "valido_ate": (hoje + timedelta(days=2)).isoformat(),
            "pagina": 1,
        }
        c.execute(
            FILA + "(%s, 'encarte', 'fort:1:arroz', %s, 'sem produto')",
            (d["item"], psycopg.types.json.Jsonb(proposta)),
        )
        c.execute(
            "insert into fila_revisao (id, tipo, referencia_id, motivo) values (%s, 'ean', 'sams:07890000000017', 'embalagem')",
            (d["ean_item"],),
        )
    return d


@pytest.fixture(scope="module")
def api(banco_url, dados):
    os.environ["PAINEL_TOKEN_SHA256"] = hashlib.sha256(TOKEN.encode()).hexdigest()
    with TestClient(create_app(banco_url)) as cliente:
        yield cliente
    del os.environ["PAINEL_TOKEN_SHA256"]


def test_sem_token_ou_com_token_errado_nao_entra(api):
    assert api.get("/v1/painel/resumo").status_code == 401
    assert api.get("/v1/painel/resumo", headers={"Authorization": "Bearer outro"}).status_code == 401


def test_muitas_tentativas_erradas_bloqueiam(api):
    painel.limite_painel._chamadas.clear()
    codigos = [api.get("/v1/painel/resumo", headers={"Authorization": "Bearer x"}).status_code for _ in range(11)]
    assert codigos[-1] == 429
    painel.limite_painel._chamadas.clear()
    assert api.get("/v1/painel/resumo", headers=ADMIN).status_code == 200  # token certo não conta


def test_sem_a_variavel_o_painel_nao_existe(banco_url, dados):
    guardado = os.environ.pop("PAINEL_TOKEN_SHA256")
    try:
        with TestClient(create_app(banco_url)) as cliente:
            assert cliente.get("/v1/painel/resumo", headers=ADMIN).status_code == 404
    finally:
        os.environ["PAINEL_TOKEN_SHA256"] = guardado


def test_pagina_do_painel_tem_csp_com_nonce(api):
    r = api.get("/painel")
    assert r.status_code == 200
    assert "script-src 'nonce-" in r.headers["content-security-policy"]
    assert "{{NONCE}}" not in r.text


def test_resumo_conta_a_fila_e_as_lojas_a_confirmar(api):
    r = api.get("/v1/painel/resumo", headers=ADMIN).json()
    assert r["revisao"] == {"encarte": 1, "ean": 1}
    assert r["lojas_a_confirmar"] == 1


def test_ligar_item_do_encarte_publica_o_preco_e_lembra_o_nome(api, dados, banco_url):
    item = str(dados["item"])
    assert [i["id"] for i in api.get("/v1/painel/revisao?tipo=encarte", headers=ADMIN).json()] == [item]
    busca = api.get("/v1/painel/produtos?busca=arroz urbano", headers=ADMIN).json()
    assert [p["id"] for p in busca] == [str(dados["arroz"])]

    r = api.post(f"/v1/painel/revisao/{item}/ligar", headers=ADMIN, json={"produto_ids": [str(dados["arroz"])]})
    assert r.status_code == 200
    assert r.json()["precos"] == 6  # varejo + clube nas três lojas do Fort em Blumenau
    assert (
        api.post(f"/v1/painel/revisao/{item}/ligar", headers=ADMIN, json={"produto_ids": [str(dados["arroz"])]}).status_code
        == 404
    )

    # No encarte seguinte o mesmo nome casa sozinho, mesmo sem a marca bater com as regras do casamento
    class SemRede:
        def __call__(self, url, corpo=None, cabecalhos=None):
            if "flyers(" in (corpo or {}).get("query", ""):
                return {"data": {"publicViewer": {"flyers": [{"id": "2", "title": "Semanal 2"}]}}}
            return {"data": {"publicViewer": {"flyer": {"pdf": {"url": "https://s3.exemplo/2.pdf"}}}}}

        def binario(self, url):
            return b"%PDF"

    hoje = datetime.now(UTC).astimezone(fort.FUSO).date()
    encarte = Encarte(hoje, hoje + timedelta(days=3), [ItemDoEncarte("Arroz Urbano Parb. 5 Quilos", 1890, None, False, 1)])
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        assert fort.rodar(conn, SemRede(), datetime.now(UTC), ler=lambda _pdf: encarte)["precos"] == 3
        assert (
            conn.execute("select count(*) as n from fila_revisao where tipo = 'encarte' and status = 'aberta'").fetchone()["n"]
            == 0
        )


def test_ligar_item_de_encarte_vencido_so_lembra_o_nome(api, dados, banco_url):
    item = uuid4()
    with psycopg.connect(banco_url, autocommit=True) as c:
        c.execute(
            FILA + "(%s, 'encarte', 'fort:0:x', %s, 'x')",
            (
                item,
                psycopg.types.json.Jsonb(
                    {"nome": "Arroz Velho 5kg", "preco_centavos": 999, "valido_ate": date(2020, 1, 1).isoformat()}
                ),
            ),
        )
    r = api.post(f"/v1/painel/revisao/{item}/ligar", headers=ADMIN, json={"produto_ids": [str(dados["arroz"])]}).json()
    assert r["precos"] == 0


def test_decidir_em_lote_e_confirmar_loja(api, dados):
    r = api.post("/v1/painel/revisao/decidir", headers=ADMIN, json={"ids": [str(dados["ean_item"])], "status": "descartada"})
    assert r.json() == {"decididos": 1}
    assert api.get("/v1/painel/revisao?tipo=ean", headers=ADMIN).json() == []
    assert [loja["id"] for loja in api.get("/v1/painel/lojas", headers=ADMIN).json()] == [str(dados["osm"])]
    assert api.post(f"/v1/painel/lojas/{dados['osm']}/confirmar", headers=ADMIN).status_code == 200
    assert api.get("/v1/painel/lojas", headers=ADMIN).json() == []
    assert api.post(f"/v1/painel/lojas/{dados['osm']}/confirmar", headers=ADMIN).status_code == 404


def test_agentes_mostram_tipo_autonomia_e_se_estao_em_dia(api, banco_url):
    from quantofica.agentes import revisor

    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        revisor.rodar(conn, None, datetime.now(UTC), buscar_nos_sites=False)
    r = api.get("/v1/painel/agentes", headers=ADMIN).json()
    por_id = {a["id"]: a for a in r["agentes"]}
    assert set(por_id) == {"catalogador", "coletor", "leitor_encartes", "vigia", "revisor"}
    assert por_id["revisor"]["saude"] == "em dia"
    assert por_id["coletor"]["saude"] == "nunca rodou"
    assert all(a["tipo"] == "Programa de regras (sem IA)" for a in r["agentes"])
    itens = api.get("/v1/painel/revisao", headers=ADMIN).json()
    assert all("sugestao" in i for i in itens)
