"""Leitura de encarte em PDF com camada de texto (Fort Atacadista e Super A).

O texto do PDF sai fora de ordem; o que vale é a posição na página. Cada cartão do encarte tem o nome
(letra de 6 a 10 pt, em linhas alinhadas à esquerda) e um ou dois preços ("R$" + inteiro + "," +
centavos) à direita ou logo abaixo. Com dois preços, o maior é o normal e o menor é o condicional
(Clube Mais ou pagando com o cartão da loja): fica guardado, mas não entra no total (R5).

Cada rede desenha o cartão de um jeito; a parte de baixo deste arquivo tem a montagem do Super A
(ver "outras redes"). A do Fort fica como está.
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
    paginas_sem_texto: int = 0  # página só com imagem (sem OCR por enquanto)
    validades_divergentes: bool = False  # páginas com datas diferentes: nada é publicado


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


# ---------- outras redes ----------
# Encartes de 05/11/2026. Cada rede desenha o cartão de um jeito. A validade e a leitura página a página (ler_com)
# servem para todas; a montagem dos cartões é de cada rede.
# - Super A: nome em linhas, o "R$" logo abaixo do nome (na mesma coluna) e o preço grande abaixo do "R$". Um cartão
#   pode empilhar variantes ("Arroz SEU ARROZ Parboilizado / Pacote 1kg R$ 3,19 / Pacote 5kg R$ 15,95").

_DATA = r"(\d{1,2})/(\d{1,2})/(\d{2,4})"
_VALIDAS = re.compile(r"v[aá]lid[oa]s?\b", re.I)
_PERIODO = re.compile(r"(\d{1,2})(?:/(\d{1,2}))?(?:/(\d{2,4}))?\s+(a|e|at[eé])\s+" + _DATA, re.I)
_UM_DIA = re.compile(_DATA)
JANELA_VALIDADE = 260  # caracteres depois de "válidas" onde a data pode estar ("válidas para a rede ... para dia 02/11")


def _ano(texto: str) -> int:
    return int(texto) + (2000 if len(texto) == 2 else 0)


def validades_escritas(texto: str) -> set[tuple[date, date]]:
    """Os períodos escritos depois de "válidas": "Ofertas válidas de 02/11 a 05/11/2026", "OFERTAS VÁLIDAS 04/11 E
    05/11/2026", "válidos somente no dia 05/11/2026", "Ofertas válidas para Quarta-feira dia 04/11/26". Data que não faz
    sentido (mais de um mês, fim antes do início, "e" entre dias que não são seguidos) fica de fora."""
    texto = re.sub(r"\s+", " ", texto)
    achadas = set()
    for v in _VALIDAS.finditer(texto):
        janela = texto[v.end() : v.end() + JANELA_VALIDADE]
        p, d = _PERIODO.search(janela), _UM_DIA.search(janela)
        try:
            if p and (d is None or p.start() <= d.start()):
                dia_i, mes_i, ano_i, ligacao, dia_f, mes_f, ano_f = p.groups()
                fim = date(_ano(ano_f), int(mes_f), int(dia_f))
                mes_inicio = int(mes_i) if mes_i else fim.month
                inicio = date(_ano(ano_i) if ano_i else fim.year - (mes_inicio > fim.month), mes_inicio, int(dia_i))
                if ligacao.lower() == "e" and (fim - inicio).days > 1:
                    continue  # dois dias soltos: não é um período
            elif d:
                inicio = fim = date(_ano(d.group(3)), int(d.group(2)), int(d.group(1)))
            else:
                continue
        except ValueError:
            continue
        if inicio <= fim and (fim - inicio).days <= 31:
            achadas.add((inicio, fim))
    return achadas


def juntar_linhas(frs: list[Fragmento]) -> list[Fragmento]:
    """Pedaços seguidos no mesmo ponto da página (o PDF às vezes escreve "Bovino " e "kg" separados) viram um só."""
    saida: list[Fragmento] = []
    for f in frs:
        u = saida[-1] if saida else None
        if u and abs(u.x - f.x) < 0.5 and abs(u.y - f.y) < 0.5:
            saida[-1] = Fragmento(u.x, u.y, u.tamanho, u.texto.rstrip("\n") + f.texto)
        else:
            saida.append(f)
    return saida


def _nome(linhas: list[str]) -> str:
    nome = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", " ".join(linhas))).strip()
    return re.sub(r"\s*-\s*cada\b|\s+cada\s*$", "", nome, flags=re.I).strip()  # "Óleo COCAMAR 900ml - cada"


def por_peso(nome: str) -> bool:
    """Vendido a peso: "Patinho Bovino kg", "Castanhas a granel Quilo", "Alho - a cada 100g". "Pacote 1kg" e
    "Saco 2 Kg" não (o "kg" é do tamanho)."""
    if re.search(r"\bgranel\b|\ba cada \d+\s*g\b|\bquilo\b", nome, re.I):
        return True
    return any(not re.search(r"\d[.,]?\s*$", nome[: m.start()]) for m in re.finditer(r"\bkg\b", nome, re.I))


# Super A ----------------------------------------------------------------------------------------------------------
_QUANTIDADE = re.compile(r"^quant\.?\s*disp", re.I)  # "Quant. Disp. 1000 un": estoque da oferta, não é nome
_PEDACO_DE_PRECO = re.compile(r"^(R\s*\$|[\d\s.,]+)$")
_SELO = re.compile(r"sai por|nesta promo", re.I)  # "NESTA PROMOÇÃO A UNIDADE SAI POR": preço de quem leva vários
_CAIXA_ALTA = re.compile(r"\b[A-ZÀ-ÖØ-Ý]{3,}\b")  # o Super A escreve a marca em maiúsculas: "Café CABOCLO"
_NAO_E_MARCA = {"IQF", "UHT", "PET", "PCT", "KG"}
_TAMANHO_NO_NOME = re.compile(r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)*\s*(?:kg|g|ml|l|litros?)\b", re.I)


def _tem_marca(linhas: list[str]) -> bool:
    return any(w not in _NAO_E_MARCA for linha in linhas for w in _CAIXA_ALTA.findall(linha))


@dataclass
class _Cartao:
    rs: Fragmento  # o "R$" do preço
    linhas: list[str]
    anterior: Fragmento | None  # "R$" do cartão logo acima, na mesma coluna
    centavos: int
    por_kg: bool
    cabeca: list[str] | None = None  # nome comum das variantes empilhadas


def itens_em_coluna(frs: list[Fragmento], pagina: int) -> tuple[list[ItemDoEncarte], int]:
    """Super A: sobe a coluna a partir de cada "R$" juntando as linhas do nome. Cartão logo abaixo de outro preço, sem
    marca no nome ("Pacote 5kg"), é variante do de cima e leva o nome comum ("Arroz SEU ARROZ Parboilizado Pacote 5kg").
    Cartão com marca no nome ("Manteiga LAC LÉLO 200g") é outro produto, mesmo empilhado."""
    frs = juntar_linhas(frs)
    cartoes: list[_Cartao] = []
    for f, centavos, por_kg in _precos(frs):
        if f.texto.strip() != "R$":
            continue  # "Preço KgR$17,90": preço de referência no meio de uma frase
        coluna = sorted((g for g in frs if abs(g.x - f.x) < 3 and g.y > f.y + 0.5), key=lambda g: g.y)
        linhas: list[str] = []
        y, tamanho, anterior = f.y, f.tamanho, None
        for g in coluna:
            t = g.texto.strip()
            if _PEDACO_DE_PRECO.match(t):
                if t.startswith("R") and g.y - y <= 4 * max(tamanho, g.tamanho):
                    anterior = g
                break
            if "R$" in t or _SELO.search(t) or g.y - y > 2.5 * max(tamanho, g.tamanho):
                break  # "R$/Un" (tabela de preço por unidade), selo "leve 5 pague 4" ou texto de outro cartão
            if not _QUANTIDADE.match(t):
                linhas.insert(0, t)
            y, tamanho = g.y, g.tamanho
        cartoes.append(_Cartao(f, linhas, anterior, centavos, por_kg))

    por_rs = {id(c.rs): c for c in cartoes}
    itens = []
    for c in sorted(cartoes, key=lambda c: -c.rs.y):  # de cima para baixo: a variante vem depois do cartão de cima
        if not c.linhas:
            continue
        nome_linhas = c.linhas
        acima = por_rs.get(id(c.anterior)) if c.anterior is not None else None
        if acima is not None and acima.linhas and not _tem_marca(c.linhas):
            c.cabeca = acima.cabeca if acima.cabeca is not None else acima.linhas[: len(acima.linhas) - len(c.linhas)]
            c.cabeca = c.cabeca or acima.linhas
            comum = _TAMANHO_NO_NOME.sub(" ", " ".join(c.cabeca)).replace("/", " ")
            nome_linhas = [comum, *c.linhas]
        nome = _nome(nome_linhas)
        itens.append(ItemDoEncarte(nome, c.centavos, None, c.por_kg or por_peso(nome), pagina))
    return itens, 0


def ler_com(pdf: bytes, montar) -> Encarte:
    """Lê o PDF página a página com a montagem de cartões da rede. A validade é a escrita no encarte; se páginas
    disserem datas diferentes, fica sem validade (e nada é publicado)."""
    leitor = PdfReader(io.BytesIO(pdf))
    encarte = Encarte(None, None)
    validades: set[tuple[date, date]] = set()
    for n, pagina in enumerate(leitor.pages, start=1):
        frs = fragmentos(pagina)
        if not frs:
            encarte.paginas_sem_texto += 1  # só imagem: sem OCR por enquanto
            continue
        validades |= validades_escritas(" ".join(f.texto for f in frs))
        itens, ambiguos = montar(frs, n)
        encarte.itens += itens
        encarte.ambiguos += ambiguos
    if len(validades) == 1:
        encarte.inicio, encarte.fim = validades.pop()
    elif validades:
        encarte.validades_divergentes = True
    return encarte


def ler_super_a(pdf: bytes) -> Encarte:
    return ler_com(pdf, itens_em_coluna)
