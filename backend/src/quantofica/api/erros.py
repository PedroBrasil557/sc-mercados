"""Monitoramento de erros do app, próprio e gratuito (sem Sentry nem outro serviço de terceiros).

O app manda o erro (mensagem, pilha, tela, versão, plataforma); erros iguais viram uma linha com contagem. Não
guarda nada que identifique a pessoa: sem token, sem casa, sem IP. Rota pública, com limite por IP, porque o erro
pode acontecer antes do aparelho ter cadastro.
"""

import hashlib
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .banco import Conexao
from .limite import LimiteDeTaxa

router = APIRouter(prefix="/v1", tags=["erros"])
limite_erros = LimiteDeTaxa(maximo=30, janela_s=600)


class ErroDoApp(BaseModel):
    mensagem: str = Field(min_length=1, max_length=500)
    pilha: str | None = Field(default=None, max_length=4000)
    onde: str = Field(default="global", max_length=120)
    versao: str = Field(default="?", max_length=40)
    plataforma: str = Field(default="?", max_length=40)
    ambiente: Literal["desenvolvimento", "publicado"] = "publicado"
    fatal: bool = False


@router.post("/erros", status_code=204, dependencies=[Depends(limite_erros)])
def registrar(erro: ErroDoApp, conn: Conexao) -> None:
    assinatura = hashlib.sha256(f"{erro.onde}\n{erro.mensagem}".encode()).hexdigest()
    conn.execute(
        """insert into erro_app (assinatura, mensagem, pilha, onde, versao, plataforma, ambiente, fatal)
           values (%s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (assinatura, versao, ambiente) do update
           set vezes = erro_app.vezes + 1, ultima_em = now(), fatal = erro_app.fatal or excluded.fatal,
               pilha = coalesce(excluded.pilha, erro_app.pilha), plataforma = excluded.plataforma""",
        (assinatura, erro.mensagem, erro.pilha, erro.onde, erro.versao, erro.plataforma, erro.ambiente, erro.fatal),
    )


def ultimos(conn, limite: int = 100) -> list[dict]:
    return conn.execute(
        """select mensagem, onde, versao, plataforma, ambiente, fatal, vezes, primeira_em, ultima_em, pilha
           from erro_app order by ultima_em desc limit %s""",
        (limite,),
    ).fetchall()
