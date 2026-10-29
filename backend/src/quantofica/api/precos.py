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
from .catalogo import catalogo
from .contexto import contexto
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
    # Itens "qualquer marca": cada mercado entra com o equivalente mais barato do mesmo grupo.
    qualquer_marca: list[UUID] = Field(default_factory=list, max_length=300)

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
        da_lista = [i for i in estado_da_lista(conn, pedido.lista_id)["itens"] if i["produto_id"] and not i["comprado"]]
        itens = {str(i["produto_id"]): Decimal(i["quantidade"]) for i in da_lista}
        genericos = {str(i["produto_id"]) for i in da_lista if i.get("qualquer_marca")}
    else:
        itens = {str(k): v for k, v in pedido.itens.items()}
        genericos = {str(p) for p in pedido.qualquer_marca}
    if not itens:
        return {"lojas": [], "comuns": 0, "itens": 0, "divisao": None, "redes_sem_preco": [], "lojas_com_poucos_itens": []}

    # R13/R14: a loja de cada rede (a mais perto com preço) e o seu mercado vêm do contexto da casa.
    ctx = contexto(conn, membro)
    lojas = ctx.lojas
    dist = {str(lj["id"]): lj["distancia_km"] for lj in lojas}
    mais_proxima: dict[str, dict] = dict(ctx.por_rede)
    preferidas = {str(p) for p in pedido.preferidas}
    seu_id = str(ctx.seu_mercado["id"]) if ctx.seu_mercado else None
    if seu_id:
        preferidas.add(seu_id)  # o seu mercado representa a rede dele e é a base da recomendação
    for lj in lojas:
        if str(lj["id"]) in preferidas:
            mais_proxima[lj["rede"]] = lj
    escolhidas = {str(lj["id"]): lj for lj in mais_proxima.values()}

    # Qualquer marca: os produtos do mesmo grupo também entram na consulta de preço.
    cat = catalogo(conn)
    membros = {}
    for p in genericos & set(itens):
        g = cat["produtos"].get(p, {}).get("grupo")
        membros[p] = cat["grupos"].get(g, [p]) if g else [p]
    consulta = set(itens) | {m for ms in membros.values() for m in ms}
    brutos = precos_atuais(conn, list(escolhidas), list(consulta), datetime.now(UTC))
    atuais: dict[str, dict] = {}
    escolhas: dict[str, list] = {}
    for loja, por in brutos.items():
        atuais[loja] = {}
        for p in itens:
            if p in membros:
                opcoes = [(m, por[m]) for m in membros[p] if m in por]
                if opcoes:
                    m, ex = min(opcoes, key=lambda x: x[1].observacao.preco_centavos)
                    atuais[loja][p] = ex
                    d = cat["produtos"].get(m, {})
                    escolhas.setdefault(loja, []).append(
                        {"item": p, "produto_id": m, "marca": d.get("marca"), "nome": d.get("nome")}
                    )
            elif p in por:
                atuais[loja][p] = por[p]
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
        vazio = {"lojas": [], "comuns": 0, "divisao": None, "lojas_com_poucos_itens": []}
        return {**vazio, "itens": len(itens), "redes_sem_preco": sem_preco}
    tabela = {loja: {p: e.observacao.preco_centavos for p, e in atuais[loja].items()} for loja in escolhidas}
    # Loja com poucos itens da lista (ex.: Fort, só o encarte) sai do total justo e aparece à parte.
    dentro = totais.nucleo(itens, tabela)
    poucos = {k: escolhidas.pop(k) for k in list(escolhidas) if k not in dentro}
    tabela_poucos = {k: tabela.pop(k) for k in poucos}
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
        {k: _centavos(v) for k, v in comp.totais.items()}, {k: dist[k] for k in escolhidas}, pedido.custo_km_centavos, seu_id
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
            "total_com_viagem_centavos": _centavos(comp.totais[loja_id]) + viagem[loja_id],
            "seu_mercado": loja_id == seu_id,
            "escolhas": escolhas.get(loja_id, []),  # qualquer marca: que marca pegar nesta loja
            "fora_da_soma": comp.fora_da_soma[loja_id],
            "comparacao_parcial": comp.parcial[loja_id],
            "preco_mais_antigo_em": min((p.observacao.observado_em for p in precos_usados), default=None),
            "algum_preco_pode_ter_mudado": any(p.estado is Estado.PODE_TER_MUDADO for p in precos_usados),
        }

    referencia = rec.loja if rec else comp.ordem[0]

    def info_poucos(loja_id: str) -> dict:
        tem = [p for p in itens if p in tabela_poucos[loja_id]]
        # Os mesmos itens na loja recomendada, para dizer se vale a pena (só os que as duas vendem).
        mesmos = [p for p in tem if p in tabela[referencia]]
        validades = [atuais[loja_id][p].observacao.valido_ate for p in tem if atuais[loja_id][p].observacao.valido_ate]
        return {
            "loja_id": loja_id,
            "rede": poucos[loja_id]["rede"],
            "nome": poucos[loja_id]["nome"],
            "bairro": poucos[loja_id]["bairro"],
            "distancia_km": round(dist[loja_id], 1),
            "itens": tem,
            "total_centavos": _centavos(sum(tabela_poucos[loja_id][p] * itens[p] for p in tem)),
            "mesmos_itens": len(mesmos),
            "mesmos_itens_aqui_centavos": _centavos(sum(tabela_poucos[loja_id][p] * itens[p] for p in mesmos)),
            "mesmos_itens_na_recomendada_centavos": _centavos(sum(tabela[referencia][p] * itens[p] for p in mesmos)),
            "valido_ate": min(validades, default=None),
        }

    return {
        "comuns": len(comp.comuns),
        "itens": len(itens),
        "redes_sem_preco": sem_preco,
        "lojas_com_poucos_itens": sorted(
            (info_poucos(k) for k in poucos),
            key=lambda x: x["mesmos_itens_aqui_centavos"] - x["mesmos_itens_na_recomendada_centavos"],
        ),
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
