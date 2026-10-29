"""Agentes de bastidor do SC Mercados.

Por enquanto são programas de regras, sem IA e sem custo, mas trabalham como um agente: investigam,
decidem com confiança e motivo escritos, agem sozinhos quando é seguro, deixam sugestão quando não é,
e cada rodada fica registrada para o painel mostrar se estão em dia. A peça que decide pode ser trocada
por um modelo de IA depois, sem mudar o resto.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta

from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class Agente:
    id: str
    nome: str
    faz: str
    agenda: str
    autonomia: str
    intervalo: timedelta  # sem rodar há mais que isso = atrasado
    tipo: str = "Programa de regras (sem IA)"


AGENTES = [
    Agente(
        "coletor",
        "Coletor de preços",
        "Busca o preço de cada produto do catálogo nos sites do Giassi, da Cooper, do Angeloni, do Sam's e da Rede Top, "
        "loja por loja.",
        "Todo dia às 5h (Rede Top às 6h) e quinta às 15h",
        "Roda e publica sozinho. Preço estranho ou embalagem diferente vai para o Revisor.",
        timedelta(hours=26),
    ),
    Agente(
        "leitor_encartes",
        "Leitor de encartes",
        "Lê os encartes do Fort Atacadista, casa cada item com o catálogo e cadastra produtos novos achados nos sites.",
        "Todo dia às 7h (encarte já lido é pulado)",
        "Roda e publica sozinho. Item que não casou vai para o Revisor.",
        timedelta(hours=26),
    ),
    Agente(
        "vigia",
        "Vigia de qualidade",
        "Confere se alguma coleta parou ou caiu e se o mesmo código de barras aparece com tamanhos diferentes entre redes.",
        "No fim de cada coleta",
        "Roda sozinho e só aponta problemas; quem decide é o Revisor.",
        timedelta(hours=26),
    ),
    Agente(
        "revisor",
        "Revisor",
        "Pega cada item da fila de revisão, junta as evidências (catálogo, sites, validade, histórico) e decide.",
        "Todo dia às 7h, depois do Leitor de encartes",
        "Resolve sozinho quando tem certeza; quando não tem, deixa uma sugestão para você aceitar com um clique.",
        timedelta(hours=26),
    ),
]
POR_ID = {a.id: a for a in AGENTES}


@contextmanager
def rodada(conn, agente: str):
    """Registra uma rodada do agente: aberta ao começar, ok ou falhou ao terminar. O resumo é um dict."""
    rodada_id = conn.execute("insert into agente_rodada (agente) values (%s) returning id", (agente,)).fetchone()
    rodada_id = rodada_id["id"] if isinstance(rodada_id, dict) else rodada_id[0]
    resumo: dict = {"_id": str(rodada_id)}
    try:
        yield resumo
    except Exception as erro:
        conn.execute(
            "update agente_rodada set terminada_em = now(), status = 'falhou', erro = %s, resumo = %s where id = %s",
            (repr(erro)[:2000], Jsonb({k: v for k, v in resumo.items() if k != "_id"}), rodada_id),
        )
        raise
    conn.execute(
        "update agente_rodada set terminada_em = now(), status = 'ok', resumo = %s where id = %s",
        (Jsonb({k: v for k, v in resumo.items() if k != "_id"}), rodada_id),
    )
