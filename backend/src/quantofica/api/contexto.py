"""Contexto da casa: as lojas da cidade com distância e tipo de preço, a loja de cada rede e o seu mercado."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from psycopg import Connection

from ..regras import totais
from .identidade import Membro

JANELA_SITE = timedelta(days=3)


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
    # A loja de cada rede: a mais perto que tem preço (uma loja sem preço, como as do OpenStreetMap, não
    # representa a rede); sem nenhuma com preço, a mais perto mesmo.
    por_rede: dict[str, dict] = {}
    for lj in lojas:
        atual = por_rede.get(lj["rede"])
        if atual is None or (atual["tipo_preco"] == "sem" and lj["tipo_preco"] != "sem"):
            por_rede[lj["rede"]] = lj
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
