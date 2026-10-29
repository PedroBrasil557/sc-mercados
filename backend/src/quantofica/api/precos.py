"""Preços atuais (R5, R6) e comparação da lista entre mercados (R7, R8, R13, R14)."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel, Field, model_validator

from ..regras import totais
from ..regras.preco import Estado, Faixa, Fonte, Observacao, PrecoExibido, preco_atual
from .banco import Conexao
from .identidade import MembroAtual
from .listas import estado_da_lista, lista_da_casa

router = APIRouter(prefix="/v1", tags=["preços"])

JANELA_OBSERVACOES = timedelta(days=37)  # validade máxima (7 dias) + 30 dias como "pode ter mudado"
CUSTO_KM_PADRAO_CENTAVOS = 90  # R8: configurável no perfil da casa


def precos_atuais(
    conn: Connection, loja_ids: list[UUID], produto_ids: list[UUID], agora: datetime
) -> dict[str, dict[str, PrecoExibido]]:
    if not loja_ids or not produto_ids:
        return {}
    linhas = conn.execute(
        """select loja_id, produto_id, preco_centavos, preco_de_centavos, faixa, fonte, observado_em, valido_ate
           from observacao_preco
           where loja_id = any(%s) and produto_id = any(%s) and observado_em >= %s""",
        (loja_ids, produto_ids, agora - JANELA_OBSERVACOES),
    ).fetchall()
    grupos: dict[tuple[str, str], list[Observacao]] = {}
    for r in linhas:
        grupos.setdefault((str(r["loja_id"]), str(r["produto_id"])), []).append(
            Observacao(
                r["preco_centavos"],
                Fonte(r["fonte"]),
                r["observado_em"],
                Faixa(r["faixa"]),
                r["preco_de_centavos"],
                r["valido_ate"],
            )
        )
    saida: dict[str, dict[str, PrecoExibido]] = {}
    for (loja, produto), obs in grupos.items():
        p = preco_atual(obs, agora)
        if p:
            saida.setdefault(loja, {})[produto] = p
    return saida


def _exibir(p: PrecoExibido) -> dict:
    o = p.observacao
    return {
        "preco_centavos": o.preco_centavos,
        "preco_de_centavos": o.preco_de_centavos,
        "fonte": o.fonte,
        "observado_em": o.observado_em,
        "estado": p.estado,
    }


@router.get("/precos")
def precos(loja_id: UUID, produto_id: Annotated[list[UUID], Query(max_length=200)], membro: MembroAtual, conn: Conexao):
    atuais = precos_atuais(conn, [loja_id], produto_id, datetime.now(UTC)).get(str(loja_id), {})
    return {"loja_id": loja_id, "precos": {pid: _exibir(p) for pid, p in atuais.items()}}


class PedidoComparacao(BaseModel):
    bairro_id: UUID
    lista_id: UUID | None = None
    itens: dict[UUID, Decimal] | None = None  # produto -> quantidade
    custo_km_centavos: int = Field(default=CUSTO_KM_PADRAO_CENTAVOS, ge=0, le=1000)
    # Loja escolhida pela casa numa rede (tela "Outras lojas da rede"); nas outras redes vale a mais perto (R13).
    preferidas: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def lista_ou_itens(self):
        if (self.lista_id is None) == (self.itens is None):
            raise ValueError("informe lista_id ou itens, não os dois")
        return self


def _reais(centavos: int) -> str:
    return "R$\u00a0" + f"{centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _km(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "\u00a0km"


def _centavos(v) -> int:
    return int(Decimal(v).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@router.post("/comparar")
def comparar(pedido: PedidoComparacao, membro: MembroAtual, conn: Conexao):
    bairro = conn.execute(
        "select id, cidade_id, lat_centro, lon_centro from bairro where id = %s", (pedido.bairro_id,)
    ).fetchone()
    if not bairro:
        raise HTTPException(404, "bairro não encontrado")
    if pedido.lista_id:
        lista_da_casa(conn, pedido.lista_id, membro)
        itens = {
            str(i["produto_id"]): Decimal(i["quantidade"])
            for i in estado_da_lista(conn, pedido.lista_id)["itens"]
            if i["produto_id"]
        }
    else:
        itens = {str(k): v for k, v in pedido.itens.items()}
    if not itens:
        return {"lojas": [], "comuns": 0, "itens": 0, "divisao": None, "redes_sem_preco": []}

    # R13: a loja mais próxima de cada rede, pela distância do centro do bairro (R14)
    lojas = conn.execute(
        """select l.id, l.nome, l.lat, l.lon, r.nome as rede, b.nome as bairro
           from loja l join rede r on r.id = l.rede_id left join bairro b on b.id = l.bairro_id
           where l.cidade_id = %s and l.lat is not null""",
        (bairro["cidade_id"],),
    ).fetchall()
    dist = {str(lj["id"]): totais.distancia_km(bairro["lat_centro"], bairro["lon_centro"], lj["lat"], lj["lon"]) for lj in lojas}
    mais_proxima: dict[str, dict] = {}
    for lj in lojas:
        atual = mais_proxima.get(lj["rede"])
        if atual is None or dist[str(lj["id"])] < dist[str(atual["id"])]:
            mais_proxima[lj["rede"]] = lj
    preferidas = {str(p) for p in pedido.preferidas}
    for lj in lojas:
        if str(lj["id"]) in preferidas:
            mais_proxima[lj["rede"]] = lj
    escolhidas = {str(lj["id"]): lj for lj in mais_proxima.values()}

    atuais = precos_atuais(conn, list(escolhidas), list(itens), datetime.now(UTC))
    # Loja sem nenhum preço desta lista fica de fora: senão zeraria os itens comuns de todas (R7).
    escolhidas = {k: v for k, v in escolhidas.items() if atuais.get(k)}
    # Redes perto de você que ainda não têm preço desta lista (cartão "Em breve" na tela Comparar).
    sem_preco = sorted(
        (
            {"rede": lj["rede"], "distancia_km": round(dist[str(lj["id"])], 1)}
            for lj in mais_proxima.values()
            if lj["rede"] not in {e["rede"] for e in escolhidas.values()}
        ),
        key=lambda r: r["distancia_km"],
    )
    if not escolhidas:
        return {"lojas": [], "comuns": 0, "itens": len(itens), "divisao": None, "redes_sem_preco": sem_preco}
    tabela = {loja: {p: e.observacao.preco_centavos for p, e in atuais[loja].items()} for loja in escolhidas}
    comp = totais.comparar(itens, tabela, {k: dist[k] for k in escolhidas})

    coords = {k: (lj["lat"], lj["lon"]) for k, lj in escolhidas.items()}
    origem = (bairro["lat_centro"], bairro["lon_centro"])
    base_km = 2 * dist[comp.ordem[0]]
    custos, extras_km = {}, {}
    for a in escolhidas:
        for b in escolhidas:
            if a < b:
                volta = dist[a] + totais.distancia_km(*coords[a], *coords[b]) + totais.distancia_km(*coords[b], *origem)
                extras_km[(a, b)] = max(0.0, volta - base_km)
                custos[(a, b)] = round(extras_km[(a, b)] * pedido.custo_km_centavos)
    div = totais.melhor_divisao(itens, tabela, custos)

    # Melhor loja para a casa: a mais perto, a não ser que outra pague a viagem a mais e sobre 10 reais (R8).
    rec = totais.recomendar(
        {k: _centavos(v) for k, v in comp.totais.items()}, {k: dist[k] for k in escolhidas}, pedido.custo_km_centavos
    )
    viagem = {k: totais.custo_deslocamento_centavos(dist[k], pedido.custo_km_centavos) for k in escolhidas}

    def nota(loja_id: str) -> str | None:
        if rec is None or loja_id == rec.loja:
            return None
        economia = _centavos(comp.totais[rec.loja]) - _centavos(comp.totais[loja_id])
        if economia <= 0:
            return None
        a_mais = max(0, viagem[loja_id] - viagem[rec.loja])
        km_a_mais = max(0.0, dist[loja_id] - dist[rec.loja])
        return (
            f"{_reais(economia)} mais barato na prateleira, mas a ida e volta a {_km(km_a_mais)} a mais custa "
            f"~{_reais(a_mais)}. Não compensa."
            if a_mais
            else f"{_reais(economia)} mais barato, mas a diferença é pequena para trocar de mercado."
        )

    def info_loja(loja_id: str) -> dict:
        precos_usados = [atuais.get(loja_id, {})[p] for p in comp.comuns if p in atuais.get(loja_id, {})]
        return {
            "loja_id": loja_id,
            "rede": escolhidas[loja_id]["rede"],
            "nome": escolhidas[loja_id]["nome"],
            "bairro": escolhidas[loja_id]["bairro"],
            "distancia_km": round(dist[loja_id], 1),
            "custo_viagem_centavos": viagem[loja_id],
            "recomendada": rec is not None and loja_id == rec.loja,
            "nota": nota(loja_id),
            "total_centavos": _centavos(comp.totais[loja_id]),
            "fora_da_soma": comp.fora_da_soma[loja_id],
            "comparacao_parcial": comp.parcial[loja_id],
            "preco_mais_antigo_em": min((p.observacao.observado_em for p in precos_usados), default=None),
            "algum_preco_pode_ter_mudado": any(p.estado is Estado.PODE_TER_MUDADO for p in precos_usados),
        }

    return {
        "comuns": len(comp.comuns),
        "itens": len(itens),
        "redes_sem_preco": sem_preco,
        # A recomendada primeiro; as outras pelo total da prateleira.
        "lojas": [info_loja(lj) for lj in sorted(comp.ordem, key=lambda lj: rec is None or lj != rec.loja)],
        "custo_km_centavos": pedido.custo_km_centavos,
        "divisao": None
        if div is None
        else {
            "lojas": list(div.lojas),
            "total_centavos": _centavos(div.total_centavos),
            "economia_centavos": _centavos(div.economia_centavos),
            "custo_deslocamento_centavos": div.custo_deslocamento_centavos,
            "distancia_extra_km": round(extras_km.get(div.lojas, extras_km.get(div.lojas[::-1], 0.0)), 1),
            "compensa": div.compensa,
        },
    }
