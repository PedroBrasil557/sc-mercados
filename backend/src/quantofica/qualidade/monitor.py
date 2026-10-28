"""Monitor de qualidade dos dados de preço.

Funções puras: recebem números já consultados e dizem se há anomalia. Quem consulta o banco e abre
o item na fila de revisão é `verificar` (no fim de cada coleta e também sozinho).
"""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from psycopg.types.json import Jsonb

from ..regras import tamanho

LIMITE_QUEDA_COBERTURA = 0.10
LIMITE_DESVIO_PRECO = 0.50
LIMITE_SEM_COLETA = timedelta(hours=26)  # coleta diária às 5h + 2h de folga
MINIMO_HISTORICO = 3  # menos que isso não dá mediana confiável


@dataclass(frozen=True)
class Anomalia:
    referencia: str
    motivo: str
    prioridade: int = 3


def queda_de_cobertura(rede: str, anterior: int, atual: int, limite: float = LIMITE_QUEDA_COBERTURA) -> Anomalia | None:
    """Coleta de hoje trouxe bem menos preços que a anterior (site mudou, bloqueio, loja fechou)."""
    if anterior <= 0 or atual >= anterior * (1 - limite):
        return None
    queda = round(100 * (anterior - atual) / anterior)
    return Anomalia(f"rede:{rede}", f"cobertura caiu {queda}% ({anterior} → {atual} preços)", prioridade=2)


def preco_fora_da_curva(preco_centavos: int, historico_centavos: list[int], limite: float = LIMITE_DESVIO_PRECO) -> bool:
    """Preço mais de 50% acima ou abaixo da mediana recente do mesmo produto."""
    if len(historico_centavos) < MINIMO_HISTORICO:
        return False
    mediana = statistics.median(historico_centavos)
    return abs(preco_centavos - mediana) > limite * mediana


def tamanho_divergente(ean: str, nomes_por_rede: dict[str, str]) -> Anomalia | None:
    """O mesmo EAN aparece com tamanhos diferentes em redes diferentes (cadastro errado de algum lado, R1)."""
    tamanhos = {rede: tamanho.extrair(nome) for rede, nome in nomes_por_rede.items()}
    conhecidos = {rede: t for rede, t in tamanhos.items() if t}
    if len(conhecidos) < 2:
        return None
    base_rede, base = next(iter(conhecidos.items()))
    for rede, t in conhecidos.items():
        if not t.mesmo_que(base):
            return Anomalia(
                f"ean:{ean}",
                f"tamanho diferente entre redes: {base_rede} {nomes_por_rede[base_rede]!r}, {rede} {nomes_por_rede[rede]!r}",
            )
    return None


def coletor_parado(
    rede: str, ultima_ok: datetime | None, agora: datetime, limite: timedelta = LIMITE_SEM_COLETA
) -> Anomalia | None:
    if ultima_ok is not None and agora - ultima_ok <= limite:
        return None
    quando = "nunca rodou com sucesso" if ultima_ok is None else f"última coleta boa em {ultima_ok:%d/%m %H:%M} UTC"
    return Anomalia(f"rede:{rede}", f"coletor parado: {quando}", prioridade=1)


def abrir_revisao(conn, tipo: str, anomalia: Anomalia, proposta=None) -> bool:
    """Abre um item na fila de revisão, a menos que já exista um aberto igual. Devolve se abriu."""
    ja_tem = conn.execute(
        "select 1 from fila_revisao where tipo = %s and referencia_id = %s and motivo = %s and status = 'aberta'",
        (tipo, anomalia.referencia, anomalia.motivo),
    ).fetchone()
    if ja_tem:
        return False
    conn.execute(
        "insert into fila_revisao (tipo, referencia_id, motivo, prioridade, proposta_agente) values (%s, %s, %s, %s, %s)",
        (tipo, anomalia.referencia, anomalia.motivo, anomalia.prioridade, Jsonb(proposta) if proposta is not None else None),
    )
    return True


def verificar(conn, agora: datetime) -> list[Anomalia]:
    """Roda as verificações que dependem do histórico e abre o que achar na fila de revisão."""
    achadas: list[Anomalia] = []
    redes = conn.execute("select id, nome from rede where tem_api").fetchall()
    for r in redes:
        execucoes = conn.execute(
            """select precos_gravados, terminada_em from execucao_coleta
               where rede_id = %s and status = 'ok' order by iniciada_em desc limit 2""",
            (r["id"],),
        ).fetchall()
        a = coletor_parado(r["nome"], execucoes[0]["terminada_em"] if execucoes else None, agora)
        if a:
            achadas.append(a)
        if len(execucoes) == 2:
            a = queda_de_cobertura(r["nome"], execucoes[1]["precos_gravados"], execucoes[0]["precos_gravados"])
            if a:
                achadas.append(a)

    nomes: dict[str, dict[str, str]] = {}
    for linha in conn.execute(
        """select e.codigo, r.nome as rede, pr.nome_no_site from ean e
           join produto_na_rede pr on pr.produto_id = e.produto_id join rede r on r.id = pr.rede_id
           where e.status = 'ok' and pr.nome_no_site is not null"""
    ).fetchall():
        nomes.setdefault(linha["codigo"], {})[linha["rede"]] = linha["nome_no_site"]
    for codigo, por_rede in nomes.items():
        a = tamanho_divergente(codigo, por_rede)
        if a:
            achadas.append(a)

    for a in achadas:
        abrir_revisao(conn, "anomalia", a)
    return achadas
