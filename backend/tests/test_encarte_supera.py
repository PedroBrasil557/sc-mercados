"""Encartes do Super A: montagem dos cartões pela posição do texto do PDF (coordenadas reais dos encartes de
02/11/2026), validade escrita, página de encartes e a rodada completa contra o Postgres, com HTTP falso."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from quantofica.coleta import encarte_pdf, encarte_rede, supera
from quantofica.coleta.encarte_pdf import Encarte, Fragmento, ItemDoEncarte

F = Fragmento


def nomes_e_precos(frs):
    itens, _ = encarte_pdf.itens_em_coluna(frs, 1)
    return sorted((i.nome, i.preco_centavos, i.por_kg) for i in itens)


class TestCartoes:
    def test_um_cartao_nome_r_cifrao_e_preco_abaixo(self):
        frs = [
            F(675.0, 484.5, 8, "Café CABOCLO \n"), F(675.0, 475.5, 8, "a Vácuo Pacote \n"), F(675.0, 466.5, 8, "500g - cada\n"),
            F(675.0, 453.5, 8, "R$"), F(685.8, 437.5, 33, "21,45"),
        ]  # fmt: skip
        assert nomes_e_precos(frs) == [("Café CABOCLO a Vácuo Pacote 500g", 2145, False)]

    def test_variantes_empilhadas_levam_o_nome_comum(self):
        frs = [
            F(491.1, 499.0, 8, "Arroz SEU ARROZ \n"), F(491.1, 490.0, 8, "Parboilizado - cada\n"),
            F(491.1, 480.0, 8, "Pacote 1kg \n"),
            F(491.1, 468.0, 8, "R$"), F(501.9, 452.0, 33, "3,19"),
            F(491.1, 442.0, 8, "Pacote 5kg  \n"), F(491.1, 430.0, 8, "R$"), F(501.9, 414.0, 33, "15,95"),
        ]  # fmt: skip
        assert nomes_e_precos(frs) == [
            ("Arroz SEU ARROZ Parboilizado Pacote 1kg", 319, False),
            ("Arroz SEU ARROZ Parboilizado Pacote 5kg", 1595, False),
        ]

    def test_variante_nao_herda_o_tamanho_do_nome_comum(self):
        # "Linguiça SEARA Mista Fininha 215g/Calabresa 400g": a Calabresa é a de 400 g, não a de 215 g
        frs = [
            F(680.5, 924.7, 8, "Linguiça SEARA \n"), F(680.5, 915.7, 8, "Mista Fininha \n"),
            F(680.5, 906.7, 8, "215g/Calabresa \n"),
            F(680.5, 897.7, 8, "400g - cada\n"), F(680.5, 887.7, 8, "Mista Fininha \n"), F(680.5, 878.7, 8, "Pacote 215g\n"),
            F(680.5, 866.7, 8, "R$"), F(691.4, 850.7, 33, "6,99"),
            F(680.5, 840.7, 8, "Calabresa Pacote \n"), F(680.5, 831.7, 8, "400g\n"),
            F(680.5, 819.7, 8, "R$"), F(691.4, 803.7, 33, "11,99"),
        ]  # fmt: skip
        itens = dict((n, p) for n, p, _ in nomes_e_precos(frs))
        calabresa = next(n for n in itens if itens[n] == 1199)
        assert calabresa == "Linguiça SEARA Mista Fininha Calabresa Calabresa Pacote 400g"
        assert "215" not in calabresa

    def test_produto_com_marca_empilhado_e_outro_produto(self):
        frs = [
            F(237.6, 558.6, 8, "Requeijão LAC \n"), F(237.6, 549.6, 8, "LÉLO 180g - cada\n"), F(237.6, 537.6, 8, "R$"),
            F(248.4, 521.6, 33, "5,99"),
            F(237.6, 511.6, 8, "Manteiga LAC \n"), F(237.6, 502.6, 8, "LÉLO 200g - cada\n"), F(237.6, 490.6, 8, "R$"),
            F(248.4, 474.6, 33, "8,99"),
        ]  # fmt: skip
        assert nomes_e_precos(frs) == [("Manteiga LAC LÉLO 200g", 899, False), ("Requeijão LAC LÉLO 180g", 599, False)]

    def test_encarte_grande_com_estoque_e_preco_em_pedacos(self):
        # Encarte do sacolão (página de 1080 x 1650): letra 24, "Quant. Disp." no meio e o preço "12" + ",90"
        frs = [
            F(244.9, 1102.8, 24, "Ovo Caipira ARES DO \n"), F(244.9, 1076.8, 24, "CAMPO Bandeja com \n"),
            F(244.9, 1050.8, 24, "20 Unidades - cada"), F(244.9, 1039.8, 8, "Quant. Disp. 1000 un"),
            F(244.9, 989.8, 34, "R$\n"), F(292.1, 949.8, 104, "12\n"), F(396.5, 989.8, 47, ",90"),
            F(303.7, 959.8, 24, "Alho a Granel - a \n"), F(303.7, 933.8, 24, "cada 100g"),
            F(303.7, 922.8, 8, "Quant. Disp. 1000 Kg"),
            F(303.7, 872.8, 34, "R$\n"), F(350.8, 832.8, 104, "1\n"), F(392.9, 872.8, 47, ",79"),
            F(303.7, 810.8, 24, "Preço KgR$17,90\n"),  # preço de referência: não é outro item
        ]  # fmt: skip
        assert nomes_e_precos(frs) == [
            ("Alho a Granel - a cada 100g", 179, True),
            ("Ovo Caipira ARES DO CAMPO Bandeja com 20 Unidades", 1290, False),
        ]

    def test_peso_no_fim_do_nome_e_preco_por_quilo(self):
        frs = [
            F(66.1, 604.8, 8, "Patinho Bovino DRI \n"), F(66.1, 595.8, 8, "Peça Resfriado Kg\n"), F(66.1, 582.8, 8, "R$"),
            F(76.9, 566.8, 33, "47,90"),
        ]  # fmt: skip
        assert nomes_e_precos(frs) == [("Patinho Bovino DRI Peça Resfriado Kg", 4790, True)]

    def test_selo_leve_pague_e_tabela_por_unidade_nao_viram_item(self):
        frs = [
            # tabela de preço por fralda, ao lado do cartão
            F(526.1, 196.5, 8.5, "QT"), F(545.4, 196.5, 8.5, "R$/Un\n"), F(546.3, 185.8, 5, "R$"), F(552.7, 185.8, 8, "1,52"),
            F(546.4, 175.4, 5, "R$"), F(552.9, 175.4, 8, "1,30"),
            # selo "leve 5 pague 4": a unidade sai por R$ 5,59
            F(252.4, 294.6, 9, " R$"), F(262.5, 280.6, 35, "5\n"), F(283.7, 293.6, 14, ",59"),
            F(191.6, 316.1, 6, "LEVE PAGUE \n"), F(260.0, 320.2, 4, "NESTA PROMOÇÃO \n"),
            F(254.2, 315.2, 5, "A UNIDADE SAI POR "),
        ]  # fmt: skip
        assert nomes_e_precos(frs) == []


class TestValidade:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Ofertas válidas de 02/11 a 05/11/2026 nas lojas de Araranguá, Blumenau", (date(2026, 11, 2), date(2026, 11, 5))),
            ("Ofertas válidas na rede Super A, de 04/11 e 05/11/2026, nas lojas", (date(2026, 11, 4), date(2026, 11, 5))),
            ("Ofertas válidas para a rede Super A em Santa Catarina nas lojas de Araranguá, Balneário Camboriú, Blumenau, "
             "Florianópolis, Jaraguá do Sul e São José, para dia 02/11 a 11/11/2026", (date(2026, 11, 2), date(2026, 11, 11))),
            ("Ofertas válidas de 29/12 a 03/01/2027", (date(2026, 12, 29), date(2027, 1, 3))),
            ("Ofertas válidas 04/11 e 07/11/2026", None),  # dois dias soltos: não é um período
            ("Ofertas válidas de 01/10 a 05/11/2026", None),  # mais de um mês: data mal lida
            ("HOJE TEM FEIRA MAIS BARATA!", None),
        ],
    )  # fmt: skip
    def test_texto(self, texto, esperado):
        achadas = encarte_pdf.validades_escritas(texto)
        assert achadas == ({esperado} if esperado else set())


# ---------- página de encartes ----------

HTML = """<div class="elementor-element elementor-element-2017100 e-con-full elementor-hidden-tablet e-flex">
<div class="elementor-element elementor-element-c7447ad elementor-align-justify elementor-hidden-desktop elementor-hidden-tablet
 elementor-hidden-mobile elementor-widget elementor-widget-button" data-id="c7447ad">
 <a class="elementor-button" href="https://statics.angeloni.com.br/encartes/Supera/supera_pascoa.pdf">
 <span class="elementor-button-text">Páscoa</span></a></div>
<div class="elementor-element elementor-element-0765a69 elementor-align-justify elementor-widget elementor-widget-button">
 <a class="elementor-button" href="https://statics.angeloni.com.br/encartes/Supera/supera_quarta_e_quinta_do_sacolao.pdf">
 <span class="elementor-button-text">Quarta e Quinta<br>do Sacolão</span></a></div>
<div class="elementor-element elementor-element-33fb805 elementor-align-justify elementor-widget elementor-widget-button">
 <a class="elementor-button" href="https://statics.angeloni.com.br/encartes/Supera/supera_semanal.pdf">
 <span class="elementor-button-text">Ofertas para Semana</span></a></div>
<div class="elementor-element elementor-element-33fb806 elementor-align-justify elementor-widget elementor-widget-button">
 <a class="elementor-button" href="https://statics.angeloni.com.br/encartes/Supera/supera_semanal.pdf">
 <span class="elementor-button-text">Semana</span></a></div>"""
SEMANAL = "https://statics.angeloni.com.br/encartes/Supera/supera_semanal.pdf"


class FakeSuperA:
    """Página do Super A, os PDFs e a busca dos sites, no formato do ClienteHttp."""

    def __init__(self, pdfs: dict[str, bytes], busca=None):
        self.pdfs, self.busca, self.baixados = pdfs, busca or {}, []

    def __call__(self, url, corpo=None, cabecalhos=None):
        self.baixados.append(url)
        return next((produtos for dominio, produtos in self.busca.items() if dominio in url), [])

    def binario(self, url):
        self.baixados.append(url)
        return HTML.encode() if url == supera.PAGINA else self.pdfs.get(url)


def test_so_os_encartes_visiveis_e_sem_repetir():
    achados = supera.encartes(FakeSuperA({}))
    assert [(e.url.rsplit("/", 1)[1], e.titulo, e.id) for e in achados] == [
        ("supera_quarta_e_quinta_do_sacolao.pdf", "Quarta e Quinta do Sacolão (supera_quarta_e_quinta_do_sacolao.pdf)", None),
        ("supera_semanal.pdf", "Ofertas para Semana (supera_semanal.pdf)", None),
    ]


# ---------- rodada contra o banco ----------


def do_site(ean, nome, marca, sku):
    return {
        "brand": marca,
        "items": [{"ean": ean, "nameComplete": nome, "itemId": sku, "measurementUnit": "un", "unitMultiplier": 1}],
    }


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        conn.execute("truncate cidade, rede, categoria, produto, ean, observacao_preco, fila_revisao, encarte_lido cascade")
        cidade, rede, giassi, kika = uuid4(), uuid4(), uuid4(), uuid4()
        conn.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (cidade,))
        conn.execute("insert into rede (id, nome) values (%s, 'Super A Atacadista'), (%s, 'Giassi')", (rede, giassi))
        conn.execute(
            "insert into loja (id, rede_id, cidade_id, nome) values (%s, %s, %s, 'Super A Garcia')", (uuid4(), rede, cidade)
        )
        conn.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g'), ('cafe', 'Café', 'g')")
        conn.execute(
            "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values "
            "(%s, 'graos', 'Arroz Parboilizado Tipo 1 Kika Pacote 5kg', 'Kika', 5000, 'g'), "
            "(%s, 'cafe', 'Café Torrado e Moído Pilão Vácuo 500g', 'Pilão', 500, 'g')",
            (kika, uuid4()),
        )
        conn.execute("insert into ean (codigo, produto_id) values ('07896006744115', %s)", (kika,))
        conn.execute("insert into ean (codigo, produto_id) select '07896089013405', id from produto where marca = 'Pilão'")
        yield conn


SEMANA = Encarte(date(2026, 11, 2), date(2026, 11, 5), [
    ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg", 1595, None, False, 1),  # no catálogo
    ItemDoEncarte("Café CABOCLO a Vácuo Pacote 500g", 2145, None, False, 1),  # achado no Giassi
    ItemDoEncarte("Patinho Bovino DRI Peça Resfriado Kg", 4790, None, True, 1),  # por quilo: fica de fora
    ItemDoEncarte("Mamão Papaya Unidade", 399, None, False, 2),  # sem tamanho: revisão
])  # fmt: skip


def test_rodar_publica_na_loja_de_blumenau_e_nao_rele_o_mesmo_pdf(banco):
    agora = datetime(2026, 11, 3, 12, tzinfo=UTC)
    pdfs = {
        SEMANAL: b"%PDF semana 1",
        "https://statics.angeloni.com.br/encartes/Supera/supera_quarta_e_quinta_do_sacolao.pdf": None,
    }
    http = FakeSuperA(pdfs, busca={"giassi.com.br": [
        do_site("7896089099997", "Café Torrado e Moído Tradicional Caboclo Vácuo 500g", "Caboclo", "21"),
    ]})  # fmt: skip
    lidos = []

    def ler(pdf):
        lidos.append(pdf)
        return SEMANA

    resumo = supera.rodar(banco, http, agora, ler=ler)

    assert lidos == [b"%PDF semana 1"]  # o sacolão não baixou: tenta amanhã
    precos = banco.execute(
        """select p.nome_humano, o.faixa, o.preco_centavos, o.valido_ate, o.evidencia_id from observacao_preco o
           join produto p on p.id = o.produto_id where o.fonte = 'encarte' order by 1"""
    ).fetchall()
    encarte_id = encarte_rede.id_do_conteudo(SEMANAL, b"%PDF semana 1")
    assert encarte_id.startswith("supera_semanal:")
    assert [(r["nome_humano"], r["faixa"], r["preco_centavos"]) for r in precos] == [
        ("Arroz Parboilizado Tipo 1 Kika Pacote 5kg", "varejo", 1595),
        ("Café Torrado e Moído Tradicional Caboclo Vácuo 500g", "varejo", 2145),
    ]
    assert precos[0]["valido_ate"] == datetime(2026, 11, 6, 2, 59, 59, tzinfo=UTC)  # fim do dia 05/11 em Brasília
    assert precos[0]["evidencia_id"] == f"super_a_atacadista:{encarte_id}:p1"

    [mamao] = banco.execute("select referencia_id, proposta_agente from fila_revisao where tipo = 'encarte'").fetchall()
    assert mamao["proposta_agente"]["rede"] == "Super A Atacadista"
    assert mamao["proposta_agente"]["valido_ate"] == "2026-11-05"
    assert mamao["proposta_agente"]["pdf"] == SEMANAL
    assert banco.execute("select encarte_id, valido_ate, itens, precos from encarte_lido").fetchone() == {
        "encarte_id": encarte_id, "valido_ate": date(2026, 11, 5), "itens": 4, "precos": 2,
    }  # fmt: skip
    assert resumo == {"produtos_novos": 1, "revisao": 1, "encartes": 1, "itens": 4, "precos": 2, "precos_valendo": 2}
    execucao = banco.execute("select status, eans_pedidos, precos_gravados, enviados_revisao from execucao_coleta").fetchone()
    assert execucao == {"status": "ok", "eans_pedidos": 4, "precos_gravados": 2, "enviados_revisao": 1}

    # No dia seguinte o PDF é o mesmo: baixa (o endereço é fixo), vê que já leu e não busca nada nos sites
    http.baixados.clear()
    assert supera.rodar(banco, http, agora + timedelta(days=1), ler=ler) == {"precos_valendo": 2}
    assert len(lidos) == 1
    assert not [u for u in http.baixados if "giassi" in u or "minhacooper" in u]

    # O Super A trocou o PDF no mesmo endereço: é encarte novo
    pdfs[SEMANAL] = b"%PDF semana 2"
    assert supera.rodar(banco, http, agora + timedelta(days=1), ler=ler)["encartes"] == 1
    assert banco.execute("select count(*) as n from encarte_lido").fetchone()["n"] == 2


@pytest.mark.parametrize(
    ("validade", "lido", "precos"),
    [
        ((date(2026, 10, 26), date(2026, 10, 29)), True, 0),  # vencido: registra sem publicar
        ((None, None), True, 0),  # sem validade escrita: não publica
        ((date(2026, 11, 6), date(2026, 11, 8)), False, 0),  # ainda não começou: lê quando começar
    ],
)
def test_validade_que_nao_inclui_hoje_nao_publica(banco, validade, lido, precos):
    enc = Encarte(*validade, [ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg", 1595, None, False, 1)])
    resumo = supera.rodar(banco, FakeSuperA({SEMANAL: b"%PDF"}), datetime(2026, 11, 3, 12, tzinfo=UTC), ler=lambda _pdf: enc)
    assert resumo.get("precos", 0) == precos
    assert banco.execute("select count(*) as n from observacao_preco").fetchone()["n"] == 0
    assert (banco.execute("select count(*) as n from encarte_lido").fetchone()["n"] == 1) is lido


def test_paginas_com_datas_diferentes_nao_publicam(banco):
    enc = Encarte(None, None, [ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg", 1595, None, False, 1)],
                  validades_divergentes=True)  # fmt: skip
    resumo = supera.rodar(banco, FakeSuperA({SEMANAL: b"%PDF"}), datetime(2026, 11, 3, 12, tzinfo=UTC), ler=lambda _pdf: enc)
    assert (resumo["precos"], resumo["validade_divergente"]) == (0, 1)
