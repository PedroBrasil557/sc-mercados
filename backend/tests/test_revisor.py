"""Revisor: decide a fila de revisão por regras, age sozinho só com certeza e registra cada decisão."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from quantofica.agentes import revisor
from quantofica.coleta.casamento import Candidato
from quantofica.regras.tamanho import Tamanho

HOJE = date(2026, 10, 28)
CATALOGO = [
    Candidato("ketchup397", "Ketchup Heinz Squeeze 397g", "Heinz", Tamanho(397, "g")),
    Candidato("nescau350", "Achocolatado Pó Nescau 350g", "Nescau", Tamanho(350, "g")),
    Candidato("urbano5", "Arroz Parboilizado Tipo 1 Urbano Pacote 5kg", "Urbano", Tamanho(5000, "g")),
    Candidato("lacta145", "Chocolate ao Leite Lacta Pacote 145g Tamanho Família", "Lacta", Tamanho(145, "g")),
]


def item(nome, preco=999):
    return {"nome": nome, "preco_centavos": preco}


class TestEncarte:
    def test_encarte_vencido_e_descartado(self):
        d = revisor.decidir_encarte(item("Arroz Urbano 5kg"), HOJE, date(2026, 10, 26), CATALOGO)
        assert (d.acao, d.confianca >= revisor.CERTEZA) == ("descartar", True)
        assert "26/10" in d.motivo

    @pytest.mark.parametrize(
        ("nome", "trecho"),
        [
            ("Chaleira Elétrica Chic Lar Inox 1,8 Litros", "Não é item de mercado"),
            ("Bombom Nestlé Especialidades", "não diz o tamanho"),
            ("Óleo de Soja Soya Fry Max Balde 14,5kg", "atacado"),
        ],
    )
    def test_o_que_nao_da_para_comparar_e_descartado_com_motivo(self, nome, trecho):
        d = revisor.decidir_encarte(item(nome), HOJE, None, CATALOGO)
        assert d.acao == "descartar" and d.confianca >= revisor.CERTEZA
        assert trecho in d.motivo

    def test_casa_com_o_catalogo_que_cresceu(self):
        d = revisor.decidir_encarte(item("Arroz Urbano Parboilizado 5kg"), HOJE, None, CATALOGO)
        assert (d.acao, d.produtos) == ("ligar", ["urbano5"])

    def test_busca_nos_sites_com_outras_palavras(self):
        buscas = []

        def procurar(nome, termos):
            buscas.append(termos)
            return ["novo"] if termos == "ketchup heinz 567g" else []

        d = revisor.decidir_encarte(item("Ketchup Heinz Tradicional 567g"), HOJE, None, CATALOGO, procurar)
        assert (d.acao, d.produtos, buscas) == ("ligar", ["novo"], ["ketchup heinz 567g"])

    def test_so_outro_tamanho_no_catalogo_fica_para_a_pessoa(self):
        d = revisor.decidir_encarte(item("Achocolatado em Pó Nescau LV+ PG- 990g"), HOJE, None, CATALOGO)
        assert d.acao == "humano" and d.confianca < revisor.CERTEZA
        assert "350 g" in d.motivo and "990 g" in d.motivo

    def test_mesma_marca_tipo_e_tamanho_vira_sugestao(self):
        d = revisor.decidir_encarte(item("Chocolate Lacta Diamante Negro 145g"), HOJE, None, CATALOGO)
        assert (d.acao, d.produtos) == ("sugerir", ["lacta145"])
        assert d.confianca < revisor.CERTEZA  # sugere, não age


class TestAlertas:
    def test_tamanho_diferente_por_pacote_e_resolvido(self):
        motivo = (
            "tamanho diferente entre redes: Cooper 'Atum Gomes da Costa Lata 120g', "
            "Sam's Club 'Atum Gomes da Costa Pack com 3 Unidades 120g Cada'"
        )
        assert revisor.decidir_tamanho_divergente(motivo).acao == "resolver"

    def test_tamanho_que_aparece_nos_dois_nomes_e_resolvido(self):
        motivo = (
            "tamanho diferente entre redes: Cooper 'Bebida Láctea Nescau Protein Caixa 250ml', "
            "Angeloni 'Bebida Láctea NESCAU Protein 15G de Proteínas 250ml'"
        )
        d = revisor.decidir_tamanho_divergente(motivo)
        assert d.acao == "resolver" and "250 ml" in d.motivo

    def test_tamanho_realmente_diferente_fica_para_a_pessoa(self):
        motivo = "tamanho diferente entre redes: Cooper 'Sardinha Pescador Lata 75g', Giassi 'Sardinha Pescador Lata 83g'"
        assert revisor.decidir_tamanho_divergente(motivo).acao == "humano"

    def test_pacote_de_verdade_e_descartado(self):
        d = revisor.decidir_embalagem("embalagem múltipla no site: 'Cerveja Heineken Pack com 12 Unidades de 473ml Cada'")
        assert d.acao == "descartar" and "R1" in d.motivo


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True, row_factory=dict_row) as conn:
        yield conn


def test_rodada_age_so_com_certeza_registra_tudo_e_nao_repete(banco):
    agora = datetime(2026, 10, 28, 12, tzinfo=UTC)
    fila = "insert into fila_revisao (id, tipo, referencia_id, motivo, proposta_agente) values (%s, %s, %s, %s, %s)"
    pacote, chaleira, sardinha = uuid4(), uuid4(), uuid4()
    banco.execute(
        fila, (pacote, "ean", "sams:1", "embalagem múltipla no site: 'Cerveja Pack com 12 Unidades de 350ml Cada'", None)
    )
    banco.execute(fila, (chaleira, "encarte", "fort:1:x", "item do encarte sem produto no catálogo",
                         Jsonb({"nome": "Chaleira Elétrica Inox 1,8 Litros", "preco_centavos": 4990})))  # fmt: skip
    banco.execute(
        fila, (sardinha, "anomalia", "ean:2", "tamanho diferente entre redes: A 'Sardinha Lata 75g', B 'Sardinha Lata 83g'", None)
    )

    resumo = revisor.rodar(banco, None, agora, buscar_nos_sites=False)
    assert resumo == {"analisados": 3, "resolvidos_sozinho": 2, "sugestoes": 0, "para_voce": 1, "sem_mudanca": 0}
    status = {
        r["id"]: (r["status"], r["revisado_por"])
        for r in banco.execute("select id, status, revisado_por from fila_revisao").fetchall()
    }
    assert status[pacote] == ("descartada", "revisor") and status[chaleira] == ("descartada", "revisor")
    assert status[sardinha] == ("aberta", None)
    decisoes = banco.execute(
        "select entrada_ref, decisao, modelo, custo_tokens from execucao_agente order by criada_em"
    ).fetchall()
    assert {(d["decisao"], d["modelo"], d["custo_tokens"]) for d in decisoes} == {
        ("descartado", "regras (sem IA)", 0), ("fila", "regras (sem IA)", 0)
    }  # fmt: skip
    rodada = banco.execute("select status, resumo from agente_rodada where agente = 'revisor'").fetchone()
    assert rodada["status"] == "ok" and rodada["resumo"]["resolvidos_sozinho"] == 2

    # No dia seguinte, a mesma conclusão sobre a sardinha não vira um registro novo
    assert revisor.rodar(banco, None, agora + timedelta(days=1), buscar_nos_sites=False)["sem_mudanca"] == 1
    assert banco.execute("select count(*) as n from execucao_agente").fetchone()["n"] == 3
