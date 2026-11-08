"""Coleta agendada: busca os preços das redes VTEX e grava as observações no banco.

Rodar uma vez:  python -m quantofica.coleta.agendador [--rede giassi]
Agenda (.github/workflows/coleta.yml): todo dia às 5h e quinta à tarde, quando saem os encartes.

Regras do que vira preço publicado:
- só o preço simulado na loja física (o de catálogo é regional, não é o da prateleira daquela loja);
- embalagem múltipla com o EAN da unidade vai para revisão (R1);
- preço que mudou mais de 50% em relação ao da própria loja vai para revisão; a coleta seguinte vendo o mesmo
  preço confirma e publica (diferença entre redes é normal e não trava nada);
- loja (seller) que a rede devolve mas não está cadastrada vai para revisão.
"""

import argparse
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..api.detalhes import gravar_ofertas
from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from ..regras.preco import Faixa
from . import gravar, por_peso
from . import redes as config
from .gravar import Preco
from .vtex import ClienteHttp, Http, PrecoColetado, Rede, coletar

# Produto que a rede ainda não tem ligado é procurado um a um (1 por segundo, até 4 pedidos cada). Quando entram
# muitos produtos de uma vez no catálogo (ex.: 1.333 do Bistek em 05/11/2026), a coleta passava das 3 horas do
# GitHub e era cancelada sem gravar. Cada rodada procura no máximo estes; o resto fica para as próximas e para o
# Catalogador de domingo, que marca o que a rede não vende.
MAX_BUSCAS_POR_RODADA = 200


@dataclass(frozen=True)
class Gravacao:
    loja_id: str
    produto_id: str
    preco_centavos: int
    preco_de_centavos: int | None
    evidencia: str


@dataclass(frozen=True)
class Revisao:
    tipo: str  # tipo da fila_revisao
    anomalia: Anomalia
    proposta: dict | None = None


@dataclass
class Plano:
    gravar: list[Gravacao] = field(default_factory=list)
    revisar: list[Revisao] = field(default_factory=list)
    skus: dict[str, tuple[str, str]] = field(default_factory=dict)  # produto -> (sku, nome no site)
    so_catalogo: int = 0
    confirmados: list[str] = field(default_factory=list)  # alertas de preço que esta coleta confirmou


def planejar(
    coletados: Iterable[PrecoColetado],
    loja_por_seller: dict[str, str],
    produto_por_ean: dict[str, str],
    anteriores: dict[tuple[str, str], int],
    pendentes: dict[str, int] | None = None,
) -> Plano:
    """Decide o que vira observação e o que vai para revisão. Não toca no banco."""
    plano = Plano()
    vistos: set[str] = set()

    def revisar_uma_vez(r: Revisao) -> None:
        chave = f"{r.tipo}|{r.anomalia.referencia}"
        if chave not in vistos:
            vistos.add(chave)
            plano.revisar.append(r)

    for c in coletados:
        produto = produto_por_ean.get(c.ean)
        if produto is None:
            continue
        plano.skus[produto] = (c.sku, c.nome_no_site)
        if c.origem == "embalagem_diferente":
            revisar_uma_vez(Revisao("ean", Anomalia(f"{c.rede}:{c.ean}", f"embalagem múltipla no site: {c.nome_no_site!r}")))
            continue
        if c.origem == "catalogo":
            plano.so_catalogo += 1
            continue
        if c.origem != "simulacao_loja" or not c.preco_centavos:
            continue
        loja = loja_por_seller.get(c.seller)
        if loja is None:
            revisar_uma_vez(Revisao("anomalia", Anomalia(f"seller:{c.rede}:{c.seller}", f"loja não cadastrada: {c.loja}")))
            continue
        evidencia = f"vtex:{c.rede}:{c.seller}:{c.sku}"
        referencia = f"preco:{loja}:{produto}"
        if (pendentes or {}).get(referencia) == c.preco_centavos:
            plano.confirmados.append(referencia)  # o mesmo preço de novo: não é erro do site
        elif monitor.preco_mudou_demais(c.preco_centavos, anteriores.get((loja, produto))):
            plano.revisar.append(
                Revisao(
                    "anomalia",
                    Anomalia(referencia, "preço mudou mais de 50% em relação ao da própria loja"),
                    {"preco_centavos": c.preco_centavos, "preco_de_centavos": c.preco_de_centavos, "evidencia": evidencia},
                )
            )
            continue
        plano.gravar.append(Gravacao(loja, produto, c.preco_centavos, c.preco_de_centavos, evidencia))
    return plano


def _rodar_rede(conn: psycopg.Connection, http: Http, rede: Rede, agora: datetime) -> dict:
    nome = config.NOME_NO_BANCO[rede.id]
    faixa = config.FAIXA.get(rede.id, Faixa.VAREJO)
    linha = conn.execute("select id from rede where nome = %s", (nome,)).fetchone()
    if linha is None:
        raise RuntimeError(f"rede {nome!r} não está cadastrada")
    rede_id = linha["id"]
    execucao = conn.execute(
        "insert into execucao_coleta (rede_id, iniciada_em) values (%s, %s) returning id", (rede_id, agora)
    ).fetchone()["id"]

    try:
        produto_por_ean = {
            r["codigo"]: str(r["produto_id"])
            for r in conn.execute("select codigo, produto_id from ean where status = 'ok'").fetchall()
        }
        loja_por_seller = {
            r["seller_id"]: str(r["id"])
            for r in conn.execute(
                "select id, seller_id from loja where rede_id = %s and seller_id is not null", (rede_id,)
            ).fetchall()
        }
        # Referência para a trava: o preço da própria loja (e os alertas que esperam a confirmação da coleta).
        anteriores = monitor.precos_anteriores(conn, list(loja_por_seller.values()), faixa)
        pendentes = monitor.precos_pendentes(conn)

        # Cache: o SKU de cada produto nesta rede e o que a rede não vende. O Catalogador refaz os dois toda semana;
        # a janela de 10 dias cobre um atraso dele sem a coleta sair procurando milhares de produtos um a um.
        conhecidos = {
            r["codigo"]: (r["sku"], r["nome_no_site"] or "")
            for r in conn.execute(
                """select distinct on (e.codigo) e.codigo, pr.sku, pr.nome_no_site
                   from produto_na_rede pr join ean e on e.produto_id = pr.produto_id where pr.rede_id = %s""",
                (rede_id,),
            ).fetchall()
        }
        ausentes = {
            r["codigo"]
            for r in conn.execute(
                "select codigo from ean_ausente where rede_id = %s and verificado_em > %s", (rede_id, agora - timedelta(days=10))
            ).fetchall()
        }
        nao_encontrados: list[str] = []
        pedir = [e for e in produto_por_ean if e not in ausentes]
        adiados = set([e for e in pedir if e not in conhecidos][MAX_BUSCAS_POR_RODADA:])
        if adiados:
            print(f"{rede.id}: {len(adiados)} produtos novos ficam para as próximas coletas", flush=True)
        coletados = coletar(http, rede, [e for e in pedir if e not in adiados], conhecidos, nao_encontrados)
        plano = planejar(coletados, loja_por_seller, produto_por_ean, anteriores, pendentes)

        with conn.transaction():
            for produto, (sku, nome_site) in plano.skus.items():
                conn.execute(
                    """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, %s, %s)
                       on conflict (rede_id, sku) do update set nome_no_site = excluded.nome_no_site""",
                    (produto, rede_id, sku, nome_site),
                )
            # Só o que mudou vai para o histórico; o resto só é confirmado no preço atual.
            gravados = gravar.registrar(
                conn,
                [
                    Preco(g.produto_id, g.loja_id, g.preco_centavos, faixa, "site", g.preco_de_centavos, None, g.evidencia)
                    for g in plano.gravar
                ],
                agora,
            )
            for codigo in nao_encontrados:
                conn.execute(
                    """insert into ean_ausente (rede_id, codigo, verificado_em) values (%s, %s, %s)
                       on conflict (rede_id, codigo) do update set verificado_em = excluded.verificado_em""",
                    (rede_id, codigo, agora),
                )
            abertas = sum(monitor.abrir_revisao(conn, r.tipo, r.anomalia, r.proposta) for r in plano.revisar)
            monitor.confirmar_precos(conn, plano.confirmados, "coletor")
            conn.execute(
                """update execucao_coleta set terminada_em = now(), status = 'ok', eans_pedidos = %s, precos_gravados = %s,
                   enviados_revisao = %s where id = %s""",
                (len(produto_por_ean), len(plano.gravar), abertas, execucao),
            )
        return {
            "rede": nome,
            "precos": len(plano.gravar),
            "mudaram": gravados["mudaram"],
            "revisao": abertas,
            "so_catalogo": plano.so_catalogo,
        }
    except Exception as erro:
        conn.execute(
            "update execucao_coleta set terminada_em = now(), status = 'falhou', erro = %s where id = %s",
            (repr(erro)[:2000], execucao),
        )
        raise


def main(argv: list[str] | None = None, http: Http | None = None) -> int:
    args = _args(argv)
    http = http or ClienteHttp()
    falhas = 0
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "coletor") as resumo:
            for rede in config.REDES_VTEX:
                if args.rede and rede.id != args.rede:
                    continue
                try:
                    r = _rodar_rede(conn, http, rede, datetime.now(UTC))
                    resumo[r["rede"]] = {"precos": r["precos"], "revisao": r["revisao"]}
                    print(r)
                except Exception as erro:  # uma rede fora do ar não impede as outras
                    falhas += 1
                    resumo[config.NOME_NO_BANCO[rede.id]] = {"falhou": repr(erro)[:300]}
                    print(f"{rede.id}: falhou: {erro!r}", file=sys.stderr)
                    continue
                try:  # itens por quilo: o preço do quilo dos genéricos ligados (coleta/por_peso.py)
                    k = por_peso.coletar(conn, http, rede, datetime.now(UTC))
                    resumo[r["rede"]]["por_kg"] = k["precos"]
                    print(k)
                except Exception as erro:
                    falhas += 1
                    resumo[r["rede"]]["por_kg"] = {"falhou": repr(erro)[:300]}
                    print(f"{rede.id}: por quilo falhou: {erro!r}", file=sys.stderr)
        with rodada(conn, "vigia") as resumo:
            achadas = monitor.verificar(conn, datetime.now(UTC))
            resumo["apontados"] = len(achadas)
            for a in achadas:
                print(f"anomalia: {a.referencia}: {a.motivo}", file=sys.stderr)
        try:  # ofertas prontas para a tela (a conta levava 12 a 26 s a cada abertura do app)
            print(f"ofertas calculadas: {gravar_ofertas(conn, datetime.now(UTC))}")
        except Exception as erro:
            falhas += 1
            print(f"ofertas: falhou: {erro!r}", file=sys.stderr)
    return 1 if falhas else 0


def _args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Coleta de preços das redes VTEX de Blumenau")
    p.add_argument("--rede", choices=[r.id for r in config.REDES_VTEX], help="coletar só esta rede")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
