from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from quantofica.coleta import agendador
from quantofica.coleta.vtex import PrecoColetado

OBS = "insert into observacao_preco (produto_id, loja_id, preco_centavos, fonte, observado_em) values "
ARROZ, CAFE, BISCOITO = "07896084700119", "07896089013405", "07622210592750"


def coletado(ean, seller="giassi01", preco=2590, origem="simulacao_loja", nome="Arroz Kiarroz 5kg"):
    return PrecoColetado("giassi", seller, "Giassi Victor Konder", ean, "10", nome, preco, None, origem)


def test_planejar_grava_so_preco_da_loja_e_manda_o_resto_para_revisao():
    lojas, produtos = {"giassi01": "L1"}, {ARROZ: "P-arroz", CAFE: "P-cafe", BISCOITO: "P-bisc"}
    plano = agendador.planejar(
        [
            coletado(ARROZ),
            coletado(CAFE, origem="catalogo", preco=1899),
            coletado(BISCOITO, origem="embalagem_diferente", preco=None, nome="Biscoito Trakinas Pack 3x"),
            coletado(BISCOITO, seller="giassi02", origem="embalagem_diferente", preco=None, nome="Biscoito Trakinas Pack 3x"),
            coletado(ARROZ, seller="giassi99"),
            coletado("07890000000001"),  # EAN que não está no catálogo: ignorado
        ],
        lojas,
        produtos,
        {},
    )
    assert [(g.loja_id, g.produto_id, g.preco_centavos) for g in plano.gravar] == [("L1", "P-arroz", 2590)]
    assert plano.so_catalogo == 1
    assert sorted(r.anomalia.referencia for r in plano.revisar) == ["giassi:07622210592750", "seller:giassi:giassi99"]


def test_planejar_segura_preco_fora_da_curva():
    plano = agendador.planejar([coletado(ARROZ, preco=5990)], {"giassi01": "L1"}, {ARROZ: "P"}, {"P": [2490, 2590, 2690]})
    assert plano.gravar == []
    assert plano.revisar[0].proposta["preco_centavos"] == 5990


class SiteFalso:
    """Responde como a API VTEX do Giassi, sem rede."""

    PRODUTOS = {
        ARROZ.lstrip("0"): ("10", "Arroz Kiarroz Tipo 1 5kg", 2590),
        CAFE.lstrip("0"): ("20", "Café Pilão Tradicional 500g", 5990),  # fora da curva
        BISCOITO.lstrip("0"): ("30", "Biscoito Trakinas Pack 3x 126g", 1299),
    }

    def __init__(self):
        self.chamadas = []

    def __call__(self, url, corpo):
        self.chamadas.append(url)
        if "/regions" in url:
            return [{"sellers": [{"id": "giassi01", "name": "Giassi Victor Konder"}]}]
        if "alternateIds_Ean:" in url:
            codigo = url.rsplit(":", 1)[1]
            if codigo not in self.PRODUTOS:
                return []
            sku, nome, _ = self.PRODUTOS[codigo]
            return [{"productName": nome, "items": [{"itemId": sku, "ean": codigo, "sellers": []}]}]
        if "/simulation" in url:
            precos = {sku: p for sku, _, p in self.PRODUTOS.values()}
            return {
                "items": [
                    {"id": i["id"], "seller": i["seller"], "availability": "available", "sellingPrice": precos[i["id"]]}
                    for i in corpo["items"]
                ]
            }
        return None


def test_coleta_grava_no_banco(banco_url, monkeypatch):
    ids = {k: uuid4() for k in ("cidade", "rede", "loja", "arroz", "cafe", "biscoito")}
    with psycopg.connect(banco_url) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (ids["cidade"],))
        c.execute("insert into rede (id, nome, tem_api) values (%s, 'Giassi', true)", (ids["rede"],))
        c.execute(
            "insert into loja (id, rede_id, cidade_id, nome, seller_id) values (%s, %s, %s, 'Giassi Victor Konder', 'giassi01')",
            (ids["loja"], ids["rede"], ids["cidade"]),
        )
        c.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g')")
        for chave, ean in (("arroz", ARROZ), ("cafe", CAFE), ("biscoito", BISCOITO)):
            c.execute("insert into produto (id, categoria_id, nome_humano) values (%s, 'graos', %s)", (ids[chave], chave))
            c.execute("insert into ean (codigo, produto_id) values (%s, %s)", (ean, ids[chave]))
        for dias in (3, 2, 1):
            c.execute(
                OBS + "(%s, %s, 1899, 'site', %s)",
                (ids["cafe"], ids["loja"], datetime.now(UTC) - timedelta(days=dias)),
            )

    monkeypatch.setenv("DATABASE_URL", banco_url)
    site = SiteFalso()
    assert agendador.main(["--rede", "giassi"], http=site) == 0
    assert agendador.main(["--rede", "giassi"], http=site) == 0  # segunda rodada não duplica a revisão

    with psycopg.connect(banco_url, row_factory=dict_row) as c:
        novos = c.execute(
            "select produto_id, preco_centavos, evidencia_id from observacao_preco where preco_centavos <> 1899"
        ).fetchall()
        # Preço igual na segunda rodada: o histórico não ganha linha nova; o preço atual só é confirmado.
        assert [(r["produto_id"], r["preco_centavos"]) for r in novos] == [(ids["arroz"], 2590)]
        atual = c.execute(
            "select preco_centavos, observado_em, desde from preco_atual where produto_id = %s", (ids["arroz"],)
        ).fetchone()
        assert atual["preco_centavos"] == 2590 and atual["observado_em"] >= atual["desde"]
        assert novos[0]["evidencia_id"] == "vtex:giassi:giassi01:10"
        fila = c.execute("select tipo, referencia_id from fila_revisao order by tipo, referencia_id").fetchall()
        assert [(r["tipo"], r["referencia_id"]) for r in fila] == [
            ("anomalia", f"preco:{ids['loja']}:{ids['cafe']}"),
            ("ean", f"giassi:{BISCOITO}"),
        ]
        execucoes = c.execute("select status, precos_gravados, eans_pedidos from execucao_coleta").fetchall()
        assert [(e["status"], e["precos_gravados"], e["eans_pedidos"]) for e in execucoes] == [("ok", 1, 3)] * 2
        nomes = c.execute("select sku, nome_no_site from produto_na_rede order by sku").fetchall()
        assert [n["sku"] for n in nomes] == ["10", "20", "30"]
