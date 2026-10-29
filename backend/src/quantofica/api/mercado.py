"""O "seu mercado" da casa, a busca inteligente e o resumo do Início.

Tudo começa pelo seu mercado: o que a casa escolheu ou, sem escolha, o mais perto com preço do site.
Outro mercado só aparece quando faz diferença, sempre com a distância.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ..regras import nome as regra_nome
from ..regras import totais
from .banco import Conexao
from .catalogo import catalogo
from .identidade import Membro, MembroAtual
from .precos import precos_atuais

router = APIRouter(prefix="/v1", tags=["seu mercado"])

PERTO_KM = 5.0
JANELA_SITE = timedelta(days=3)


# ---------- contexto da casa ----------


@dataclass
class Contexto:
    bairro: dict
    lojas: list[dict]  # lojas da cidade com distancia_km e tipo_preco
    por_rede: dict[str, dict]  # a loja mais perto de cada rede
    seu_mercado: dict | None
    automatico: bool


def contexto(conn: Connection, membro: Membro) -> Contexto:
    casa = conn.execute("select bairro_id, config from casa where id = %s", (membro.casa_id,)).fetchone()
    if not casa or not casa["bairro_id"]:
        raise HTTPException(422, "a casa ainda não escolheu o bairro")
    bairro = conn.execute(
        "select id, nome, cidade_id, lat_centro, lon_centro from bairro where id = %s", (casa["bairro_id"],)
    ).fetchone()
    lojas = conn.execute(
        """select l.id, l.nome, l.lat, l.lon, r.nome as rede, b.nome as bairro
           from loja l join rede r on r.id = l.rede_id left join bairro b on b.id = l.bairro_id
           where l.cidade_id = %s and l.lat is not null""",
        (bairro["cidade_id"],),
    ).fetchall()
    fontes: dict[str, set] = {}
    for r in conn.execute(
        """select distinct loja_id, fonte from observacao_preco
           where loja_id = any(%s) and observado_em >= %s and (valido_ate is null or valido_ate >= now())""",
        ([lj["id"] for lj in lojas], datetime.now(UTC) - JANELA_SITE),
    ).fetchall():
        fontes.setdefault(str(r["loja_id"]), set()).add(r["fonte"])
    for lj in lojas:
        lj["distancia_km"] = totais.distancia_km(bairro["lat_centro"], bairro["lon_centro"], lj["lat"], lj["lon"])
        f = fontes.get(str(lj["id"]), set())
        lj["tipo_preco"] = "site" if "site" in f else "encarte" if "encarte" in f else "sem"
    lojas.sort(key=lambda lj: lj["distancia_km"])
    por_rede: dict[str, dict] = {}
    for lj in lojas:
        por_rede.setdefault(lj["rede"], lj)
    escolhido = (casa["config"] or {}).get("meu_mercado")
    seu = next((lj for lj in lojas if str(lj["id"]) == escolhido), None)
    if seu is not None:
        por_rede[seu["rede"]] = seu  # o seu mercado representa a rede dele
    automatico = seu is None
    if seu is None:
        seu = next((lj for lj in lojas if lj["tipo_preco"] == "site"), None)
    return Contexto(bairro, lojas, por_rede, seu, automatico)


def loja_publica(lj: dict | None) -> dict | None:
    if lj is None:
        return None
    return {
        "loja_id": lj["id"],
        "rede": lj["rede"],
        "nome": lj["nome"],
        "bairro": lj["bairro"],
        "distancia_km": round(lj["distancia_km"], 1),
        "tipo_preco": lj["tipo_preco"],
    }


@router.get("/mercados")
def mercados(membro: MembroAtual, conn: Conexao):
    """Lojas perto da casa, com distância e o tipo de preço que temos (site todo dia, encarte ou ainda nada)."""
    ctx = contexto(conn, membro)
    return {
        "seu_mercado": loja_publica(ctx.seu_mercado),
        "automatico": ctx.automatico,
        "lojas": [loja_publica(lj) for lj in ctx.lojas],
    }


class EscolhaMercado(BaseModel):
    loja_id: UUID | None = None  # None = escolher sempre o mais perto


@router.put("/casa/mercado")
def escolher_mercado(escolha: EscolhaMercado, membro: MembroAtual, conn: Conexao):
    if escolha.loja_id is None:
        conn.execute("update casa set config = config - 'meu_mercado' where id = %s", (membro.casa_id,))
    else:
        if not conn.execute("select 1 from loja where id = %s", (escolha.loja_id,)).fetchone():
            raise HTTPException(404, "loja não encontrada")
        conn.execute(
            "update casa set config = config || %s where id = %s", (Jsonb({"meu_mercado": str(escolha.loja_id)}), membro.casa_id)
        )
    return mercados(membro, conn)


def preco_por_unidade(centavos: int, tamanho, unidade: str | None) -> str | None:
    """R$ por kg, por litro ou por unidade: o que deixa comparar tamanhos diferentes."""
    if not tamanho or not unidade or not centavos:
        return None
    q = float(tamanho)
    if q <= 0:
        return None
    if unidade == "g":
        valor, sufixo = centavos * 1000 / q, "kg"
    elif unidade == "ml":
        valor, sufixo = centavos * 1000 / q, "l"
    else:
        valor, sufixo = centavos / q, "un"
    return f"R$ {valor / 100:.2f}/{sufixo}".replace(".", ",")


def _valor_por_unidade(centavos: int, tamanho, unidade) -> float:
    if not tamanho or not centavos:
        return float("inf")
    return centavos / float(tamanho) * (1000 if unidade in ("g", "ml") else 1)


def tamanho_texto(tamanho, unidade) -> str | None:
    if tamanho is None or not unidade:
        return None
    q = float(tamanho)
    if unidade in ("g", "ml") and q >= 1000:
        return f"{q / 1000:g}".replace(".", ",") + (" kg" if unidade == "g" else " l")
    return f"{q:g}".replace(".", ",") + f" {unidade}"


# ---------- busca inteligente ----------

PARE = {"de", "da", "do", "das", "dos", "e", "com", "para", "em", "o", "a"}
NEGACAO = {"zero", "sem", "0", "diet", "light"}


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _norm(texto).replace("-", " "))


def _casa_termo(termo: str, palavras: list[str]) -> list[int]:
    return [i for i, w in enumerate(palavras) if w.startswith(termo)]


def avaliar(produto: dict, termos: list[str]) -> tuple[int, bool] | None:
    """(pontos, só_negado) se o produto bate com todos os termos; None se não bate.

    "Só negado": o termo aparece só depois de "zero"/"sem" ("Refrigerante Zero Açúcar" numa busca por açúcar).
    """
    nome = _palavras(produto["nome"])
    marca = _palavras(produto["marca"] or "")
    curto = _palavras(produto["nome_curto"])
    pontos, negado = 0, True
    for t in termos:
        pos = _casa_termo(t, nome)
        if not pos and not _casa_termo(t, marca):
            return None
        if any(not (set(nome[max(0, i - 3) : i]) & NEGACAO) for i in pos) or _casa_termo(t, marca):
            negado = False
        if _casa_termo(t, curto):
            pontos += 2
        if _casa_termo(t, marca):
            pontos += 1
    if curto and curto[0].startswith(termos[0]):
        pontos += 4
    return pontos, negado and not (set(termos) & NEGACAO)


@router.get("/busca")
def busca(
    membro: MembroAtual,
    conn: Conexao,
    q: Annotated[str, Query(max_length=60)] = "",
    onde: Literal["seu", "perto", "todos"] = "todos",
    tipo: Annotated[str | None, Query(max_length=60)] = None,
    tamanho: Annotated[str | None, Query(max_length=20)] = None,
    marca: Annotated[str | None, Query(max_length=60)] = None,
    rede: Annotated[list[str] | None, Query(max_length=10)] = None,
    oferta: bool = False,
    mostrar_zero: bool = False,
    ordem: Literal["relevancia", "preco", "preco_unidade", "desconto"] = "relevancia",
    limite: Annotated[int, Query(ge=1, le=100)] = 40,
):
    """Busca que entende o tipo: "açúcar" traz açúcar (não "zero açúcar"), primeiro os grupos "qualquer marca",
    depois marcas e tamanhos com o preço no seu mercado; filtros com contagem."""
    termos = [t for t in _palavras(q) if t not in PARE]
    ctx = contexto(conn, membro)
    cat = catalogo(conn)
    escondidos = 0
    achados = []
    for p in cat["produtos"].values():
        if not termos:
            achados.append((0, p))
            continue
        r = avaliar(p, termos)
        if r is None:
            continue
        pontos, so_negado = r
        if so_negado and not mostrar_zero:
            escondidos += 1
            continue
        achados.append((pontos, p))

    seu = ctx.seu_mercado
    lojas_consideradas = {str(lj["id"]): lj for lj in ctx.por_rede.values()}
    if seu:
        lojas_consideradas[str(seu["id"])] = seu
    agora = datetime.now(UTC)
    atuais = precos_atuais(conn, list(lojas_consideradas), [p["id"] for _, p in achados], agora) if achados else {}

    linhas = []
    for pontos, p in achados:
        precos = [(lid, ex) for lid, por in atuais.items() for pid, ex in por.items() if pid == p["id"]]
        no_seu = next((ex for lid, ex in precos if seu and lid == str(seu["id"])), None)
        perto = [(lid, ex) for lid, ex in precos if lojas_consideradas[lid]["distancia_km"] <= PERTO_KM]
        mais_barato = min(precos, key=lambda x: x[1].observacao.preco_centavos, default=None)
        principal = (
            no_seu
            or (min((ex for _, ex in perto), key=lambda e: e.observacao.preco_centavos, default=None))
            or (mais_barato[1] if mais_barato else None)
        )
        loja_principal = seu if no_seu else next((lojas_consideradas[lid] for lid, ex in precos if ex is principal), None)
        o = principal.observacao if principal else None
        desconto = (
            round(100 * (o.preco_de_centavos - o.preco_centavos) / o.preco_de_centavos)
            if o and o.preco_de_centavos and o.preco_de_centavos > o.preco_centavos
            else 0
        )
        longe = None
        if no_seu and mais_barato and mais_barato[1].observacao.preco_centavos < no_seu.observacao.preco_centavos:
            lj = lojas_consideradas[mais_barato[0]]
            longe = {
                "rede": lj["rede"],
                "loja": lj["nome"],
                "distancia_km": round(lj["distancia_km"], 1),
                "preco_centavos": mais_barato[1].observacao.preco_centavos,
            }
        linhas.append(
            {
                "pontos": pontos,
                "produto_id": p["id"],
                "nome": p["nome"],
                "nome_curto": p["nome_curto"],
                "marca": p["marca"],
                "tamanho": p["tamanho"],
                "unidade": p["unidade"],
                "tamanho_texto": tamanho_texto(p["tamanho"], p["unidade"]),
                "categoria": p["categoria"],
                "grupo": p["grupo"],
                "preco_centavos": o.preco_centavos if o else None,
                "preco_por_unidade": preco_por_unidade(o.preco_centavos, p["tamanho"], p["unidade"]) if o else None,
                "desconto_pct": desconto,
                "no_seu_mercado": no_seu is not None,
                "onde": loja_publica(loja_principal),
                "mais_barato_longe": longe,
                "_redes": {lojas_consideradas[lid]["rede"] for lid, _ in precos},
                "_perto": bool(perto),
            }
        )

    def passa(linha, sem=None) -> bool:
        if onde == "seu" and not linha["no_seu_mercado"]:
            return False
        if onde == "perto" and not linha["_perto"]:
            return False
        if rede and not (linha["_redes"] & set(rede)):
            return False
        if oferta and not linha["desconto_pct"]:
            return False
        if tipo and sem != "tipo" and linha["nome_curto"] != tipo:
            return False
        if tamanho and sem != "tamanho" and linha["tamanho_texto"] != tamanho:
            return False
        if marca and sem != "marca" and linha["marca"] != marca:
            return False
        return True

    filtradas = [linha for linha in linhas if passa(linha)]

    def contar(campo):
        cont: dict = {}
        for linha in linhas:
            if passa(linha, sem=campo) and linha[{"tipo": "nome_curto", "tamanho": "tamanho_texto", "marca": "marca"}[campo]]:
                v = linha[{"tipo": "nome_curto", "tamanho": "tamanho_texto", "marca": "marca"}[campo]]
                cont[v] = cont.get(v, 0) + 1
        return [{"valor": k, "n": n} for k, n in sorted(cont.items(), key=lambda kv: -kv[1])][:12]

    chave = {
        "relevancia": lambda x: (-x["pontos"], not x["no_seu_mercado"], x["preco_centavos"] is None, x["preco_centavos"] or 0),
        "preco": lambda x: (x["preco_centavos"] is None, x["preco_centavos"] or 0),
        "preco_unidade": lambda x: _valor_por_unidade(x["preco_centavos"], x["tamanho"], x["unidade"]),
        "desconto": lambda x: (-x["desconto_pct"], x["preco_centavos"] or 0),
    }[ordem]
    filtradas.sort(key=chave)

    # "Qualquer marca": grupos com mais de uma marca, do mais relevante para o menos
    grupos = []
    vistos = set()
    for linha in sorted(filtradas, key=lambda x: (-x["pontos"], x["preco_centavos"] or 10**9)):
        g = linha["grupo"]
        if not g or g in vistos or len(cat["grupos"].get(g, [])) < 2:
            continue
        vistos.add(g)
        membros = [x for x in linhas if x["grupo"] == g and x["preco_centavos"]]
        com_preco_seu = [x for x in membros if x["no_seu_mercado"]]
        base = com_preco_seu or membros
        if not base:
            continue
        barato = min(base, key=lambda x: x["preco_centavos"])
        grupos.append(
            {
                "grupo": g,
                "nome": f"{linha['nome_curto']} · {linha['tamanho_texto']}",
                "produto_id": barato["produto_id"],
                "marcas": len({x["marca"] for x in base}),
                "no_seu_mercado": bool(com_preco_seu),
                "a_partir_centavos": barato["preco_centavos"],
                "marca_mais_barata": barato["marca"],
                "em_oferta": barato["desconto_pct"] > 0,
                "categoria": linha["categoria"],
                "tamanho_texto": linha["tamanho_texto"],
            }
        )
        if len(grupos) == 3:
            break

    for linha in filtradas:
        linha.pop("_redes", None)
        linha.pop("_perto", None)
    return {
        "termo": q,
        "escondidos_zero": escondidos,
        "seu_mercado": loja_publica(seu),
        "grupos": grupos if termos else [],
        "total": len(filtradas),
        "produtos": filtradas[:limite],
        "filtros": {
            "tipos": contar("tipo"),
            "tamanhos": contar("tamanho"),
            "marcas": contar("marca"),
            "redes": sorted(
                [
                    {"rede": r, "distancia_km": round(lj["distancia_km"], 1), "tipo_preco": lj["tipo_preco"]}
                    for r, lj in ctx.por_rede.items()
                ],
                key=lambda x: x["distancia_km"],
            ),
        },
    }


# ---------- Início ----------


@router.get("/inicio")
def inicio(membro: MembroAtual, conn: Conexao):
    """Tudo o que a tela inicial mostra, numa chamada: seu mercado, o que está acabando, encarte, economia e status."""
    ctx = contexto(conn, membro)
    cat = catalogo(conn)
    agora = datetime.now(UTC)
    lista = conn.execute("select id from lista where casa_id = %s order by nome limit 1", (membro.casa_id,)).fetchone()

    # Acabando em casa: produtos que a casa pôs na lista mais de uma vez nos últimos 90 dias e não estão nela agora
    acabando = []
    if lista:
        na_lista = {
            str(r["produto_id"])
            for r in conn.execute(
                """select i.produto_id from item_lista i where i.lista_id = %s and i.produto_id is not null
                   and not i.comprado
                   and not exists (select 1 from operacao_lista o where o.item_id = i.id and o.tipo = 'remover')""",
                (lista["id"],),
            ).fetchall()
        }
        for r in conn.execute(
            """select i.produto_id, count(*) as vezes from item_lista i
               join operacao_lista o on o.item_id = i.id and o.tipo = 'criar'
               where i.lista_id = %s and i.produto_id is not null and o.feita_em >= %s
               group by i.produto_id having count(*) >= 2 order by count(*) desc limit 8""",
            (lista["id"], agora - timedelta(days=90)),
        ).fetchall():
            pid = str(r["produto_id"])
            if pid in na_lista or pid not in cat["produtos"]:
                continue
            p = cat["produtos"][pid]
            acabando.append(
                {
                    "produto_id": pid,
                    "nome_curto": p["nome_curto"],
                    "tamanho_texto": tamanho_texto(p["tamanho"], p["unidade"]),
                    "vezes": r["vezes"],
                }
            )

    # Encartes válidos de lojas perto
    encartes = []
    for r in conn.execute(
        """select r.nome as rede, max(e.valido_ate) as valido_ate, sum(e.itens) as itens
           from encarte_lido e join rede r on r.id = e.rede_id
           where e.valido_ate >= %s group by r.nome""",
        ((agora - timedelta(hours=3)).date(),),
    ).fetchall():
        lj = ctx.por_rede.get(r["rede"])
        if lj:
            encartes.append(
                {"rede": r["rede"], "loja": loja_publica(lj), "valido_ate": r["valido_ate"], "itens": int(r["itens"] or 0)}
            )

    economia = conn.execute(
        """select coalesce(sum(economia_centavos), 0) as total, count(*) as compras from cupom_lido
           where casa_id = %s and data_compra >= date_trunc('month', now())""",
        (membro.casa_id,),
    ).fetchone()
    atividade = []
    if lista:
        for r in conn.execute(
            """select o.tipo, o.feita_em, m.apelido, coalesce(p.nome_humano, i.categoria_id) as item, p.marca
               from operacao_lista o join item_lista i on i.id = o.item_id left join produto p on p.id = i.produto_id
               left join membro m on m.id = o.membro_id
               where o.lista_id = %s and o.membro_id is distinct from %s and o.tipo in ('criar', 'marcar', 'remover')
               order by o.feita_em desc limit 5""",
            (lista["id"], membro.id),
        ).fetchall():
            atividade.append(
                {
                    "quem": r["apelido"],
                    "tipo": r["tipo"],
                    "item": regra_nome.nome_curto(r["item"], r["marca"]) if r["item"] else "um item",
                    "quando": r["feita_em"],
                }
            )
    ultima = conn.execute("select max(terminada_em) as quando from execucao_coleta where status = 'ok'").fetchone()["quando"]
    return {
        "seu_mercado": loja_publica(ctx.seu_mercado),
        "automatico": ctx.automatico,
        "lista_id": lista["id"] if lista else None,
        "acabando": acabando[:6],
        "encartes": encartes,
        "economia_mes_centavos": int(economia["total"]),
        "compras_no_mes": economia["compras"],
        "atividade": atividade,
        "status": {
            "conferido_em": ultima,
            "redes": sum(1 for lj in ctx.por_rede.values() if lj["tipo_preco"] != "sem"),
            "produtos": len(cat["produtos"]),
        },
        "basicos": _basicos(cat),
    }


BASICOS = ["arroz", "feijao carioca", "cafe", "leite integral", "acucar refinado", "oleo soja", "ovos", "papel higienico"]


def _basicos(cat: dict) -> list[dict]:
    """Os básicos da despensa como grupos "qualquer marca" (para a casa nova começar a lista com um toque)."""
    saida = []
    for alvo in BASICOS:
        candidatos = [
            p
            for p in cat["produtos"].values()
            if p["grupo"] and _norm(p["nome_curto"]).startswith(alvo) and len(cat["grupos"][p["grupo"]]) >= 2
        ]
        if not candidatos:
            continue
        # o grupo com mais marcas é o "padrão" da família (ex.: arroz 5 kg, leite 1 l)
        g = max({p["grupo"] for p in candidatos}, key=lambda g: len(cat["grupos"][g]))
        p = cat["produtos"][cat["grupos"][g][0]]
        saida.append(
            {"grupo": g, "produto_id": p["id"], "nome": f"{p['nome_curto']} {tamanho_texto(p['tamanho'], p['unidade'])}"}
        )
    return saida
