"""Catalogador, versão 1 (determinística): os produtos mais vendidos de cada subcategoria do Giassi.

Gera db/dados/03_catalogo_ampliado.sql. A API pública de catálogo do Giassi informa, por subcategoria, os
produtos em ordem de venda (O=OrderByTopSaleDESC), com o código de barras. O código de barras é o mesmo
em todas as redes, então a coleta diária já acha o preço de cada um no Giassi, na Cooper, no Angeloni e
no Sam's (R1: mesmo produto = mesmo EAN de 14 dígitos).

Fica de fora, de propósito:
- item vendido por quilo (preço depende da pesagem: R4, granel, entra depois);
- pack/kit com o EAN da unidade (R1: iria para revisão de qualquer jeito);
- produto sem tamanho legível no nome (não dá para comparar com justiça, R2).

Rodar:  python scripts/gerar_catalogo_ampliado.py   (~40 requisições, 1 por segundo, respeitando o robots.txt)
"""

import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantofica.coleta.vtex import ClienteHttp  # noqa: E402
from quantofica.regras import ean, tamanho  # noqa: E402

SAIDA = Path(__file__).resolve().parents[2] / "db" / "dados" / "03_catalogo_ampliado.sql"
ESPACO = uuid.UUID("0c6a3f7e-2b1d-4e8a-9f55-31d2c4b7a901")  # o mesmo do catálogo inicial: o mesmo EAN vira o mesmo produto
GIASSI = "https://www.giassi.com.br"
POR_SUBCATEGORIA = 20


# (departamento, subcategoria) do Giassi -> nossa categoria. Função quando depende do nome do produto.
def _matinal(nome: str) -> str:
    return "cafe" if re.search(r"\b(caf[eé]|ch[aá]|cappuccino|filtro)\b", nome, re.I) else "mercearia"


def _basicos(nome: str) -> str:
    return (
        "graos" if re.search(r"\b(arroz|feij[aã]o|lentilha|gr[aã]o|ervilha|milho de pipoca|aveia)\b", nome, re.I) else "mercearia"
    )


SUBCATEGORIAS: dict[tuple[int, int], str | object] = {
    (11, 82): "mercearia",
    (11, 84): _basicos,
    (11, 86): "doces",
    (11, 87): "doces",
    (11, 88): "mercearia",
    (11, 90): "graos",
    (11, 91): _matinal,
    (11, 92): "mercearia",
    (11, 93): "doces",
    (12, 99): "padaria",
    (3, 29): "bebidas",
    (3, 35): "bebidas",
    (3, 36): "bebidas",
    (3, 30): "bebidas",
    (3, 33): "bebidas",
    (2, 25): "bebidas",
    (7, 59): "laticinios",
    (7, 60): "laticinios",
    (7, 61): "laticinios",
    (7, 62): "laticinios",
    (7, 63): "laticinios",
    (7, 64): "laticinios",
    (9, 74): "hortifruti",
    (8, 69): "higiene",
    (8, 70): "higiene",
    (8, 66): "higiene",
    (8, 67): "higiene",
    (409, 411): "higiene",
    (10, 78): "limpeza",
    (10, 79): "limpeza",
    (10, 80): "limpeza",
    (10, 81): "limpeza",
    (15, 56): "limpeza",
    # Carnes e congelados embalados (com código de barras). Sem categoria própria no Figma ainda: mercearia por enquanto.
    (4, 41): "mercearia",
    (4, 43): "mercearia",
    (6, 51): "mercearia",
    (6, 52): "mercearia",
}


# O nome manda mais que a seção do site (o Giassi põe requeijão junto dos pães, por exemplo).
CORRECOES = [
    (r"\b(requeij[aã]o|queijo|iogurte|manteiga|margarina|creme de leite|leite condensado|nata)\b", "laticinios"),
    (r"\b(caf[eé] (em p[oó]|sol[uú]vel|torrado)|cappuccino)\b", "cafe"),
]


def corrigir_categoria(nome: str, categoria: str) -> str:
    for padrao, destino in CORRECOES:
        if re.search(padrao, nome, re.I):
            return destino
    return categoria


def texto(v) -> str:
    return "null" if v is None else "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    http = ClienteHttp()
    produtos: dict[str, dict] = {}
    descartes = {"sem_ean": 0, "granel": 0, "pack": 0, "sem_tamanho": 0}
    for (dep, sub), destino in SUBCATEGORIAS.items():
        busca = f"fq=C:/{dep}/{sub}/&O=OrderByTopSaleDESC&_from=0&_to={POR_SUBCATEGORIA - 1}"
        url = f"{GIASSI}/api/catalog_system/pub/products/search?{busca}"
        for p in http(url, None) or []:
            item = (p.get("items") or [{}])[0]
            nome = (item.get("nameComplete") or p.get("productName") or "").strip().rstrip(".").strip()
            try:
                gtin = ean.normalizar(item.get("ean") or "")
            except ValueError:
                descartes["sem_ean"] += 1
                continue
            if not ean.digito_verificador_ok(gtin):
                descartes["sem_ean"] += 1
                continue
            if (item.get("measurementUnit") or "un").lower() == "kg" or (item.get("unitMultiplier") or 1) != 1:
                descartes["granel"] += 1
                continue
            if tamanho.embalagem_multipla(nome):
                descartes["pack"] += 1
                continue
            t = tamanho.extrair(nome)
            if t is None:
                descartes["sem_tamanho"] += 1
                continue
            categoria = corrigir_categoria(nome, destino(nome) if callable(destino) else destino)
            produtos.setdefault(
                gtin,
                {
                    "nome": nome,
                    "marca": (p.get("brand") or "").strip() or None,
                    "categoria": categoria,
                    "t": t,
                    "sku": item.get("itemId"),
                },
            )
        print(f"  {dep}/{sub}: {len(produtos)} produtos até aqui", flush=True)

    linhas = [
        "-- Gerado por backend/scripts/gerar_catalogo_ampliado.py (Catalogador v1). Não edite à mão: rode o script de novo.",
        "-- Fonte: mais vendidos de cada subcategoria na API pública de catálogo do Giassi.",
        "begin;",
    ]
    for gtin, d in sorted(produtos.items(), key=lambda kv: (kv[1]["categoria"], kv[1]["nome"])):
        pid = uuid.uuid5(ESPACO, gtin)
        linhas.append(
            "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values "
            f"({texto(pid)}, {texto(d['categoria'])}, {texto(d['nome'])}, {texto(d['marca'])}, "
            f"{d['t'].quantidade}, {texto(d['t'].unidade)}) "
            "on conflict (id) do nothing;"
        )
        linhas.append(
            f"insert into ean (codigo, produto_id) values ({texto(gtin)}, {texto(pid)}) on conflict (codigo) do nothing;"
        )
        if d["sku"]:
            # O SKU do Giassi já vem junto: a coleta não precisa procurar o produto lá.
            linhas.append(
                "insert into produto_na_rede (produto_id, rede_id, sku, nome_no_site) "
                f"select e.produto_id, r.id, {texto(d['sku'])}, {texto(d['nome'])} from ean e cross join rede r "
                f"where e.codigo = {texto(gtin)} and r.nome = 'Giassi' on conflict (rede_id, sku) do nothing;"
            )
    linhas += ["commit;", ""]
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    por_categoria: dict[str, int] = {}
    for d in produtos.values():
        por_categoria[d["categoria"]] = por_categoria.get(d["categoria"], 0) + 1
    print(f"{len(produtos)} produtos em {SAIDA.name}; por categoria: {dict(sorted(por_categoria.items()))}; fora: {descartes}")


if __name__ == "__main__":
    main()
