"""Painel de controle interno: fila de revisão, lojas a confirmar e saúde da coleta.

Só para quem tem o token do painel. O servidor guarda apenas o SHA-256 dele (PAINEL_TOKEN_SHA256); sem
essa variável o painel não existe (404). Tentativas com token errado são limitadas por IP.
"""

import hashlib
import hmac
import os
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..agentes import AGENTES
from ..coleta import fort
from .banco import Conexao
from .limite import LimiteDeTaxa
from .produtos import _CONDICAO

limite_painel = LimiteDeTaxa(maximo=10, janela_s=600)


def administrador(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    esperado = os.environ.get("PAINEL_TOKEN_SHA256", "")
    if not esperado:
        raise HTTPException(404)
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), esperado.lower()):
        limite_painel(request)  # só as tentativas erradas contam
        raise HTTPException(401, "token do painel inválido")


router = APIRouter(prefix="/v1/painel", tags=["painel"], dependencies=[Depends(administrador)])

TIPOS = ("encarte", "ean", "anomalia", "reporte", "cupom", "categoria")


@router.get("/resumo")
def resumo(conn: Conexao):
    return {
        "revisao": {
            r["tipo"]: r["n"]
            for r in conn.execute("select tipo, count(*) as n from fila_revisao where status = 'aberta' group by tipo").fetchall()
        },
        "coletas": conn.execute(
            """select distinct on (r.nome) r.nome as rede, e.iniciada_em, e.terminada_em, e.status,
                      e.precos_gravados, e.enviados_revisao, e.erro
               from execucao_coleta e join rede r on r.id = e.rede_id order by r.nome, e.iniciada_em desc"""
        ).fetchall(),
        "encartes": conn.execute(
            """select r.nome as rede, l.titulo, l.valido_ate, l.itens, l.precos, l.lido_em
               from encarte_lido l join rede r on r.id = l.rede_id order by l.lido_em desc limit 10"""
        ).fetchall(),
        "cobertura": conn.execute(
            """select r.nome as rede, count(distinct o.produto_id) as produtos
               from observacao_preco o join loja l on l.id = o.loja_id join rede r on r.id = l.rede_id
               where o.observado_em > now() - interval '2 days' group by r.nome order by produtos desc"""
        ).fetchall(),
        "produtos": conn.execute("select count(*) as n from produto").fetchone()["n"],
        "lojas_a_confirmar": conn.execute(
            "select count(*) as n from loja where origem = 'openstreetmap' and confirmada_em is null"
        ).fetchone()["n"],
        "casas": conn.execute("select count(*) as n from casa").fetchone()["n"],
        "membros": conn.execute("select count(*) as n from membro").fetchone()["n"],
    }


@router.get("/revisao")
def revisao(
    conn: Conexao,
    tipo: Annotated[Literal[TIPOS] | None, Query()] = None,  # type: ignore[valid-type]
    limite: Annotated[int, Query(ge=1, le=200)] = 100,
):
    itens = conn.execute(
        """select f.id, f.tipo, f.referencia_id, f.motivo, f.proposta_agente as proposta, f.prioridade, f.criada_em,
                  s.saida as sugestao, s.confianca as sugestao_confianca, s.criada_em as sugestao_em
           from fila_revisao f
           left join lateral (select e.saida, e.confianca, e.criada_em from execucao_agente e
                              where e.entrada_ref = f.id::text and e.agente = 'revisor'
                              order by e.criada_em desc limit 1) s on true
           where f.status = 'aberta' and (%s::text is null or f.tipo = %s)
           order by (s.saida->>'acao' = 'sugerir') desc nulls last, f.prioridade, f.criada_em limit %s""",
        (tipo, tipo, limite),
    ).fetchall()
    # Nome dos produtos que o Revisor sugeriu, para mostrar na tela
    ids = {pid for i in itens if i["sugestao"] for pid in i["sugestao"].get("produtos") or []}
    nomes = {}
    if ids:
        nomes = {
            str(r["id"]): r["nome_humano"]
            for r in conn.execute("select id, nome_humano from produto where id::text = any(%s)", (list(ids),)).fetchall()
        }
    for i in itens:
        if i["sugestao"]:
            i["sugestao"]["produtos"] = [{"id": pid, "nome": nomes.get(pid, pid)} for pid in i["sugestao"].get("produtos") or []]
    return itens


@router.get("/agentes")
def agentes(conn: Conexao):
    """Cada agente: o que faz, se é IA ou programa, se age sozinho, a última rodada e se está em dia."""
    agora = datetime.now(UTC)
    saida = []
    for a in AGENTES:
        rodadas = conn.execute(
            """select iniciada_em, terminada_em, status, resumo, erro from agente_rodada
               where agente = %s order by iniciada_em desc limit 7""",
            (a.id,),
        ).fetchall()
        ultima = rodadas[0] if rodadas else None
        if ultima is None:
            saude = "nunca rodou"
        elif ultima["status"] == "rodando":
            saude = "trabalhando agora"
        elif ultima["status"] == "falhou":
            saude = "falhou na última rodada"
        elif agora - ultima["iniciada_em"] > a.intervalo:
            saude = "atrasado"
        else:
            saude = "em dia"
        saida.append({
            "id": a.id, "nome": a.nome, "faz": a.faz, "tipo": a.tipo, "agenda": a.agenda, "autonomia": a.autonomia,
            "saude": saude, "rodadas": rodadas,
        })  # fmt: skip
    decisoes = conn.execute(
        """select e.criada_em, e.saida, e.confianca, e.decisao, f.tipo, f.motivo,
                  coalesce(f.proposta_agente->>'nome', f.referencia_id) as item
           from execucao_agente e left join fila_revisao f on f.id::text = e.entrada_ref
           where e.agente = 'revisor' order by e.criada_em desc limit 60"""
    ).fetchall()
    return {"agentes": saida, "decisoes": decisoes}


class Decisao(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=200)
    status: Literal["resolvida", "descartada"]


@router.post("/revisao/decidir")
def decidir(decisao: Decisao, conn: Conexao):
    n = conn.execute(
        """update fila_revisao set status = %s, revisado_por = 'painel', decidido_em = now()
           where id = any(%s) and status = 'aberta'""",
        (decisao.status, decisao.ids),
    ).rowcount
    return {"decididos": n}


class Ligacao(BaseModel):
    produto_ids: list[UUID] = Field(min_length=1, max_length=30)


@router.post("/revisao/{item_id}/ligar")
def ligar(item_id: UUID, ligacao: Ligacao, conn: Conexao):
    """Item do encarte -> produto(s) do catálogo: publica o preço e lembra o nome para os próximos encartes."""
    with conn.transaction():
        item = conn.execute(
            "select tipo, proposta_agente as p from fila_revisao where id = %s and status = 'aberta' for update", (item_id,)
        ).fetchone()
        if item is None or item["tipo"] != "encarte" or not item["p"]:
            raise HTTPException(404, "item de encarte aberto não encontrado")
        existentes = {
            str(r["id"]) for r in conn.execute("select id from produto where id = any(%s)", (ligacao.produto_ids,)).fetchall()
        }
        if len(existentes) != len(set(ligacao.produto_ids)):
            raise HTTPException(422, "produto não encontrado")
        precos, valido_ate = fort.ligar_item(conn, str(item_id), item["p"], sorted(existentes), "painel", datetime.now(UTC))
    return {"precos": precos, "valido_ate": valido_ate}


@router.get("/produtos")
def produtos(conn: Conexao, busca: Annotated[str, Query(min_length=2, max_length=60)]):
    palavras = busca.split()[:5]
    parametros = [termo for p in palavras for termo in (f"%{p}%", f"%{p}%")]
    return conn.execute(
        f"""select p.id, p.nome_humano as nome, p.marca, p.tamanho, p.unidade, p.categoria_id as categoria
            from produto p where {" and ".join([_CONDICAO] * len(palavras))} order by p.nome_humano limit 30""",
        parametros,
    ).fetchall()


@router.get("/lojas")
def lojas(conn: Conexao):
    return conn.execute(
        """select l.id, r.nome as rede, l.nome, l.endereco, b.nome as bairro, l.lat, l.lon
           from loja l join rede r on r.id = l.rede_id left join bairro b on b.id = l.bairro_id
           where l.origem = 'openstreetmap' and l.confirmada_em is null order by r.nome, l.nome"""
    ).fetchall()


@router.post("/lojas/{loja_id}/confirmar")
def confirmar_loja(loja_id: UUID, conn: Conexao):
    n = conn.execute("update loja set confirmada_em = now() where id = %s and confirmada_em is null", (loja_id,)).rowcount
    if not n:
        raise HTTPException(404, "loja a confirmar não encontrada")
    return {"confirmada": True}
