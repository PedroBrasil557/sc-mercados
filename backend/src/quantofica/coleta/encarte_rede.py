"""Encarte em PDF publicado pela própria rede (Super A): o mesmo desenho do Fort (fort.py), pronto para outras redes.

Para cada encarte novo: baixa o PDF, lê nomes, preços e validade escritos (encarte_pdf) e só publica se a validade
estiver escrita e incluir hoje. Cada item é casado com o catálogo (ou achado na busca do Giassi e da Cooper, que
devolvem o EAN); o preço vale em todas as lojas da rede em Blumenau até o fim da validade; o que não casar vai para
a fila de revisão (tipo 'encarte', com a rede na proposta, para o painel e o Revisor publicarem nas lojas certas).
Preço por quilo fica de fora (R4). Encarte lido fica em encarte_lido e não é lido de novo.

A rede tem site no cadastro, então o Vigia acompanha a coleta em execucao_coleta. Ali "precos_gravados" é quantos
preços de encarte da rede estão valendo agora (a cobertura), não quantos entraram na rodada: encarte já lido não
grava nada, e isso não é coleta parada.
"""

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime, time
from urllib.parse import unquote, urlparse

import psycopg
from psycopg.rows import dict_row
from pypdf.errors import PyPdfError

from ..agentes import rodada
from .fort import FUSO, origem, preparar, publicar_item, registrar_encarte
from .vtex import ClienteHttp


@dataclass(frozen=True)
class PdfDaRede:
    url: str
    titulo: str
    id: str | None = None  # None: o id sai do conteúdo (o Super A troca o PDF no mesmo endereço)


def id_do_conteudo(url: str, pdf: bytes) -> str:
    """ "supera_semanal:3f2a9c..." : o mesmo PDF tem o mesmo id; PDF trocado no mesmo endereço é encarte novo."""
    nome = unquote(urlparse(url).path.rsplit("/", 1)[-1]).removesuffix(".pdf")
    return f"{nome}:{hashlib.sha256(pdf).hexdigest()[:16]}"


def rodar(conn, http, agora: datetime, rede: str, pdfs: list[PdfDaRede], ler) -> dict:
    lt = preparar(conn, rede, agora)
    hoje = agora.astimezone(FUSO).date()
    prefixo = origem(rede)
    for e in pdfs:
        if e.id and e.id in lt.lidos:
            continue
        pdf = http.binario(e.url)
        if not pdf:
            continue  # tenta de novo amanhã
        encarte_id = e.id or id_do_conteudo(e.url, pdf)
        if encarte_id in lt.lidos:
            continue
        try:
            enc = ler(pdf)
        except (PyPdfError, ValueError, KeyError) as erro:  # PDF cortado ou fora do padrão: tenta amanhã
            lt.resumo["pdf_ilegivel"] += 1
            print(f"{rede}: não deu para ler {e.url}: {erro!r}")
            continue
        inicio, fim = enc.inicio, enc.fim  # só a validade escrita no encarte: sem ela, nada é publicado
        if inicio and inicio > hoje:
            continue  # encarte que ainda não começou: lê quando começar
        titulo = e.titulo
        if enc.paginas_sem_texto and not enc.itens:
            titulo += " (só imagem, sem texto)"
        for chave, n in (("ambiguos", enc.ambiguos), ("paginas_sem_texto", enc.paginas_sem_texto),
                         ("validade_divergente", int(enc.validades_divergentes))):  # fmt: skip
            if n:
                lt.resumo[chave] += n
        # Um encarte por vez, inteiro ou nada: se cair no meio, amanhã lê de novo sem duplicar preço.
        with conn.transaction():
            precos = 0
            if fim and fim >= hoje and lt.lojas:
                valido_ate = datetime.combine(fim, time(23, 59, 59), FUSO)
                for item in enc.itens:
                    if item.por_kg:  # preço por quilo depende da pesagem (R4)
                        continue
                    proposta = {
                        "nome": item.nome,
                        "preco_centavos": item.preco_centavos,
                        "condicional_centavos": item.condicional_centavos,
                        "encarte": titulo,
                        "encarte_id": encarte_id,
                        "valido_ate": fim.isoformat(),
                        "pagina": item.pagina,
                        "rede": rede,
                        "pdf": e.url,  # para conferir o item no encarte
                    }
                    precos += publicar_item(
                        conn, http, lt, item, proposta, encarte_id, agora, valido_ate, f"{prefixo}:{encarte_id}:p{item.pagina}"
                    )
            registrar_encarte(conn, lt, encarte_id, titulo, fim, len(enc.itens), precos, agora)
    return dict(lt.resumo)


def precos_valendo(conn, rede: str, agora: datetime) -> int:
    """Preços de encarte da rede que valem agora, em todas as lojas (a cobertura do encarte)."""
    return conn.execute(
        """select count(*) as n from preco_atual a join loja l on l.id = a.loja_id join rede r on r.id = l.rede_id
           where r.nome = %s and a.fonte = 'encarte' and a.valido_ate >= %s""",
        (rede, agora),
    ).fetchone()["n"]


def com_execucao(conn, rede: str, agora: datetime, coletar) -> dict:
    """Roda `coletar()` registrando a rodada em execucao_coleta (o Vigia avisa se a coleta da rede parar)."""
    linha = conn.execute("select id from rede where nome = %s", (rede,)).fetchone()
    if linha is None:
        raise RuntimeError(f"rede {rede!r} não está cadastrada")
    execucao = conn.execute(
        "insert into execucao_coleta (rede_id, iniciada_em) values (%s, %s) returning id", (linha["id"], agora)
    ).fetchone()["id"]
    try:
        resumo = coletar()
    except Exception as erro:
        conn.execute(
            "update execucao_coleta set terminada_em = now(), status = 'falhou', erro = %s where id = %s",
            (repr(erro)[:2000], execucao),
        )
        raise
    resumo["precos_valendo"] = precos_valendo(conn, rede, agora)
    conn.execute(
        """update execucao_coleta set terminada_em = now(), status = 'ok', eans_pedidos = %s, precos_gravados = %s,
           enviados_revisao = %s where id = %s""",
        (resumo.get("itens", 0), resumo["precos_valendo"], resumo.get("revisao", 0), execucao),
    )
    return resumo


def main(rodar_rede) -> int:
    """`rodar_rede(conn, http, agora)` de cada rede (por ora, supera), com a rodada do Leitor de encartes."""
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with rodada(conn, "leitor_encartes") as resumo:
            r = rodar_rede(conn, ClienteHttp(), datetime.now(UTC))
            resumo.update(r)
            print(r)
    return 0
