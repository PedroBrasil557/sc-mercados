"""Casa o nome de um item de encarte (sem código de barras) com produtos que têm EAN.

O encarte escreve "Café Odebrecht Tradicional/ Extraforte Vácuo 500g"; o site escreve "Café Torrado e
Moído Tradicional Odebrecht Vácuo 500g". Para casar, tudo tem de bater:
- tamanho exato (R2) e a mesma quantidade de unidades no pacote ("c/ 4 un.");
- a marca do produto aparece no nome do encarte;
- o tipo (primeira palavra: café, arroz, biscoito...) aparece no nome do encarte;
- linha especial (zero, diet, sem glúten...) só se o encarte disser;
- o resto do nome: 3/4 das palavras do encarte estão no produto. Quando o encarte vale para vários
  ("Sabores", "Tipos", "Tradicional/ Extraforte"), basta metade, e todos os que passam levam o preço.
Sem certeza (dois produtos empatados sem o encarte dizer que vale para vários), não casa: vai para revisão.
"""

import re
import unicodedata
from dataclasses import dataclass

from ..regras import tamanho as tam


@dataclass(frozen=True)
class Candidato:
    chave: str  # produto_id (catálogo) ou GTIN (produto achado num site)
    nome: str
    marca: str | None
    tamanho: tam.Tamanho | None


PARE = {"a", "o", "de", "da", "do", "das", "dos", "com", "c", "s", "sem", "e", "em", "p", "para", "ou", "no", "na"}
# Palavras de embalagem e de oferta: não dizem qual é o produto.
EMBALAGEM = {
    "pacote", "pct", "garrafa", "caixa", "cx", "lata", "pote", "sache", "vidro", "frasco", "copo", "tp", "pet",
    "tamanho", "familia", "unidade", "unidades", "un", "und", "emb", "embalagem", "economica", "lv", "pg", "leve",
    "pague", "refil", "squeeze", "bandeja", "tetra", "pak", "cong", "congelado", "congelada",
}  # fmt: skip
VARIOS = {"sabores", "tipos", "sortidos", "sortido", "fragrancias", "cores", "versoes"}
# Linha especial costuma ter outro preço: "Divine 70g Sabores" não inclui o Divine Zero nem o sem glúten.
DIFERENCIAIS = {"zero", "diet", "light", "gluten", "lactose", "integral", "organico", "vegano", "proteico", "kids"}
_NUMERO = re.compile(r"^\d+([.,]\d+)?[a-z]*$")
_POR_PACOTE = re.compile(r"c/\s*(\d+)\s*un", re.I)
_UNIDADES_NO_NOME = re.compile(r"(\d+)\s*(?:unidades|un\b|rolos)", re.I)


def palavras(texto: str) -> list[str]:
    texto = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+(?:[.,]\d+)?[a-z]*", texto)


def _distintas(texto: str, marca: set[str] = frozenset()) -> set[str]:
    return {w for w in palavras(texto) if w not in PARE | EMBALAGEM | VARIOS and w not in marca and not _NUMERO.match(w)}


def vale_para_varios(nome_encarte: str) -> bool:
    return "/" in nome_encarte or bool(set(palavras(nome_encarte)) & (VARIOS | {"ou"}))


def _unidades_no_pacote(nome: str) -> int | None:
    m = _POR_PACOTE.search(nome)
    return int(m.group(1)) if m else None


def casar(nome_encarte: str, candidatos: list[Candidato]) -> list[Candidato]:
    """Produtos que são o item do encarte. Vazio quando nenhum serve ou quando não dá para ter certeza."""
    t = tam.extrair(nome_encarte)
    if t is None:
        return []
    texto = set(palavras(nome_encarte))
    varios = vale_para_varios(nome_encarte)
    no_pacote = _unidades_no_pacote(nome_encarte)
    aceitos: list[tuple[float, Candidato]] = []
    for c in candidatos:
        if not c.marca or c.tamanho is None or not c.tamanho.mesmo_que(t, 0.005):
            continue
        marca = set(palavras(c.marca))
        nome_c = palavras(c.nome)
        if not marca or not marca <= texto or not nome_c or nome_c[0] not in texto:
            continue
        # "Creme Dental 90g c/ 4 un." é o pacote com 4; não é o tubo avulso de 90 g.
        unidades_c = _UNIDADES_NO_NOME.search(c.nome)
        if no_pacote and (not unidades_c or int(unidades_c.group(1)) != no_pacote):
            continue
        if not no_pacote and tam.embalagem_multipla(c.nome):
            continue
        if DIFERENCIAIS & set(nome_c) != DIFERENCIAIS & texto:
            continue
        procuradas = _distintas(nome_encarte, marca)
        achadas = len(procuradas & set(nome_c)) / len(procuradas) if procuradas else 1.0
        if achadas >= (0.5 if varios else 0.75):
            aceitos.append((achadas, c))
    if not aceitos:
        return []
    if varios:
        return [c for _, c in aceitos]
    melhor = max(a for a, _ in aceitos)
    empatados = [c for a, c in aceitos if a == melhor]
    return empatados if len(empatados) == 1 else []
