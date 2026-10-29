"""Leitura de encarte que é só imagem (Komprão, publicado no Issuu): OCR com a posição de cada palavra.

O desenho é o do encarte_pdf: o que vale é a posição na página. Cada cartão tem o nome (letra pequena,
preta ou branca, em linhas alinhadas à esquerda) e, à direita ou logo abaixo, o preço em dígitos grandes
("R$" pequeno + inteiro + "," + centavos). No cartão do Clube K há dois preços: o maior é o normal e o
menor é o condicional (só para quem é do clube): fica guardado, mas não entra no total (R5).

OCR erra, então a leitura tem duas camadas:
- o Tesseract (pytesseract.image_to_data) lê as palavras dos nomes na página inteira; os preços são achados
  pela cor (dígitos vermelhos, ou amarelos sobre o fundo vermelho), recortados sem o "R$" (que o Tesseract
  gruda nos dígitos: "R$ 2,79" vira "52,79") e lidos um a um, duas vezes em escalas diferentes;
- a montagem dos cartões (itens_da_pagina) só aceita preço bem formado, com as duas leituras iguais e
  confiança alta, e nome legível. O que ficar em dúvida sai em `duvidosos`, para uma pessoa conferir na imagem.
A montagem não depende do Tesseract: os testes usam palavras com posição sintéticas.
"""

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from .encarte_pdf import ItemDoEncarte

LARGURA_PADRAO = 1965  # largura das páginas do Issuu; outra resolução é redimensionada para esta
CONFIANCA_PRECO = 70  # confiança mínima (0 a 100, mediana das três leituras) do preço
CONFIANCA_NOME = 70  # confiança média mínima das palavras do nome
CONFIANCA_PALAVRA = 45  # abaixo disso a palavra é ruído (texto da embalagem na foto, sombra...)
CONFIANCA_DATA = 70
ALTURA_NOME = (9, 34)  # altura em pixels da letra dos nomes
ALTURA_PRECO = (38, 120)  # altura dos dígitos do preço
DISTANCIA_MAXIMA = 4.0  # entre o preço e o nome do cartão, em alturas do preço
VALIDADE_MAXIMA = timedelta(days=60)  # encarte publicado no Issuu vale no máximo isto depois de publicado

_PRECO = re.compile(r"^(\d{1,3}),(\d{2})$")
# Palavras que encerram o nome: limite por cliente, chamada do clube, "leve 12 pague 10", parcelamento, "R$".
_FIM_DO_NOME = re.compile(r"^(limite|nesta|exclusivo|clube|leve\d*|pague\d*|juros|r\$|de\.|por)$", re.I)
# Perto do preço, indicam o selo do Clube K ("clube K", "EXCLUSIVO NO KOMPRÃO", "NESTA OFERTA A UN. SAI POR").
_CLUBE = re.compile(r"^(clube|exclusivo|nesta|oferta|leve\d*|pague\d*)", re.I)
# "Tkg", "Ikg", "l00g": o OCR troca o "1" inicial por letra antes da unidade.
_UM_TROCADO = re.compile(r"^1?[TIl|](\d*(?:kg|g|ml|l)\.?)$", re.I)
_VALIDADE = re.compile(
    r"v[aá]lid[oa]s?\s+(?:de\s+)?(\d{1,2})(?:/(\d{1,2}))?(?:/(\d{2,4}))?\s+(?:a|at[eé])\s+(\d{1,2})/(\d{1,2})/(\d{2,4})", re.I
)
_VALIDADE_ATE = re.compile(r"v[aá]lid[oa]s?\s+at[eé]\s+(\d{1,2})/(\d{1,2})/(\d{2,4})", re.I)


@dataclass(frozen=True)
class Palavra:
    x: int
    y: int  # topo (a imagem cresce para baixo)
    largura: int
    altura: int
    confianca: float  # 0 a 100, como o Tesseract
    texto: str

    @property
    def direita(self) -> int:
        return self.x + self.largura

    @property
    def base(self) -> int:
        return self.y + self.altura


@dataclass
class _Bloco:
    x: int
    topo: int
    base: int
    direita: int
    palavras: list[Palavra]
    precos: list[tuple[Palavra, bool]] = field(default_factory=list)  # (preço, é do clube)

    @property
    def nome(self) -> str:
        return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", " ".join(p.texto for p in self.palavras))).strip()


@dataclass
class PaginaLida:
    itens: list[ItemDoEncarte]
    duvidosos: list[ItemDoEncarte]  # leitura incerta: vão para revisão, sem publicar
    ambiguos: int
    validade: tuple[date | None, date] | None


# ---------- montagem dos cartões (sem OCR) ----------


def _linhas(palavras: list[Palavra]) -> list[list[Palavra]]:
    """Palavras na mesma altura e próximas, da esquerda para a direita."""
    linhas: list[list[Palavra]] = []
    for p in sorted(palavras, key=lambda p: p.x):
        for linha in linhas:
            u = linha[-1]
            alt = max(u.altura, p.altura)
            mesma_altura = abs((u.y + u.base) / 2 - (p.y + p.base) / 2) < 0.5 * alt
            if mesma_altura and -0.5 * alt <= p.x - u.direita < 2.5 * alt:
                linha.append(p)
                break
        else:
            linhas.append([p])
    return linhas


def _corrigir(p: Palavra) -> Palavra:
    texto = _UM_TROCADO.sub(r"1\1", p.texto.strip())
    return p if texto == p.texto else Palavra(p.x, p.y, p.largura, p.altura, p.confianca, texto)


def _blocos(palavras: list[Palavra]) -> list[_Bloco]:
    """Linhas alinhadas à esquerda, uma logo abaixo da outra, formam o nome de um cartão."""
    candidatas = [
        _corrigir(p) for p in palavras
        if p.confianca >= CONFIANCA_PALAVRA and ALTURA_NOME[0] <= p.altura <= ALTURA_NOME[1]
        and re.search(r"[0-9A-Za-zÀ-ú]", p.texto)
    ]  # fmt: skip
    blocos: list[_Bloco] = []
    for linha in sorted(_linhas(candidatas), key=lambda linha: min(p.y for p in linha)):
        fim = next((i for i, p in enumerate(linha) if _FIM_DO_NOME.match(p.texto)), len(linha))
        linha = linha[:fim]
        if not linha or not re.search(r"[A-Za-zÀ-ú]{2}", " ".join(p.texto for p in linha)):
            continue
        x, topo = linha[0].x, min(p.y for p in linha)
        base, direita = max(p.base for p in linha), max(p.direita for p in linha)
        altura = base - topo
        for b in blocos:
            # a linha seguinte começa no mesmo x (ou um pouco à direita, se o OCR perdeu a primeira palavra)
            alinhada = b.x - 25 < x < b.x + max(25, 0.5 * (b.direita - b.x))
            if alinhada and -0.3 * altura <= topo - b.base < 1.2 * altura:
                b.palavras += linha
                b.base, b.direita = max(b.base, base), max(b.direita, direita)
                break
        else:
            blocos.append(_Bloco(x, topo, base, direita, list(linha)))
    return blocos


def _do_clube(preco: Palavra, palavras: list[Palavra]) -> bool:
    """Preço dentro do selo do Clube K: "clube" ou "NESTA OFERTA..." logo acima, "EXCLUSIVO NO KOMPRÃO" logo abaixo."""
    for p in palavras:
        if not _CLUBE.match(p.texto) or p.direita < preco.x - preco.altura or p.x > preco.direita + preco.altura:
            continue
        if -2.5 * preco.altura <= p.y - preco.y <= 2.2 * preco.altura:
            return True
    return False


def _nome_minimo(b: _Bloco) -> bool:
    """Ao menos duas palavras de verdade: menos que isso é texto da embalagem na foto, nem vale revisar."""
    return len([p for p in b.palavras if len(re.findall(r"[A-Za-zÀ-ú]", p.texto)) >= 3]) >= 2 and len(b.nome) >= 8


def _nome_legivel(b: _Bloco) -> bool:
    return _nome_minimo(b) and sum(p.confianca for p in b.palavras) / len(b.palavras) >= CONFIANCA_NOME


def centavos(texto: str) -> int | None:
    m = _PRECO.match(texto.strip())
    return int(m.group(1)) * 100 + int(m.group(2)) if m else None


def itens_da_pagina(palavras: list[Palavra], precos: list[Palavra], pagina: int) -> tuple[list, list, int]:
    """(itens confiáveis, itens duvidosos, cartões ambíguos). `precos` são os números grandes lidos à parte."""
    blocos = _blocos(palavras)
    for preco in precos:
        if centavos(preco.texto) is None or not ALTURA_PRECO[0] <= preco.altura <= ALTURA_PRECO[1]:
            continue
        melhor, menor = None, float("inf")
        for b in blocos:
            # o preço fica à direita do nome ou logo abaixo dele, nunca à esquerda nem acima do topo
            if preco.x < b.x - 0.3 * preco.altura or preco.base < b.topo:
                continue
            # a distância vertical pesa o dobro: texto da embalagem na foto fica acima do preço, o nome fica ao lado
            dx, dy = max(0, preco.x - b.direita), 2 * max(0, preco.y - b.base)
            d = (dx * dx + dy * dy) ** 0.5
            if d < menor:
                melhor, menor = b, d
        if melhor is not None and menor < DISTANCIA_MAXIMA * preco.altura:
            melhor.precos.append((preco, _do_clube(preco, palavras)))

    itens, duvidosos, ambiguos = [], [], 0
    for b in blocos:
        if not b.precos:
            continue
        valores = sorted({centavos(p.texto) for p, _ in b.precos})
        if len(valores) > 2 or (len(b.precos) == 1 and b.precos[0][1]) or not _nome_minimo(b):
            ambiguos += 1  # três preços, só o do clube (o normal não foi lido) ou nome ilegível: fica de fora
            continue
        nome = b.nome
        por_kg = bool(re.search(r"\bkg\.?\s*$", nome, re.I))
        condicional = valores[0] if len(valores) == 2 else None
        item = ItemDoEncarte(nome, valores[-1], condicional, por_kg, pagina)
        confiavel = min(p.confianca for p, _ in b.precos) >= CONFIANCA_PRECO and _nome_legivel(b)
        (itens if confiavel else duvidosos).append(item)
    return itens, duvidosos, ambiguos


def _ano(texto: str) -> int:
    return int(texto) + (2000 if len(texto) == 2 else 0)


def validade(palavras: list[Palavra], publicado_em: date | None = None) -> tuple[date | None, date] | None:
    """ "Preços válidos de 01 a 02/11/2025 ou enquanto durarem os estoques" -> (01/11/2025, 02/11/2025).

    Data lida com pouca confiança não vale; e, se o Issuu diz quando o encarte foi publicado, a validade tem de
    terminar depois disso e no máximo 60 dias depois (um "2025" lido como "2026" publicaria encarte velho)."""
    for linha in _linhas([p for p in palavras if p.texto.strip()]):
        texto = " ".join(p.texto for p in linha)
        datas = [p for p in linha if re.search(r"\d", p.texto)]
        if not datas or min(p.confianca for p in datas) < CONFIANCA_DATA:
            continue
        inicio = None
        try:
            if m := _VALIDADE.search(texto):
                fim = date(_ano(m.group(6)), int(m.group(5)), int(m.group(4)))
                mes = int(m.group(2)) if m.group(2) else fim.month
                ano = _ano(m.group(3)) if m.group(3) else fim.year - (mes > fim.month)
                inicio = date(ano, mes, int(m.group(1)))
                if not m.group(2) and inicio > fim:  # "de 30 a 02/11": começa no mês anterior
                    inicio = date(fim.year - (fim.month == 1), fim.month - 1 or 12, int(m.group(1)))
            elif m := _VALIDADE_ATE.search(texto):
                fim = date(_ano(m.group(3)), int(m.group(2)), int(m.group(1)))
            else:
                continue
        except ValueError:
            continue
        if inicio and not timedelta(0) <= fim - inicio <= timedelta(days=31):
            continue  # encarte de mais de um mês: data mal lida
        if publicado_em and not publicado_em - timedelta(days=7) <= fim <= publicado_em + VALIDADE_MAXIMA:
            continue
        return inicio, fim
    return None


# ---------- OCR (Tesseract) ----------


def _componentes(mascara) -> list[tuple[int, int, int, int]]:
    """Caixas (x0, y0, x1, y1) das manchas conectadas de tinta numa máscara preto/branco (tinta = 255)."""
    w, h = mascara.size
    px = bytearray(mascara.tobytes())
    caixas = []
    i = px.find(255)
    while i != -1:
        px[i] = 0
        pilha = [i]
        x0 = x1 = i % w
        y0 = y1 = i // w
        while pilha:
            j = pilha.pop()
            x, y = j % w, j // w
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for k in (j - 1 if x else -1, j + 1 if x < w - 1 else -1, j - w, j + w if y < h - 1 else -1):
                if k >= 0 and px[k]:
                    px[k] = 0
                    pilha.append(k)
        caixas.append((x0, y0, x1 + 1, y1 + 1))
        i = px.find(255, i + 1)
    return caixas


def grupos_de_digitos(caixas: list[tuple[int, int, int, int]], altura_min: int, altura_max: int) -> list[tuple]:
    """Manchas altas lado a lado com uma vírgula (mancha pequena embaixo, no meio delas) = um preço.
    Devolve (x0, y0, x1, y1, x da vírgula) de cada grupo, já sem o "R$" (que é baixo e fica fora)."""
    altas = sorted((c for c in caixas if altura_min <= c[3] - c[1] <= altura_max and c[2] - c[0] <= 3 * (c[3] - c[1])),
                   key=lambda c: c[0])  # fmt: skip
    grupos: list[list] = []
    for c in altas:
        alt = c[3] - c[1]
        for g in grupos:
            u = g[-1]
            sobrepoe = min(u[3], c[3]) - max(u[1], c[1]) >= 0.6 * min(alt, u[3] - u[1])
            if sobrepoe and 0 <= c[0] - u[2] <= 0.7 * alt:
                g.append(c)
                break
        else:
            grupos.append([c])
    saida = []
    for g in grupos:
        x0, y0, x1, y1 = g[0][0], min(c[1] for c in g), g[-1][2], max(c[3] for c in g)
        alt = y1 - y0
        virgulas = [
            (c[0] + c[2]) / 2
            for c in caixas
            if c not in g and x0 < c[0] and c[2] < x1 and c[3] - c[1] < 0.5 * alt and y0 + 0.5 * alt < c[1] < y1 + 0.2 * alt
        ]
        if len(g) >= 2 and len(virgulas) == 1:
            saida.append((x0, y0, x1, y1, virgulas[0]))
    return saida


def _largura(digitos: str) -> float:
    return sum(0.6 if d == "1" else 1.0 for d in digitos)  # o "1" é mais estreito que os outros dígitos


def virgula_confere(digitos: str, x0: float, x1: float, virgula: float) -> bool:
    """A vírgula achada na imagem separa os dígitos lidos na proporção certa (inteiro x 2 centavos)?
    Pega o dígito a mais ou a menos que o OCR inventa ou perde ("16,99" lido "699")."""
    if not 3 <= len(digitos) <= 5 or not x0 < virgula < x1:
        return False
    esperado = _largura(digitos[:-2]) / _largura(digitos[-2:])
    medido = (virgula - x0) / (x1 - virgula)
    return abs(medido / esperado - 1) < 0.35


def _tesseract():
    import pytesseract  # só quem lê encarte de imagem precisa do Tesseract instalado

    return pytesseract


def _ler_numero(recorte) -> tuple[str, float]:
    """Recorte com só os dígitos do preço -> (dígitos, confiança). Lido em três escalas que têm de concordar;
    a vírgula lida é ignorada (o OCR a perde muito), porque preço sempre tem dois dígitos de centavos."""
    from PIL import Image, ImageOps

    pt = _tesseract()
    leituras = []
    for alvo in (24, 40, 56):  # altura dos dígitos em pixels
        esc = alvo / recorte.height
        im = recorte.resize((max(1, int(recorte.width * esc)), alvo), Image.LANCZOS)
        im = ImageOps.expand(im, border=alvo // 2, fill=255)
        d = pt.image_to_data(im, lang="por", config="--psm 7 -c tessedit_char_whitelist=0123456789,", output_type=pt.Output.DICT)
        partes = [(t.strip(), float(c)) for t, c in zip(d["text"], d["conf"], strict=True) if t.strip()]
        if not partes:
            return "", 0.0
        leituras.append(("".join(t for t, _ in partes).replace(",", ""), min(c for _, c in partes)))
    textos = {t for t, _ in leituras}
    confiancas = sorted(c for _, c in leituras)
    return leituras[-1][0], (confiancas[1] if len(textos) == 1 else 0.0)  # mediana, se as três concordam


def _mascaras(img):
    """Tinta dos preços: vermelho (sobre amarelo ou branco) e amarelo (sobre o fundo vermelho)."""
    from PIL import ImageChops

    r, g, b = img.split()

    def faixa(canal, minimo, maximo):
        return canal.point(lambda v: 255 if minimo <= v <= maximo else 0)

    vermelho = ImageChops.multiply(ImageChops.multiply(faixa(r, 150, 255), faixa(g, 0, 110)), faixa(b, 0, 120))
    amarelo = ImageChops.multiply(ImageChops.multiply(faixa(r, 200, 255), faixa(g, 170, 255)), faixa(b, 0, 120))
    return vermelho, amarelo


def precos_da_imagem(img) -> list[Palavra]:
    """Os números grandes da página (img em RGB, largura padrão), com a confiança da leitura."""
    from PIL import Image

    meia = img.resize((img.width // 2, img.height // 2), Image.BILINEAR)
    precos = []
    for mascara in _mascaras(meia):
        caixas = _componentes(mascara)
        for x0, y0, x1, y1, virgula in grupos_de_digitos(caixas, ALTURA_PRECO[0] // 2, ALTURA_PRECO[1] // 2):
            alt = y1 - y0
            # a vírgula desce abaixo da linha dos dígitos; o "R$" fica à esquerda de x0 e não entra
            recorte = mascara.crop((x0, y0 - alt // 5, x1, y1 + alt // 3)).point(lambda v: 0 if v else 255)
            digitos, conf = _ler_numero(recorte)
            if not re.fullmatch(r"\d{3,5}", digitos) or digitos.startswith("0") and len(digitos) > 3:
                continue
            if not virgula_confere(digitos, x0, x1, virgula):
                conf = 0.0  # a leitura não bate com a imagem: vai para revisão, se tiver nome
            precos.append(Palavra(x0 * 2, y0 * 2, (x1 - x0) * 2, alt * 2, conf, f"{int(digitos[:-2])},{digitos[-2:]}"))
    return precos


FAIXA, PASSO = 450, 300  # a página é lida em faixas sobrepostas: o Tesseract lê melhor um pedaço que a página toda


def palavras_da_imagem(img) -> list[Palavra]:
    pt = _tesseract()
    lidas: list[Palavra] = []
    for topo in range(0, max(1, img.height - FAIXA + PASSO), PASSO):
        fundo = min(img.height, topo + FAIXA)
        d = pt.image_to_data(img.crop((0, topo, img.width, fundo)), lang="por", config="--psm 11", output_type=pt.Output.DICT)
        for i, t in enumerate(d["text"]):
            y, alt = d["top"][i] + topo, d["height"][i]
            cortada = (y <= topo + 2 and topo > 0) or (y + alt >= fundo - 2 and fundo < img.height)
            if t.strip() and not cortada:
                lidas.append(Palavra(d["left"][i], y, d["width"][i], alt, float(d["conf"][i]), t.strip()))
    # a mesma palavra lida em duas faixas: fica a leitura mais confiante
    palavras: list[Palavra] = []
    for p in sorted(lidas, key=lambda p: -p.confianca):
        if not any(_sobreposicao(p, q) > 0.5 for q in palavras):
            palavras.append(p)
    return palavras


def _sobreposicao(a: Palavra, b: Palavra) -> float:
    w = min(a.direita, b.direita) - max(a.x, b.x)
    h = min(a.base, b.base) - max(a.y, b.y)
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / max(1, min(a.largura * a.altura, b.largura * b.altura))


def ler_pagina(imagem: bytes, pagina: int, publicado_em: date | None = None) -> PaginaLida:
    from PIL import Image

    img = Image.open(io.BytesIO(imagem)).convert("RGB")
    if abs(img.width - LARGURA_PADRAO) > 0.05 * LARGURA_PADRAO:
        img = img.resize((LARGURA_PADRAO, round(img.height * LARGURA_PADRAO / img.width)), Image.LANCZOS)
    palavras = palavras_da_imagem(img)
    itens, duvidosos, ambiguos = itens_da_pagina(palavras, precos_da_imagem(img), pagina)
    return PaginaLida(itens, duvidosos, ambiguos, validade(palavras, publicado_em))
