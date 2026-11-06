"""Monitoramento de erros do app: o mesmo erro vira uma linha com contagem, sem dado pessoal."""

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from quantofica.api.app import create_app
from quantofica.qualidade import monitor


def test_erro_igual_agrupa_e_fatal_repetido_vira_alerta(banco_url):
    erro = {"mensagem": "undefined is not a function", "pilha": "at Lista (lista.tsx:10)", "onde": "tela",
            "versao": "0.1.0", "plataforma": "android 34", "ambiente": "publicado", "fatal": True}  # fmt: skip
    with TestClient(create_app(banco_url)) as api:
        for _ in range(5):
            assert api.post("/v1/erros", json=erro).status_code == 204
        assert api.post("/v1/erros", json={**erro, "mensagem": "x" * 501}).status_code == 422
    with psycopg.connect(banco_url, row_factory=dict_row) as c:
        linhas = c.execute("select mensagem, vezes, fatal from erro_app").fetchall()
        assert [(r["mensagem"], r["vezes"], r["fatal"]) for r in linhas] == [("undefined is not a function", 5, True)]
        colunas = {r["column_name"] for r in c.execute(
            "select column_name from information_schema.columns where table_name = 'erro_app'").fetchall()}  # fmt: skip
        assert not colunas & {"casa_id", "membro_id", "ip", "token"}
        alertas = monitor.erros_fatais(c)
        assert len(alertas) == 1 and "5x em 24 h" in alertas[0].motivo


def test_apk_de_teste_manda_erro_com_ambiente_teste(banco_url, monkeypatch):
    """O APK de teste (MODO_TESTE) marca o erro como "teste": o banco e a API aceitam."""
    import psycopg

    with psycopg.connect(banco_url, autocommit=True) as c:
        c.execute(
            """insert into erro_app (assinatura, mensagem, onde, versao, plataforma, ambiente, fatal)
               values ('x', 'quebrou', 'busca', '0.1.0', 'android 34', 'teste', true)"""
        )
        assert c.execute("select ambiente from erro_app where assinatura = 'x'").fetchone()[0] == "teste"
