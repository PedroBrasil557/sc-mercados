"""Regras R5 e R6: qual preço mostrar, frescor e conflito entre fontes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class Fonte(StrEnum):
    CUPOM = "cupom"
    FEED_OFICIAL = "feed_oficial"
    ETIQUETA = "etiqueta"
    ENCARTE = "encarte"
    SITE = "site"


class Faixa(StrEnum):
    VAREJO = "varejo"
    ATACADO = "atacado"
    CLUBE = "clube"
    APP = "app"


# Peso em caso de empate de data: menor número vence (R6).
PRIORIDADE = {Fonte.CUPOM: 1, Fonte.FEED_OFICIAL: 1, Fonte.ETIQUETA: 2, Fonte.ENCARTE: 3, Fonte.SITE: 4}
VALIDADE = {
    Fonte.CUPOM: timedelta(days=7),
    Fonte.FEED_OFICIAL: timedelta(days=7),
    Fonte.ETIQUETA: timedelta(days=7),
    Fonte.SITE: timedelta(hours=24),
}
LIMITE_ANTIGO = timedelta(days=30)


@dataclass(frozen=True)
class Observacao:
    preco_centavos: int
    fonte: Fonte
    observado_em: datetime
    faixa: Faixa = Faixa.VAREJO
    preco_de_centavos: int | None = None
    valido_ate: datetime | None = None  # encarte traz a validade impressa
    confirmada: bool = True  # etiqueta informada só vale depois de confirmada (R11)


class Estado(StrEnum):
    VALIDO = "valido"
    PODE_TER_MUDADO = "pode_ter_mudado"  # vencido há menos de 30 dias: aparece em cinza


@dataclass(frozen=True)
class PrecoExibido:
    observacao: Observacao
    estado: Estado


def _vence_em(o: Observacao) -> datetime:
    if o.fonte is Fonte.ENCARTE:
        return o.valido_ate or o.observado_em
    return o.observado_em + VALIDADE[o.fonte]


def preco_atual(observacoes: list[Observacao], agora: datetime, faixa: Faixa = Faixa.VAREJO) -> PrecoExibido | None:
    """Preço a exibir para um produto numa loja.

    Por padrão a faixa é o varejo (R5: o lançamento mostra o varejo; o preço de sócio vem depois).
    Vence o mais recente; em empate de data, vale a prioridade da fonte (R6). Vencido há menos de
    30 dias aparece como "pode ter mudado"; depois disso sai do cálculo.
    """
    candidatas = [o for o in observacoes if o.faixa is faixa and (o.fonte is not Fonte.ETIQUETA or o.confirmada)]
    if not candidatas:
        return None
    ordenadas = sorted(candidatas, key=lambda o: (-o.observado_em.timestamp(), PRIORIDADE[o.fonte]))
    validas = [o for o in ordenadas if _vence_em(o) >= agora]
    if validas:
        return PrecoExibido(validas[0], Estado.VALIDO)
    recente = ordenadas[0]
    if agora - _vence_em(recente) <= LIMITE_ANTIGO:
        return PrecoExibido(recente, Estado.PODE_TER_MUDADO)
    return None
