"""Fases 2 e 3: detalhe do produto, outras lojas da rede, ofertas reais, reporte de preço, cupom e economia."""

import hashlib
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel, Field

from ..regras import economia as regra_economia
from ..regras import totais
from ..regras.ean import normalizar
from ..regras.ofertas import oferta_real, percentual_desconto
from ..regras.preco import Faixa
from .banco import Conexao
from .identidade import Membro, MembroAtual
from .precos import precos_atuais

router = APIRouter(prefix="/v1", tags=["detalhes"])


def _lojas_do_bairro(conn: Connection, bairro_id: UUID) -> tuple[dict, list[dict]]:
    """Lojas da cidade do bairro, com a distância do centro do bairro (R14)."""
    bairro = conn.execute("select id, cidade_id, lat_centro, lon_centro from bairro where id = %s", (bairro_id,)).fetchone()
    if not bairro:
        raise HTTPException(404, "bairro não encontrado")
    lojas = conn.execute(
        """select l.id, l.nome, l.lat, l.lon, r.nome as rede, b.nome as bairro
           from loja l join rede r on r.id = l.rede_id left join bairro b on b.id = l.bairro_id
           where l.cidade_id = %s and l.lat is not null""",
        (bairro["cidade_id"],),
    ).fetchall()
    for lj in lojas:
        lj["distancia_km"] = totais.distancia_km(bairro["lat_centro"], bairro["lon_centro"], lj["lat"], lj["lon"])
    return bairro, lojas


def _bairro_da_casa(conn: Connection, membro: Membro) -> UUID:
    linha = conn.execute("select bairro_id from casa where id = %s", (membro.casa_id,)).fetchone()
    if not linha or not linha["bairro_id"]:
        raise HTTPException(422, "a casa ainda não escolheu o bairro")
    return linha["bairro_id"]


def _loja_publica(lj: dict) -> dict:
    return {
        "loja_id": lj["id"],
        "rede": lj["rede"],
        "nome": lj["nome"],
        "bairro": lj["bairro"],
        "distancia_km": round(lj["distancia_km"], 1),
    }


# ---------- 06 Detalhe do produto ----------


@router.get("/produtos/{produto_id}")
def detalhe(produto_id: UUID, membro: MembroAtual, conn: Conexao):
    """O produto e o preço atual em cada loja da cidade, do mais barato ao mais caro (R5, R6, R13)."""
    produto = conn.execute(
        """select p.id, p.nome_humano as nome, p.marca, p.tamanho, p.unidade, p.categoria_id as categoria,
                  (select min(codigo) from ean e where e.produto_id = p.id) as ean
           from produto p where p.id = %s""",
        (produto_id,),
    ).fetchone()
    if not produto:
        raise HTTPException(404, "produto não encontrado")
    _, lojas = _lojas_do_bairro(conn, _bairro_da_casa(conn, membro))
    atuais = precos_atuais(conn, [lj["id"] for lj in lojas], [produto_id], datetime.now(UTC))
    precos = []
    for lj in lojas:
        p = atuais.get(str(lj["id"]), {}).get(str(produto_id))
        if p:
            o = p.observacao
            precos.append(
                _loja_publica(lj)
                | {
                    "preco_centavos": o.preco_centavos,
                    "preco_de_centavos": o.preco_de_centavos,
                    "fonte": o.fonte,
                    "observado_em": o.observado_em,
                    "estado": p.estado,
                }
            )
    precos.sort(key=lambda x: (x["preco_centavos"], x["distancia_km"]))
    # Gráfico "Preço no <loja>, últimos 30 dias": o menor preço de cada dia na loja mais barata.
    historico = []
    if precos:
        historico = conn.execute(
            """select (observado_em at time zone 'America/Sao_Paulo')::date as dia, min(preco_centavos) as preco_centavos
               from observacao_preco where produto_id = %s and loja_id = %s and faixa = 'varejo' and observado_em >= %s
               group by 1 order by 1""",
            (produto_id, precos[0]["loja_id"], datetime.now(UTC) - timedelta(days=30)),
        ).fetchall()
    return {"produto": produto, "precos": precos, "historico": historico}


# ---------- 18 Outras lojas da rede ----------


class PedidoRede(BaseModel):
    rede: str = Field(min_length=1, max_length=80)
    itens: dict[UUID, Decimal] = Field(min_length=1, max_length=300)


@router.post("/comparar/rede")
def outras_lojas(pedido: PedidoRede, membro: MembroAtual, conn: Conexao):
    """Total da lista em cada loja da rede (a Cooper tem preço por loja), com quantos itens cada uma tem."""
    _, lojas = _lojas_do_bairro(conn, _bairro_da_casa(conn, membro))
    da_rede = [lj for lj in lojas if lj["rede"] == pedido.rede]
    itens = {str(k): v for k, v in pedido.itens.items()}
    atuais = precos_atuais(conn, [lj["id"] for lj in da_rede], list(itens), datetime.now(UTC))
    saida = []
    for lj in sorted(da_rede, key=lambda x: x["distancia_km"]):
        precos = atuais.get(str(lj["id"]), {})
        total = sum(Decimal(precos[p].observacao.preco_centavos) * q for p, q in itens.items() if p in precos)
        saida.append(_loja_publica(lj) | {"total_centavos": int(total), "itens_com_preco": len(precos), "itens": len(itens)})
    return {"rede": pedido.rede, "lojas": saida}


# ---------- 07 Ofertas reais (R9) ----------


@router.get("/ofertas")
def ofertas(membro: MembroAtual, conn: Conexao, limite: Annotated[int, Query(ge=1, le=100)] = 40):
    """Ofertas reais na loja mais perto de cada rede. Com menos de 30 dias de histórico vale a regra provisória do R9."""
    _, lojas = _lojas_do_bairro(conn, _bairro_da_casa(conn, membro))
    mais_proxima: dict[str, dict] = {}
    for lj in lojas:
        if lj["rede"] not in mais_proxima or lj["distancia_km"] < mais_proxima[lj["rede"]]["distancia_km"]:
            mais_proxima[lj["rede"]] = lj
    escolhidas = {str(lj["id"]): lj for lj in mais_proxima.values()}
    agora = datetime.now(UTC)
    produtos = {
        str(r["id"]): r
        for r in conn.execute(
            "select id, nome_humano as nome, marca, tamanho, unidade, categoria_id as categoria from produto"
        ).fetchall()
    }
    atuais = precos_atuais(conn, list(escolhidas), list(produtos), agora)
    historico: dict[tuple[str, str], list[tuple[datetime, int]]] = {}
    for r in conn.execute(
        """select loja_id, produto_id, observado_em, preco_centavos from observacao_preco
           where loja_id = any(%s) and faixa = %s and observado_em >= %s""",
        (list(escolhidas), Faixa.VAREJO, agora - timedelta(days=60)),
    ).fetchall():
        historico.setdefault((str(r["loja_id"]), str(r["produto_id"])), []).append((r["observado_em"], r["preco_centavos"]))

    achadas = []
    for loja_id, por_produto in atuais.items():
        for produto_id, exibido in por_produto.items():
            o = exibido.observacao
            serie = historico.get((loja_id, produto_id), [])
            dias = (agora - min(t for t, _ in serie)).days if serie else 0
            h30 = [v for t, v in serie if t >= agora - timedelta(days=30)]
            outras = [p[produto_id].observacao.preco_centavos for lid, p in atuais.items() if lid != loja_id and produto_id in p]
            if not oferta_real(o.preco_centavos, h30, [v for _, v in serie], dias, o.preco_de_centavos, outras):
                continue
            referencia = int(median(h30)) if dias >= 30 and h30 else (o.preco_de_centavos or o.preco_centavos)
            achadas.append(
                {"produto": produtos[produto_id]}
                | _loja_publica(escolhidas[loja_id])
                | {
                    "preco_centavos": o.preco_centavos,
                    "referencia_centavos": referencia,
                    "desconto_pct": percentual_desconto(o.preco_centavos, referencia),
                    "base": "mediana de 30 dias" if dias >= 30 else "preço anterior da loja, conferido com as outras",
                    "observado_em": o.observado_em,
                }
            )
    achadas.sort(key=lambda a: -a["desconto_pct"])
    return {"ofertas": achadas[:limite]}


# ---------- 19 Preço diferente ----------


class Reporte(BaseModel):
    produto_id: UUID
    loja_id: UUID
    preco_centavos: int = Field(gt=0, lt=10_000_000)


@router.post("/reportes", status_code=201)
def reportar(pedido: Reporte, membro: MembroAtual, conn: Conexao):
    """Alguém viu outro preço na prateleira (R11): vai para a revisão; só vira preço depois de confirmado."""
    with conn.transaction():
        if not conn.execute("select 1 from loja where id = %s", (pedido.loja_id,)).fetchone():
            raise HTTPException(422, "loja desconhecida")
        r = conn.execute(
            "insert into reporte_preco (membro_id, produto_id, loja_id, preco_centavos) values (%s, %s, %s, %s) returning id",
            (membro.id, pedido.produto_id, pedido.loja_id, pedido.preco_centavos),
        ).fetchone()
        conn.execute(
            "insert into fila_revisao (tipo, referencia_id, motivo, prioridade) values ('reporte', %s, %s, 2)",
            (str(r["id"]), f"preço visto na prateleira: {pedido.preco_centavos} centavos"),
        )
    return {"id": r["id"], "status": "pendente"}


# ---------- Código de barras ----------


@router.get("/produtos/ean/{codigo}")
def por_ean(codigo: str, _membro: MembroAtual, conn: Conexao):
    try:
        gtin = normalizar(codigo)
    except ValueError as e:
        raise HTTPException(422, "código de barras inválido") from e
    produto = conn.execute(
        """select p.id, p.nome_humano as nome, p.marca, p.tamanho, p.unidade, p.categoria_id as categoria
           from ean e join produto p on p.id = e.produto_id where e.codigo = %s""",
        (gtin,),
    ).fetchone()
    if not produto:
        raise HTTPException(404, "produto ainda não está no catálogo")
    return produto


# ---------- 09/10 Cupom fiscal (NFC-e) e economia (R12) ----------


class ItemDoCupom(BaseModel):
    descricao: str = Field(max_length=200)
    codigo: str = Field(max_length=60)
    quantidade: Decimal = Field(gt=0)
    valor_total_centavos: int = Field(ge=0)


class Cupom(BaseModel):
    chave: str = Field(min_length=44, max_length=60)  # chave de acesso da NFC-e
    emitente: str | None = Field(default=None, max_length=200)
    cnpj: str | None = Field(default=None, max_length=20)
    emitido_em: date
    total_centavos: int = Field(ge=0)
    itens: list[ItemDoCupom] = Field(max_length=400)


@router.post("/cupons", status_code=201)
def ler_cupom(cupom: Cupom, membro: MembroAtual, conn: Conexao):
    """Guarda o cupom (só o hash da chave) e calcula a economia nos itens que já reconhecemos (R12).

    Item com código de barras no lugar do código interno é reconhecido na hora; os outros vão para o
    agente Casador de Cupom, e a economia é calculada só com os reconhecidos (a base fica escrita).
    """
    chave = re.sub(r"\D", "", cupom.chave)
    if len(chave) != 44:
        raise HTTPException(422, "chave de acesso inválida")
    hash_chave = hashlib.sha256(chave.encode()).hexdigest()
    informado = re.sub(r"\D", "", cupom.cnpj or "")
    cnpj = informado if len(informado) == 14 else chave[6:20]  # o CNPJ do emitente está na própria chave
    with conn.transaction():
        if conn.execute("select 1 from cupom_lido where hash_chave = %s", (hash_chave,)).fetchone():
            raise HTTPException(409, "este cupom já foi lido")
        loja = conn.execute(
            "select l.id, r.nome as rede from loja l join rede r on r.id = l.rede_id where l.cnpj = %s", (cnpj,)
        ).fetchone()
        reconhecidos: dict[str, tuple[Decimal, int]] = {}
        for it in cupom.itens:
            try:
                gtin = normalizar(it.codigo) if 8 <= len(re.sub(r"\D", "", it.codigo)) <= 14 else None
            except ValueError:
                gtin = None
            produto = conn.execute("select produto_id from ean where codigo = %s", (gtin,)).fetchone() if gtin else None
            if produto:
                q, v = reconhecidos.get(str(produto["produto_id"]), (Decimal(0), 0))
                reconhecidos[str(produto["produto_id"])] = (q + it.quantidade, v + it.valor_total_centavos)
            else:
                conn.execute(
                    """insert into codigo_item_loja (cnpj_loja, codigo_interno, descricao_cupom) values (%s, %s, %s)
                       on conflict do nothing""",
                    (cnpj, it.codigo[:60], it.descricao[:200]),
                )
        economia = _economia_do_cupom(conn, membro, reconhecidos, loja["rede"] if loja else None)
        conn.execute(
            """insert into cupom_lido (casa_id, hash_chave, loja_id, data_compra, total_centavos, economia_centavos)
               values (%s, %s, %s, %s, %s, %s)""",
            (
                membro.casa_id,
                hash_chave,
                loja["id"] if loja else None,
                cupom.emitido_em,
                cupom.total_centavos,
                economia.economia_centavos if economia else 0,
            ),
        )
    return {
        "loja": loja["rede"] if loja else cupom.emitente,
        "total_centavos": cupom.total_centavos,
        "itens": len(cupom.itens),
        "itens_reconhecidos": len(reconhecidos),
        "economia": None
        if economia is None
        else {
            "economia_centavos": economia.economia_centavos,
            "pago_centavos": economia.pago_centavos,
            "media_centavos": economia.media_centavos,
            "base": economia.base,
        },
    }


def _economia_do_cupom(conn: Connection, membro: Membro, itens: dict[str, tuple[Decimal, int]], rede_do_cupom: str | None):
    if not itens:
        return None
    _, lojas = _lojas_do_bairro(conn, _bairro_da_casa(conn, membro))
    mais_proxima: dict[str, dict] = {}
    for lj in lojas:
        if lj["rede"] != rede_do_cupom and (
            lj["rede"] not in mais_proxima or lj["distancia_km"] < mais_proxima[lj["rede"]]["distancia_km"]
        ):
            mais_proxima[lj["rede"]] = lj
    atuais = precos_atuais(conn, [lj["id"] for lj in mais_proxima.values()], list(itens), datetime.now(UTC))
    # Só as redes que têm TODOS os itens reconhecidos entram na média (comparação justa, R7).
    totais_por_rede = {}
    for rede, lj in mais_proxima.items():
        precos = atuais.get(str(lj["id"]), {})
        if all(p in precos for p in itens):
            totais_por_rede[rede] = int(sum(Decimal(precos[p].observacao.preco_centavos) * q for p, (q, _) in itens.items()))
    if not totais_por_rede:
        return None
    return regra_economia.calcular(sum(v for _, v in itens.values()), totais_por_rede)


@router.get("/economia")
def economia_do_mes(membro: MembroAtual, conn: Conexao):
    """Economia da casa no mês (R12): soma das economias dos cupons lidos; economia negativa nunca entra."""
    inicio = date.today().replace(day=1)
    r = conn.execute(
        """select coalesce(sum(economia_centavos), 0) as economia, count(*) as cupons
           from cupom_lido where casa_id = %s and data_compra >= %s""",
        (membro.casa_id, inicio),
    ).fetchone()
    return {"mes": inicio.isoformat(), "economia_centavos": r["economia"], "cupons": r["cupons"]}
