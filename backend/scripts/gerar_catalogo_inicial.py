"""Gera db/dados/catalogo_inicial.sql: as 10 categorias e os 32 produtos das cestas validadas na coleta de 22/10/2026.

O catálogo de verdade cresce pelo agente Catalogador (com revisão); este é só o ponto de partida para o
teste com as famílias e para a coleta diária ter o que buscar.

Rodar:  python scripts/gerar_catalogo_inicial.py
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantofica.regras import ean, tamanho  # noqa: E402

SAIDA = Path(__file__).resolve().parents[2] / "db" / "dados" / "catalogo_inicial.sql"
ESPACO = uuid.UUID("0c6a3f7e-2b1d-4e8a-9f55-31d2c4b7a901")

# id, nome, unidade de comparação (R2). Categorias com embalagens de medidas diferentes comparam por unidade.
CATEGORIAS = [
    ("bebidas", "Bebidas", "ml"),
    ("cafe", "Café e chás", "g"),
    ("doces", "Doces e biscoitos", "g"),
    ("graos", "Grãos e massas", "g"),
    ("higiene", "Higiene", "un"),
    ("hortifruti", "Hortifrúti", "g"),
    ("laticinios", "Laticínios", "un"),
    ("limpeza", "Limpeza", "un"),
    ("mercearia", "Mercearia", "un"),
    ("padaria", "Padaria", "g"),
]

# EAN, nome como a família fala, marca, categoria
PRODUTOS = [
    ("7894900027013", "Refrigerante Coca-Cola 2L", "Coca-Cola", "bebidas"),
    ("7894900010015", "Refrigerante Coca-Cola lata 350ml", "Coca-Cola", "bebidas"),
    ("70847022015", "Energético Monster 473ml", "Monster", "bebidas"),
    ("611269991000", "Energético Red Bull 250ml", "Red Bull", "bebidas"),
    ("7622210592750", "Biscoito Trakinas chocolate 126g", "Trakinas", "doces"),
    ("7622300830151", "Biscoito Oreo 90g", "Oreo", "doces"),
    ("7622210575975", "Chocolate Bis 100,8g", "Lacta", "doces"),
    ("7891000248768", "Chocolate KitKat 41,5g", "Nestlé", "doces"),
    ("7896022086909", "Biscoito cream cracker Isabela 350g", "Isabela", "doces"),
    ("7892840822446", "Salgadinho Doritos queijo nacho 120g", "Doritos", "mercearia"),
    ("7896038321032", "Arroz branco tipo 1 Tio Urbano 5kg", "Tio Urbano", "graos"),
    ("7896273900313", "Feijão carioca Caldo Bom 1kg", "Caldo Bom", "graos"),
    ("7896273900306", "Feijão preto Caldo Bom 1kg", "Caldo Bom", "graos"),
    ("7896022200756", "Macarrão espaguete Galo 500g", "Galo", "graos"),
    ("7896089013405", "Café Pilão extraforte 500g", "Pilão", "cafe"),
    ("7891107101621", "Óleo de soja Soya 900ml", "Soya", "mercearia"),
    ("7891910000197", "Açúcar refinado União 1kg", "União", "mercearia"),
    ("7896412819520", "Farinha de trigo Orquídea 1kg", "Orquídea", "mercearia"),
    ("7896035210001", "Sal refinado Cisne 1kg", "Cisne", "mercearia"),
    ("7896036099988", "Molho de tomate Pomarola 300g", "Pomarola", "mercearia"),
    ("7891000412855", "Achocolatado Nescau 350g", "Nescau", "mercearia"),
    ("7896256601848", "Leite integral Tirol 1L", "Tirol", "laticinios"),
    ("7893000394209", "Margarina Qualy 500g", "Qualy", "laticinios"),
    ("7891000100103", "Leite condensado Moça 395g", "Nestlé", "laticinios"),
    ("7891000126905", "Creme de leite Nestlé 200g", "Nestlé", "laticinios"),
    ("7891024134702", "Creme dental Colgate Máxima Proteção 90g", "Colgate", "higiene"),
    ("7898422746759", "Sabonete Dove original 90g", "Dove", "higiene"),
    ("7896026800709", "Papel higiênico Duetto 12 rolos", "Duetto", "higiene"),
    ("7896098900208", "Detergente Ypê neutro 500ml", "Ypê", "limpeza"),
    ("7891150069121", "Sabão em pó Omo 2,2kg", "Omo", "limpeza"),
    ("7891150080010", "Amaciante Comfort Fiber Protect 1,5L", "Comfort", "limpeza"),
]


def texto(v) -> str:
    return "null" if v is None else "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    linhas = ["-- Gerado por backend/scripts/gerar_catalogo_inicial.py. Não edite à mão: rode o script de novo.", "begin;"]
    for cid, nome, unidade in CATEGORIAS:
        linhas.append(
            f"insert into categoria (id, nome, unidade_medida) values ({texto(cid)}, {texto(nome)}, {texto(unidade)}) "
            "on conflict (id) do update set nome = excluded.nome, unidade_medida = excluded.unidade_medida;"
        )
    vistos = set()
    for codigo, nome, marca, categoria in PRODUTOS:
        gtin = ean.normalizar(codigo)
        if gtin in vistos or not ean.digito_verificador_ok(gtin):
            raise ValueError(f"EAN repetido ou inválido: {codigo}")
        vistos.add(gtin)
        t = tamanho.extrair(nome)
        if t is None:
            raise ValueError(f"sem tamanho no nome: {nome}")
        pid = uuid.uuid5(ESPACO, gtin)
        linhas.append(
            "insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values "
            f"({texto(pid)}, {texto(categoria)}, {texto(nome)}, {texto(marca)}, {t.quantidade}, {texto(t.unidade)}) "
            "on conflict (id) do update set categoria_id = excluded.categoria_id, nome_humano = excluded.nome_humano, "
            "marca = excluded.marca, tamanho = excluded.tamanho, unidade = excluded.unidade;"
        )
        linhas.append(
            f"insert into ean (codigo, produto_id) values ({texto(gtin)}, {texto(pid)}) on conflict (codigo) do nothing;"
        )
    linhas += ["commit;", ""]
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    print(f"{len(CATEGORIAS)} categorias e {len(PRODUTOS)} produtos em {SAIDA}")


if __name__ == "__main__":
    main()
