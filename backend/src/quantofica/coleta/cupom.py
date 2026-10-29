"""Preço pelo cupom fiscal (NFC-e): o preço que a família pagou vira o preço da loja.

É a fonte dos mercados sem site (Bistek, Atacadão, Komprão e os menores) e a mais confiável de todas (R6: cupom
vence em empate de data e vale 7 dias). Só entram:
- itens reconhecidos pelo código de barras (R1), em quantidade inteira (item pesado tem preço por quilo, R4);
- cupons de até 30 dias atrás (preço velho não diz nada sobre a prateleira de hoje);
- preços até 50% longe da mediana do produto nas outras lojas; o resto vai para revisão, como na coleta.

Cupom de loja sem CNPJ no cadastro: os preços ficam guardados num item da fila de revisão (um por CNPJ,
acumulando os cupons seguintes). Quando o CNPJ é ligado a uma loja (painel), eles são publicados.
Nada do consumidor é lido ou guardado: o app nem lê o CPF; aqui chegam só emitente, CNPJ, data e itens.
"""

import re
import unicodedata
from datetime import UTC, date, datetime, time, timedelta, timezone

from psycopg.types.json import Jsonb

from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from . import gravar
from .gravar import Preco

FUSO = timezone(timedelta(hours=-3))  # America/Sao_Paulo, sem horário de verão
VALIDADE_CUPOM = timedelta(days=30)
MAX_PRECOS_GUARDADOS = 400
EVIDENCIA = "cupom"  # sem a chave do cupom: o preço não aponta para a casa que comprou


def momento(emitido_em: date, agora: datetime) -> datetime | None:
    """Quando o preço foi visto: meio-dia do dia da compra (o cupom lido traz só a data). None se velho ou futuro."""
    quando = datetime.combine(emitido_em, time(12), FUSO).astimezone(UTC)
    if emitido_em > agora.astimezone(FUSO).date() or agora - quando > VALIDADE_CUPOM:
        return None
    return min(quando, agora)


def preco_unitario(quantidade, valor_total_centavos: int) -> int | None:
    """Preço de uma unidade, só para quantidade inteira (item pesado não tem preço por unidade)."""
    if quantidade <= 0 or quantidade != int(quantidade) or valor_total_centavos <= 0:
        return None
    return round(valor_total_centavos / int(quantidade))


def _referencias(conn, produtos: list[str], agora: datetime) -> dict[str, list[int]]:
    ref: dict[str, list[int]] = {}
    for r in conn.execute(
        """select produto_id, preco_centavos from preco_atual
           where produto_id = any(%s) and faixa = 'varejo' and observado_em >= %s""",
        (produtos, agora - timedelta(days=30)),
    ).fetchall():
        ref.setdefault(str(r["produto_id"]), []).append(r["preco_centavos"])
    return ref


def publicar(conn, loja_id: str, precos: dict[str, int], quando: datetime, agora: datetime) -> dict:
    """Publica os preços do cupom na loja; o que estiver fora da curva vai para revisão."""
    if not precos:
        return {"publicados": 0, "revisao": 0}
    referencias = _referencias(conn, list(precos), agora)
    linhas, revisao = [], 0
    for produto, preco in precos.items():
        if monitor.preco_fora_da_curva(preco, referencias.get(produto, [])):
            revisao += monitor.abrir_revisao(
                conn,
                "anomalia",
                Anomalia(f"preco:{loja_id}:{produto}", "preço do cupom mais de 50% longe da mediana de 30 dias"),
                {"preco_centavos": preco, "evidencia": EVIDENCIA, "fonte": "cupom"},
            )
            continue
        linhas.append(Preco(produto, str(loja_id), preco, "varejo", "cupom", None, None, EVIDENCIA))
    gravar.registrar(conn, linhas, quando)
    return {"publicados": len(linhas), "revisao": revisao}


def guardar_para_revisao(conn, cnpj: str, emitente: str | None, precos: dict[str, int], quando: datetime) -> None:
    """Loja sem cadastro: um item aberto por CNPJ, juntando os preços de cada cupom novo até alguém ligar a loja."""
    novos = [{"produto_id": p, "preco_centavos": v, "quando": quando.isoformat()} for p, v in precos.items()]
    aberto = conn.execute(
        """select id, proposta_agente from fila_revisao
           where tipo = 'cupom' and referencia_id = %s and status = 'aberta' for update""",
        (f"cnpj:{cnpj}",),
    ).fetchone()
    if aberto:
        p = aberto["proposta_agente"] or {}
        p["precos"] = (novos + (p.get("precos") or []))[:MAX_PRECOS_GUARDADOS]
        p["cupons"] = int(p.get("cupons") or 0) + 1
        p["emitente"] = p.get("emitente") or emitente
        conn.execute("update fila_revisao set proposta_agente = %s where id = %s", (Jsonb(p), aberto["id"]))
        return
    conn.execute(
        """insert into fila_revisao (tipo, referencia_id, motivo, prioridade, proposta_agente)
           values ('cupom', %s, %s, 2, %s)""",
        (
            f"cnpj:{cnpj}",
            f"cupom de loja sem cadastro: {emitente or 'emitente não lido'} (CNPJ {cnpj})",
            Jsonb({"cnpj": cnpj, "emitente": emitente, "cupons": 1, "precos": novos[:MAX_PRECOS_GUARDADOS]}),
        ),
    )


def ligar_cnpj(conn, item_id: str, loja_id: str, quem: str, agora: datetime) -> dict:
    """Liga o CNPJ do cupom à loja e publica os preços guardados (os de até 30 dias). Resolve o item."""
    item = conn.execute(
        "select proposta_agente as p from fila_revisao where id = %s and tipo = 'cupom' and status = 'aberta' for update",
        (item_id,),
    ).fetchone()
    if item is None or not item["p"]:
        raise LookupError("item de cupom aberto não encontrado")
    cnpj = item["p"]["cnpj"]
    dono = conn.execute("select id from loja where cnpj = %s", (cnpj,)).fetchone()
    if dono and str(dono["id"]) != str(loja_id):
        raise ValueError("este CNPJ já está ligado a outra loja")
    conn.execute("update loja set cnpj = %s where id = %s", (cnpj, loja_id))
    publicados = revisao = 0
    por_dia: dict[str, dict[str, int]] = {}
    for x in item["p"].get("precos") or []:
        quando = datetime.fromisoformat(x["quando"])
        if agora - quando <= VALIDADE_CUPOM:
            por_dia.setdefault(x["quando"], {}).setdefault(x["produto_id"], x["preco_centavos"])
    for quando, precos in sorted(por_dia.items()):  # do mais antigo para o mais novo: o atual fica com o último
        r = publicar(conn, loja_id, precos, datetime.fromisoformat(quando), agora)
        publicados += r["publicados"]
        revisao += r["revisao"]
    conn.execute(
        "update fila_revisao set status = 'resolvida', revisado_por = %s, decidido_em = now() where id = %s",
        (quem, item_id),
    )
    return {"publicados": publicados, "revisao": revisao}


def _simples(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", texto))


def lojas_candidatas(conn, emitente: str | None) -> tuple[str | None, list[dict]]:
    """Rede cujo nome aparece no emitente ("BISTEK SUPERMERCADOS LTDA" -> Bistek) e as lojas dela ainda sem CNPJ."""
    nome = _simples(emitente or "")
    if not nome:
        return None, []
    redes = conn.execute("select id, nome from rede").fetchall()
    achadas = [r for r in redes if _simples(r["nome"]) and re.search(rf"\b{re.escape(_simples(r['nome']))}\b", nome)]
    if len(achadas) != 1:
        return None, []
    rede = achadas[0]
    lojas = conn.execute(
        "select id, nome, endereco from loja where rede_id = %s and cnpj is null order by nome", (rede["id"],)
    ).fetchall()
    return rede["nome"], lojas
