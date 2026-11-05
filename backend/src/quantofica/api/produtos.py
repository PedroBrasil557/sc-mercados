"""Busca no catálogo: o que a família pode pôr na lista."""

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from .banco import Conexao
from .identidade import MembroAtual
from .precos import precos_atuais

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
    membro: MembroAtual,
    conn: Conexao,
    busca: Annotated[str, Query(max_length=60)] = "",
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Produtos cujo nome ou marca contém cada palavra da busca. Sem busca: o catálogo inteiro (até o limite)."""
    palavras = busca.split()[:5]
    onde = ("where " + " and ".join([_CONDICAO] * len(palavras))) if palavras else ""
    parametros = [termo for p in palavras for termo in (f"%{p}%", f"%{p}%")]
    produtos = conn.execute(
        f"""select p.id, p.nome_humano as nome, p.marca, p.tamanho, p.unidade, p.categoria_id as categoria
            from produto p {onde} order by p.categoria_id, p.nome_humano limit %s""",
        (*parametros, limite),
    ).fetchall()
    # "a partir de R$ 22,98 no Giassi": o menor preço atual (varejo, R5/R6) entre as lojas da cidade da casa.
    lojas = conn.execute(
        """select l.id, r.nome as rede from loja l join rede r on r.id = l.rede_id
           where l.cidade_id = (select b.cidade_id from casa c join bairro b on b.id = c.bairro_id where c.id = %s)""",
        (membro.casa_id,),
    ).fetchall()
    rede_da_loja = {str(lj["id"]): lj["rede"] for lj in lojas}
    atuais = precos_atuais(conn, list(rede_da_loja), [p["id"] for p in produtos], datetime.now(UTC))
    for p in produtos:
        ofertas = [
            (por_produto[str(p["id"])].observacao.preco_centavos, loja)
            for loja, por_produto in atuais.items()
            if str(p["id"]) in por_produto
        ]
        menor = min(ofertas, default=None)
        p["menor_preco_centavos"] = menor[0] if menor else None
        p["menor_preco_rede"] = rede_da_loja[menor[1]] if menor else None
    return produtos


# Foto do produto no site de uma rede, para o app mostrar no modo de teste (Expo Go). A foto é da rede ou do
# fabricante: o app publicado não a usa até haver autorização (ver db/migrations/0016_imagem_no_site.sql).
_REDES_DA_FOTO = ["Giassi", "Cooper", "Angeloni", "Sam's Club", "Rede Top", "Fort Atacadista"]  # primeira com foto
_VTEX_IDS = re.compile(r"(/arquivos/ids/\d+)(?:-\d+-\d+)?/")


def foto_pequena(url: str, lado: int = 400) -> str:
    """Na VTEX, /arquivos/ids/123/ vira /arquivos/ids/123-400-400/: o site entrega a imagem já reduzida."""
    return _VTEX_IDS.sub(rf"\1-{lado}-{lado}/", url, count=1)


@router.get("/fotos")
def fotos(_membro: MembroAtual, conn: Conexao, ids: Annotated[str, Query(max_length=4000)] = ""):
    """Produto -> endereço da foto no site de uma rede, para até 100 produtos por pedido."""
    lista = [i for i in ids.split(",") if re.fullmatch(r"[0-9a-f-]{36}", i)][:100]
    if not lista:
        return {}
    linhas = conn.execute(
        """select pr.produto_id, pr.imagem_url, r.nome as rede from produto_na_rede pr join rede r on r.id = pr.rede_id
           where pr.produto_id = any(%s::uuid[]) and pr.imagem_url is not null""",
        (lista,),
    ).fetchall()
    ordem = {nome: i for i, nome in enumerate(_REDES_DA_FOTO)}
    melhor: dict[str, tuple[int, str]] = {}
    for r in linhas:
        chave, prioridade = str(r["produto_id"]), ordem.get(r["rede"], 99)
        if chave not in melhor or prioridade < melhor[chave][0]:
            melhor[chave] = (prioridade, r["imagem_url"])
    return {p: foto_pequena(url) for p, (_, url) in melhor.items()}
