"""Gravação de preços em lote, guardando no histórico só o que mudou.

Preço igual ao atual: só confirma (preco_atual.observado_em = agora, o "conferido hoje" do app).
Preço novo ou diferente: uma linha em observacao_preco; o gatilho do banco atualiza o preco_atual.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Preco:
    produto_id: str
    loja_id: str
    preco_centavos: int
    faixa: str = "varejo"
    fonte: str = "site"
    preco_de_centavos: int | None = None
    valido_ate: datetime | None = None
    evidencia: str | None = None


def registrar(conn, precos: list[Preco], agora: datetime) -> dict:
    """Grava os preços vistos agora. Devolve quantos mudaram (histórico) e quantos só foram confirmados."""
    if not precos:
        return {"mudaram": 0, "confirmados": 0}
    lojas = list({p.loja_id for p in precos})
    atuais = {
        (str(r["loja_id"]), str(r["produto_id"]), r["faixa"], r["fonte"]): (
            r["preco_centavos"],
            r["preco_de_centavos"],
            r["valido_ate"],
        )
        for r in conn.execute(
            """select loja_id, produto_id, faixa, fonte, preco_centavos, preco_de_centavos, valido_ate
               from preco_atual where loja_id = any(%s)""",
            (lojas,),
        ).fetchall()
    }
    novos, iguais = [], []
    vistos = set()
    for p in precos:
        chave = (str(p.loja_id), str(p.produto_id), p.faixa, p.fonte)
        if chave in vistos:
            continue  # o mesmo produto duas vezes na mesma loja e coleta: vale o primeiro
        vistos.add(chave)
        if atuais.get(chave) == (p.preco_centavos, p.preco_de_centavos, p.valido_ate):
            iguais.append(chave)
        else:
            novos.append(p)
    with conn.transaction():
        if novos:
            with conn.cursor() as cur:
                cur.executemany(
                    """insert into observacao_preco
                         (produto_id, loja_id, preco_centavos, preco_de_centavos, faixa, fonte, observado_em, valido_ate,
                          evidencia_id)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        (
                            p.produto_id,
                            p.loja_id,
                            p.preco_centavos,
                            p.preco_de_centavos,
                            p.faixa,
                            p.fonte,
                            agora,
                            p.valido_ate,
                            p.evidencia,
                        )
                        for p in novos
                    ],
                )
        if iguais:
            conn.execute(
                """update preco_atual a set observado_em = %s
                   from unnest(%s::uuid[], %s::uuid[], %s::text[], %s::text[]) as v(loja_id, produto_id, faixa, fonte)
                   where a.loja_id = v.loja_id and a.produto_id = v.produto_id and a.faixa = v.faixa and a.fonte = v.fonte
                     and a.observado_em < %s""",
                (agora, [c[0] for c in iguais], [c[1] for c in iguais], [c[2] for c in iguais], [c[3] for c in iguais], agora),
            )
    return {"mudaram": len(novos), "confirmados": len(iguais)}
