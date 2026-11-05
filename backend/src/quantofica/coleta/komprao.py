"""Encartes do Komprão Koch Atacadista nas lojas de Blumenau.

O Komprão não tem loja virtual. A página de ofertas de Blumenau (komprao.com.br/ofertas/blumenau/, robots.txt
libera tudo) embute o encarte do Issuu (conta "superkoch"). A API do WordPress (wp-json/wp/v2/oferta) só
devolve o título da cidade, sem o encarte; por isso a fonte é o HTML da página. O leitor do Issuu publica a
lista de páginas (reader3.isu.pub); cada página é uma imagem JPEG (image.isu.pub) e, quando o PDF original tinha
texto, uma camada de texto (layers.isu.pub) com nomes, preços e validade exatos (encarte_issuu). Sem camada, a
página é lida por OCR (encarte_ocr). Os dois domínios do Issuu não têm robots.txt; o ClienteHttp confere mesmo assim.

A página de Blumenau às vezes fica parada num encarte velho (em 11/2026 ainda mostrava o de 11/2025). Por isso
a outra fonte é o perfil público da rede no Issuu (issuu.com/superkoch, robots.txt libera; só /api/ e áreas de
conta são proibidas), que lista todos os encartes com título: entram os do Komprão marcados "(REDE)" (valem
para todas as lojas) ou que citam Blumenau. Inauguração e ofertas de outras cidades ficam de fora.

Depois de lido, segue o desenho do Fort (e usa as mesmas funções): cada item é casado com o catálogo ou
achado nos sites, o preço vale para as três lojas de Blumenau até o fim da validade escrita no encarte, e o
que não casar vai para a fila de revisão. Leitura incerta do OCR também vai para a fila, marcada para uma
pessoa conferir o preço na imagem; sem validade legível, nada é publicado.

Rodar:  python -m quantofica.coleta.komprao
Agenda (.github/workflows/encartes.yml): todo dia de manhã, depois do Fort; encarte já lido é pulado.
"""

import gzip
import html
import json
import os
import re
import sys
from datetime import UTC, date, datetime, time
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg.rows import dict_row

from ..agentes import rodada
from ..qualidade import monitor
from ..qualidade.monitor import Anomalia
from . import encarte_issuu, encarte_ocr
from .fort import FUSO, preparar, publicar_item, registrar_encarte
from .vtex import ClienteHttp

PAGINA = "https://komprao.com.br/ofertas/blumenau/"
PERFIL = "https://issuu.com/superkoch"
CONTA = "superkoch"
# Título de encarte do Komprão que vale em Blumenau: o da rede inteira ou o que cita a cidade.
VALE_EM_BLUMENAU = re.compile(r"\bKOMPR[AÃ]O\b.*(\(REDE\)|\bREDE\b|\bBLUMENAU\b)", re.I)
LEITOR = "https://reader3.isu.pub/{usuario}/{documento}/reader3_4.json"
REDE = "Komprão"


def encartes(http) -> list[dict]:
    """Os encartes embutidos na página de Blumenau: documento e conta do Issuu e o título do quadro."""
    bruto = http.binario(PAGINA)
    if not bruto:
        return []
    texto = bruto.decode("utf-8", "replace")
    achados = []
    for tag in re.findall(r"<iframe\b[^>]*>", texto, re.I):
        src = re.search(r'\bsrc="([^"]+)"', tag)
        if not src or "issuu.com/embed" not in src.group(1):
            continue
        q = parse_qs(urlparse(html.unescape(src.group(1))).query)
        documento, usuario = (q.get("d") or [None])[0], (q.get("u") or [None])[0]
        if not documento or not usuario:
            continue
        titulo = re.search(r'\btitle="([^"]*)"', tag)
        achados.append({
            "documento": documento,
            "usuario": usuario,
            "titulo": html.unescape(titulo.group(1)) if titulo else documento,
        })  # fmt: skip
    return achados


def encartes_da_rede(http) -> list[dict]:
    """Encartes do Komprão no perfil da rede no Issuu que valem em Blumenau (rede inteira ou a cidade)."""
    bruto = http.binario(PERFIL)
    if not bruto:
        return []
    texto = bruto.decode("utf-8", "replace")
    achados = []
    # Cada cartão: endereço do documento, capa (a revisão atual: image.isu.pub/<revisão>/jpg/...) e título.
    cartoes = re.findall(
        r'href="/' + CONTA + r'/docs/([A-Za-z0-9_.-]+)".*?image\.isu\.pub/([0-9]{12}-[0-9a-f]+)/.*?'
        r'data-testid="publication-card-title"[^>]*>([^<]+)<',
        texto,
        re.S,
    )
    for doc, revisao, titulo in cartoes:
        titulo = html.unescape(titulo).strip()
        if VALE_EM_BLUMENAU.search(titulo):
            achados.append({"documento": doc, "usuario": CONTA, "titulo": titulo, "revisao": revisao})
    return achados


def validade_do_titulo(titulo: str, publicado: date | None) -> tuple[date, date] | None:
    """ "... 02.11 A 06.11 (REDE)" -> (02/11, 06/11) do ano da publicação. Só quando o rodapé não for legível."""
    m = re.search(r"(\d{1,2})[./](\d{1,2})\s*(?:A|ATÉ|ATE|-)\s*(\d{1,2})[./](\d{1,2})", titulo.upper())
    if not m or publicado is None:
        return None
    try:
        inicio = date(publicado.year, int(m.group(2)), int(m.group(1)))
        fim = date(publicado.year + (int(m.group(4)) < int(m.group(2))), int(m.group(4)), int(m.group(3)))
    except ValueError:
        return None
    return (inicio, fim) if inicio <= fim and (fim - inicio).days <= 31 else None


def _json(bruto: bytes | None):
    if not bruto:
        return None
    if bruto[:2] == b"\x1f\x8b":  # o Issuu guarda o JSON compactado e responde assim mesmo sem pedirmos
        bruto = gzip.decompress(bruto)
    try:
        return json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def publicado_em(revisao: str) -> date | None:
    """A revisão do Issuu começa pela data da publicação: "251031230419" -> 31/10/2025."""
    try:
        return datetime.strptime(revisao[:6], "%y%m%d").date()
    except ValueError:
        return None


MAX_PAGINAS = 40


def _pela_revisao(http, revisao: str) -> dict | None:
    """O leitor do Issuu (reader3) às vezes fica preso numa revisão velha do documento ou não responde (11/2026). A
    capa no perfil diz a revisão atual; as páginas dela são image.isu.pub/<revisão>/jpg/page_N.jpg, até a primeira
    que não existe. Baixa aqui mesmo (é o jeito de saber quantas páginas há) e guarda para o OCR."""
    imagens: dict[str, bytes] = {}
    for n in range(1, MAX_PAGINAS + 1):
        url = f"https://image.isu.pub/{revisao}/jpg/page_{n}.jpg"
        bruto = http.binario(url)
        if not bruto:
            break
        imagens[url] = bruto
    if not imagens:
        return None
    rev, publicacao = revisao.split("-", 1)
    camadas = [f"https://layers.isu.pub/{publicacao}/{rev}/v2/page_{n}.bin" for n in range(1, len(imagens) + 1)]
    return {
        "id": f"{rev}-{publicacao}",
        "paginas": list(imagens),
        "camadas": camadas,
        "publicado_em": publicado_em(rev),
        "imagens": imagens,
    }


def documento(http, encarte: dict) -> dict | None:
    """Páginas (URLs das imagens) e identificação de uma revisão do encarte no Issuu."""
    if encarte.get("revisao"):
        return _pela_revisao(http, encarte["revisao"])
    j = _json(http.binario(LEITOR.format(**encarte))) or {}
    doc = j.get("document") or {}
    revisao, publicacao = str(doc.get("revisionId") or ""), str(doc.get("publicationId") or "")
    abertas = [p for p in doc.get("pages") or [] if p.get("imageUri") and not p.get("isPagePaywalled")]
    paginas = [f"https://{p['imageUri']}" for p in abertas]
    camadas = [
        f"https://{(p.get('layersInfo') or {}).get('uri')}" if (p.get("layersInfo") or {}).get("uri") else None for p in abertas
    ]
    if not revisao or not publicacao or not paginas:
        return None
    # Encarte novo no mesmo documento é uma revisão nova: entra como outro encarte.
    return {"id": f"{revisao}-{publicacao}", "paginas": paginas, "camadas": camadas, "publicado_em": publicado_em(revisao)}


def _pela_camada(http, doc: dict, n: int, imagem: bytes):
    """A página pela camada de texto do Issuu (exata), se houver; None para cair no OCR."""
    camadas = doc.get("camadas") or []
    url = camadas[n - 1] if n <= len(camadas) else None
    bruto = http.binario(url) if url else None
    if not bruto:
        return None
    try:
        largura = encarte_issuu.largura_do_jpeg(imagem) or encarte_ocr.LARGURA_PADRAO
        pagina = encarte_issuu.ler_camada(bruto, n, largura, doc["publicado_em"])
    except (OSError, ValueError, EOFError):
        return None
    return pagina if pagina and (pagina.itens or pagina.duvidosos or pagina.validade) else None


def rodar(conn, http, agora: datetime, ler_pagina=encarte_ocr.ler_pagina) -> dict:
    lt = preparar(conn, REDE, agora)
    hoje = agora.astimezone(FUSO).date()
    vistos: set[str] = set()
    for e in encartes(http) + encartes_da_rede(http):
        if e["documento"] in vistos:
            continue
        vistos.add(e["documento"])
        doc = documento(http, e)
        if doc is None or doc["id"] in lt.lidos:
            continue
        titulo = f"{e['titulo']} ({e['documento']})"
        lidas, validades, completo = [], set(), True
        for n, url in enumerate(doc["paginas"], start=1):
            imagem = (doc.get("imagens") or {}).get(url) or http.binario(url)
            if imagem is None:
                completo = False
                break
            pagina = _pela_camada(http, doc, n, imagem)
            if pagina is None:
                pagina = ler_pagina(imagem, n, doc["publicado_em"])
                lt.resumo["paginas_por_ocr"] += 1
            else:
                lt.resumo["paginas_por_texto"] += 1
            lidas.append((url, pagina))
            if pagina.validade:
                validades.add(pagina.validade[1])
                if pagina.validade[1] < hoje:
                    break  # encarte vencido: nem baixa o resto
        if not completo and not (validades and max(validades) < hoje):
            continue  # faltou página: tenta de novo amanhã
        # A validade vem do rodapé; páginas que dizem datas diferentes = leitura errada em alguma: não publica.
        fim = validades.pop() if len(validades) == 1 else None
        inicio = next((p.validade[0] for _, p in lidas if p.validade and p.validade[1] == fim), None)
        if fim is None and not validades and (pelo_titulo := validade_do_titulo(e["titulo"], doc["publicado_em"])):
            inicio, fim = pelo_titulo  # rodapé ilegível: vale a data do título que a própria rede escreveu
        if inicio and inicio > hoje:
            continue  # encarte da semana que vem: lê quando começar
        itens = sum(len(p.itens) + len(p.duvidosos) for _, p in lidas)
        lt.resumo["ambiguos"] += sum(p.ambiguos for _, p in lidas)
        # Um encarte por vez, inteiro ou nada: se cair no meio, amanhã lê de novo sem duplicar preço.
        with conn.transaction():
            precos = 0
            if fim and fim >= hoje and lt.lojas:
                valido_ate = datetime.combine(fim, time(23, 59, 59), FUSO)
                for url, pagina in lidas:
                    for item, conferir in [(i, False) for i in pagina.itens] + [(i, True) for i in pagina.duvidosos]:
                        if item.por_kg:  # preço por quilo depende da pesagem (R4)
                            continue
                        proposta = {
                            "nome": item.nome,
                            "preco_centavos": item.preco_centavos,
                            "condicional_centavos": item.condicional_centavos,
                            "encarte": titulo,
                            "encarte_id": doc["id"],
                            "valido_ate": fim.isoformat(),
                            "pagina": item.pagina,
                            "rede": REDE,
                            "imagem": url,  # para conferir o item na página do encarte
                        }
                        if conferir:  # OCR incerto: não publica; uma pessoa confere o preço na imagem
                            anomalia = Anomalia(
                                f"komprao:{doc['id']}:{item.nome}"[:300], "item do encarte com leitura incerta (OCR)"
                            )
                            lt.resumo["duvidosos"] += monitor.abrir_revisao(conn, "encarte", anomalia, {
                                **proposta, "conferir_preco": True
                            })  # fmt: skip
                            continue
                        precos += publicar_item(
                            conn, http, lt, item, proposta, doc["id"], agora, valido_ate, f"komprao:{doc['id']}:p{item.pagina}"
                        )
            registrar_encarte(conn, lt, doc["id"], titulo, fim, itens, precos, agora)
    return dict(lt.resumo)


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "leitor_encartes") as resumo:
            r = rodar(conn, ClienteHttp(), datetime.now(UTC))
            resumo.update(r)
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
