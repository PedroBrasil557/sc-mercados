"""Lista da casa sincronizada por operações (R15)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel, Field, field_validator

from ..regras.lista import Operacao, Tipo, aplicar
from .banco import Conexao

router = APIRouter(prefix="/v1/listas", tags=["listas"])

TOLERANCIA_RELOGIO = timedelta(minutes=5)


class OperacaoEntrada(BaseModel):
    id: UUID  # gerado no aparelho: reenviar a mesma operação não duplica
    item_id: UUID
    tipo: Literal["criar", "somar", "tirar", "marcar", "desmarcar", "remover"]
    feita_em: datetime
    membro_id: UUID | None = None
    valor: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    produto_id: UUID | None = None  # só em "criar"
    categoria_id: str | None = None  # item genérico (R3)

    @field_validator("feita_em")
    @classmethod
    def com_fuso_e_sem_futuro(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("feita_em precisa de fuso horário")
        if v > datetime.now(UTC) + TOLERANCIA_RELOGIO:
            raise ValueError("feita_em está no futuro")
        return v


class LoteOperacoes(BaseModel):
    operacoes: list[OperacaoEntrada] = Field(min_length=1, max_length=500)


def _lista_existe(conn: Connection, lista_id: UUID) -> None:
    if not conn.execute("select 1 from lista where id = %s", (lista_id,)).fetchone():
        raise HTTPException(404, "lista não encontrada")


def _cursor(conn: Connection, lista_id: UUID) -> int:
    return conn.execute("select coalesce(max(seq), 0) as c from operacao_lista where lista_id = %s", (lista_id,)).fetchone()["c"]


@router.post("/{lista_id}/operacoes")
def receber(lista_id: UUID, lote: LoteOperacoes, conn: Conexao):
    novas = 0
    with conn.transaction():
        # Trava a lista: envios da mesma casa entram um de cada vez, então o `seq` cresce na ordem de
        # gravação e quem lê "depois de N" nunca pula uma operação que ainda não tinha sido gravada.
        lista = conn.execute("select casa_id from lista where id = %s for update", (lista_id,)).fetchone()
        if not lista:
            raise HTTPException(404, "lista não encontrada")
        membros = {r["id"] for r in conn.execute("select id from membro where casa_id = %s", (lista["casa_id"],)).fetchall()}
        if any(op.membro_id and op.membro_id not in membros for op in lote.operacoes):
            raise HTTPException(422, "membro não pertence à casa desta lista")
        pedidos = {op.produto_id for op in lote.operacoes if op.produto_id}
        if pedidos:
            achados = {r["id"] for r in conn.execute("select id from produto where id = any(%s)", (list(pedidos),)).fetchall()}
            if pedidos - achados:
                raise HTTPException(422, "produto desconhecido")
        for op in lote.operacoes:
            if op.tipo == "criar" and (op.produto_id or op.categoria_id):
                conn.execute(
                    """insert into item_lista (id, lista_id, produto_id, categoria_id, quantidade, adicionado_por)
                       values (%s, %s, %s, %s, %s, %s) on conflict (id) do nothing""",
                    (op.item_id, lista_id, op.produto_id, op.categoria_id, op.valor or 1, op.membro_id),
                )
            cur = conn.execute(
                """insert into operacao_lista (id, lista_id, item_id, membro_id, tipo, valor, feita_em)
                   values (%s, %s, %s, %s, %s, %s, %s) on conflict (id) do nothing returning seq""",
                (op.id, lista_id, op.item_id, op.membro_id, op.tipo, op.valor, op.feita_em),
            )
            novas += cur.rowcount
    return {"recebidas": len(lote.operacoes), "novas": novas, "cursor": _cursor(conn, lista_id)}


@router.get("/{lista_id}/operacoes")
def desde(
    lista_id: UUID,
    conn: Conexao,
    desde: Annotated[int, Query(ge=0)] = 0,
    limite: Annotated[int, Query(ge=1, le=1000)] = 500,
):
    """Operações recebidas depois do cursor `desde`, para o aparelho se atualizar."""
    _lista_existe(conn, lista_id)
    linhas = conn.execute(
        """select seq, id, item_id, membro_id, tipo, valor, feita_em from operacao_lista
           where lista_id = %s and seq > %s order by seq limit %s""",
        (lista_id, desde, limite),
    ).fetchall()
    return {"operacoes": linhas, "cursor": linhas[-1]["seq"] if linhas else desde}


@router.get("/{lista_id}")
def estado(lista_id: UUID, conn: Conexao):
    """Itens da lista agora, calculados a partir de todas as operações (R15)."""
    _lista_existe(conn, lista_id)
    ops = conn.execute(
        "select id, item_id, membro_id, tipo, valor, feita_em from operacao_lista where lista_id = %s", (lista_id,)
    ).fetchall()
    nomes = {
        str(m["id"]): m["apelido"]
        for m in conn.execute(
            "select m.id, m.apelido from membro m join lista l on l.casa_id = m.casa_id where l.id = %s", (lista_id,)
        ).fetchall()
    }
    itens = aplicar(
        [
            Operacao(
                str(o["id"]),
                str(o["item_id"]),
                Tipo(o["tipo"]),
                o["feita_em"],
                str(o["membro_id"]) if o["membro_id"] else None,
                o["valor"],
            )
            for o in ops
        ],
        nomes,
    )
    detalhes = {
        str(r["id"]): r
        for r in conn.execute(
            """select i.id, i.categoria_id, i.marca_fixa, p.id as produto_id, p.nome_humano, p.marca, p.tamanho, p.unidade,
                      coalesce(p.categoria_id, i.categoria_id) as categoria
               from item_lista i left join produto p on p.id = i.produto_id where i.lista_id = %s""",
            (lista_id,),
        ).fetchall()
    }
    saida = []
    for item_id, it in itens.items():
        if it.removido:
            continue
        d = detalhes.get(item_id, {})
        saida.append(
            {
                "id": item_id,
                "quantidade": it.quantidade,
                "comprado": it.comprado,
                "aviso": it.aviso,
                "adicionado_por": nomes.get(it.adicionado_por) if it.adicionado_por else None,
                "produto_id": d.get("produto_id"),
                "nome": d.get("nome_humano"),
                "marca": d.get("marca"),
                "tamanho": d.get("tamanho"),
                "unidade": d.get("unidade"),
                "categoria": d.get("categoria"),
            }
        )
    return {"itens": saida, "cursor": _cursor(conn, lista_id)}
