"""Encartes do Fort Atacadista nas lojas de Blumenau.

O site do Fort mostra o preço de outra cidade nas páginas de produto, então não serve para Blumenau. Mas
a loja virtual publica, por loja, a lista de encartes e o PDF de cada um, numa API pública. O PDF tem
texto: dá para ler sem OCR (encarte_pdf). O encarte não tem código de barras; cada item é casado com um
produto que tem EAN (casamento): primeiro no nosso catálogo e, se não houver, na busca do Giassi e da
Cooper, que devolvem o EAN. Produto achado assim entra no catálogo e passa a ter coleta diária nas redes.

Rodar:  python -m quantofica.coleta.fort
Agenda (.github/workflows/encartes.yml): todo dia de manhã; encarte já lido é pulado.
"""

import os
import re
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from ..regras import ean as ean_util
from ..regras import tamanho as tam
from . import encarte_pdf, gravar
from .casamento import Candidato, casar, palavras
from .gravar import Preco
from .vtex import ClienteHttp

API = "https://api.fortatacadista.com.br/storefront/graphql"
# A API só responde a pedidos com a origem da própria loja virtual (o mesmo que o navegador manda). O
# agente continua identificado como coletor; não há login nem bloqueio a contornar.
CABECALHOS = {"Origin": "https://www.fortatacadista.com.br"}
LOJAS_NA_LOJA_VIRTUAL = ("1645", "1682")  # as duas lojas de Blumenau
REDE = "Fort Atacadista"
CIDADE = "Blumenau"
FUSO = ZoneInfo("America/Sao_Paulo")
# Onde procurar o EAN de um item do encarte que não está no catálogo (robots.txt permite a busca por texto).
SITES = [("Giassi", "www.giassi.com.br"), ("Cooper", "www.minhacooper.com.br")]
ESPACO = uuid.UUID("0c6a3f7e-2b1d-4e8a-9f55-31d2c4b7a901")  # o mesmo dos scripts de catálogo: mesmo EAN, mesmo produto
JANELA_HISTORICO = timedelta(days=30)
MESES = {m: i for i, m in enumerate(("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"), 1)}

_LISTA = (
    "query F($storeId: ID!) { publicViewer(storeId: $storeId) "
    "{ id flyers(storeId: $storeId, limit: 30, offset: 0) { id title } } }"
)
_PDF = (
    "query F($id: ID!, $storeId: ID!) { publicViewer(storeId: $storeId) "
    "{ id flyer(id: $id, storeId: $storeId) { pdf { url } } } }"
)


def encartes(http) -> list[dict]:
    vistos: dict[str, dict] = {}
    for loja in LOJAS_NA_LOJA_VIRTUAL:
        r = http(API, {"query": _LISTA, "variables": {"storeId": loja}}, CABECALHOS) or {}
        for e in ((r.get("data") or {}).get("publicViewer") or {}).get("flyers") or []:
            vistos.setdefault(e["id"], {**e, "loja": loja})
    return list(vistos.values())


def url_do_pdf(http, encarte: dict) -> str | None:
    r = http(API, {"query": _PDF, "variables": {"id": encarte["id"], "storeId": encarte["loja"]}}, CABECALHOS) or {}
    flyer = ((r.get("data") or {}).get("publicViewer") or {}).get("flyer") or {}
    return (flyer.get("pdf") or {}).get("url")


def validade_do_titulo(titulo: str, hoje: date) -> tuple[date | None, date] | None:
    """ "SC_Fort_Food_26 a 01_OUT_NOV_26_Regional" -> 26/10 a 01/11/2026; "..._ATE_13_DEZ_26" -> até 13/12/2026."""
    t = titulo.upper()
    m = re.search(r"(\d{1,2}) A (\d{1,2})_([A-Z]{3})(?:_([A-Z]{3}))?_(\d{2})(?!\d)", t)
    if m and m.group(3) in MESES and (m.group(4) or m.group(3)) in MESES:
        ano = 2000 + int(m.group(5))
        mes_fim, mes_inicio = MESES[m.group(4) or m.group(3)], MESES[m.group(3)]
        try:
            fim = date(ano, mes_fim, int(m.group(2)))
            inicio = date(ano - (mes_inicio > mes_fim), mes_inicio, int(m.group(1)))
        except ValueError:
            return None
        return inicio, fim
    m = re.search(r"AT[EÉ]_(\d{1,2})_([A-Z]{3})_(\d{2})(?!\d)", t)
    if m and m.group(2) in MESES:
        try:
            return None, date(2000 + int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    return None


def _do_site(p: dict) -> tuple[Candidato, str | None] | None:
    """Produto da busca de um site VTEX -> candidato (chave = GTIN) e SKU. Fora: sem EAN, granel, sem tamanho."""
    item = (p.get("items") or [{}])[0]
    nome = (item.get("nameComplete") or p.get("productName") or "").strip().rstrip(".").strip()
    try:
        gtin = ean_util.normalizar(item.get("ean") or "")
    except ValueError:
        return None
    if not ean_util.digito_verificador_ok(gtin):
        return None
    if (item.get("measurementUnit") or "un").lower() == "kg" or (item.get("unitMultiplier") or 1) != 1:
        return None
    t = tam.extrair(nome)
    if t is None:
        return None
    return Candidato(gtin, nome, (p.get("brand") or "").strip() or None, t), item.get("itemId")


def termos_de_busca(nome: str) -> str:
    return " ".join(w for w in palavras(nome) if w not in {"de", "da", "do", "c", "s", "p", "e", "ou", "sabores", "tipos"})[:80]


@dataclass
class Catalogo:
    candidatos: list[Candidato]
    categoria_do_tipo: dict[str, str]  # primeira palavra do nome -> categoria mais comum ("cafe" -> "cafe")
    rede_do_site: dict[str, str]  # nome da rede -> id


def carregar_catalogo(conn) -> Catalogo:
    linhas = conn.execute(
        """select p.id, p.nome_humano, p.marca, p.tamanho, p.unidade, p.categoria_id from produto p
           where exists (select 1 from ean e where e.produto_id = p.id and e.status = 'ok')"""
    ).fetchall()
    tipos: dict[str, Counter] = {}
    candidatos = []
    for r in linhas:
        t = tam.Tamanho(float(r["tamanho"]), r["unidade"]) if r["tamanho"] is not None and r["unidade"] else None
        candidatos.append(Candidato(str(r["id"]), r["nome_humano"], r["marca"], t))
        if p := palavras(r["nome_humano"]):
            tipos.setdefault(p[0], Counter())[r["categoria_id"]] += 1
    redes = {r["nome"]: str(r["id"]) for r in conn.execute("select id, nome from rede").fetchall()}
    return Catalogo(candidatos, {k: c.most_common(1)[0][0] for k, c in tipos.items()}, redes)


def procurar_nos_sites(conn, http, catalogo: Catalogo, nome: str, termos: str | None = None) -> list[str]:
    """Acha o item do encarte na busca dos sites; cria no catálogo o que casar. Devolve os produto_id."""
    for rede, dominio in SITES:
        url = (
            f"https://{dominio}/api/catalog_system/pub/products/search?ft={quote(termos or termos_de_busca(nome))}&_from=0&_to=19"
        )
        achados = [a for p in (http(url, None) or []) if (a := _do_site(p))]
        sku_do = {c.chave: sku for c, sku in achados}
        casados = casar(nome, [c for c, _ in achados])
        produtos = []
        for c in casados:
            categoria = catalogo.categoria_do_tipo.get(palavras(c.nome)[0])
            if categoria is None:  # tipo de produto que o catálogo ainda não tem: revisão decide a categoria
                continue
            pid = str(uuid.uuid5(ESPACO, c.chave))
            conn.execute(
                """insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values (%s, %s, %s, %s, %s, %s)
                   on conflict (id) do nothing""",
                (pid, categoria, c.nome, c.marca, c.tamanho.quantidade, c.tamanho.unidade),
            )
            conn.execute("insert into ean (codigo, produto_id) values (%s, %s) on conflict (codigo) do nothing", (c.chave, pid))
            pid = str(conn.execute("select produto_id from ean where codigo = %s", (c.chave,)).fetchone()["produto_id"])
            if sku_do.get(c.chave) and rede in catalogo.rede_do_site:
                conn.execute(
                    """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, %s, %s)
                       on conflict (rede_id, sku) do nothing""",
                    (pid, catalogo.rede_do_site[rede], sku_do[c.chave], c.nome),
                )
            catalogo.candidatos.append(Candidato(pid, c.nome, c.marca, c.tamanho))
            produtos.append(pid)
        if produtos:
            return produtos
    return []


def nome_normalizado(nome: str) -> str:
    return " ".join(palavras(nome))


def lojas_da_cidade(conn, rede_id) -> list[str]:
    return [
        str(r["id"])
        for r in conn.execute(
            "select l.id from loja l join cidade c on c.id = l.cidade_id where l.rede_id = %s and c.nome = %s", (rede_id, CIDADE)
        ).fetchall()
    ]


def gravar_precos(conn, produto, lojas, preco_centavos, condicional_centavos, agora, valido_ate, evidencia, gravados=None) -> int:
    """Preço normal (varejo) e condicional (Clube Mais ou cartão da loja, fora do total: R5) em cada loja."""
    gravados = set() if gravados is None else gravados
    faixas = [("varejo", preco_centavos)] + ([("clube", condicional_centavos)] if condicional_centavos else [])
    linhas = []
    for faixa, centavos in faixas:
        if (str(produto), faixa) in gravados:
            continue
        gravados.add((str(produto), faixa))
        linhas += [Preco(str(produto), str(loja), centavos, faixa, "encarte", None, valido_ate, evidencia) for loja in lojas]
    gravar.registrar(conn, linhas, agora)
    return len(linhas)


def validade_do_item(conn, rede_id, proposta: dict) -> date | None:
    if proposta.get("valido_ate"):
        return date.fromisoformat(proposta["valido_ate"])
    linha = conn.execute(  # itens abertos antes de a proposta guardar a validade
        "select valido_ate from encarte_lido where rede_id = %s and titulo = %s", (rede_id, proposta.get("encarte"))
    ).fetchone()
    return linha["valido_ate"] if linha else None


def ligar_item(conn, item_id: str, proposta: dict, produtos: list[str], quem: str, agora: datetime) -> tuple[int, date | None]:
    """Item do encarte (fila de revisão) -> produto(s): publica o preço se o encarte ainda vale, lembra o nome
    para os próximos encartes e resolve o item. Usado pelo painel e pelo Revisor."""
    rede_id = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()["id"]
    valido_ate = validade_do_item(conn, rede_id, proposta)
    precos = 0
    if valido_ate and valido_ate >= agora.astimezone(FUSO).date():  # vencido: só lembra o nome, não publica preço velho
        limite = datetime.combine(valido_ate, time(23, 59, 59), FUSO)
        lojas = lojas_da_cidade(conn, rede_id)
        for produto in produtos:
            precos += gravar_precos(
                conn, produto, lojas, proposta["preco_centavos"], proposta.get("condicional_centavos"),
                agora, limite, f"fort:{quem}:{item_id}",
            )  # fmt: skip
    for produto in produtos:
        conn.execute(
            "insert into nome_no_encarte (rede_id, nome, produto_id) values (%s, %s, %s) on conflict do nothing",
            (rede_id, nome_normalizado(proposta["nome"]), produto),
        )
    conn.execute(
        "update fila_revisao set status = 'resolvida', revisado_por = %s, decidido_em = now() where id = %s", (quem, item_id)
    )
    return precos, valido_ate


def rodar(conn, http, agora: datetime, ler=encarte_pdf.ler) -> dict:
    rede = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()
    if rede is None:
        raise RuntimeError(f"rede {REDE!r} não está cadastrada")
    rede_id = rede["id"]
    lojas = lojas_da_cidade(conn, rede_id)
    ligados: dict[str, list[str]] = {}
    for r in conn.execute("select nome, produto_id from nome_no_encarte where rede_id = %s", (rede_id,)).fetchall():
        ligados.setdefault(r["nome"], []).append(str(r["produto_id"]))
    lidos = {
        r["encarte_id"] for r in conn.execute("select encarte_id from encarte_lido where rede_id = %s", (rede_id,)).fetchall()
    }
    catalogo = carregar_catalogo(conn)
    historico: dict[str, list[int]] = {}
    for r in conn.execute(
        """select produto_id, preco_centavos from preco_atual where faixa = 'varejo' and observado_em >= %s
           union all
           select produto_id, preco_centavos from observacao_preco where faixa = 'varejo' and observado_em >= %s""",
        (agora - JANELA_HISTORICO, agora - JANELA_HISTORICO),
    ).fetchall():
        historico.setdefault(str(r["produto_id"]), []).append(r["preco_centavos"])

    hoje = agora.astimezone(FUSO).date()
    resumo = Counter()
    gravados: set[tuple[str, str]] = set()  # (produto, faixa): o mesmo produto em dois encartes vale o primeiro
    for e in encartes(http):
        if e["id"] in lidos:
            continue
        url = url_do_pdf(http, e)
        pdf = http.binario(url) if url else None
        if pdf is None:
            continue  # tenta de novo amanhã
        enc = ler(pdf)
        inicio, fim = (enc.inicio, enc.fim) if enc.fim else (validade_do_titulo(e["title"], hoje) or (None, None))
        if inicio and inicio > hoje:
            continue  # encarte da semana que vem: lê quando começar
        # Um encarte por vez, inteiro ou nada: se cair no meio, amanhã lê de novo sem duplicar preço.
        with conn.transaction():
            precos = 0
            if fim and fim >= hoje and lojas:
                valido_ate = datetime.combine(fim, time(23, 59, 59), FUSO)
                for item in enc.itens:
                    if item.por_kg:  # preço por quilo depende da pesagem (R4)
                        continue
                    # Nome já ligado no painel vale primeiro; depois o catálogo; depois a busca nos sites.
                    produtos = ligados.get(nome_normalizado(item.nome)) or [
                        c.chave for c in casar(item.nome, catalogo.candidatos)
                    ]
                    if not produtos:
                        produtos = procurar_nos_sites(conn, http, catalogo, item.nome)
                        resumo["produtos_novos"] += len(produtos)
                    proposta = {
                        "nome": item.nome,
                        "preco_centavos": item.preco_centavos,
                        "condicional_centavos": item.condicional_centavos,
                        "encarte": e["title"],
                        "encarte_id": e["id"],
                        "valido_ate": fim.isoformat(),
                        "pagina": item.pagina,
                    }
                    if not produtos:
                        anomalia = Anomalia(f"fort:{e['id']}:{item.nome}"[:300], "item do encarte sem produto no catálogo")
                        resumo["revisao"] += monitor.abrir_revisao(conn, "encarte", anomalia, proposta)
                        continue
                    for produto in produtos:
                        if monitor.preco_fora_da_curva(item.preco_centavos, historico.get(produto, [])):
                            anomalia = Anomalia(
                                f"preco:fort:{produto}", "preço do encarte mais de 50% longe da mediana de 30 dias"
                            )
                            resumo["revisao"] += monitor.abrir_revisao(conn, "anomalia", anomalia, proposta)
                            continue
                        precos += gravar_precos(
                            conn, produto, lojas, item.preco_centavos, item.condicional_centavos,
                            agora, valido_ate, f"fort:{e['id']}:p{item.pagina}", gravados,
                        )  # fmt: skip
            conn.execute(
                """insert into encarte_lido (rede_id, encarte_id, titulo, valido_ate, itens, precos, lido_em)
                   values (%s, %s, %s, %s, %s, %s, %s) on conflict (rede_id, encarte_id) do nothing""",
                (rede_id, e["id"], e["title"], fim, len(enc.itens), precos, agora),
            )
        resumo["encartes"] += 1
        resumo["itens"] += len(enc.itens)
        resumo["precos"] += precos
    return dict(resumo)


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "leitor_encartes") as resumo:
            r = rodar(conn, ClienteHttp(), datetime.now(UTC))
            resumo.update(r)
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
