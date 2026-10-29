"""Nome limpo e grupo de equivalência de um produto ("qualquer marca").

O site escreve "Leite UHT Integral Tirol Caixa com Tampa 1l"; o app mostra "Leite integral" em destaque e
"Tirol · 1 l" embaixo. O grupo junta o que a família trata como a mesma coisa: o mesmo tipo (primeira
palavra), as mesmas características que mudam o produto (integral, carioca, refinado, zero lactose...) e o
mesmo tamanho. "Qualquer marca" na lista vale para todos do grupo; cada mercado entra com o mais barato.
"""

import re
import unicodedata

from . import tamanho as tam

# Palavras que mudam o produto: entram no nome curto e no grupo. A ordem é a do nome no site.
CARACTERISTICAS = {
    # leite e laticínios
    "integral", "desnatado", "semidesnatado", "lactose", "zero", "light", "diet", "natural", "grego", "fatiado",
    "mussarela", "prato", "requeijao", "condensado", "creme", "sal", "com", "sem",
    # grãos e massas
    "parboilizado", "branco", "carioca", "preto", "vermelho", "fradinho", "jasmim", "arboreo", "espaguete",
    "parafuso", "penne", "talharim", "instantaneo", "lasanha",
    # açúcar, café, óleo, farinhas
    "refinado", "cristal", "demerara", "mascavo", "organico", "soluvel", "tradicional", "extraforte", "forte",
    "descafeinado", "graos", "capsula", "soja", "girassol", "canola", "milho", "oliva", "trigo", "mandioca",
    # bebidas
    "laranja", "uva", "limao", "guarana", "cola", "maracuja", "pessego", "morango", "chocolate", "baunilha",
    # limpeza e higiene
    "liquido", "po", "lavanda", "coco", "neutro", "concentrado", "tripla", "dupla", "folha",
}  # fmt: skip
EMBALAGEM = {
    "pacote", "pct", "caixa", "cx", "garrafa", "lata", "pote", "sache", "frasco", "copo", "tp", "pet", "embalagem",
    "economica", "supereconomica", "tamanho", "familia", "unidade", "unidades", "un", "leve", "pague", "refil",
    "squeeze", "bandeja", "tampa", "uht", "tipo",
}  # fmt: skip
# Segunda palavra que faz parte do tipo ("creme dental", "papel higiênico", "creme de leite", "sabão em pó").
COMPOSTOS = {
    "dental", "higienico", "sanitaria", "roupas", "loucas", "toalha", "umedecido", "umedecida", "umedecidos",
    "condensado", "leite", "tomate", "trigo", "mandioca", "rosca", "aveia", "frutas", "amendoim", "cacau", "po",
    "barra", "cozinha", "pia", "banheiro", "lixo", "vidro", "chuveiro", "unhas", "bucal", "cabelo",
}  # fmt: skip
_TAMANHO = re.compile(r"^\d+([.,]\d+)?(kg|g|ml|l|litros?|un|unidades|rolos|m)?$")


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def _palavras(texto: str) -> list[str]:
    texto = re.sub(r"(?<=[^\W\d_])-(?=[^\W\d_])", " ", texto.lower())  # "Lava-Roupas" -> "lava roupas"
    return re.findall(r"[a-zà-ú0-9]+(?:[.,]\d+)?[a-z]*", texto)


def nome_curto(nome: str, marca: str | None) -> str:
    """ "Leite UHT Integral Tirol Caixa 1l" -> "Leite integral"; "Feijão Carioca Tipo 1 Kicaldo 1kg" -> "Feijão carioca"."""
    marca_n = set(_palavras(_sem_acento(marca or "")))
    originais = _palavras(nome)
    if not originais:
        return nome
    saida = [originais[0]]
    resto = originais[1:]
    # tipo composto: "creme dental", "creme de leite", "sabão em pó"
    if resto and _sem_acento(resto[0]) in COMPOSTOS:
        saida.append(resto.pop(0))
    elif len(resto) >= 2 and _sem_acento(resto[0]) in ("de", "em", "para") and _sem_acento(resto[1]) in COMPOSTOS:
        saida += [resto.pop(0), resto.pop(0)]
    for w in resto:
        n = _sem_acento(w)
        if n in marca_n or n in EMBALAGEM or _TAMANHO.match(n):
            continue
        if n in CARACTERISTICAS and n not in ("com", "sem"):
            saida.append(w)
        elif n in ("com", "sem") and len(saida) < 4:
            saida.append(w)
    # "sem" ou "com" sozinho no fim não diz nada
    while len(saida) > 1 and _sem_acento(saida[-1]) in ("com", "sem"):
        saida.pop()
    texto = " ".join(saida[:4])
    return texto[:1].upper() + texto[1:]


def grupo(nome: str, marca: str | None, quantidade=None, unidade: str | None = None) -> str | None:
    """Chave do grupo de equivalência: tipo + características + tamanho. None sem tamanho legível."""
    t = tam.Tamanho(float(quantidade), unidade) if quantidade is not None and unidade else tam.extrair(nome)
    if t is None or tam.embalagem_multipla(nome):
        return None
    curto = _sem_acento(nome_curto(nome, marca))
    return f"{curto}|{t.quantidade:g}{t.unidade}"
