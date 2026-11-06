"""Encartes do Super A Atacadista (rede do Angeloni) na loja de Blumenau.

A página de encartes de Blumenau (encartes.superaatacadista.com.br/blumenau/) tem um botão por encarte, com o PDF em
statics.angeloni.com.br/encartes/Supera/<nome>.pdf. Os dois domínios não têm robots.txt (404: nada proibido); o
ClienteHttp confere mesmo assim. A página guarda os botões de encartes antigos escondidos (classes
elementor-hidden-desktop, -tablet e -mobile juntas): só os visíveis são baixados. O PDF novo substitui o antigo no
mesmo endereço, então o id do encarte é o nome do arquivo mais o hash do conteúdo: PDF igual não é relido.

O PDF tem texto (encarte_pdf.ler_super_a): nome, preço e a validade escrita ("Ofertas válidas de 02/11 a 05/11/2026
nas lojas de ... Blumenau"). O encarte não tem código de barras; o casamento, a publicação e a fila de revisão são
os do Fort (encarte_rede).

Rodar:  python -m quantofica.coleta.supera
Agenda (.github/workflows/encartes.yml): todo dia de manhã; encarte já lido é pulado.
"""

import html
import re
import sys
from datetime import datetime
from urllib.parse import quote

from . import encarte_pdf, encarte_rede
from .encarte_rede import PdfDaRede

PAGINA = "https://encartes.superaatacadista.com.br/blumenau/"
REDE = "Super A Atacadista"
_PDF = re.compile(r'href="(https://statics\.angeloni\.com\.br/encartes/Supera/[^"]+\.pdf)"')
_ESCONDIDO = ("elementor-hidden-desktop", "elementor-hidden-tablet", "elementor-hidden-mobile")


def encartes(http) -> list[PdfDaRede]:
    """Os encartes visíveis na página de Blumenau, na ordem da página."""
    bruto = http.binario(PAGINA)
    if not bruto:
        return []
    texto = bruto.decode("utf-8", "replace")
    achados: dict[str, PdfDaRede] = {}
    for bloco in re.split(r'(?=<div class="elementor-element )', texto):
        m = _PDF.search(bloco)
        if not m:
            continue
        abertura = bloco.split(">", 1)[0]
        if all(c in abertura for c in _ESCONDIDO):
            continue  # botão de encarte antigo, escondido em todas as telas
        url = quote(html.unescape(m.group(1)), safe=":/%")
        rotulo = re.search(r'elementor-button-text">(.*?)</span>', bloco, re.S)
        titulo = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(rotulo.group(1)))).strip() if rotulo else ""
        achados.setdefault(url, PdfDaRede(url, f"{titulo or 'Encarte'} ({url.rsplit('/', 1)[-1]})"))
    return list(achados.values())


def rodar(conn, http, agora: datetime, ler=encarte_pdf.ler_super_a) -> dict:
    return encarte_rede.com_execucao(conn, REDE, agora, lambda: encarte_rede.rodar(conn, http, agora, REDE, encartes(http), ler))


if __name__ == "__main__":
    sys.exit(encarte_rede.main(rodar))
