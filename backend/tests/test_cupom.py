"""Preço pelo cupom fiscal: o preço pago vira o preço da loja; loja sem CNPJ espera a revisão."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from quantofica.agentes.revisor import decidir_cupom
from quantofica.coleta import cupom

AGORA = datetime(2026, 10, 30, 15, tzinfo=UTC)


def test_momento_e_preco_unitario():
    assert cupom.momento(date(2026, 10, 29), AGORA) == datetime(2026, 10, 29, 15, tzinfo=UTC)  # meio-dia em Blumenau
    assert cupom.momento(date(2026, 10, 30), datetime(2026, 10, 30, 13, tzinfo=UTC)) == datetime(2026, 10, 30, 13, tzinfo=UTC)
    assert cupom.momento(date(2026, 10, 31), AGORA) is None  # data no futuro
    assert cupom.momento(date(2026, 9, 1), AGORA) is None  # velho demais
    assert cupom.preco_unitario(Decimal(2), 1398) == 699
    assert cupom.preco_unitario(Decimal("0.512"), 1530) is None  # pesado: preço por quilo, não por unidade


def test_revisor_sugere_a_unica_loja_da_rede_sem_cnpj():
    loja = {"id": uuid4(), "nome": "Bistek Itoupava"}
    d = decidir_cupom({"emitente": "BISTEK SUPERMERCADOS LTDA"}, "Bistek", [loja])
    assert d.acao == "sugerir" and d.confianca < 0.9 and d.loja == {"id": str(loja["id"]), "nome": "Bistek Itoupava"}
    assert decidir_cupom({"emitente": "X"}, "Bistek", [loja, loja]).acao == "humano"
    assert decidir_cupom({"emitente": "PADARIA DO ZE"}, None, []).acao == "humano"


def test_cupom_publica_na_loja_e_guarda_o_de_loja_sem_cadastro(banco_url):
    ids = {k: uuid4() for k in ("cidade", "rede", "bistek1", "bistek2", "arroz", "cafe")}
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (ids["cidade"],))
        c.execute("insert into rede (id, nome) values (%s, 'Bistek')", (ids["rede"],))
        c.execute(
            "insert into loja (id, rede_id, cidade_id, nome, cnpj) values (%s, %s, %s, 'Bistek Centro', '11111111000111'),"
            " (%s, %s, %s, 'Bistek Itoupava', null)",
            (ids["bistek1"], ids["rede"], ids["cidade"], ids["bistek2"], ids["rede"], ids["cidade"]),
        )
        c.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g')")
        for k in ("arroz", "cafe"):
            c.execute("insert into produto (id, categoria_id, nome_humano) values (%s, 'graos', %s)", (ids[k], k))
        arroz, cafe = str(ids["arroz"]), str(ids["cafe"])

        # Loja conhecida: publica na hora (fonte cupom).
        r = cupom.publicar(c, str(ids["bistek1"]), {arroz: 2290}, AGORA - timedelta(hours=3), AGORA)
        assert r == {"publicados": 1, "revisao": 0}
        atual = c.execute("select fonte, preco_centavos, evidencia_id from preco_atual").fetchone()
        assert (atual["fonte"], atual["preco_centavos"], atual["evidencia_id"]) == ("cupom", 2290, "cupom")

        # Loja sem cadastro: dois cupons do mesmo CNPJ juntam os preços num só item da fila.
        cupom.guardar_para_revisao(c, "22222222000122", "BISTEK SUPERMERCADOS", {arroz: 2390}, AGORA - timedelta(days=2))
        cupom.guardar_para_revisao(c, "22222222000122", "BISTEK SUPERMERCADOS", {cafe: 1899}, AGORA - timedelta(days=1))
        itens = c.execute("select id, proposta_agente as p from fila_revisao where tipo = 'cupom'").fetchall()
        assert len(itens) == 1 and itens[0]["p"]["cupons"] == 2 and len(itens[0]["p"]["precos"]) == 2
        assert cupom.lojas_candidatas(c, "BISTEK SUPERMERCADOS LTDA")[0] == "Bistek"
        assert [lj["nome"] for lj in cupom.lojas_candidatas(c, "BISTEK SUPERMERCADOS LTDA")[1]] == ["Bistek Itoupava"]

        r = cupom.ligar_cnpj(c, str(itens[0]["id"]), str(ids["bistek2"]), "painel", AGORA)
        assert r == {"publicados": 2, "revisao": 0}
        assert c.execute("select cnpj from loja where id = %s", (ids["bistek2"],)).fetchone()["cnpj"] == "22222222000122"
        assert c.execute("select status from fila_revisao where id = %s", (itens[0]["id"],)).fetchone()["status"] == "resolvida"
        precos = c.execute(
            "select produto_id, preco_centavos from preco_atual where loja_id = %s order by preco_centavos", (ids["bistek2"],)
        ).fetchall()
        assert [(str(x["produto_id"]), x["preco_centavos"]) for x in precos] == [(cafe, 1899), (arroz, 2390)]
