"""Catalogador v2: o catálogo de mercado inteiro das redes com site e o SKU de cada produto em cada rede.

O v1 (scripts/gerar_catalogo_ampliado.py) pegava os 20 mais vendidos de cada subcategoria do Giassi. Este
percorre todas as categorias de mercado (não bazar, eletro, roupa...) do Giassi, da Cooper e do Angeloni,
50 produtos por página, 1 requisição por segundo, respeitando o robots.txt:
- Giassi, Cooper e Sam's: API pública de catálogo (fq=C:/departamento/categoria/);
- Angeloni: o robots.txt proíbe fq=, então vai pela busca inteligente da categoria.

Para cada produto com código de barras válido:
- produto que já existe (mesmo EAN, R1): só liga o SKU da rede (a coleta diária não precisa procurar);
- produto novo: entra no catálogo se estiver à venda, não for granel nem pack, tiver tamanho no nome (R2) e
  cair numa das nossas categorias. Sam's não cria produto (catálogo nacional, embalagens de clube), só liga SKU.
Com a rede percorrida inteira, o que o catálogo tem e a rede não vende vai para ean_ausente: a coleta diária
não procura, um a um, milhares de produtos que a rede não tem.

Rodar:  python -m quantofica.coleta.catalogador [--rede giassi] [--salvar itens.json] [--de itens.json]
Agenda (.github/workflows/catalogador.yml): domingo de madrugada, antes da coleta.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..regras import ean as ean_util
from ..regras import tamanho
from . import redes as config
from .vtex import BloqueadoPeloRobots, ClienteHttp, Http, Rede

POR_PAGINA = 50
LIMITE_CONSULTA = 2500  # a API VTEX não passa do item 2.500 de uma mesma consulta: categoria maior desce um nível
BUSCA_INTELIGENTE = {"angeloni"}
SO_LIGA_SKU = {"sams"}
ESPACO = uuid.UUID("0c6a3f7e-2b1d-4e8a-9f55-31d2c4b7a901")  # o mesmo dos catálogos anteriores: mesmo EAN, mesmo id


@dataclass(frozen=True)
class ItemDoSite:
    rede: str
    sku: str
    gtin: str | None  # None: sem código de barras ou código inválido
    nome: str
    marca: str | None
    caminho: str  # "/Mercearia/Arroz/"
    granel: bool
    disponivel: bool


def _simples(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


# ---------- categorias ----------

# Departamentos fora do mercado do dia a dia.
FORA = re.compile(
    r"\b(pet|racao|utensilio|eletro|vestuario|ferramenta|lazer|papelaria|festa|brinquedo|bazar|moda|cama|esporte|"
    r"movei|decorac|utilidade|informatica|sazonal|importado|membership|jardinag|automotiv|z: category)|^casa$"
)

# O começo do nome diz o que é o produto com mais certeza que a seção do site (o Giassi põe requeijão junto
# dos pães; a Cooper põe leite zero lactose em "Vida e Saúde").
POR_NOME = [
    (
        r"(leite (uht|integral|desnatado|semidesnatado|zero|em po|longa|condensado|fermentado|pasteurizado)|bebida lactea|"
        r"iogurte|queijo|requeijao|manteiga|margarina|creme de leite|nata|coalhada|petit suisse|presunto|apresuntado|"
        r"mortadela|salame|peito de peru|blanquet)",
        "laticinios",
    ),
    (r"(cafe|cha|cappuccino|capuccino|erva mate|filtro de (papel|cafe))\b", "cafe"),
    (
        r"(refrigerante|suco|nectar|agua (mineral|tonica|de coco|com gas|sem gas)|cerveja|chopp|vinho|espumante|vodka|"
        r"whisky|cachaca|gin|rum|licor|energetico|isotonico|bebida)\b",
        "bebidas",
    ),
    (
        r"(chocolate|biscoito|bolacha|bala|bombom|wafer|goma de mascar|chiclete|pirulito|sobremesa|doce|pacoca|"
        r"marshmallow|gelatina|pudim|cookie|rosquinha|tortinha|confeito)\b",
        "doces",
    ),
    (
        r"(arroz|feijao|lentilha|grao de bico|ervilha (seca|partida)|milho de pipoca|aveia|macarrao|espaguete|talharim|"
        r"massa (para lasanha|com ovos|grano duro|de semola))\b",
        "graos",
    ),
    (
        r"(papel higienico|fralda|absorvente|sabonete|shampoo|condicionador|creme dental|escova dental|enxaguante|"
        r"fio dental|desodorante|antitranspirante|hidratante|protetor solar|aparelho de barbear|cotonete|haste|"
        r"lenco umedecido|toalha umedecida|creme para pentear)\b",
        "higiene",
    ),
    (
        r"(detergente|lava[ -]loucas|lava[ -]roupas?|sabao|amaciante|desinfetante|agua sanitaria|alvejante|limpador|"
        r"multiuso|esponja|saco (de|para) lixo|papel toalha|toalha de papel|guardanapo|papel aluminio|filme pvc|"
        r"inseticida|lustra moveis|tira manchas|saponaceo|odorizador)\b",
        "limpeza",
    ),
    (r"(pao|paes|bisnaguinha|torrada|bolo|panetone|chocotone|croissant|cuca)\b", "padaria"),
    (r"ovos?\b", "hortifruti"),
    (r"(papinha|composto lacteo|formula infantil|cereal infantil|mucilon)\b", "mercearia"),
]
POR_NOME = [(re.compile(r"^" + p), c) for p, c in POR_NOME]

# Seção do site, da mais funda para a mais rasa: a primeira que casar decide.
POR_SECAO = [
    (r"lacteo|laticin|frios|iogurte|queijo|leite", "laticinios"),
    (r"bebida|adega|vinho|cervej|destilad|refrigerante|suco|\baguas?\b(?! sanit)", "bebidas"),
    (r"\bcafe|\bchas?\b", "cafe"),
    (r"doce|biscoito|chocolate|\bbala|guloseima|sobremesa|bomboniere|goma", "doces"),
    (r"arroz|feijao|grao|massa|lentilha", "graos"),
    (r"hortifruti|fruta|verdura|legume", "hortifruti"),
    (r"padaria|\bpaes|\bpao", "padaria"),
    (r"limpeza|descartave|lavanderia|lava roupa", "limpeza"),
    (r"higiene|beleza|perfumaria|fralda|bebe", "higiene"),
    (
        r"carne|aves|peixe|peixaria|acougue|congelad|churrasco|mercearia|aliment|matina|conserva|tempero|molho|oleo|"
        r"azeite|farin|acucar|enlatad|snack|salgad|sopa|suplement|diet|integra|organic|lactose|gluten|saudave|"
        r"especiais|oriental|mexican|cereal|condimento|vinagre|vida e saude",
        "mercearia",
    ),
]
POR_SECAO = [(re.compile(p), c) for p, c in POR_SECAO]


def categoria(caminho: str, nome: str) -> str | None:
    """Nossa categoria para o produto, ou None quando ele não é de mercado (bazar, pet, roupa...)."""
    secoes = [_simples(s) for s in caminho.strip("/").split("/") if s]
    if not secoes or FORA.search(secoes[0]):
        return None
    n = _simples(nome)
    for padrao, destino in POR_NOME:
        if padrao.search(n):
            return destino
    for secao in reversed(secoes):
        for padrao, destino in POR_SECAO:
            if padrao.search(secao):
                return destino
    return None


# ---------- leitura dos sites ----------


def _nome(produto: dict, item: dict) -> str:
    nome = (produto.get("productName") or item.get("nameComplete") or "").strip()
    nome = re.sub(r"\s+", " ", nome).rstrip(".").strip()
    marca = (produto.get("brand") or "").strip()
    if marca and marca.isupper() and len(marca) > 3 and marca in nome:
        nome = nome.replace(marca, marca.title())  # o Angeloni escreve a marca em maiúsculas no meio do nome
    return nome


def itens(produto: dict, rede: str) -> list[ItemDoSite]:
    """Cada SKU (item) do produto VTEX, com o código de barras validado. Mesmo formato nas duas APIs."""
    caminhos = produto.get("categories") or ["/"]
    caminho = max(caminhos, key=len)  # o mais fundo
    marca = (produto.get("brand") or "").strip() or None
    saida = []
    for item in produto.get("items") or []:
        gtin = ean_util.gtin_de_produto(item.get("ean"))  # código interno de loja nunca liga redes (R1)
        ofertas = [s.get("commertialOffer") or {} for s in item.get("sellers") or []]
        disponivel = any(o.get("AvailableQuantity", 0) > 0 and o.get("Price", 0) > 0 for o in ofertas)
        granel = (item.get("measurementUnit") or "un").lower() == "kg" or (item.get("unitMultiplier") or 1) != 1
        saida.append(ItemDoSite(rede, str(item.get("itemId")), gtin, _nome(produto, item), marca, caminho, granel, disponivel))
    return saida


def _pagina_catalogo(http: Http, dominio: str, ids: list[int], inicio: int) -> list | None:
    fq = "/".join(str(i) for i in ids)
    url = f"https://{dominio}/api/catalog_system/pub/products/search?fq=C:/{fq}/&_from={inicio}&_to={inicio + POR_PAGINA - 1}"
    try:
        r = http(url, None)
    except BloqueadoPeloRobots:
        return None
    return r if isinstance(r, list) else None


def _pagina_busca(http: Http, dominio: str, slugs: list[str], pagina: int) -> tuple[list, int] | None:
    caminho = "/".join(f"category-{i + 1}/{s}" for i, s in enumerate(slugs))
    url = (
        f"https://{dominio}/api/io/_v/api/intelligent-search/product_search/{caminho}"
        f"?page={pagina}&count={POR_PAGINA}&hideUnavailableItems=false"
    )
    try:
        r = http(url, None)
    except BloqueadoPeloRobots:
        return None
    if not isinstance(r, dict):
        return None
    return r.get("products") or [], int(r.get("recordsFiltered") or 0)


@dataclass
class Varredura:
    itens: list[ItemDoSite]
    completa: bool  # nenhuma página falhou nem ficou cortada: dá para dizer o que a rede não vende
    paginas: int
    departamentos: list[str]
    problemas: list[str] = field(default_factory=list)


TENTATIVAS = 3  # uma página que falha (site lento, erro 5xx) é pedida de novo antes de dar a rede por incompleta


def _tentar(ler, *args):
    for _ in range(TENTATIVAS):
        r = ler(*args)
        if r is not None:
            return r
    return None


def varrer(http: Http, rede: Rede) -> Varredura:
    """Percorre as categorias de mercado da rede. Categoria grande demais para uma consulta desce um nível."""
    v = Varredura([], True, 0, [])
    try:
        arvore = http(f"https://{rede.dominio}/api/catalog_system/pub/category/tree/3", None)
    except BloqueadoPeloRobots:
        arvore = None
    if not isinstance(arvore, list) or not arvore:
        v.completa = False
        v.problemas.append("árvore de categorias não respondeu")
        return v
    inteligente = rede.id in BUSCA_INTELIGENTE
    vistos: set[str] = set()

    def problema(texto: str) -> None:
        v.completa = False
        v.problemas.append(texto)

    def guardar(produtos: list) -> None:
        for p in produtos:
            for it in itens(p, rede.id):
                if it.sku not in vistos:
                    vistos.add(it.sku)
                    v.itens.append(it)

    def ler(cadeia: list[dict]) -> bool:
        """Lê a categoria inteira. False quando passa do limite de uma consulta (e não leu nada)."""
        nome = "/".join(c["name"] for c in cadeia)
        if inteligente:
            slugs = [c["url"].rstrip("/").rsplit("/", 1)[-1] for c in cadeia]
            pagina, total = 1, None
            while True:
                r = _tentar(_pagina_busca, http, rede.dominio, slugs, pagina)
                v.paginas += 1
                if r is None:
                    problema(f"{nome}: página {pagina} falhou")
                    return True
                produtos, total = r
                if total > LIMITE_CONSULTA and cadeia[-1].get("children"):
                    return False
                guardar(produtos)
                if len(produtos) < POR_PAGINA or pagina * POR_PAGINA >= min(total, LIMITE_CONSULTA):
                    if total > LIMITE_CONSULTA:
                        problema(f"{nome}: {total} produtos, mais que uma consulta lê")
                    return True
                pagina += 1
        ids = [c["id"] for c in cadeia]
        lidos: list = []
        for inicio in range(0, LIMITE_CONSULTA, POR_PAGINA):
            r = _tentar(_pagina_catalogo, http, rede.dominio, ids, inicio)
            v.paginas += 1
            if r is None:
                problema(f"{nome}: página a partir do item {inicio} falhou")
                break
            lidos += r
            if len(r) < POR_PAGINA:
                guardar(lidos)
                return True
        else:
            if cadeia[-1].get("children"):
                return False
            problema(f"{nome}: mais produtos que uma consulta lê")
        guardar(lidos)
        return True

    def visitar(cadeia: list[dict]) -> None:
        no = cadeia[-1]
        filhos = no.get("children") or []
        # Departamento: lê pelas categorias de baixo (cada uma cabe numa consulta, quase sempre).
        if len(cadeia) == 1 and filhos:
            for f in filhos:
                visitar(cadeia + [f])
            return
        if not ler(cadeia):
            for f in filhos:
                visitar(cadeia + [f])

    for dep in arvore:
        if FORA.search(_simples(dep["name"])):
            continue
        v.departamentos.append(dep["name"])
        visitar([dep])
        print(f"  {rede.id}: {dep['name']}: {len(v.itens)} SKUs até aqui, {v.paginas} páginas", flush=True)
    return v


# ---------- gravação ----------


def gravar(conn: psycopg.Connection, rede: Rede, varredura: Varredura, agora: datetime, marcar: bool = True) -> dict:
    """Liga os SKUs, cria os produtos novos e marca o que a rede não vende. Devolve as contagens.

    Com várias redes, marque as ausências só depois de gravar todas (marcar=False e depois marcar_ausentes):
    o produto novo que veio da Cooper também precisa constar como "o Giassi não vende"."""
    nome_rede = config.NOME_NO_BANCO[rede.id]
    linha = conn.execute("select id from rede where nome = %s", (nome_rede,)).fetchone()
    if linha is None:
        raise RuntimeError(f"rede {nome_rede!r} não está cadastrada")
    rede_id = linha["id"]
    produto_por_ean = {r["codigo"]: str(r["produto_id"]) for r in conn.execute("select codigo, produto_id from ean").fetchall()}
    tamanhos = {
        str(r["id"]): (r["tamanho"], r["unidade"]) for r in conn.execute("select id, tamanho, unidade from produto").fetchall()
    }
    cria = rede.id not in SO_LIGA_SKU
    conta: Counter = Counter()
    fora: Counter = Counter()
    novos_produtos, novos_eans, ligacoes = [], [], {}
    recusados: dict[str, tuple[str, str]] = {}  # sku -> (produto, gtin): mesmo código, outra embalagem
    for it in varredura.itens:
        if it.gtin is None:
            conta["sem_ean"] += 1
            continue
        pid = produto_por_ean.get(it.gtin)
        if pid is None:
            if not cria:
                conta["fora_do_catalogo"] += 1
                continue
            motivo = None
            cat = categoria(it.caminho, it.nome)
            t = tamanho.extrair(it.nome)
            if not it.disponivel:
                motivo = "indisponivel"
            elif it.granel:
                motivo = "granel"
            elif tamanho.embalagem_multipla(it.nome):
                motivo = "pack"
            elif cat is None:
                motivo = "fora_do_mercado"
                fora[it.caminho.strip("/").split("/")[0]] += 1
            elif t is None:
                motivo = "sem_tamanho"
            if motivo:
                conta[motivo] += 1
                continue
            pid = str(uuid.uuid5(ESPACO, it.gtin))
            produto_por_ean[it.gtin] = pid
            tamanhos[pid] = (t.quantidade, t.unidade)
            novos_produtos.append((pid, cat, it.nome, it.marca, t.quantidade, t.unidade))
            novos_eans.append((it.gtin, pid))
            conta["novos"] += 1
        elif not tamanho.mesmo_tamanho_no_site(it.nome, *tamanhos.get(pid, (None, None))):
            # O site desta rede mostra outra embalagem com o mesmo código: não liga, não coleta, não compara.
            conta["tamanho_diferente"] += 1
            recusados[it.sku] = (pid, it.gtin)
            continue
        ligacoes[it.sku] = (pid, it.nome)
    aceitos = {pid for pid, _ in ligacoes.values()}
    recusados = {sku: v for sku, v in recusados.items() if v[0] not in aceitos}

    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(
                """insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade)
                   values (%s, %s, %s, %s, %s, %s) on conflict (id) do nothing""",
                novos_produtos,
            )
            cur.executemany("insert into ean (codigo, produto_id) values (%s, %s) on conflict (codigo) do nothing", novos_eans)
            cur.executemany(
                """insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) values (%s, %s, %s, %s)
                   on conflict (rede_id, sku) do update
                   set produto_id = excluded.produto_id, nome_no_site = excluded.nome_no_site""",
                [(pid, rede_id, sku, nome) for sku, (pid, nome) in ligacoes.items()],
            )
            # Ligação e preço de antes com a embalagem errada saem (o histórico fica, imutável).
            cur.execute("delete from produto_na_rede where rede_id = %s and sku = any(%s)", (rede_id, list(recusados)))
            cur.execute(
                """delete from preco_atual where produto_id = any(%s)
                   and loja_id in (select id from loja where rede_id = %s)""",
                ([pid for pid, _ in recusados.values()], rede_id),
            )
        outra_embalagem = {g for _, g in recusados.values()}
        ausentes = marcar_ausentes(conn, rede, varredura, agora, outra_embalagem) if marcar else 0
    return {
        "paginas": varredura.paginas,
        "skus": len(varredura.itens),
        "ligados": len(ligacoes),
        "novos": conta["novos"],
        "ausentes": ausentes,
        "completa": varredura.completa,
        "descartes": {k: n for k, n in conta.items() if k != "novos"},
        "fora_do_mercado": dict(fora.most_common(8)),
        "outra_embalagem": outra_embalagem,
    }


def marcar_ausentes(
    conn: psycopg.Connection, rede: Rede, varredura: Varredura, agora: datetime, outra_embalagem: set[str] | None = None
) -> int:
    """O que a rede vende deixa de ser "ausente"; com a varredura completa, o resto do catálogo passa a ser.
    Código que a rede usa para outra embalagem conta como "não vende": a coleta não procura nem compara."""
    rede_id = conn.execute("select id from rede where nome = %s", (config.NOME_NO_BANCO[rede.id],)).fetchone()["id"]
    vistos = list({it.gtin for it in varredura.itens if it.gtin} - (outra_embalagem or set()))
    with conn.transaction():
        conn.execute("delete from ean_ausente where rede_id = %s and codigo = any(%s)", (rede_id, vistos))
        if not varredura.completa:
            return 0
        return conn.execute(
            """insert into ean_ausente (rede_id, codigo, verificado_em)
               select %s, e.codigo, %s from ean e where e.status = 'ok' and not (e.codigo = any(%s))
               on conflict (rede_id, codigo) do update set verificado_em = excluded.verificado_em""",
            (rede_id, agora, vistos),
        ).rowcount


def _salvar(caminho: Path, varreduras: dict[str, Varredura]) -> None:
    caminho.write_text(
        json.dumps({k: {**asdict(v), "itens": [asdict(i) for i in v.itens]} for k, v in varreduras.items()}, ensure_ascii=False),
        encoding="utf-8",
    )


def _carregar(caminho: Path) -> dict[str, Varredura]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {
        k: Varredura(
            [ItemDoSite(**i) for i in v["itens"]], v["completa"], v["paginas"], v["departamentos"], v.get("problemas") or []
        )
        for k, v in dados.items()
    }


def main(argv: list[str] | None = None, http: Http | None = None) -> int:
    p = argparse.ArgumentParser(description="Catalogador v2: catálogo de mercado inteiro das redes VTEX")
    p.add_argument("--rede", choices=[r.id for r in config.REDES_VTEX], help="só esta rede")
    p.add_argument("--salvar", type=Path, help="guarda o que foi lido dos sites neste arquivo JSON")
    p.add_argument("--de", type=Path, help="não lê os sites: usa o arquivo de uma leitura anterior")
    p.add_argument("--sem-banco", action="store_true", help="só lê os sites (com --salvar)")
    args = p.parse_args(argv)
    redes = [r for r in config.REDES_VTEX if not args.rede or r.id == args.rede]

    varreduras = _carregar(args.de) if args.de else {}
    if not args.de:
        http = http or ClienteHttp()
        for rede in redes:
            varreduras[rede.id] = varrer(http, rede)
            v = varreduras[rede.id]
            print(f"{rede.id}: {len(v.itens)} SKUs em {v.paginas} páginas, completa={v.completa}", flush=True)
            for problema in v.problemas[:20]:
                print(f"  problema: {problema}", flush=True)
    if args.salvar:
        _salvar(args.salvar, varreduras)
    if args.sem_banco:
        return 0

    falhas = 0
    outras_embalagens: dict[str, set[str]] = {}
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "catalogador") as resumo:
            for rede in redes:
                if rede.id not in varreduras:
                    continue
                try:
                    r = gravar(conn, rede, varreduras[rede.id], datetime.now(UTC), marcar=False)
                    outras_embalagens[rede.id] = r.pop("outra_embalagem")
                except Exception as erro:  # uma rede com problema não impede as outras
                    falhas += 1
                    resumo[config.NOME_NO_BANCO[rede.id]] = {"falhou": repr(erro)[:300]}
                    print(f"{rede.id}: falhou: {erro!r}", file=sys.stderr)
                    continue
                resumo[config.NOME_NO_BANCO[rede.id]] = {k: r[k] for k in ("skus", "ligados", "novos", "ausentes", "completa")}
                if varreduras[rede.id].problemas:
                    resumo[config.NOME_NO_BANCO[rede.id]]["problemas"] = len(varreduras[rede.id].problemas)
                print(rede.id, r, flush=True)
            # Ausências só agora, com os produtos novos de todas as redes já no catálogo.
            for rede in redes:
                nome = config.NOME_NO_BANCO[rede.id]
                if rede.id in varreduras and "falhou" not in resumo.get(nome, {}):
                    resumo[nome]["ausentes"] = marcar_ausentes(
                        conn, rede, varreduras[rede.id], datetime.now(UTC), outras_embalagens.get(rede.id)
                    )
                    print(f"{rede.id}: {resumo[nome]['ausentes']} produtos do catálogo que a rede não vende", flush=True)
            if not any(v.itens for v in varreduras.values()):
                raise RuntimeError("nenhuma rede respondeu")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
