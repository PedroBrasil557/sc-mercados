"""Preço atual + histórico só com mudanças: o banco cresce com as mudanças de preço, não com os dias."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from quantofica.api.detalhes import serie_diaria
from quantofica.coleta import gravar
from quantofica.coleta.gravar import Preco


def test_preco_igual_so_confirma_e_preco_novo_vai_para_o_historico(banco_url):
    cidade, rede, loja, produto = uuid4(), uuid4(), uuid4(), uuid4()
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (cidade,))
        c.execute("insert into rede (id, nome) values (%s, 'Giassi')", (rede,))
        c.execute("insert into loja (id, rede_id, cidade_id, nome) values (%s, %s, %s, 'Giassi')", (loja, rede, cidade))
        c.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g')")
        c.execute(
            "insert into produto (id, categoria_id, nome_humano, tamanho, unidade) values (%s, 'graos', 'Arroz 5kg', 5000, 'g')",
            (produto,),
        )
        dia = datetime(2026, 10, 27, 8, tzinfo=UTC)
        p = Preco(str(produto), str(loja), 2590)
        assert gravar.registrar(c, [p], dia) == {"mudaram": 1, "confirmados": 0}
        assert gravar.registrar(c, [p], dia + timedelta(days=1)) == {"mudaram": 0, "confirmados": 1}
        assert gravar.registrar(c, [Preco(str(produto), str(loja), 2490)], dia + timedelta(days=2)) == {
            "mudaram": 1,
            "confirmados": 0,
        }
        historico = c.execute("select preco_centavos from observacao_preco order by observado_em").fetchall()
        assert [h["preco_centavos"] for h in historico] == [2590, 2490]
        atual = c.execute("select preco_centavos, observado_em, desde, anterior_centavos from preco_atual").fetchone()
        assert (atual["preco_centavos"], atual["desde"], atual["observado_em"], atual["anterior_centavos"]) == (
            2490,
            dia + timedelta(days=2),
            dia + timedelta(days=2),
            2590,  # o primeiro preço visto não tem anterior; a mudança tem (e só ela pode virar oferta)
        )


def test_serie_diaria_repete_o_ultimo_preco_ate_a_proxima_mudanca():
    agora = datetime(2026, 10, 30, 12, tzinfo=UTC)
    mudancas = [(datetime(2026, 10, 20, 12, tzinfo=UTC), 2590), (datetime(2026, 10, 28, 12, tzinfo=UTC), 2490)]
    serie = serie_diaria(mudancas, 30, agora)
    assert serie[0] == (date(2026, 10, 20), 2590)
    assert dict(serie)[date(2026, 10, 27)] == 2590 and dict(serie)[date(2026, 10, 28)] == 2490
    assert serie[-1] == (date(2026, 10, 30), 2490) and len(serie) == 11
