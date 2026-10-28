"""Busca no catálogo: o que a família pode pôr na lista."""

from typing import Annotated

from fastapi import APIRouter, Query

from .banco import Conexao
from .identidade import MembroAtual

router = APIRouter(prefix="/v1", tags=["catálogo"])

# Busca sem acento e sem diferença de maiúsculas ("cafe" acha "Café"), sem depender da extensão unaccent.
_COM_ACENTO = "áàâãäéèêëíìîïóòôõöúùûüç"
_SEM_ACENTO = "aaaaaeeeeiiiiooooouuuuc"


def _normalizar(expressao: str) -> str:
    return f"translate(lower({expressao}), '{_COM_ACENTO}', '{_SEM_ACENTO}')"


_NOME, _MARCA, _TERMO = _normalizar("p.nome_humano"), _normalizar("coalesce(p.marca, '')"), _normalizar("%s")
_CONDICAO = f"({_NOME} like {_TERMO} or {_MARCA} like {_TERMO})"


@router.get("/produtos")
def buscar(
    _membro: MembroAtual,
    conn: Conexao,
    busca: Annotated[str, Query(max_length=60)] = "",
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Produtos cujo nome ou marca contém cada palavra da busca. Sem busca: o catálogo inteiro (até o limite)."""
    palavras = busca.split()[:5]
    onde = ("where " + " and ".join([_CONDICAO] * len(palavras))) if palavras else ""
    parametros = [termo for p in palavras for termo in (f"%{p}%", f"%{p}%")]
    return conn.execute(
        f"""select p.id, p.nome_humano as nome, p.marca, p.tamanho, p.unidade, p.categoria_id as categoria
            from produto p {onde} order by p.categoria_id, p.nome_humano limit %s""",
        (*parametros, limite),
    ).fetchall()
