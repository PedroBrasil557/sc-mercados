"""Preços do site do Fort: ligação sem código de barras só com certeza, sugestão para o painel e trava de preço."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from quantofica.coleta import fort_site
from quantofica.coleta.casamento import Candidato, casar_estrito
from quantofica.regras.tamanho import Tamanho


def cand(chave, nome, marca, q, u):
    return Candidato(chave, nome, marca, Tamanho(q, u))


def test_casador_estrito_so_liga_o_mesmo_produto():
    fanta = [cand("laranja", "Refrigerante Laranja Fanta Garrafa 600ml", "Fanta", 600, "ml"),
             cand("uva", "Refrigerante Uva Fanta Garrafa 600ml", "Fanta", 600, "ml")]  # fmt: skip
    assert [c.chave for c in casar_estrito("Refrigerante Fanta Laranja Pet 600ml", "Fanta", fanta)] == ["laranja"]
    kitano = [cand("com", "Tempero Completo com Pimenta Kitano Pote 300g", "Kitano", 300, "g")]
    assert casar_estrito("Tempero Completo Kitano sem Pimenta 300g", "Kitano", kitano) == []
    nescafe = [cand("7", "Café Solúvel Liofilizado Intensidade 7 Nescafé Gold Sachê 40g", "Nescafé", 40, "g")]
    assert casar_estrito("Café Solúvel Nescafé Gold Intensidade 6 Sachê 40g", "Nescafé", nescafe) == []
    lixo = [cand("10", "Saco Lixo Dover Roll Preto 100 litros Pacote 10 Unidades", "Dover Roll", 100000, "ml")]
    assert casar_estrito("Saco para Lixo Dover Roll Preto 100L Com 15 Unidades", "Dover Roll", lixo) == []
    granado = [cand("refil", "Sabonete Líquido Camomila Granado Bebê Sachê 250ml Refil", "Granado", 250, "ml")]
    assert casar_estrito("Sabonete Líquido Infantil Granado Bebê Camomila 250ml Frasco", "Granado", granado) == []
    sundown = [cand("kit", "Protetor Solar Sundown Praia e Piscina Fps50 200ml Gratis FPS50 120ml", "Sundown", 200, "ml")]
    assert casar_estrito("Protetor Solar Sundown Praia e Piscina FPS50 200ml", "Sundown", sundown) == []
    # O mesmo produto cadastrado duas vezes (dois códigos de barras): leva os dois.
    red = [cand("a", "Whisky Escocês Red Label Johnnie Walker Garrafa 1l", "Johnnie Walker", 1000, "ml"),
           cand("b", "Whisky Escocês Red Label Johnnie Walker Garrafa 1L", "Johnnie Walker", 1000, "ml")]  # fmt: skip
    achados = casar_estrito("Whisky Escocês Johnnie Walker Red Label 1 Litro", "Johnnie Walker", red)
    assert {c.chave for c in achados} == {"a", "b"}


class SiteDoFort:
    """O sitemap e a API da loja virtual, sem rede."""

    def __init__(self, produtos):
        self.produtos = produtos

    def binario(self, url):
        return "".join(f"<loc>https://fortatacadista.com.br/produtos/{i}/x</loc>" for i in self.produtos).encode()

    def __call__(self, url, corpo, cabecalhos=None):
        pedidos = [p.split('"')[0] for p in corpo["query"].split('product(id: "')[1:]]
        visao = {f"p{i}": self.produtos[i] for i in pedidos if i in self.produtos}
        return {"data": {"publicViewer": {"id": "x", **visao}}}


def produto_do_site(i, nome, marca, preco, promo=0.0):
    precos = {"price": preco, "promotionalPrice": promo, "promotion": promo > 0}
    return {"id": i, "name": nome, "brand": {"name": marca}, "pricing": precos}


def test_coleta_liga_publica_sugere_e_trava(banco_url):
    agora = datetime(2026, 10, 30, 10, tzinfo=UTC)
    ids = {k: uuid4() for k in ("cidade", "fort", "giassi", "f1", "f2", "g1", "fanta", "nescau", "coca")}
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as c:
        c.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (ids["cidade"],))
        c.execute("insert into rede (id, nome) values (%s, 'Fort Atacadista'), (%s, 'Giassi')", (ids["fort"], ids["giassi"]))
        for loja, rede in (("f1", "fort"), ("f2", "fort"), ("g1", "giassi")):
            c.execute(
                "insert into loja (id, rede_id, cidade_id, nome) values (%s, %s, %s, %s)",
                (ids[loja], ids[rede], ids["cidade"], loja),
            )
        c.execute("insert into categoria (id, nome, unidade_medida) values ('bebidas', 'Bebidas', 'ml')")
        catalogo = [
            ("fanta", "Refrigerante Laranja Fanta Garrafa 600ml", "Fanta", 600, "ml", "07894900031515"),
            ("nescau", "Achocolatado Pó Nescau Menos Açúcar Lata 350g", "Nescau", 350, "g", "07891000315507"),
            ("coca", "Refrigerante Coca-Cola Garrafa 2l", "Coca-Cola", 2000, "ml", "07894900027013"),
        ]
        for chave, nome, marca, q, u, ean in catalogo:
            c.execute(
                "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) "
                "values (%s, 'bebidas', %s, %s, %s, %s)",
                (ids[chave], nome, marca, q, u),
            )
            c.execute("insert into ean (codigo, produto_id) values (%s, %s)", (ean, ids[chave]))
        # Referência dos outros mercados: a Coca de 2 L custa R$ 10,00 no Giassi.
        c.execute(
            "insert into observacao_preco (produto_id, loja_id, preco_centavos, fonte, observado_em) "
            "values (%s, %s, 1000, 'site', %s)",
            (ids["coca"], ids["g1"], agora - timedelta(hours=5)),
        )
        site = SiteDoFort({
            "1": produto_do_site("1", "Refrigerante Fanta Laranja Pet 600ml", "Fanta", 5.49, promo=4.99),
            "2": produto_do_site("2", "Achocolatado em Pó Nescau 350g Leve Mais Pague Menos", "Nescau", 9.98),
            "3": produto_do_site("3", "Refrigerante Coca-Cola Pet 2 Litros", "Coca-Cola", 19.90),  # o dobro: trava
        })  # fmt: skip
        r = fort_site.rodar(c, site, agora)
        assert (r["no_site"], r["ligados_agora"], r["sugestoes"], r["travados"]) == (3, 2, 1, 1)

        precos = c.execute(
            "select loja_id, preco_centavos, preco_de_centavos from preco_atual where produto_id = %s order by loja_id",
            (ids["fanta"],),
        ).fetchall()
        assert sorted(str(p["loja_id"]) for p in precos) == sorted([str(ids["f1"]), str(ids["f2"])])
        assert {(p["preco_centavos"], p["preco_de_centavos"]) for p in precos} == {(499, 549)}
        fora_do_giassi = "select count(*) as n from preco_atual where produto_id = %s and loja_id <> %s"
        assert c.execute(fora_do_giassi, (ids["coca"], ids["g1"])).fetchone()["n"] == 0  # travado: não publicou

        sugestao = c.execute("select id, proposta_agente as p from fila_revisao where referencia_id = 'fort-site:2'").fetchone()
        assert sugestao["p"]["produtos"] == [str(ids["nescau"])]  # o casador de encarte ligaria "menos" com "Menos Açúcar"
        assert c.execute("select count(*) as n from produto_na_rede where sku = '2'").fetchone()["n"] == 0

        # A pessoa confere e aceita (aqui só para testar o caminho; neste exemplo ela deveria descartar).
        assert fort_site.ligar_sugestao(c, str(sugestao["id"]), sugestao["p"], [str(ids["nescau"])], "painel", agora) == 2
        assert c.execute("select status from fila_revisao where id = %s", (sugestao["id"],)).fetchone()["status"] == "resolvida"
        execucao = c.execute("select status, precos_gravados from execucao_coleta").fetchone()
        assert (execucao["status"], execucao["precos_gravados"]) == ("ok", 2)
