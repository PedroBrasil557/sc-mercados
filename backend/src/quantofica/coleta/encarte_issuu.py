"""Leitura de encarte pela camada de texto do Issuu (sem OCR).

Cada página publicada no Issuu tem, além da imagem, uma camada com o texto do PDF original
(layers.isu.pub/<publicação>/<revisão>/v2/page_N.bin): protobuf compactado com gzip, em que cada trecho de texto
traz a string em UTF-8, o tamanho da fonte, a matriz de posição (escala e x, y da linha de base, no espaço em pixels
da imagem da página) e a posição de cada letra. Os preços vêm em pedaços ("R$", "13", ",", "99"), como no PDF do Fort.

O texto é exato (nomes, preços e a validade do rodapé), então a leitura é mais completa e confiável que o OCR: os
trechos viram as mesmas "palavras com posição" que o OCR produz, e a montagem dos cartões (encarte_ocr) é a mesma.
Sem camada (encarte que é só imagem), o coletor cai no OCR.
"""

import gzip
import re
import struct
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .encarte_ocr import LARGURA_PADRAO, PaginaLida, Palavra, itens_da_pagina, validade

ALTURA_LETRA = 0.72  # altura da letra maiúscula/dígito em relação ao tamanho da fonte
ESCALA_PRECO = 1.2  # trecho de dígitos com escala acima disto (fonte ~2x a dos nomes) é preço
CONFIANCA = 99  # texto do próprio PDF: não há leitura incerta


@dataclass(frozen=True)
class Trecho:
    texto: str
    fonte: float  # tamanho efetivo da fonte, em pixels da imagem
    x: float
    base: float  # linha de base
    letras: tuple[float, ...]  # início de cada letra, em pixels, a partir de x


def _varint(b: bytes, i: int) -> tuple[int, int]:
    n = s = 0
    while True:
        c = b[i]
        i += 1
        n |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return n, i


def _campos(b: bytes) -> dict[int, list]:
    i, d = 0, defaultdict(list)
    while i < len(b):
        chave, i = _varint(b, i)
        f, w = chave >> 3, chave & 7
        if w == 0:
            v, i = _varint(b, i)
        elif w == 1:
            v, i = b[i : i + 8], i + 8
        elif w == 5:
            v, i = struct.unpack("<f", b[i : i + 4])[0], i + 4
        elif w == 2:
            n, i = _varint(b, i)
            v, i = b[i : i + n], i + n
        else:
            raise ValueError("formato desconhecido")
        if i > len(b):
            raise ValueError("mensagem cortada")
        d[f].append((w, v))
    return d


def trechos(bruto: bytes) -> list[Trecho]:
    """Todos os trechos de texto da página (mensagens com string no campo 1 e matriz de 6 floats no campo 5)."""
    dados = gzip.decompress(bruto) if bruto[:2] == b"\x1f\x8b" else bruto
    saida: list[Trecho] = []

    def visitar(b: bytes, prof: int) -> None:
        try:
            d = _campos(b)
        except (ValueError, IndexError, struct.error):
            return
        texto = d.get(1, [(None, None)])[0]
        matriz = d.get(5, [(None, None)])[0]
        if texto[0] == 2 and matriz[0] == 2 and len(matriz[1]) == 24:
            try:
                s = texto[1].decode("utf-8")
            except UnicodeDecodeError:
                s = ""
            if s and s.isprintable():
                a, _, _, _, x, y = struct.unpack("<6f", matriz[1])
                fonte = (d[3][0][1] if 3 in d and d[3][0][0] == 5 else 50.0) * a
                letras = d.get(6, [(None, b"")])[0][1]
                pos = struct.unpack(f"<{len(letras) // 4}f", letras) if isinstance(letras, bytes) else ()
                saida.append(Trecho(s, fonte, x, y, tuple(p * a for p in pos)))
                return
        if prof < 12:
            for _, campos in d.items():
                for w, v in campos:
                    if w == 2 and len(v) > 2:
                        visitar(v, prof + 1)

    visitar(dados, 0)
    return saida


def _larguras(ts: list[Trecho]) -> dict[str, float]:
    """Largura de cada letra (em frações do tamanho da fonte): o menor avanço visto até a letra seguinte. Entre
    palavras o avanço é maior (o espaço não vem como letra), e é assim que os espaços voltam."""
    avancos: dict[str, list[float]] = defaultdict(list)
    for t in ts:
        if len(t.letras) != len(t.texto) or t.fonte <= 0:
            continue
        for c, a, b in zip(t.texto, t.letras, t.letras[1:], strict=False):
            avancos[c].append((b - a) / t.fonte)
    return {c: _largura(v) for c, v in avancos.items()}


def _largura(avancos: list[float]) -> float:
    """Os avanços de uma letra formam dois grupos quando ela às vezes vem antes de um espaço ("g" de "200g un."): a
    largura é a mediana do grupo de baixo. Um grupo só (o "R" com ajuste fino em "RA") é a mediana de todos."""
    v = sorted(avancos)
    saltos = [(b - a, i) for i, (a, b) in enumerate(zip(v, v[1:], strict=False))]
    maior, onde = max(saltos, default=(0.0, 0))
    grupo = v[: onde + 1] if maior > 0.12 else v
    return grupo[len(grupo) // 2]


# Espaços que nem a posição das letras devolve: "ArrozBranco", "CaféNESCAFE", "170gun." (o tamanho tem de ficar
# separado para o casamento reconhecer "170g").
_JUNTAS = [
    (re.compile(r"([a-zà-ÿ])([A-ZÀ-Þ])"), r"\1 \2"),
    (re.compile(r"(\d(?:kg|g|ml|l|L|un))(un\.?|Un\.?)$"), r"\1 \2"),
]


def _separar(texto: str) -> list[str]:
    for padrao, troca_por in _JUNTAS:
        texto = padrao.sub(troca_por, texto)
    return texto.split()


def _palavras(t: Trecho, larguras: dict[str, float], fator: float) -> list[Palavra]:
    altura = t.fonte * ALTURA_LETRA
    topo = t.base - altura
    if len(t.letras) != len(t.texto):
        return [Palavra(round(t.x * fator), round(topo * fator), round(altura * len(t.texto) * 0.6 * fator),
                        round(altura * fator), CONFIANCA, t.texto)]  # fmt: skip
    saida, inicio = [], 0
    for i in range(1, len(t.texto) + 1):
        fim_de_palavra = i == len(t.texto)
        if not fim_de_palavra:
            largura = larguras.get(t.texto[i - 1], 0.55) * t.fonte
            fim_de_palavra = (t.letras[i] - t.letras[i - 1]) - largura > 0.18 * t.fonte
        if fim_de_palavra:
            x0 = t.x + t.letras[inicio]
            x1 = t.x + t.letras[i - 1] + larguras.get(t.texto[i - 1], 0.55) * t.fonte
            pedacos = _separar(t.texto[inicio:i])
            passo = (x1 - x0) / max(1, len(pedacos))
            for k, pedaco in enumerate(pedacos):
                saida.append(Palavra(round((x0 + k * passo) * fator), round(topo * fator), round(passo * fator),
                                     round(altura * fator), CONFIANCA, pedaco))  # fmt: skip
            inicio = i
    return saida


def _ao_lado(g: Trecho, t: Trecho, ate: float) -> bool:
    """O trecho t vem logo depois de g, na mesma linha (até `ate` vezes a fonte de g)."""
    return 0 < t.x - g.x < ate * g.fonte and abs(t.base - g.base) < 0.35 * g.fonte


def _precos(ts: list[Trecho], fator: float) -> list[Palavra]:
    """ "R$" "13" "," "99" (ou "13,99" num trecho só) -> uma palavra "13,99" na posição dos dígitos grandes."""
    grande = ESCALA_PRECO * 50 * 0.52  # fonte do preço: bem maior que a dos nomes
    grandes = [t for t in ts if re.fullmatch(r"\d{1,3}", t.texto) and t.fonte >= grande]
    virgulas = [t for t in ts if t.texto.strip() == ","]
    centavos = sorted((t for t in ts if re.fullmatch(r"\d{2}", t.texto)), key=lambda t: t.x)
    saida = []
    for g in grandes:
        v = next((t for t in virgulas if _ao_lado(g, t, 2.2)), None)
        c = next((t for t in centavos if t is not g and _ao_lado(g, t, 2.8) and (v is None or t.x > v.x)), None)
        if v is None or c is None:
            continue
        altura = g.fonte * ALTURA_LETRA
        texto = f"{g.texto},{c.texto}"
        saida.append(Palavra(round(g.x * fator), round((g.base - altura) * fator),
                             round((c.x + c.fonte - g.x) * fator), round(altura * fator), CONFIANCA, texto))  # fmt: skip
    for t in ts:  # preço num trecho só
        if m := re.fullmatch(r"(\d{1,3}),(\d{2})", t.texto.strip()):
            if t.fonte >= ESCALA_PRECO * 50 * 0.52:
                altura = t.fonte * ALTURA_LETRA
                saida.append(Palavra(round(t.x * fator), round((t.base - altura) * fator), round(t.fonte * 2.5 * fator),
                                     round(altura * fator), CONFIANCA, m.group(0)))  # fmt: skip
    return saida


def ler_camada(bruto: bytes, pagina: int, largura_pagina: int, publicado_em: date | None = None) -> PaginaLida | None:
    """A página lida pela camada de texto, no mesmo formato do OCR. None se a camada não tem texto."""
    ts = trechos(bruto)
    if len(ts) < 5:
        return None
    fator = LARGURA_PADRAO / largura_pagina
    larguras = _larguras(ts)
    pequenos = [
        t for t in ts
        if (not re.fullmatch(r"[\d,]{1,3}", t.texto) or t.fonte < ESCALA_PRECO * 50 * 0.52) and not t.texto.startswith("R$")
    ]  # fmt: skip
    palavras = [p for t in pequenos for p in _palavras(t, larguras, fator)]
    itens, duvidosos, ambiguos = itens_da_pagina(palavras, _precos(ts, fator), pagina)
    return PaginaLida(itens, duvidosos, ambiguos, validade(palavras, publicado_em))


def largura_do_jpeg(bruto: bytes) -> int | None:
    """Largura da imagem JPEG, lida do cabeçalho (sem abrir a imagem)."""
    i = 2
    while i + 9 < len(bruto):
        if bruto[i] != 0xFF:
            return None
        marca, tamanho = bruto[i + 1], struct.unpack(">H", bruto[i + 2 : i + 4])[0]
        if marca in (0xC0, 0xC1, 0xC2):
            return struct.unpack(">H", bruto[i + 7 : i + 9])[0]
        i += 2 + tamanho
    return None
