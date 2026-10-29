"""Preços da Rede Top nas lojas de Blumenau, pela loja virtual (VipCommerce).

O site redetop.com.br leva a www.redetoponline.com.br, uma loja VipCommerce. A página é só o aplicativo; os
dados vêm da API da plataforma em services.vipcommerce.com.br (sem robots.txt: 404, ou seja, nada proibido;
o robots.txt do site da loja proíbe /busca, /produtos/ofertas etc., páginas que esta coleta não visita).
Investigado em 29/10/2026 lendo o JavaScript público do site:

1. GET /organizacoes/filiais/dominio/redetoponline.com.br -> organização (229) da rede;
2. POST /org/{org}/auth/loja/login -> token de visitante. É o que o navegador de qualquer visitante faz ao
   abrir a loja, sem cadastro: o usuário ("loja") e a chave vêm escritos no JavaScript público do site
   (environment.lojaAuthJWT), iguais para todo mundo. Não é login de cliente nem segredo;
3. GET /org/{org}/filial/1/loja/centros_distribuicoes/retiradas -> lojas físicas (cada uma é um "centro de
   distribuição" com preço e sortimento próprios), com endereço e cidade;
4. por loja: a árvore de departamentos e os produtos de cada departamento, 20 por página. Cada produto
   traz o código de barras (EAN), o preço e a oferta daquela loja.

Mapeamento loja virtual -> nossas lojas (tabela `loja`, rede 'Rede Top', Blumenau), pelo endereço:
  CD 1  Escola Agrícola   Rua Benjamin Constant 939           -> Rede Top Escola Agrícola
  CD 3  Itoupava Central  Rua Doutor Pedro Zimmermann 7155    -> Rede Top Itoupava Central · Rua Doutor Pedro Zimmermann
  CD 9  Fortaleza         Rua Francisco Vahldieck 1881        -> Rede Top Fortaleza
  CD 13 Velha Central     Rua José Reuter 961                 -> Rede Top Velha Central
As outras três lojas de Blumenau do cadastro (Tribess, Velha na General Osório e Itoupava Central na
Gustavo Zimmermann) não estão na loja virtual e ficam sem preço: preço de outra loja não é o da prateleira
delas. Loja da loja virtual em Blumenau sem par no cadastro vai para revisão.

O que fica de fora, como no Catalogador (scripts/gerar_catalogo_ampliado.py):
- código que não é GTIN de verdade (código interno curto, prefixo 2 de peso variável, dígito errado: R1);
- item vendido por quilo (preço depende da pesagem: R4);
- pack/kit com o EAN da unidade (R1: produto já no catálogo vai para revisão);
- produto novo sem tamanho legível no nome (R2) ou de um tipo que o catálogo ainda não tem.

Preço: o de prateleira. A oferta "Preço TOP" (para todos, a partir de 1 unidade) vale; oferta que pede
quantidade (leve e pague, 2ª unidade) ou é do clube fica de fora e vale o preço normal.

Rodar:  python -m quantofica.coleta.redetop
Agenda (.github/workflows/redetop.yml): todo dia às 6h de Brasília. ~600 páginas por loja, 1 por segundo.
"""

import os
import re
import sys
import unicodedata
import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from ..regras import ean as ean_util
from ..regras import tamanho as tam
from . import gravar
from .casamento import palavras
from .fort import carregar_catalogo
from .gravar import Preco
from .vtex import ClienteHttp

API = "https://services.vipcommerce.com.br/api-admin/v1"
DOMINIO = "redetoponline.com.br"
FILIAL = 1  # filial da organização na loja virtual (a única da Rede Top)
# Usuário e chave de visitante que o JavaScript público do site manda para abrir a loja (ver o topo).
USUARIO_VISITANTE = "loja"
CHAVE_VISITANTE = "df072f85df9bf7dd71b6811c34bdbaa4f219d98775b56cff9dfa5f8ca1bf8469"
REDE = "Rede Top"
CIDADE = "Blumenau"
ESPACO = uuid.UUID("0c6a3f7e-2b1d-4e8a-9f55-31d2c4b7a901")  # o mesmo dos scripts de catálogo: mesmo EAN, mesmo produto
JANELA_HISTORICO = timedelta(days=30)
# Cada EAN novo no catálogo vira busca diária nas quatro redes VTEX: o catálogo cresce aos poucos, pelos mais vendidos.
LIMITE_NOVOS_POR_RODADA = 100
LIMITE_PAGINAS = 500  # por departamento; trava de segurança contra paginação que não acaba


@dataclass
class Sessao:
    org: int
    cabecalhos: dict[str, str]

    def url(self, caminho: str) -> str:
        return f"{API}/org/{self.org}{caminho}"


@dataclass(frozen=True)
class ItemDoSite:
    gtin: str
    id_no_site: str
    nome: str
    marca: str | None
    preco_centavos: int
    preco_de_centavos: int | None
    vendidos: int


def abrir_sessao(http) -> Sessao:
    """Organização da loja e token de visitante, como o navegador faz ao abrir o site."""
    filial = http(f"{API}/organizacoes/filiais/dominio/{DOMINIO}", None) or {}
    org = ((filial.get("data") or {}).get("organizacao") or {}).get("id")
    if not org:
        raise RuntimeError("loja virtual da Rede Top não respondeu (organização)")
    cabecalhos = {"DomainKey": DOMINIO, "OrganizationId": str(org)}
    corpo = {"domain": DOMINIO, "username": USUARIO_VISITANTE, "key": CHAVE_VISITANTE}
    token = (http(f"{API}/org/{org}/auth/loja/login", corpo, cabecalhos) or {}).get("data")
    if not token:
        raise RuntimeError("loja virtual da Rede Top não deu o token de visitante")
    return Sessao(org, {**cabecalhos, "Authorization": f"Bearer {token}"})


def _simples(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", texto))


def lojas_da_cidade_no_site(http, s: Sessao) -> list[dict]:
    resp = http(s.url(f"/filial/{FILIAL}/loja/centros_distribuicoes/retiradas"), None, s.cabecalhos) or {}
    return [
        cd
        for cd in resp.get("data") or []
        if cd.get("ativo", True) and _simples((cd.get("endereco") or {}).get("cidade")) == _simples(CIDADE)
    ]


def loja_do_cd(cd: dict, lojas: list[dict]) -> str | None:
    """Nossa loja com o mesmo endereço (rua e número) do centro de distribuição."""
    e = cd.get("endereco") or {}
    alvo = _simples(f"{e.get('logradouro')} {e.get('numero')}")
    achadas = [str(loja["id"]) for loja in lojas if alvo and _simples(loja["endereco"]).startswith(alvo)]
    return achadas[0] if len(achadas) == 1 else None


def produtos_do_cd(http, s: Sessao, cd: int) -> Iterator[dict]:
    """Todos os produtos da loja, departamento por departamento, página por página."""
    base = f"/filial/{FILIAL}/centro_distribuicao/{cd}/loja/classificacoes_mercadologicas/departamentos"
    arvore = http(s.url(f"{base}/arvore"), None, s.cabecalhos) or {}
    vistos: set = set()
    for dep in arvore.get("data") or []:
        pagina, total = 1, 1
        while pagina <= min(total, LIMITE_PAGINAS):
            resp = http(s.url(f"{base}/{dep['classificacao_mercadologica_id']}/produtos?page={pagina}"), None, s.cabecalhos)
            if not resp:
                break  # falha de rede: segue no próximo departamento
            total = int((resp.get("paginator") or {}).get("total_pages") or 1)
            for p in resp.get("data") or []:
                if p.get("produto_id") not in vistos:
                    vistos.add(p.get("produto_id"))
                    yield p
            pagina += 1


def gtin_valido(codigo: str | None) -> str | None:
    """GTIN-14 de um código de barras de verdade, ou None.

    Fora: código interno da loja (curto: "93" passaria no dígito verificador), faixas de uso restrito do GS1
    (02x, 04x e 2xx no EAN-13: peso variável e numeração interna, o mesmo número é outro produto em outra
    rede) e dígito verificador errado.
    """
    digitos = re.sub(r"\D", "", codigo or "")
    if len(digitos) not in (8, 12, 13, 14):
        return None
    gtin = ean_util.normalizar(digitos)
    if not ean_util.digito_verificador_ok(gtin):
        return None
    if len(digitos) != 8 and gtin[0] == "0" and (gtin[1] == "2" or gtin[1:3] in ("02", "04")):
        return None
    return gtin


def _centavos(valor) -> int | None:
    try:
        centavos = int((Decimal(str(valor)) * 100).to_integral_value())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return centavos if centavos > 0 else None


def _quantidade(valor) -> Decimal:
    try:
        return Decimal(str(valor)) if valor not in (None, "") else Decimal(1)
    except InvalidOperation:
        return Decimal(-1)  # ilegível: não é a oferta simples


def _oferta_para_todos(o: dict) -> bool:
    """Oferta "Preço TOP": desconto direto, a partir de 1 unidade, sem clube nem faixa de quantidade."""
    rotulo = _simples(" ".join(str(o.get(k) or "") for k in ("nome", "tag", "classe_oferta")))
    return (
        str(o.get("tipo_oferta_id")) == "1"
        and _quantidade(o.get("quantidade_minima")) <= 1
        and _quantidade(o.get("quantidade_pagar")) == _quantidade(o.get("quantidade_oferta")) == 1
        and not o.get("faixas_precos")
        and not re.search(r"\b(clube|exclusiv\w*)\b", rotulo)
    )


def precos(p: dict) -> tuple[int, int | None] | None:
    """(preço, preço "de") de uma unidade na prateleira, em centavos."""
    normal = _centavos(p.get("preco"))
    if normal is None:
        return None
    o = p.get("oferta") or {}
    if p.get("em_oferta") and _oferta_para_todos(o):
        oferta = _centavos(o.get("preco_oferta"))
        if oferta and oferta < normal:
            return oferta, max(_centavos(o.get("preco_antigo")) or normal, normal)
    return normal, None


def ler_item(p: dict) -> tuple[ItemDoSite | None, str | None]:
    """Produto da API -> item comparável, ou o motivo de ficar de fora."""
    gtin = gtin_valido(p.get("codigo_barras"))
    if gtin is None:
        return None, "sem_ean"
    if (
        (p.get("unidade_sigla") or "UN").upper() == "KG"
        or p.get("possui_unidade_diferente")
        or p.get("habilitar_seletor_unidade_peso")
    ):
        return None, "granel"
    if p.get("disponivel") is False:
        return None, "indisponivel"
    valores = precos(p)
    if valores is None:
        return None, "sem_preco"
    marca = p.get("marca")
    if isinstance(marca, dict):
        marca = marca.get("descricao") or marca.get("nome")
    nome = re.sub(r"\s+", " ", p.get("descricao") or "").strip()
    return (
        ItemDoSite(
            gtin, str(p.get("produto_id")), nome, (marca or "").strip() or None, *valores, int(p.get("quantidade_vendida") or 0)
        ),
        None,
    )


def _criar_produtos(conn, catalogo, novos: dict[str, ItemDoSite], resumo: Counter) -> dict[str, str]:
    """EANs que o catálogo não tem -> produtos novos, os mais vendidos primeiro. Devolve GTIN -> produto."""
    criados: dict[str, str] = {}
    for item in sorted(novos.values(), key=lambda i: (-i.vendidos, i.gtin)):
        if len(criados) >= LIMITE_NOVOS_POR_RODADA:
            resumo["novos_adiados"] += 1
            continue
        if tam.embalagem_multipla(item.nome):
            resumo["fora_pack"] += 1
            continue
        t = tam.extrair(item.nome)
        categoria = catalogo.categoria_do_tipo.get((palavras(item.nome) or [""])[0])
        if t is None or categoria is None:  # sem tamanho (R2) ou tipo que o catálogo ainda não tem
            resumo["fora_sem_tamanho_ou_tipo"] += 1
            continue
        pid = str(uuid.uuid5(ESPACO, item.gtin))
        conn.execute(
            """insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values (%s, %s, %s, %s, %s, %s)
               on conflict (id) do nothing""",
            (pid, categoria, item.nome, item.marca, t.quantidade, t.unidade),
        )
        conn.execute("insert into ean (codigo, produto_id) values (%s, %s) on conflict (codigo) do nothing", (item.gtin, pid))
        criados[item.gtin] = pid
    return criados


def rodar(conn, http, agora: datetime) -> dict:
    rede = conn.execute("select id from rede where nome = %s", (REDE,)).fetchone()
    if rede is None:
        raise RuntimeError(f"rede {REDE!r} não está cadastrada")
    rede_id = rede["id"]
    execucao = conn.execute(
        "insert into execucao_coleta (rede_id, iniciada_em) values (%s, %s) returning id", (rede_id, agora)
    ).fetchone()["id"]
    try:
        resumo = _coletar(conn, http, agora, rede_id)
        conn.execute(
            """update execucao_coleta set terminada_em = now(), status = 'ok', eans_pedidos = %s, precos_gravados = %s,
               enviados_revisao = %s where id = %s""",
            (resumo.get("itens", 0), resumo.get("precos", 0), resumo.get("revisao", 0), execucao),
        )
        return resumo
    except Exception as erro:
        conn.execute(
            "update execucao_coleta set terminada_em = now(), status = 'falhou', erro = %s where id = %s",
            (repr(erro)[:2000], execucao),
        )
        raise


def _coletar(conn, http, agora: datetime, rede_id) -> dict:
    resumo: Counter = Counter()
    revisar: list[tuple[str, Anomalia, dict | None]] = []
    lojas = conn.execute(
        """select l.id, coalesce(l.endereco, '') as endereco from loja l join cidade c on c.id = l.cidade_id
           where l.rede_id = %s and c.nome = %s""",
        (rede_id, CIDADE),
    ).fetchall()

    # 1. Internet: a loja virtual inteira, loja por loja (nada é gravado se cair no meio).
    s = abrir_sessao(http)
    por_loja: dict[str, dict[str, ItemDoSite]] = {}  # loja -> GTIN -> item
    for cd in lojas_da_cidade_no_site(http, s):
        loja = loja_do_cd(cd, lojas)
        if loja is None:
            nome = cd.get("nome_site") or cd.get("nome")
            revisar.append(
                ("anomalia", Anomalia(f"loja:redetop:cd{cd.get('id')}", f"loja da loja virtual sem cadastro: {nome}"), None)
            )
            continue
        itens = por_loja.setdefault(loja, {})
        for p in produtos_do_cd(http, s, cd["id"]):
            resumo["itens"] += 1
            item, motivo = ler_item(p)
            if item is None:
                resumo[f"fora_{motivo}"] += 1
            else:
                itens.setdefault(item.gtin, item)
    if not por_loja:
        raise RuntimeError("nenhuma loja de Blumenau na loja virtual da Rede Top")

    # 2. Banco: catálogo, produtos novos e preços, tudo ou nada.
    produto_por_ean = {
        r["codigo"]: str(r["produto_id"])
        for r in conn.execute("select codigo, produto_id from ean where status = 'ok'").fetchall()
    }
    todos_eans = {r["codigo"] for r in conn.execute("select codigo from ean").fetchall()}
    historico: dict[str, list[int]] = {}
    for r in conn.execute(
        """select produto_id, preco_centavos from preco_atual where faixa = 'varejo' and observado_em >= %s
           union all
           select produto_id, preco_centavos from observacao_preco where faixa = 'varejo' and observado_em >= %s""",
        (agora - JANELA_HISTORICO, agora - JANELA_HISTORICO),
    ).fetchall():
        historico.setdefault(str(r["produto_id"]), []).append(r["preco_centavos"])

    with conn.transaction():
        novos: dict[str, ItemDoSite] = {}
        for itens in por_loja.values():
            for gtin, item in itens.items():
                if gtin not in todos_eans:
                    atual = novos.get(gtin)
                    novos[gtin] = item if atual is None or item.vendidos > atual.vendidos else atual
        criados = _criar_produtos(conn, carregar_catalogo(conn), novos, resumo)
        produto_por_ean.update(criados)
        resumo["produtos_novos"] = len(criados)

        no_site: dict[str, ItemDoSite] = {}
        linhas: list[Preco] = []
        for loja, itens in por_loja.items():
            for gtin, item in itens.items():
                produto = produto_por_ean.get(gtin)
                if produto is None:
                    continue
                if tam.embalagem_multipla(item.nome):  # o EAN da unidade num pack: R1, revisão decide
                    revisar.append(("ean", Anomalia(f"redetop:{gtin}", f"embalagem múltipla no site: {item.nome!r}"), None))
                    continue
                no_site.setdefault(produto, item)
                evidencia = f"vipcommerce:redetop:{item.id_no_site}"
                if monitor.preco_fora_da_curva(item.preco_centavos, historico.get(produto, [])):
                    proposta = {
                        "preco_centavos": item.preco_centavos,
                        "preco_de_centavos": item.preco_de_centavos,
                        "evidencia": evidencia,
                    }
                    revisar.append(
                        (
                            "anomalia",
                            Anomalia(f"preco:{loja}:{produto}", "preço mais de 50% longe da mediana de 30 dias"),
                            proposta,
                        )
                    )
                    continue
                linhas.append(
                    Preco(produto, loja, item.preco_centavos, "varejo", "site", item.preco_de_centavos, None, evidencia)
                )
                resumo["precos"] += 1
        # Só o que mudou vai para o histórico; o resto só é confirmado no preço atual.
        resumo["mudaram"] = gravar.registrar(conn, linhas, agora)["mudaram"]
        for produto, item in no_site.items():  # nome no site: o Vigia compara o tamanho entre redes (R1)
            conn.execute(
                """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, %s, %s)
                   on conflict (rede_id, sku) do update set nome_no_site = excluded.nome_no_site""",
                (produto, rede_id, item.id_no_site, item.nome),
            )
        vistos: set[str] = set()
        for tipo, anomalia, proposta in revisar:
            if f"{tipo}|{anomalia.referencia}" not in vistos:
                vistos.add(f"{tipo}|{anomalia.referencia}")
                resumo["revisao"] += monitor.abrir_revisao(conn, tipo, anomalia, proposta)
    resumo["lojas"] = len(por_loja)
    return dict(resumo)


def main(http=None) -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "coletor") as resumo:
            r = rodar(conn, http or ClienteHttp(), datetime.now(UTC))
            resumo[REDE] = {k: r.get(k, 0) for k in ("lojas", "precos", "revisao", "produtos_novos")}
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
