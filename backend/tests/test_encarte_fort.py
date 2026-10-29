"""Encartes do Fort: leitura do PDF pela posição do texto, casamento com o catálogo e gravação dos preços."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from quantofica.coleta import casamento, encarte_pdf, fort
from quantofica.coleta.casamento import Candidato
from quantofica.coleta.encarte_pdf import Encarte, Fragmento, ItemDoEncarte
from quantofica.regras.tamanho import Tamanho

F = Fragmento


def preco(x, y, reais, centavos, unidade="un"):
    """Um preço como o PDF do Fort escreve: "R", "$", inteiro, vírgula, centavos e a unidade, em pedaços."""
    return [F(x, y, 5, "R"), F(x + 3, y, 5, "$"), F(x + 6, y - 12, 25, reais), F(x + 19, y - 11, 15, ","),
            F(x + 20, y - 6, 16, centavos), F(x + 32, y - 11, 5, unidade), F(x + 38, y - 11, 5, ".")]  # fmt: skip


class TestLeituraDaPagina:
    def test_dois_precos_o_maior_e_o_normal_e_o_menor_o_condicional(self):
        # Cartão do feijão (coordenadas reais do encarte de 26/10): o preço normal fica acima do topo do nome.
        frs = [
            F(222, 681, 8, "Feijão Preto"),
            F(222, 674, 8, "Colonial TP1 1kg"),
            *preco(301, 704, "4", "98"),
            *preco(300, 672, "4", "59"),
        ]
        itens, ambiguos = encarte_pdf.itens_da_pagina(frs, 1)
        assert itens == [ItemDoEncarte("Feijão Preto Colonial TP1 1kg", 498, 459, False, 1)]
        assert ambiguos == 0

    def test_cada_preco_vai_para_o_nome_do_seu_cartao(self):
        frs = [
            F(326, 207, 8, "Achocolatado"), F(326, 200, 8, "em Pó Nescau"), F(326, 192, 8, "LV+ PG- 990g"),
            *preco(379, 207, "17", "90"),
            F(460, 225, 7, "Leite Condensado"), F(460, 218, 7, "Campos do Jordão"), F(460, 211, 7, "TP 395g"),
            *preco(457, 201, "4", "59"), *preco(539, 209, "4", "29"),
        ]  # fmt: skip
        itens, _ = encarte_pdf.itens_da_pagina(frs, 2)
        assert {(i.nome, i.preco_centavos, i.condicional_centavos) for i in itens} == {
            ("Achocolatado em Pó Nescau LV+ PG- 990g", 1790, None),
            ("Leite Condensado Campos do Jordão TP 395g", 459, 429),
        }

    def test_preco_por_quilo_e_marcado(self):
        frs = [F(100, 300, 8, "Galinha Inteira Do"), F(100, 292, 8, "Sítio Congelada kg"), *preco(160, 300, "5", "98", "kg")]
        [item], _ = encarte_pdf.itens_da_pagina(frs, 1)
        assert item.por_kg

    def test_validade_escrita_no_encarte(self):
        assert encarte_pdf.validade("BLUMENAU / SC Validade de 26/10/2026 até 29/10/2026, ou enquanto") == (
            date(2026, 10, 26),
            date(2026, 10, 29),
        )


class TestValidadeDoTitulo:
    @pytest.mark.parametrize(
        ("titulo", "esperado"),
        [
            ("SC_Fort_Semanal 4ed_26 a 29_OUT_26_Blumenau", (date(2026, 10, 26), date(2026, 10, 29))),
            ("SC_Fort_Food_26 a 01_OUT_NOV_26_Regional", (date(2026, 10, 26), date(2026, 11, 1))),
            ("SC_Fort_Virada_29 a 02_DEZ_JAN_27", (date(2026, 12, 29), date(2027, 1, 2))),
            ("SC_Fort_Revista de Natal_ATE_13_DEZ_26_Regional", (None, date(2026, 12, 13))),
            ("SC_Fort_Sem data", None),
        ],
    )
    def test_titulos(self, titulo, esperado):
        assert fort.validade_do_titulo(titulo, date(2026, 10, 28)) == esperado


def cand(chave, nome, marca, q, u="g"):
    return Candidato(chave, nome, marca, Tamanho(q, u))


class TestCasamento:
    ARROZ = [
        cand("urbano5", "Arroz Parboilizado Tipo 1 Urbano Seleção Especial Pacote 5kg", "Urbano", 5000),
        cand("kiarroz5", "Arroz Parboilizado Tipo 1 Kiarroz Pacote 5kg", "Kiarroz", 5000),
        cand("urbano1", "Arroz Parboilizado Tipo 1 Integral Urbano Pacote 1kg", "Urbano", 1000),
    ]

    def test_marca_e_tamanho_exatos(self):
        assert [c.chave for c in casamento.casar("Arroz Urbano Parboilizado 5kg", self.ARROZ)] == ["urbano5"]

    def test_pacote_com_varios_nao_e_o_avulso(self):
        avulso = [cand("colgate", "Creme Dental Menta Original Colgate Tripla Ação Caixa 90g", "Colgate", 90)]
        assert casamento.casar("Creme Dental Colgate Tripla Ação 90g c/ 4 un.", avulso) == []

    def test_sabores_leva_o_preco_para_todos_da_marca_e_tamanho(self):
        lacta = [
            cand("branco", "Chocolate Branco Lacta Laka Pacote 145g Tamanho Família", "Lacta", 145),
            cand("leite", "Chocolate ao Leite Lacta Pacote 145g Tamanho Família", "Lacta", 145),
            cand("outro", "Chocolate ao Leite Lacta Pacote 90g", "Lacta", 90),
            cand("nestle", "Chocolate ao Leite Nestlé Classic 145g", "Nestlé", 145),
        ]
        assert {c.chave for c in casamento.casar("Chocolate Lacta 145g Sabores", lacta)} == {"branco", "leite"}

    def test_linha_especial_so_quando_o_encarte_diz(self):
        divine = [
            cand("cremoso", "Chocolate em Barra Mais Cremoso ao Leite Divine Pacote 70g", "Divine", 70),
            cand("zero", "Chocolate em Barra Zero 37% Cacau Divine 70g", "Divine", 70),
            cand("gluten", "Chocolate em Barra sem Glúten Branco 30% Cacau Divine 70g", "Divine", 70),
        ]
        assert [c.chave for c in casamento.casar("Chocolate em Barra Divine 70g Sabores", divine)] == ["cremoso"]
        assert [c.chave for c in casamento.casar("Chocolate em Barra Divine Zero 70g Sabores", divine)] == ["zero"]

    def test_dois_empatados_sem_o_encarte_dizer_que_vale_para_varios_nao_casa(self):
        dois = [
            cand("a", "Biscoito Recheado Chocolate Zezé 300g", "Zezé", 300),
            cand("b", "Biscoito Recheado Morango Zezé 300g", "Zezé", 300),
        ]
        assert casamento.casar("Biscoito Recheado Zezé 300g", dois) == []

    def test_sem_marca_no_nome_do_encarte_nao_casa(self):
        assert casamento.casar("Arroz Parboilizado 5kg", self.ARROZ) == []


class FakeFort:
    """API do Fort e busca dos sites, com o mesmo formato de chamada do ClienteHttp."""

    def __init__(self, busca: dict[str, list]):
        self.busca, self.chamadas = busca, []

    def __call__(self, url, corpo=None, cabecalhos=None):
        self.chamadas.append(url)
        if url == fort.API:
            assert cabecalhos == fort.CABECALHOS
            if "flyers(" in corpo["query"]:
                return {
                    "data": {"publicViewer": {"flyers": [{"id": "3750", "title": "SC_Fort_Semanal 4ed_26 a 29_OUT_26_Blumenau"}]}}
                }
            return {"data": {"publicViewer": {"flyer": {"pdf": {"url": "https://s3.exemplo/encarte.pdf"}}}}}
        for dominio, produtos in self.busca.items():
            if dominio in url:
                return produtos
        return []

    def binario(self, url):
        return b"%PDF"


def do_site(ean, nome, marca, sku):
    return {
        "brand": marca,
        "items": [{"ean": ean, "nameComplete": nome, "itemId": sku, "measurementUnit": "un", "unitMultiplier": 1}],
    }


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        yield conn


def test_rodar_grava_os_precos_do_encarte_nas_lojas_de_blumenau(banco):
    agora = datetime(2026, 10, 27, 12, tzinfo=UTC)
    cidade, fort_id, giassi, l1, l2, arroz = (uuid4() for _ in range(6))
    banco.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (cidade,))
    banco.execute("insert into rede (id, nome) values (%s, 'Fort Atacadista'), (%s, 'Giassi')", (fort_id, giassi))
    for loja in (l1, l2):
        banco.execute("insert into loja (id, rede_id, cidade_id, nome) values (%s, %s, %s, 'Fort')", (loja, fort_id, cidade))
    banco.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g'), ('cafe', 'Café', 'g')")
    banco.execute(
        "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values "
        "(%s, 'graos', 'Arroz Parboilizado Tipo 1 Urbano Pacote 5kg', 'Urbano', 5000, 'g'), "
        "(%s, 'cafe', 'Café Torrado e Moído Pilão Vácuo 500g', 'Pilão', 500, 'g')",
        (arroz, uuid4()),
    )
    banco.execute("insert into ean (codigo, produto_id) values ('07896038306039', %s)", (arroz,))
    banco.execute(
        "insert into ean (codigo, produto_id) select '07896089013405', id from produto where marca = 'Pilão'",
    )

    encarte = Encarte(date(2026, 10, 26), date(2026, 10, 29), [
        ItemDoEncarte("Arroz Urbano Parboilizado 5kg", 1990, 1890, False, 1),  # já no catálogo
        ItemDoEncarte("Café Odebrecht Tradicional/ Extraforte Vácuo 500g", 1398, None, False, 1),  # achado no Giassi
        ItemDoEncarte("Chaleira Elétrica Chic Lar Inox 1,8 Litros", 4990, None, False, 1),  # não é de mercado
        ItemDoEncarte("Galinha Inteira Do Sítio Congelada kg", 598, None, True, 1),  # granel: fica de fora
    ])  # fmt: skip
    http = FakeFort({
        "giassi.com.br": [
            do_site("7896005800027", "Café Torrado e Moído Tradicional Odebrecht Vácuo 500g", "Odebrecht", "11"),
            do_site("7896005800034", "Café Torrado e Moído Extraforte Odebrecht Vácuo 500g", "Odebrecht", "12"),
            do_site("7896089029475", "Café Torrado e Moído a Vácuo Café do Ponto Pacote 500g", "Ponto", "13"),
        ]
    })  # fmt: skip

    resumo = fort.rodar(banco, http, agora, ler=lambda _pdf: encarte)

    precos = banco.execute(
        """select p.nome_humano, o.faixa, o.preco_centavos, o.valido_ate, count(*) as lojas
           from observacao_preco o join produto p on p.id = o.produto_id
           where o.fonte = 'encarte' group by 1, 2, 3, 4 order by 1, 2"""
    ).fetchall()
    assert [(r["nome_humano"], r["faixa"], r["preco_centavos"], r["lojas"]) for r in precos] == [
        ("Arroz Parboilizado Tipo 1 Urbano Pacote 5kg", "clube", 1890, 2),
        ("Arroz Parboilizado Tipo 1 Urbano Pacote 5kg", "varejo", 1990, 2),
        ("Café Torrado e Moído Extraforte Odebrecht Vácuo 500g", "varejo", 1398, 2),
        ("Café Torrado e Moído Tradicional Odebrecht Vácuo 500g", "varejo", 1398, 2),
    ]
    # Vale até o fim do último dia do encarte, no horário de Brasília
    assert precos[0]["valido_ate"] == datetime(2026, 10, 30, 2, 59, 59, tzinfo=UTC)
    # O café novo entrou no catálogo com o EAN, a categoria do tipo "café" e o SKU do Giassi (coleta diária)
    novo = banco.execute(
        """select p.categoria_id, pr.sku from ean e join produto p on p.id = e.produto_id
           join produto_na_rede pr on pr.produto_id = p.id where e.codigo = '07896005800027'"""
    ).fetchone()
    assert (novo["categoria_id"], novo["sku"]) == ("cafe", "11")
    revisao = banco.execute("select proposta_agente from fila_revisao where tipo = 'encarte'").fetchall()
    assert [r["proposta_agente"]["nome"] for r in revisao] == ["Chaleira Elétrica Chic Lar Inox 1,8 Litros"]
    assert resumo == {"produtos_novos": 2, "revisao": 1, "encartes": 1, "itens": 4, "precos": 8}

    # No dia seguinte o mesmo encarte é pulado: nada de preço repetido nem busca nos sites
    http.chamadas.clear()
    assert fort.rodar(banco, http, agora + timedelta(days=1), ler=lambda _pdf: encarte) == {}
    assert not [u for u in http.chamadas if u != fort.API]
