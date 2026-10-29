"""Encartes do Komprão: montagem dos cartões a partir das palavras do OCR (com posição), validade, página do
Issuu e a rodada completa contra o Postgres, com HTTP e OCR falsos. O OCR de verdade (Tesseract) só roda no
último teste, e só se o Tesseract estiver instalado."""

import gzip
import json
import shutil
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from quantofica.agentes import revisor
from quantofica.coleta import encarte_ocr, fort, komprao
from quantofica.coleta.encarte_ocr import PaginaLida, Palavra
from quantofica.coleta.encarte_pdf import ItemDoEncarte


def linha(x, y, texto, conf=95, alt=18):
    """Uma linha de nome como o Tesseract devolve: uma Palavra por palavra, 10 px por letra."""
    palavras, cursor = [], x
    for w in texto.split():
        palavras.append(Palavra(cursor, y, 10 * len(w), alt, conf, w))
        cursor += 10 * (len(w) + 1)
    return palavras


def preco(x, y, texto, conf=92, alt=56):
    return Palavra(x, y, 30 * len(texto), alt, conf, texto)


def montar(palavras, precos):
    return encarte_ocr.itens_da_pagina(palavras, precos, 1)


class TestCartoes:
    def test_nome_em_duas_linhas_e_o_preco_ao_lado(self):
        itens, duvidosos, ambiguos = montar(
            linha(40, 1300, "Arroz Parboilizado KIKA") + linha(40, 1322, "Pacote 5kg un."), [preco(300, 1290, "8,79")]
        )
        assert itens == [ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg un.", 879, None, False, 1)]
        assert (duvidosos, ambiguos) == ([], 0)

    def test_cada_preco_vai_para_o_seu_cartao(self):
        palavras = (
            linha(40, 1300, "Arroz Parboilizado KIKA") + linha(40, 1322, "Pacote 5kg un.")
            + linha(520, 1300, "Feijão Preto RESERVA") + linha(520, 1322, "1kg un.")
            + linha(40, 1700, "Café em Pó Torrado") + linha(40, 1722, "CABOCLO 500g un.")
        )  # fmt: skip
        precos = [preco(300, 1290, "8,79"), preco(780, 1290, "2,79"), preco(260, 1690, "25,90")]
        itens, _, _ = montar(palavras, precos)
        assert {(i.nome, i.preco_centavos) for i in itens} == {
            ("Arroz Parboilizado KIKA Pacote 5kg un.", 879),
            ("Feijão Preto RESERVA 1kg un.", 279),
            ("Café em Pó Torrado CABOCLO 500g un.", 2590),
        }

    def test_texto_da_embalagem_acima_nao_rouba_o_preco(self):
        # "CALDÃO CALDÃO" (escrito no pacote, na foto) está mais perto em linha reta, mas acima do preço
        palavras = (
            linha(250, 1215, "CALDÃO CALDÃO") + linha(40, 1300, "Farinha de Mandioca") + linha(40, 1322, "CALDÃO fina 1kg un.")
        )
        [item], _, _ = montar(palavras, [preco(320, 1290, "3,99")])
        assert item.nome == "Farinha de Mandioca CALDÃO fina 1kg un."

    def test_preco_do_clube_e_o_condicional(self):
        palavras = (
            linha(40, 1300, "Farinha de Trigo ANNIELA") + linha(40, 1322, "5kg un.")
            + linha(330, 1240, "clube", alt=20) + linha(320, 1345, "EXCLUSIVO NO KOMPRÃO", alt=14)
        )  # fmt: skip
        [item], _, _ = montar(palavras, [preco(60, 1350, "10,69"), preco(330, 1280, "9,99")])
        assert (item.preco_centavos, item.condicional_centavos) == (1069, 999)

    def test_so_o_preco_do_clube_lido_fica_de_fora(self):
        palavras = linha(40, 1300, "Farinha de Trigo ANNIELA") + linha(40, 1322, "5kg un.") + linha(330, 1240, "clube", alt=20)
        assert montar(palavras, [preco(330, 1280, "9,99")]) == ([], [], 1)

    def test_chamadas_da_oferta_e_limite_nao_entram_no_nome(self):
        # O OCR junta "NESTA OFERTA..." (do selo do clube, logo à direita) à última linha do nome
        palavras = (
            linha(37, 1235, "Cerveja SKOL Pilsen") + linha(37, 1257, "Lata 350ml un.")
            + linha(220, 1257, "NESTA OFERTA A UN. SAI POR") + linha(60, 1410, "Limite por cliente 192 un.")
        )  # fmt: skip
        [item], _, _ = montar(palavras, [preco(40, 1350, "3,39")])
        assert item.nome == "Cerveja SKOL Pilsen Lata 350ml un."

    def test_um_trocado_por_letra_antes_da_unidade(self):
        for lido in ("Tkg", "1Tkg", "Ikg"):
            [item], _, _ = montar(
                linha(520, 1300, "Feijão Preto RESERVA") + linha(520, 1322, f"{lido} un."), [preco(780, 1290, "2,79")]
            )
            assert item.nome == "Feijão Preto RESERVA 1kg un."

    def test_primeira_palavra_perdida_pelo_ocr_nao_quebra_o_nome(self):
        # "inteiro" saiu ilegível (confiança 38): a linha começa em "a vácuo kg.", um pouco à direita
        palavras = (
            linha(1430, 1336, "Contra filé bovino ATC") + linha(1432, 1357, "ineo", conf=38) + linha(1512, 1357, "a vácuo kg.")
        )
        [item], _, _ = montar(palavras, [preco(1693, 1312, "36,89")])
        assert item.nome == "Contra filé bovino ATC a vácuo kg."
        assert item.por_kg

    def test_numero_pequeno_da_tabela_nao_e_preco(self):
        palavras = linha(320, 2700, "Fralda MILI") + linha(320, 2722, "Baby Giga un.")
        assert montar(palavras, [preco(480, 2700, "0,62", alt=13)]) == ([], [], 0)

    def test_leitura_incerta_vai_para_duvidosos(self):
        nome = linha(40, 1300, "Arroz Parboilizado KIKA") + linha(40, 1322, "Pacote 5kg un.")
        itens, duvidosos, _ = montar(nome, [preco(300, 1290, "8,79", conf=40)])
        assert itens == [] and [d.preco_centavos for d in duvidosos] == [879]
        itens, duvidosos, _ = montar(linha(40, 1300, "Arroz Parboilizado KIKA 5kg", conf=55), [preco(300, 1290, "8,79")])
        assert itens == [] and len(duvidosos) == 1

    def test_nome_ilegivel_nem_vai_para_revisao(self):
        assert montar(linha(40, 1300, "qa un."), [preco(120, 1290, "11,79")]) == ([], [], 1)


class TestPrecoNaImagem:
    def test_virgula_confere_com_os_digitos(self):
        # "16,99" com dígitos de 40 px ("1" de 24) e a vírgula no meio de 20 px: o OCR que lê "699" é pego
        assert encarte_ocr.virgula_confere("1699", 0, 164, 74)
        assert not encarte_ocr.virgula_confere("699", 0, 164, 74)
        assert encarte_ocr.virgula_confere("195", 0, 124, 34)  # o "1" é estreito
        assert not encarte_ocr.virgula_confere("1195", 0, 124, 34)

    def test_grupo_de_digitos_sem_o_r_cifrao(self):
        caixas = [
            (0, 40, 20, 56),  # "R$" baixo, à esquerda
            (30, 20, 52, 58), (58, 20, 80, 58),  # "1" "6"
            (84, 50, 90, 64),  # vírgula, descendo abaixo da linha
            (94, 20, 116, 58), (120, 20, 142, 58),  # "9" "9"
        ]  # fmt: skip
        assert encarte_ocr.grupos_de_digitos(caixas, 19, 60) == [(30, 20, 142, 58, 87.0)]

    def test_sem_virgula_nao_e_preco(self):
        assert encarte_ocr.grupos_de_digitos([(30, 20, 52, 58), (58, 20, 80, 58)], 19, 60) == []

    def test_componentes_conectados(self):
        from PIL import Image, ImageDraw

        img = Image.new("L", (40, 20), 0)
        d = ImageDraw.Draw(img)
        d.rectangle((2, 2, 5, 15), fill=255)
        d.rectangle((10, 4, 20, 8), fill=255)
        assert sorted(encarte_ocr._componentes(img)) == [(2, 2, 6, 16), (10, 4, 21, 9)]


class TestValidade:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Preços válidos de 01 a 02/11/2025 ou enquanto durarem os estoques", (date(2025, 11, 1), date(2025, 11, 2))),
            ("Preços válidos de 30 a 02/11/2025", (date(2025, 10, 30), date(2025, 11, 2))),
            ("Preços válidos de 01/11 a 02/11/2025 ou enquanto", (date(2025, 11, 1), date(2025, 11, 2))),
            ("Ofertas válidas até 09/11/2025", (None, date(2025, 11, 9))),
            ("Preços válidos de 01/01 a 02/11/2025", None),  # mais de um mês: data mal lida
            ("Encarte de fim de semana", None),
        ],
    )
    def test_texto_do_rodape(self, texto, esperado):
        assert encarte_ocr.validade(linha(30, 2950, texto)) == esperado

    def test_data_lida_com_pouca_confianca_nao_vale(self):
        palavras = linha(30, 2950, "Preços válidos de") + linha(230, 2950, "01 a 02/11/2025", conf=40)
        assert encarte_ocr.validade(palavras) is None

    def test_ano_mal_lido_e_pego_pela_data_de_publicacao(self):
        palavras = linha(30, 2950, "Preços válidos de 01 a 02/11/2026")  # publicado em 31/10/2025
        assert encarte_ocr.validade(palavras, date(2025, 10, 31)) is None
        assert encarte_ocr.validade(linha(30, 2950, "Preços válidos de 01 a 02/11/2025"), date(2025, 10, 31))


# ---------- página do Komprão e Issuu ----------

HTML = """<html><body><h2>Encarte de fim de semana</h2>
<iframe title="Encarte de fim de semana - Blumenau" allowfullscreen="true"
 src="https://e.issuu.com/embed.html?d=kompr_o_fim_de_semana_07&amp;u=superkoch"></iframe>
<iframe src="https://www.youtube.com/embed/xyz"></iframe></body></html>"""


def leitor(revisao="261030120000", paginas=2):
    return {"document": {
        "revisionId": revisao, "publicationId": "76198a65",
        "pages": [{"imageUri": f"image.isu.pub/{revisao}-76198a65/jpg/page_{n}.jpg"} for n in range(1, paginas + 1)],
    }}  # fmt: skip


class TestPaginaDoKomprao:
    def test_encartes_embutidos(self):
        http = FakeKomprao()
        assert komprao.encartes(http) == [
            {"documento": "kompr_o_fim_de_semana_07", "usuario": "superkoch", "titulo": "Encarte de fim de semana - Blumenau"}
        ]

    def test_documento_do_issuu_compactado(self):
        doc = komprao.documento(FakeKomprao(), komprao.encartes(FakeKomprao())[0])
        assert doc == {
            "id": "261030120000-76198a65",
            "paginas": [f"https://image.isu.pub/261030120000-76198a65/jpg/page_{n}.jpg" for n in (1, 2)],
            "publicado_em": date(2026, 10, 30),
        }


class FakeKomprao:
    """Página do Komprão, leitor e imagens do Issuu e busca dos sites, no formato do ClienteHttp."""

    def __init__(self, documento=None, busca=None):
        self.documento, self.busca, self.baixados = documento or leitor(), busca or {}, []

    def __call__(self, url, corpo=None, cabecalhos=None):
        self.baixados.append(url)
        for dominio, produtos in self.busca.items():
            if dominio in url:
                return produtos
        return []

    def binario(self, url):
        self.baixados.append(url)
        if url == komprao.PAGINA:
            return HTML.encode()
        if url == "https://reader3.isu.pub/superkoch/kompr_o_fim_de_semana_07/reader3_4.json":
            return gzip.compress(json.dumps(self.documento).encode())
        if url.startswith("https://image.isu.pub/"):
            return b"\xff\xd8jpeg"
        return None


def do_site(ean, nome, marca, sku):
    return {
        "brand": marca,
        "items": [{"ean": ean, "nameComplete": nome, "itemId": sku, "measurementUnit": "un", "unitMultiplier": 1}],
    }


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        conn.execute("truncate cidade, rede, categoria, produto, ean, observacao_preco, fila_revisao, encarte_lido cascade")
        cidade, kompr, giassi, kika = uuid4(), uuid4(), uuid4(), uuid4()
        conn.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (cidade,))
        conn.execute("insert into rede (id, nome) values (%s, 'Komprão'), (%s, 'Giassi')", (kompr, giassi))
        for _ in range(3):
            conn.execute(
                "insert into loja (id, rede_id, cidade_id, nome) values (%s, %s, %s, 'Komprão')", (uuid4(), kompr, cidade)
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


def pagina(itens=(), duvidosos=(), validade=None, ambiguos=0):
    return PaginaLida(list(itens), list(duvidosos), ambiguos, validade)


def test_rodar_grava_os_precos_nas_tres_lojas_de_blumenau(banco):
    agora = datetime(2026, 10, 31, 12, tzinfo=UTC)
    paginas = [
        pagina([
            ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg un.", 879, None, False, 1),  # no catálogo
            ItemDoEncarte("Café em Pó Torrado Moído CABOCLO 500g un.", 2590, None, False, 1),  # achado no Giassi
            ItemDoEncarte("Contra filé bovino ATC inteiro a vácuo kg.", 3689, None, True, 1),  # granel: fica de fora
        ], ambiguos=2),
        pagina(
            [ItemDoEncarte("Smart TV PHILCO 58 LED P58KGA un.", 229990, None, False, 2)],  # não é de mercado: revisão
            [ItemDoEncarte("Feijão Preto RESERVA 1kg un.", 279, None, False, 2)],  # OCR incerto: revisão, sem publicar
            validade=(date(2026, 10, 31), date(2026, 11, 1)),  # o rodapé só foi lido na página 2
        ),
    ]  # fmt: skip
    http = FakeKomprao(busca={"giassi.com.br": [
        do_site("7896089099997", "Café Torrado e Moído Tradicional Caboclo Vácuo 500g", "Caboclo", "21"),
    ]})  # fmt: skip
    vistos = []

    def ler(imagem, n, publicado_em):
        vistos.append((n, publicado_em))
        return paginas[n - 1]

    resumo = komprao.rodar(banco, http, agora, ler_pagina=ler)

    assert vistos == [(1, date(2026, 10, 30)), (2, date(2026, 10, 30))]
    precos = banco.execute(
        """select p.nome_humano, o.faixa, o.preco_centavos, o.valido_ate, o.evidencia_id, count(*) as lojas
           from observacao_preco o join produto p on p.id = o.produto_id
           where o.fonte = 'encarte' group by 1, 2, 3, 4, 5 order by 1, 2"""
    ).fetchall()
    assert [(r["nome_humano"], r["preco_centavos"], r["lojas"]) for r in precos] == [
        ("Arroz Parboilizado Tipo 1 Kika Pacote 5kg", 879, 3),
        ("Café Torrado e Moído Tradicional Caboclo Vácuo 500g", 2590, 3),
    ]
    assert precos[0]["valido_ate"] == datetime(2026, 11, 2, 2, 59, 59, tzinfo=UTC)  # fim do dia 01/11 em Brasília
    assert precos[0]["evidencia_id"] == "komprao:261030120000-76198a65:p1"

    fila = {
        r["proposta_agente"]["nome"]: r
        for r in banco.execute("select motivo, proposta_agente from fila_revisao where tipo = 'encarte'").fetchall()
    }
    assert set(fila) == {"Smart TV PHILCO 58 LED P58KGA un.", "Feijão Preto RESERVA 1kg un."}
    feijao = fila["Feijão Preto RESERVA 1kg un."]["proposta_agente"]
    assert feijao["conferir_preco"] and feijao["rede"] == "Komprão"
    assert feijao["imagem"] == "https://image.isu.pub/261030120000-76198a65/jpg/page_2.jpg"
    assert "conferir_preco" not in fila["Smart TV PHILCO 58 LED P58KGA un."]["proposta_agente"]

    lido = banco.execute("select encarte_id, titulo, valido_ate, itens, precos from encarte_lido").fetchone()
    assert lido == {
        "encarte_id": "261030120000-76198a65",
        "titulo": "Encarte de fim de semana - Blumenau (kompr_o_fim_de_semana_07)",
        "valido_ate": date(2026, 11, 1),
        "itens": 5,
        "precos": 6,
    }
    assert resumo == {"ambiguos": 2, "produtos_novos": 1, "revisao": 1, "duvidosos": 1, "encartes": 1, "itens": 5, "precos": 6}

    # No dia seguinte o mesmo encarte é pulado: nada de imagem baixada, OCR ou busca nos sites
    http.baixados.clear()
    assert komprao.rodar(banco, http, agora + timedelta(days=1), ler_pagina=ler) == {}
    assert http.baixados == [komprao.PAGINA, "https://reader3.isu.pub/superkoch/kompr_o_fim_de_semana_07/reader3_4.json"]

    # O Revisor não liga sozinho o item de leitura incerta, mesmo que o nome case: fica para uma pessoa
    d = revisor.decidir_encarte(feijao, agora.date(), date(2026, 11, 1), [])
    assert d.acao == "humano"

    # Pelo painel, ligar o item publica o preço nas lojas do Komprão (não nas do Fort)
    item = banco.execute("select id from fila_revisao where proposta_agente->>'nome' = 'Feijão Preto RESERVA 1kg un.'").fetchone()
    arroz = banco.execute("select produto_id from ean where codigo = '07896006744115'").fetchone()["produto_id"]
    gravados, _ = fort.ligar_item(banco, str(item["id"]), feijao, [str(arroz)], "painel", agora)
    assert gravados == 3


def test_encarte_vencido_e_registrado_sem_preco_e_sem_baixar_o_resto(banco):
    # O caso real de 29/10/2026: a página de Blumenau ainda mostrava o encarte de 01 a 02/11/2025.
    http = FakeKomprao(documento=leitor("251031230419", paginas=4))
    lidas = []

    def ler(imagem, n, publicado_em):
        lidas.append(n)
        return pagina([ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg un.", 879, None, False, 1)],
                      validade=(date(2025, 11, 1), date(2025, 11, 2)))  # fmt: skip

    resumo = komprao.rodar(banco, http, datetime(2026, 10, 29, 12, tzinfo=UTC), ler_pagina=ler)
    assert lidas == [1]
    assert resumo["precos"] == 0
    assert banco.execute("select count(*) as n from observacao_preco").fetchone()["n"] == 0
    assert banco.execute("select valido_ate, precos from encarte_lido").fetchone() == {
        "valido_ate": date(2025, 11, 2),
        "precos": 0,
    }


@pytest.mark.parametrize(
    "validades",
    [
        [None, None],  # rodapé ilegível
        [(None, date(2026, 11, 1)), (None, date(2026, 11, 8))],  # páginas discordam: alguma foi mal lida
    ],
)
def test_sem_validade_certa_nao_publica(banco, validades):
    def ler(imagem, n, publicado_em):
        return pagina([ItemDoEncarte("Arroz Parboilizado KIKA Pacote 5kg un.", 879, None, False, n)], validade=validades[n - 1])

    resumo = komprao.rodar(banco, FakeKomprao(), datetime(2026, 10, 31, 12, tzinfo=UTC), ler_pagina=ler)
    assert (resumo["encartes"], resumo["precos"]) == (1, 0)
    assert banco.execute("select valido_ate, itens from encarte_lido").fetchone() == {"valido_ate": None, "itens": 2}


def test_pagina_que_nao_baixou_tenta_de_novo_amanha(banco):
    class SemImagem(FakeKomprao):
        def binario(self, url):
            return None if url.endswith("page_2.jpg") else super().binario(url)

    def ler(imagem, n, publicado_em):
        return pagina(validade=(None, date(2026, 11, 1)))

    assert komprao.rodar(banco, SemImagem(), datetime(2026, 10, 31, 12, tzinfo=UTC), ler_pagina=ler) == {}
    assert banco.execute("select count(*) as n from encarte_lido").fetchone()["n"] == 0


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract não instalado (no CI ele só vai no job de encartes)")
def test_ocr_de_verdade_le_um_cartao_desenhado():
    """Um cartão desenhado com o Pillow: nome preto, "R$" pequeno e preço vermelho sobre amarelo."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1965, 600), (255, 230, 0))
    d = ImageDraw.Draw(img)
    d.text((40, 300), "Arroz Parboilizado KIKA", fill=(20, 20, 20), font=ImageFont.load_default(22))
    d.text((40, 328), "Pacote 5kg un.", fill=(20, 20, 20), font=ImageFont.load_default(22))
    d.text((330, 318), "R$", fill=(220, 20, 30), font=ImageFont.load_default(24))
    d.text((370, 270), "8,79", fill=(220, 20, 30), font=ImageFont.load_default(80))
    bruto = BytesIO()
    img.save(bruto, "PNG")
    lida = encarte_ocr.ler_pagina(bruto.getvalue(), 1)
    assert [(i.nome, i.preco_centavos) for i in lida.itens + lida.duvidosos] == [("Arroz Parboilizado KIKA Pacote 5kg un.", 879)]
