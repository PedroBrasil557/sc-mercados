"""Leitura de encarte em PDF com camada de texto (Fort Atacadista).

O texto do PDF sai fora de ordem; o que vale é a posição na página. Cada cartão do encarte tem o nome
(letra de 6 a 10 pt, em linhas alinhadas à esquerda) e um ou dois preços ("R$" + inteiro + "," +
centavos) à direita ou logo abaixo. Com dois preços, o maior é o normal e o menor é o condicional
(Clube Mais ou pagando com o cartão da loja): fica guardado, mas não entra no total (R5).
"""

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from pypdf import PdfReader


@dataclass(frozen=True)
class Fragmento:
    x: float
    y: float
    tamanho: float  # tamanho da letra em pontos
    texto: str


@dataclass(frozen=True)
class ItemDoEncarte:
    nome: str
    preco_centavos: int
    condicional_centavos: int | None  # Clube Mais ou cartão da loja
    por_kg: bool
    pagina: int


@dataclass
class Encarte:
    inicio: date | None
    fim: date | None
    itens: list[ItemDoEncarte] = field(default_factory=list)
    ambiguos: int = 0  # cartões com mais de dois preços: ficam de fora


@dataclass
class _Bloco:
    x: float
    topo: float
    base: float
    linhas: list[str]
    precos: list[tuple[int, bool]] = field(default_factory=list)  # (centavos, por kg)


_PRECO = re.compile(r"R\s*\$\s*(\d{1,4})\s*,\s*(\d{2})")
_VALIDADE = re.compile(r"Validade de (\d{2}/\d{2}/\d{4}) at[ée] (\d{2}/\d{2}/\d{4})")
_SO_SIMBOLO = re.compile(r"\s*(un\.?|kg|\.|R|\$|,)\s*", re.I)
DISTANCIA_MAXIMA = 70  # pontos entre o preço e o nome do cartão
LARGURA_NOME = 75  # o preço pode ficar à direita do nome sem contar como distância


def fragmentos(pagina) -> list[Fragmento]:
    partes: list[Fragmento] = []

    def visitar(texto, cm, tm, _fonte, tamanho):
        if texto.strip():
            x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            partes.append(Fragmento(x, y, tamanho * abs(tm[3] or tm[0]) * abs(cm[3] or cm[0]), texto))

    pagina.extract_text(visitor_text=visitar)
    return partes


def _precos(frs: list[Fragmento]) -> list[tuple[Fragmento, int, bool]]:
    """Preços na ordem do texto, com a posição do "R$" e se é preço por quilo."""
    texto, inicio = "", []
    for f in frs:
        inicio.append(len(texto))
        texto += f.texto.replace("\n", " ") + " "
    achados = []
    for m in _PRECO.finditer(texto):
        i = max(k for k, s in enumerate(inicio) if s <= m.start())
        por_kg = bool(re.match(r"\s*kg", texto[m.end() : m.end() + 12], re.I))
        achados.append((frs[i], int(m.group(1)) * 100 + int(m.group(2)), por_kg))
    return achados


def _nomes(frs: list[Fragmento]) -> list[_Bloco]:
    blocos: list[_Bloco] = []
    for f in frs:
        if not 6 <= f.tamanho <= 10 or _SO_SIMBOLO.fullmatch(f.texto) or not re.search(r"[A-Za-zÀ-ú]{2}", f.texto):
            continue
        for b in blocos:
            if abs(b.x - f.x) < 3 and 0 < b.base - f.y < 11:  # próxima linha do mesmo nome
                b.linhas.append(f.texto.strip())
                b.base = f.y
                break
        else:
            blocos.append(_Bloco(f.x, f.y, f.y, [f.texto.strip()]))
    return blocos


def itens_da_pagina(frs: list[Fragmento], pagina: int) -> tuple[list[ItemDoEncarte], int]:
    blocos = _nomes(frs)
    for f, centavos, por_kg in _precos(frs):
        melhor, menor = None, float("inf")
        for b in blocos:
            # o preço fica à direita ou abaixo do nome (no máximo um pouco acima do topo), no mesmo cartão
            if f.x < b.x - 12 or f.y > b.topo + 30:
                continue
            dx, dy = max(0.0, f.x - (b.x + LARGURA_NOME)), max(0.0, b.base - f.y)
            d = (dx * dx + dy * dy) ** 0.5
            if d < menor:
                melhor, menor = b, d
        if melhor is not None and menor < DISTANCIA_MAXIMA:
            melhor.precos.append((centavos, por_kg))

    itens, ambiguos = [], 0
    for b in blocos:
        if not b.precos:
            continue
        if len(b.precos) > 2:
            ambiguos += 1
            continue
        valores = [c for c, _ in b.precos]
        nome = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", " ".join(b.linhas))).strip()  # "ﬁ" vira "fi"
        por_kg = any(k for _, k in b.precos) or bool(re.search(r"\bkg\s*$", nome, re.I))
        condicional = min(valores) if len(valores) == 2 and min(valores) < max(valores) else None
        itens.append(ItemDoEncarte(nome, max(valores), condicional, por_kg, pagina))
    return itens, ambiguos


def validade(texto: str) -> tuple[date, date] | None:
    m = _VALIDADE.search(texto)
    if not m:
        return None
    return tuple(datetime.strptime(d, "%d/%m/%Y").date() for d in m.groups())  # type: ignore[return-value]


def ler(pdf: bytes) -> Encarte:
    leitor = PdfReader(io.BytesIO(pdf))
    encarte = Encarte(None, None)
    for n, pagina in enumerate(leitor.pages, start=1):
        frs = fragmentos(pagina)
        if encarte.fim is None and (v := validade(" ".join(f.texto for f in frs))):
            encarte.inicio, encarte.fim = v
        itens, ambiguos = itens_da_pagina(frs, n)
        encarte.itens += itens
        encarte.ambiguos += ambiguos
    return encarte
