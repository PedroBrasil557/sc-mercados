"""Identidade sem cadastro (R16), convites para a casa e exclusão de conta.

O aparelho recebe um token aleatório na primeira abertura e o envia em `Authorization: Bearer`.
O banco guarda só o SHA-256 do token e do código de convite.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

from .banco import Conexao
from .limite import LimiteDeTaxa

router = APIRouter(prefix="/v1", tags=["identidade"])

VALIDADE_CONVITE = timedelta(hours=48)
USOS_CONVITE = 10
# Sem 0/O, 1/I/L: o código é lido em voz alta e digitado no celular.
ALFABETO_CONVITE = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
TAMANHO_CONVITE = 8

limite_cadastro = LimiteDeTaxa(maximo=20, janela_s=3600)
limite_convite = LimiteDeTaxa(maximo=10, janela_s=600)


def _hash(segredo: str) -> str:
    return hashlib.sha256(segredo.encode()).hexdigest()


@dataclass(frozen=True)
class Membro:
    id: UUID
    casa_id: UUID
    apelido: str
    papel: str


def membro_atual(conn: Conexao, authorization: Annotated[str | None, Header()] = None) -> Membro:
    esquema, _, token = (authorization or "").partition(" ")
    if esquema.lower() != "bearer" or not token:
        raise HTTPException(401, "faltou o token do aparelho", headers={"WWW-Authenticate": "Bearer"})
    linha = conn.execute(
        """update credencial c set usada_em = now() from membro m
           where c.hash_token = %s and m.id = c.membro_id
           returning m.id, m.casa_id, m.apelido, m.papel""",
        (_hash(token),),
    ).fetchone()
    if linha is None:
        raise HTTPException(401, "token inválido", headers={"WWW-Authenticate": "Bearer"})
    return Membro(linha["id"], linha["casa_id"], linha["apelido"], linha["papel"])


MembroAtual = Annotated[Membro, Depends(membro_atual)]


def _emitir_token(conn, membro_id: UUID) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("insert into credencial (hash_token, membro_id) values (%s, %s)", (_hash(token), membro_id))
    return token


class NovoAparelho(BaseModel):
    apelido: str = Field(min_length=1, max_length=40)
    bairro_id: UUID | None = None


@router.post("/aparelhos", status_code=201, dependencies=[Depends(limite_cadastro)])
def registrar(pedido: NovoAparelho, conn: Conexao):
    """Primeira abertura do app: cria a casa, o membro dono e a lista, e devolve o token."""
    with conn.transaction():
        if pedido.bairro_id and not conn.execute("select 1 from bairro where id = %s", (pedido.bairro_id,)).fetchone():
            raise HTTPException(422, "bairro desconhecido")
        casa = conn.execute("insert into casa (bairro_id) values (%s) returning id", (pedido.bairro_id,)).fetchone()["id"]
        membro = conn.execute(
            "insert into membro (casa_id, apelido, papel) values (%s, %s, 'dono') returning id", (casa, pedido.apelido.strip())
        ).fetchone()["id"]
        lista = conn.execute("insert into lista (casa_id, nome) values (%s, 'Lista da casa') returning id", (casa,)).fetchone()[
            "id"
        ]
        token = _emitir_token(conn, membro)
    return {"token": token, "membro_id": membro, "casa_id": casa, "lista_id": lista}


@router.get("/bairros")
def bairros(conn: Conexao, cidade: str = "Blumenau"):
    """Pública: a escolha do bairro vem antes do token, na primeira abertura (R14)."""
    return conn.execute(
        """select b.id, b.nome, b.lat_centro as lat, b.lon_centro as lon
           from bairro b join cidade c on c.id = b.cidade_id where c.nome = %s order by b.nome""",
        (cidade,),
    ).fetchall()


@router.post("/casa/convites", status_code=201)
def convidar(membro: MembroAtual, conn: Conexao):
    codigo = "".join(secrets.choice(ALFABETO_CONVITE) for _ in range(TAMANHO_CONVITE))
    expira = datetime.now(UTC) + VALIDADE_CONVITE
    conn.execute(
        "insert into convite (hash_codigo, casa_id, criado_por, expira_em) values (%s, %s, %s, %s)",
        (_hash(codigo), membro.casa_id, membro.id, expira),
    )
    return {"codigo": codigo, "expira_em": expira, "usos_restantes": USOS_CONVITE}


class Entrada(BaseModel):
    apelido: str = Field(min_length=1, max_length=40)


@router.post("/convites/{codigo}", status_code=201, dependencies=[Depends(limite_convite)])
def entrar(codigo: str, pedido: Entrada, conn: Conexao):
    """Outro aparelho entra na casa com o código do convite e recebe o próprio token."""
    codigo = codigo.strip().upper().replace("-", "").replace(" ", "")
    with conn.transaction():
        convite = conn.execute(
            """update convite set usos = usos + 1
               where hash_codigo = %s and expira_em > now() and usos < %s returning casa_id""",
            (_hash(codigo), USOS_CONVITE),
        ).fetchone()
        if convite is None:
            raise HTTPException(404, "convite não encontrado ou vencido")
        membro = conn.execute(
            "insert into membro (casa_id, apelido) values (%s, %s) returning id", (convite["casa_id"], pedido.apelido.strip())
        ).fetchone()["id"]
        token = _emitir_token(conn, membro)
    listas = conn.execute("select id from lista where casa_id = %s order by nome", (convite["casa_id"],)).fetchall()
    return {"token": token, "membro_id": membro, "casa_id": convite["casa_id"], "lista_id": listas[0]["id"] if listas else None}


@router.get("/eu")
def eu(membro: MembroAtual, conn: Conexao):
    casa = conn.execute("select bairro_id from casa where id = %s", (membro.casa_id,)).fetchone()
    membros = conn.execute(
        "select id, apelido, papel from membro where casa_id = %s order by apelido", (membro.casa_id,)
    ).fetchall()
    listas = conn.execute("select id, nome from lista where casa_id = %s order by nome", (membro.casa_id,)).fetchall()
    return {
        "membro": {"id": membro.id, "apelido": membro.apelido, "papel": membro.papel},
        "casa": {"id": membro.casa_id, "bairro_id": casa["bairro_id"], "membros": membros},
        "listas": listas,
    }


class Alteracao(BaseModel):
    apelido: str | None = Field(default=None, min_length=1, max_length=40)
    bairro_id: UUID | None = None


@router.patch("/eu")
def alterar(pedido: Alteracao, membro: MembroAtual, conn: Conexao):
    """Muda o apelido de quem chamou e/ou o bairro da casa (tela "Trocar bairro")."""
    with conn.transaction():
        if pedido.apelido is not None:
            conn.execute("update membro set apelido = %s where id = %s", (pedido.apelido.strip(), membro.id))
        if pedido.bairro_id is not None:
            if not conn.execute("select 1 from bairro where id = %s", (pedido.bairro_id,)).fetchone():
                raise HTTPException(422, "bairro desconhecido")
            conn.execute("update casa set bairro_id = %s where id = %s", (pedido.bairro_id, membro.casa_id))
    return eu(Membro(membro.id, membro.casa_id, pedido.apelido.strip() if pedido.apelido else membro.apelido, membro.papel), conn)


@router.delete("/eu", status_code=204)
def excluir_conta(membro: MembroAtual, conn: Conexao):
    """Exclusão a pedido do titular (LGPD art. 18; Google Play). Último membro a sair leva a casa junto.

    As operações que ele fez na lista ficam, sem autoria, para a lista dos outros continuar certa.
    """
    with conn.transaction():
        conn.execute("set local quantofica.exclusao_titular = 'sim'")
        conn.execute("delete from membro where id = %s", (membro.id,))
        restantes = conn.execute("select count(*) as n from membro where casa_id = %s", (membro.casa_id,)).fetchone()["n"]
        if restantes == 0:
            conn.execute("delete from casa where id = %s", (membro.casa_id,))
        elif membro.papel == "dono":
            # A casa não fica sem dono: passa para quem entrou primeiro.
            conn.execute(
                """update membro set papel = 'dono' where id = (
                     select id from membro where casa_id = %s order by entrou_em, id limit 1)""",
                (membro.casa_id,),
            )
    return Response(status_code=204)
