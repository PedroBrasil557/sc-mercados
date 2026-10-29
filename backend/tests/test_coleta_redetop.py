"""Coleta da Rede Top (loja virtual VipCommerce): respostas no formato visto em 29/10/2026, sem internet."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from quantofica.coleta import redetop


class TestGtin:
    @pytest.mark.parametrize(
        ("codigo", "esperado"),
        [
            ("7896022087104", "07896022087104"),  # EAN-13
            ("98765430", "00000098765430"),  # EAN-8
            ("17891008376958", "17891008376958"),  # GTIN-14 de caixa
            ("93", None),  # código interno da cenoura: passa no dígito, mas não é GTIN
            ("2000123000008", None),  # prefixo 2: peso variável, uso restrito à loja
            ("212345678909", None),  # UPC com prefixo 2, idem
            ("0401234567893", None),  # faixa 04x: numeração interna
            ("021234567893", "00021234567893"),  # UPC comum que começa com 0
            ("7896022087105", None),  # dígito verificador errado
            (None, None),
        ],
    )
    def test_so_codigo_de_barras_de_verdade(self, codigo, esperado):
        assert redetop.gtin_valido(codigo) == esperado


def produto(pid, ean, nome, preco, oferta=None, vendidos=0, unidade="UN", disponivel=True):
    return {
        "produto_id": pid,
        "codigo_barras": ean,
        "descricao": nome,
        "preco": preco,
        "disponivel": disponivel,
        "em_oferta": oferta is not None,
        "oferta": oferta,
        "unidade_sigla": unidade,
        "possui_unidade_diferente": unidade == "KG",
        "habilitar_seletor_unidade_peso": False,
        "quantidade_vendida": vendidos,
        "marca": None,
    }


def oferta(preco_oferta, preco_antigo, nome="Preço TOP", tipo=1, minima=1, pagar=1, leve=1, tag="preco-top"):
    return {
        "tipo_oferta_id": tipo,
        "nome": nome,
        "tag": tag,
        "classe_oferta": "preco-vip",
        "preco_antigo": preco_antigo,
        "preco_oferta": preco_oferta,
        "quantidade_minima": minima,
        "quantidade_pagar": pagar,
        "quantidade_oferta": leve,
        "faixas_precos": None,
    }


class TestPrecos:
    def test_sem_oferta_vale_o_preco_normal(self):
        assert redetop.precos(produto(1, "", "", "3.49")) == (349, None)

    def test_preco_top_para_todos_vale_com_o_preco_de(self):
        assert redetop.precos(produto(1, "", "", "4.99", oferta("3.99", "4.99"))) == (399, 499)

    def test_leve_e_pague_nao_e_preco_de_uma_unidade(self):
        leve3 = oferta("1.86", "2.79", nome="Leve e pague", tipo=3, pagar=2, leve=3, tag="leve-e-pague")
        assert redetop.precos(produto(1, "", "", "2.79", leve3)) == (279, None)

    def test_oferta_do_clube_fica_fora_do_varejo(self):
        clube = oferta("5.49", "6.99", nome="Clube Mais TOP", tag="oferta-exclusiva")
        assert redetop.precos(produto(1, "", "", "6.99", clube)) == (699, None)

    def test_vendido_por_quilo_fica_de_fora(self):
        item, motivo = redetop.ler_item(produto(1, "7898186220045", "Picanha Bovina Resfriada", "89.90", unidade="KG"))
        assert (item, motivo) == (None, "granel")


class TestLojaDoCd:
    LOJAS = [
        {"id": "escola", "endereco": "Rua Benjamin Constant 939 - Escola Agrícola"},
        {"id": "pz", "endereco": "Rua Doutor Pedro Zimmermann 7155 - Itoupava Central"},
        {"id": "gz", "endereco": "Rua Gustavo Zimmermann 1365 - Itoupava Central"},
    ]

    def test_casa_pela_rua_e_numero_sem_acento(self):
        cd = {"endereco": {"logradouro": "Rua Benjamin Constant", "numero": "939", "cidade": "Blumenau"}}
        assert redetop.loja_do_cd(cd, self.LOJAS) == "escola"

    def test_mesmo_bairro_outra_rua_nao_casa(self):
        cd = {"endereco": {"logradouro": "Rua Doutor Pedro Zimmermann", "numero": "7155"}}
        assert redetop.loja_do_cd(cd, self.LOJAS) == "pz"
        assert redetop.loja_do_cd({"endereco": {"logradouro": "Rua Hermann Tribess", "numero": "1026"}}, self.LOJAS) is None


def cd(id_, nome, logradouro, numero, cidade):
    return {"id": id_, "nome": nome, "nome_site": nome, "ativo": True,
            "endereco": {"logradouro": logradouro, "numero": numero, "bairro": "", "cidade": cidade}}  # fmt: skip


CDS = [
    cd(1, "Rede Top - Escola Agrícola", "Rua Benjamin Constant", "939", "Blumenau"),
    cd(2, "Rede Top - Barra Velha", "Rua Waldemar Francisco", "434", "Barra Velha"),  # outra cidade: nem é visitada
    cd(3, "Rede Top - Itoupava Central", "Rua Doutor Pedro Zimmermann", "7155", "Blumenau"),
    cd(9, "Rede Top - Fortaleza", "Rua Francisco Vahldieck", "1881", "Blumenau"),  # sem cadastro: revisão
]
MACARRAO, SNICKERS, MINUETO, AGUIA, GAROTO = "7896022087104", "7896423481853", "7896004010007", "7896005223512", "7891008123975"
PRODUTOS = {  # (cd, departamento) -> páginas
    (1, 6): [
        [
            produto(101, SNICKERS, "Chocolate Snickers 42g Dark", "4.99", oferta("3.99", "4.99"), vendidos=50),
            produto(
                102,
                MINUETO,
                "Biscoito Wafer Minueto 81g Limao",
                "2.79",
                oferta("1.86", "2.79", nome="Leve e pague", tipo=3, pagar=2, leve=3),
                vendidos=30,
            ),
            produto(
                103,
                AGUIA,
                "Biscoito Aguia 360g Salt Plus Integral",
                "6.99",
                oferta("5.49", "6.99", nome="Clube Mais TOP", tag="oferta-exclusiva"),
                vendidos=10,
            ),
        ],
        [
            produto(104, GAROTO, "Chocolate Garoto 80g Ao Leite Pack 3 Un", "21.90"),  # EAN da unidade num pack
            produto(105, "7891008124170", "Barra Chocolate Garoto 80g Castanha", "8.49", disponivel=False),
        ],
    ],
    (1, 14): [
        [
            produto(201, MACARRAO, "Macarrao Isabela 400g Semola Furadinho", "3.49"),
            produto(202, "7891132019403", "Tempero Sazon 60g Legumes", "6.99", vendidos=99),  # tipo que o catálogo não tem
            produto(203, "93", "Cenoura 250g ( Aprox. 1 Uni. )", "1.74", unidade="KG"),
        ]
    ],
    (3, 6): [[produto(101, SNICKERS, "Chocolate Snickers 42g Dark", "4.99", oferta("3.99", "4.99"), vendidos=50)]],
    (3, 14): [[produto(201, MACARRAO, "Macarrao Isabela 400g Semola Furadinho", "3.79")]],
}
ARVORE = {"success": True, "data": [{"classificacao_mercadologica_id": 6, "descricao": "Biscoitos"},
                                    {"classificacao_mercadologica_id": 14, "descricao": "Mercearia"}]}  # fmt: skip


class FakeVip:
    """API da VipCommerce com o mesmo formato de chamada do ClienteHttp."""

    def __init__(self):
        self.chamadas: list[str] = []

    def __call__(self, url, corpo=None, cabecalhos=None):
        self.chamadas.append(url)
        org = f"{redetop.API}/org/229"
        if url == f"{redetop.API}/organizacoes/filiais/dominio/redetoponline.com.br":
            return {"success": True, "data": {"id": 263, "organizacao": {"id": 229, "enderecoServidor": "redetoponline.com.br"}}}
        if url == f"{org}/auth/loja/login":
            assert corpo == {"domain": "redetoponline.com.br", "username": "loja", "key": redetop.CHAVE_VISITANTE}
            assert cabecalhos == {"DomainKey": "redetoponline.com.br", "OrganizationId": "229"}
            return {"success": True, "data": "token-de-visitante"}
        assert cabecalhos["Authorization"] == "Bearer token-de-visitante"
        if url == f"{org}/filial/1/loja/centros_distribuicoes/retiradas":
            return {"success": True, "data": CDS}
        if url.endswith("/departamentos/arvore"):
            return ARVORE
        cd_id = int(url.split("/centro_distribuicao/")[1].split("/")[0])
        dep = int(url.split("/departamentos/")[1].split("/")[0])
        pagina = int(url.rsplit("page=", 1)[1])
        paginas = PRODUTOS.get((cd_id, dep), [[]])
        return {"success": True, "paginator": {"page": pagina, "total_pages": len(paginas)}, "data": paginas[pagina - 1]}


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        yield conn


def test_coleta_grava_o_preco_de_cada_loja_de_blumenau(banco, banco_url, monkeypatch):
    cidade, rede, escola, itoupava, tribess, macarrao, garoto = (uuid4() for _ in range(7))
    banco.execute("insert into cidade (id, nome, uf) values (%s, 'Blumenau', 'SC')", (cidade,))
    banco.execute("insert into rede (id, nome) values (%s, 'Rede Top')", (rede,))
    for loja, endereco in [
        (escola, "Rua Benjamin Constant 939 - Escola Agrícola"),
        (itoupava, "Rua Doutor Pedro Zimmermann 7155 - Itoupava Central"),
        (tribess, "Rua Hermann Tribess 1026 - Tribess"),  # não está na loja virtual
    ]:
        banco.execute(
            "insert into loja (id, rede_id, cidade_id, nome, endereco) values (%s, %s, %s, 'Rede Top', %s)",
            (loja, rede, cidade, endereco),
        )
    banco.execute("insert into categoria (id, nome, unidade_medida) values ('graos', 'Grãos', 'g'), ('doces', 'Doces', 'g')")
    banco.execute(
        "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values "
        "(%s, 'graos', 'Macarrão Sêmola Furadinho Isabela Pacote 400g', 'Isabela', 400, 'g'), "
        "(%s, 'doces', 'Chocolate ao Leite Garoto 80g', 'Garoto', 80, 'g'), "
        "(%s, 'doces', 'Biscoito Recheado Bono Morango 90g', 'Bono', 90, 'g')",
        (macarrao, garoto, uuid4()),
    )
    banco.execute(
        "insert into ean (codigo, produto_id) values ('07896022087104', %s), ('07891008123975', %s)", (macarrao, garoto)
    )
    banco.execute("insert into ean (codigo, produto_id) select '07891000376959', id from produto where marca = 'Bono'")
    monkeypatch.setattr(redetop, "LIMITE_NOVOS_POR_RODADA", 2)
    monkeypatch.setenv("DATABASE_URL", banco_url)
    http = FakeVip()

    assert redetop.main(http) == 0

    precos = banco.execute(
        """select coalesce(p.nome_humano, '') as nome, l.endereco, o.preco_centavos, o.preco_de_centavos, o.faixa, o.fonte
           from observacao_preco o join produto p on p.id = o.produto_id join loja l on l.id = o.loja_id order by 1, 2"""
    ).fetchall()
    assert [(r["nome"], r["endereco"].split(" - ")[1], r["preco_centavos"], r["preco_de_centavos"]) for r in precos] == [
        ("Biscoito Wafer Minueto 81g Limao", "Escola Agrícola", 279, None),  # leve e pague: preço de uma unidade
        ("Chocolate Snickers 42g Dark", "Escola Agrícola", 399, 499),  # Preço TOP
        ("Chocolate Snickers 42g Dark", "Itoupava Central", 399, 499),
        ("Macarrão Sêmola Furadinho Isabela Pacote 400g", "Escola Agrícola", 349, None),  # cada loja com o seu preço
        ("Macarrão Sêmola Furadinho Isabela Pacote 400g", "Itoupava Central", 379, None),
    ]
    assert {(r["faixa"], r["fonte"]) for r in precos} == {("varejo", "site")}

    # EANs novos viram produto com o uuid5 do catálogo e a categoria do tipo; no máximo 2 por rodada (os mais vendidos)
    novos = banco.execute(
        """select e.codigo, p.id, p.categoria_id, p.tamanho, p.unidade from ean e join produto p on p.id = e.produto_id
           where e.codigo in ('07896423481853', '07896004010007', '07896005223512', '07891132019403') order by 1"""
    ).fetchall()
    assert [(r["codigo"], r["categoria_id"], float(r["tamanho"]), r["unidade"]) for r in novos] == [
        ("07896004010007", "doces", 81.0, "g"),
        ("07896423481853", "doces", 42.0, "g"),
    ]
    assert str(novos[1]["id"]) == str(redetop.uuid.uuid5(redetop.ESPACO, "07896423481853"))
    assert {r["sku"] for r in banco.execute("select sku from produto_na_rede where rede_id = %s", (rede,)).fetchall()} == {
        "101",
        "102",
        "201",
    }

    revisao = banco.execute("select tipo, referencia_id from fila_revisao order by 1").fetchall()
    assert [(r["tipo"], r["referencia_id"]) for r in revisao] == [
        ("anomalia", "loja:redetop:cd9"),
        ("ean", "redetop:07891008123975"),
    ]
    execucao = banco.execute("select status, precos_gravados, enviados_revisao from execucao_coleta").fetchone()
    assert (execucao["status"], execucao["precos_gravados"], execucao["enviados_revisao"]) == ("ok", 5, 2)
    rodada = banco.execute("select status, resumo from agente_rodada where agente = 'coletor'").fetchone()
    assert rodada["status"] == "ok"
    assert rodada["resumo"] == {"Rede Top": {"lojas": 2, "precos": 5, "revisao": 2, "produtos_novos": 2}}

    # Só as lojas de Blumenau são visitadas; a página 2 é pedida e a 3 não
    assert not [u for u in http.chamadas if "/centro_distribuicao/2/" in u or "/centro_distribuicao/9/" in u]
    assert any(u.endswith("/departamentos/6/produtos?page=2") for u in http.chamadas)
    assert not any(u.endswith("page=3") for u in http.chamadas)

    # Na rodada seguinte entra o EAN que ficou para depois, com o preço normal (a oferta do clube não é varejo)
    resumo = redetop.rodar(banco, http, datetime.now(UTC) + timedelta(days=1))
    assert resumo["produtos_novos"] == 1 and resumo["precos"] == 6
    aguia = banco.execute(
        """select o.preco_centavos, o.preco_de_centavos from observacao_preco o join ean e on e.produto_id = o.produto_id
           where e.codigo = '07896005223512'"""
    ).fetchone()
    assert (aguia["preco_centavos"], aguia["preco_de_centavos"]) == (699, None)
    assert banco.execute("select count(*) as n from fila_revisao").fetchone()["n"] == 2  # sem revisão repetida


def test_loja_virtual_fora_do_ar_registra_a_falha_sem_gravar_nada(banco):
    antes = banco.execute("select count(*) as n from observacao_preco").fetchone()["n"]
    with pytest.raises(RuntimeError, match="não respondeu"):
        redetop.rodar(banco, lambda url, corpo=None, cabecalhos=None: None, datetime.now(UTC))
    falhas = banco.execute("select erro from execucao_coleta where status = 'falhou'").fetchall()
    assert len(falhas) == 1 and "não respondeu" in falhas[0]["erro"]
    assert banco.execute("select count(*) as n from observacao_preco").fetchone()["n"] == antes
