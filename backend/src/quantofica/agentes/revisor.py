"""Revisor: decide cada item da fila de revisão como um agente faria, mas por regras escritas.

Para cada item: junta as evidências, decide (descartar, resolver, ligar a produto, sugerir ou deixar
para a pessoa), escreve a confiança e o motivo, e só age sozinho com confiança de pelo menos 90%.
Toda decisão fica em execucao_agente (modelo "regras-v1", custo zero) e aparece no painel.

Rodar:  python -m quantofica.agentes.revisor
"""

import ast
import os
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..coleta import fort
from ..coleta.casamento import PARE, VARIOS, Candidato, casar, palavras
from ..coleta.vtex import ClienteHttp
from ..regras import tamanho as tam
from . import rodada

VERSAO = "regras-v1"
CERTEZA = 0.9  # a partir daqui o Revisor age sozinho; abaixo, deixa sugestão
# Não é item de mercado: o encarte do Fort também anuncia utilidades domésticas.
NAO_MERCADO = {
    "chaleira", "panela", "frigideira", "liquidificador", "ventilador", "cafeteira", "sanduicheira", "torradeira",
    "batedeira", "airfryer", "fritadeira", "travesseiro", "cobertor", "edredom", "lencol", "churrasqueira",
    "cadeira", "mesa", "assadeira", "garrafa termica", "pote hermetico", "tapete", "cooler",
}  # fmt: skip
ATACADO = {"balde", "fardo", "display", "galao"}


@dataclass
class Decisao:
    acao: str  # descartar | resolver | ligar | sugerir | humano
    confianca: float
    motivo: str
    produtos: list[str] = field(default_factory=list)
    conferido: list[str] = field(default_factory=list)  # o que o Revisor olhou antes de decidir


def _reais(c: int) -> str:
    return f"R$ {c / 100:.2f}".replace(".", ",")


def _fmt(t: tam.Tamanho) -> str:
    q = t.quantidade
    if t.unidade in ("g", "ml") and q >= 1000:
        return f"{q / 1000:g}".replace(".", ",") + (" kg" if t.unidade == "g" else " l")
    return f"{q:g} {t.unidade}"


# ---------- itens do encarte ----------


def decidir_encarte(proposta: dict, hoje, valido_ate, catalogo: list[Candidato], procurar=None) -> Decisao:
    """`procurar(nome, termos)` busca nos sites e cadastra o que casar (devolve produto_ids); None = não buscar."""
    nome = proposta.get("nome") or ""
    conferido = []
    texto = palavras(nome)
    if valido_ate and valido_ate < hoje:
        return Decisao(
            "descartar", 0.99, f"O encarte venceu em {valido_ate:%d/%m}: esse preço não vale mais.", conferido=["validade"]
        )
    conferido.append("validade")
    if (set(texto) & NAO_MERCADO) or any(" ".join(texto[i : i + 2]) in NAO_MERCADO for i in range(len(texto))):
        return Decisao("descartar", 0.92, "Não é item de mercado (utilidade doméstica).", conferido=[*conferido, "tipo de item"])
    t = tam.extrair(nome)
    conferido.append("tamanho")
    if t is None:
        return Decisao(
            "descartar", 0.95, "O encarte não diz o tamanho: não dá para comparar com justiça (R2).", conferido=conferido
        )
    if set(texto) & ATACADO or t.quantidade >= 10000:
        return Decisao("descartar", 0.92, f"Tamanho de atacado ({_fmt(t)}): fora do catálogo de varejo.", conferido=conferido)

    conferido.append("catálogo")
    casados = casar(nome, catalogo)
    if casados:
        return Decisao("ligar", 0.95, "Casou com o catálogo (que cresceu depois que o encarte foi lido).",
                       [c.chave for c in casados], conferido)  # fmt: skip

    if procurar is not None:
        conferido.append("busca nos sites")
        distintas = [w for w in texto if w not in PARE | VARIOS and not re.match(r"^\d", w)]
        tamanho_txt = next((w for w in texto if re.match(r"^\d+([.,]\d+)?(kg|g|ml|l|litros?)$", w)), "")
        for termos in (" ".join(distintas[:2] + [tamanho_txt]).strip(), " ".join(distintas[:4])):
            if termos and (achados := procurar(nome, termos)):
                return Decisao(
                    "ligar", 0.9, f"Achei nos sites buscando “{termos}”: mesma marca, tipo e tamanho.", achados, conferido
                )

    # Sugestão: mesma marca, mesmo tipo e mesmo tamanho, mas o nome não bateu o suficiente para ter certeza.
    palavras_item = set(texto)
    parecidos = []
    for c in catalogo:
        if not c.marca or c.tamanho is None or not c.tamanho.mesmo_que(t, 0.005):
            continue
        marca, nome_c = set(palavras(c.marca)), palavras(c.nome)
        if marca and marca <= palavras_item and nome_c and nome_c[0] in palavras_item:
            parecidos.append((len(palavras_item & set(nome_c)) / max(len(palavras_item), 1), c))
    if parecidos:
        parecidos.sort(key=lambda x: -x[0])
        melhores = [c for _, c in parecidos[:3]]
        return Decisao("sugerir", round(min(0.85, 0.5 + parecidos[0][0] / 2), 2),
                       f"Mesma marca, tipo e tamanho ({_fmt(t)}); o resto do nome é diferente. Confira se é o mesmo.",
                       [c.chave for c in melhores], conferido)  # fmt: skip
    outros = sorted({_fmt(c.tamanho) for c in catalogo if c.tamanho and c.marca and set(palavras(c.marca)) <= palavras_item
                     and palavras(c.nome)[:1] == texto[:1]})  # fmt: skip
    if outros:
        lista = ", ".join(outros[:4])
        return Decisao("humano", 0.5, f"O catálogo tem esse produto só em outro tamanho ({lista}), não em {_fmt(t)}. "
                       "Ligar a outro tamanho deixaria a comparação injusta.", conferido=conferido)  # fmt: skip
    return Decisao(
        "humano",
        0.4,
        "Produto que o catálogo ainda não tem e que não achei nos sites do Giassi e da Cooper.",
        conferido=conferido,
    )


# ---------- alertas da coleta ----------

# O Vigia escreve: "tamanho diferente entre redes: Cooper 'Nome A', Sam's Club 'Nome B'" (repr do Python).
# O nome entre aspas vem depois de um espaço e antes de ", " ou do fim (o apóstrofo de "Sam's" não conta).
_NOMES = re.compile(r"""\s('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")(?=,\s|$)""")


def _nomes(motivo: str) -> list[str]:
    saida = []
    for literal in _NOMES.findall(motivo):
        try:
            saida.append(ast.literal_eval(literal))
        except (ValueError, SyntaxError):
            continue
    return saida


def decidir_tamanho_divergente(motivo: str) -> Decisao:
    nomes = _nomes(motivo)
    conferido = ["nomes nas redes"]
    if any(tam.embalagem_multipla(n) for n in nomes):
        return Decisao("resolver", 0.95, "Um dos sites vende o pacote com várias unidades com o código da unidade; "
                       "o coletor já ignora o preço do pacote.", conferido=conferido)  # fmt: skip
    if len(nomes) >= 2:
        comuns = {(x.quantidade, x.unidade) for x in tam.todos(nomes[0])} & {
            (x.quantidade, x.unidade) for x in tam.todos(nomes[1])
        }
        if comuns:
            q, u = sorted(comuns)[0]
            return Decisao("resolver", 0.92, f"Os dois nomes têm {_fmt(tam.Tamanho(q, u))}; o outro número é outra coisa "
                           "(proteína, brinde ou quantidade da promoção).", conferido=conferido)  # fmt: skip
        if any(re.search(r"\b(leve|pague|gratis|desconto|edicao)\b", " ".join(palavras(n))) for n in nomes):
            return Decisao("sugerir", 0.8, "Embalagem promocional (leve mais, pague menos ou edição especial) num dos sites.",
                           conferido=conferido)  # fmt: skip
    return Decisao("humano", 0.5, "O mesmo código de barras aparece com tamanhos diferentes. Se a embalagem mudou, resolva; "
                   "se o cadastro de um site está errado, descarte.", conferido=conferido)  # fmt: skip


def decidir_preco(item: dict, mediana: int | None, agora: datetime) -> Decisao:
    p = item["proposta"] or {}
    if agora - item["criada_em"] > timedelta(days=7):
        return Decisao(
            "descartar", 0.9, "Alerta de mais de 7 dias: as coletas seguintes já trouxeram preço novo.", conferido=["idade"]
        )
    if mediana and p.get("preco_centavos"):
        diferenca = round(100 * (p["preco_centavos"] - mediana) / mediana)
        return Decisao("humano", 0.5, f"{_reais(p['preco_centavos'])} contra a mediana de {_reais(mediana)} nos últimos 30 dias "
                       f"({diferenca:+d}%). Pode ser oferta forte ou erro do site.",
                       conferido=["histórico de 30 dias"])  # fmt: skip
    return Decisao(
        "humano", 0.4, "Preço fora da curva; sem histórico suficiente para decidir.", conferido=["histórico de 30 dias"]
    )


def decidir_coleta(ultima_ok: datetime | None, agora: datetime) -> Decisao:
    if ultima_ok and agora - ultima_ok < timedelta(hours=26):
        return Decisao(
            "resolver", 0.95, f"A coleta voltou a funcionar ({ultima_ok:%d/%m %H:%M} UTC).", conferido=["últimas coletas"]
        )
    return Decisao(
        "humano", 0.6, "A coleta continua sem rodar bem: pode ser mudança no site da rede.", conferido=["últimas coletas"]
    )


def decidir_embalagem(motivo: str) -> Decisao:
    nome = motivo.split(":", 1)[-1].strip().strip("'\"")
    if tam.embalagem_multipla(nome):
        return Decisao("descartar", 0.97, "Pacote com várias unidades usando o código de barras da unidade: o preço do pacote "
                       "não vale para o produto avulso (R1). O coletor já ignora esse preço.",
                       conferido=["nome no site"])  # fmt: skip
    return Decisao(
        "resolver", 0.95, "Não é pacote de vários (a regra antiga confundia “com 30 unidades”).", conferido=["nome no site"]
    )


# ---------- rodada ----------


def rodar(conn, http, agora: datetime, buscar_nos_sites: bool = True) -> dict:
    with rodada(conn, "revisor") as resumo:
        _rodar(conn, http, agora, buscar_nos_sites, resumo)
        return {k: v for k, v in resumo.items() if k != "_id"}


def _rodar(conn, http, agora, buscar_nos_sites, resumo) -> None:
    rodada_id = resumo["_id"]
    hoje = agora.astimezone(fort.FUSO).date()
    catalogo = fort.carregar_catalogo(conn)
    rede_fort = conn.execute("select id from rede where nome = %s", (fort.REDE,)).fetchone()
    itens = conn.execute(
        """select f.id, f.tipo, f.referencia_id, f.motivo, f.proposta_agente as proposta, f.criada_em,
                  (select e.saida from execucao_agente e where e.entrada_ref = f.id::text and e.agente = 'revisor'
                   order by e.criada_em desc limit 1) as anterior
           from fila_revisao f where f.status = 'aberta' order by f.prioridade, f.criada_em"""
    ).fetchall()
    for c in ("analisados", "resolvidos_sozinho", "sugestoes", "para_voce", "sem_mudanca"):
        resumo[c] = 0

    for item in itens:
        resumo["analisados"] += 1
        tipo, motivo = item["tipo"], item["motivo"]
        if tipo == "encarte" and item["proposta"]:
            valido = fort.validade_do_item(conn, rede_fort["id"], item["proposta"]) if rede_fort else None
            # Busca nos sites só na primeira vez que o Revisor vê o item (é o passo caro: 1 requisição por segundo).
            ja_buscou = bool(item["anterior"]) and "busca nos sites" in (item["anterior"].get("conferido") or [])
            procurar = None
            if buscar_nos_sites and http is not None and not ja_buscou:

                def procurar(nome, termos):  # noqa: E306
                    return fort.procurar_nos_sites(conn, http, catalogo, nome, termos)

            d = decidir_encarte(item["proposta"], hoje, valido, catalogo.candidatos, procurar)
        elif tipo == "ean":
            d = decidir_embalagem(motivo)
        elif tipo == "anomalia" and motivo.startswith("tamanho diferente"):
            d = decidir_tamanho_divergente(motivo)
        elif tipo == "anomalia" and "mediana" in motivo:
            d = decidir_preco(item, _mediana(conn, item["referencia_id"], agora), agora)
        elif tipo == "anomalia" and motivo.startswith(("coletor parado", "cobertura caiu")):
            d = decidir_coleta(_ultima_coleta_ok(conn, item["referencia_id"]), agora)
        else:
            d = Decisao("humano", 0.3, "Tipo de item que o Revisor ainda não sabe decidir: precisa de uma pessoa.")

        aplicada = False
        if d.confianca >= CERTEZA and d.acao in ("descartar", "resolver"):
            conn.execute(
                "update fila_revisao set status = %s, revisado_por = 'revisor', decidido_em = now() where id = %s",
                ("descartada" if d.acao == "descartar" else "resolvida", item["id"]),
            )
            aplicada = True
        elif d.confianca >= CERTEZA and d.acao == "ligar" and d.produtos and item["proposta"]:
            fort.ligar_item(conn, str(item["id"]), item["proposta"], d.produtos, "revisor", agora)
            aplicada = True

        anterior = item["anterior"] or {}
        if not aplicada and anterior.get("acao") == d.acao and anterior.get("motivo") == d.motivo:
            resumo["sem_mudanca"] += 1  # mesma conclusão de ontem: não repete o registro
        else:
            conn.execute(
                """insert into execucao_agente (agente, versao_prompt, modelo, entrada_ref, saida, confianca, validacoes,
                                                decisao, custo_tokens, rodada_id)
                   values ('revisor', %s, 'regras (sem IA)', %s, %s, %s, %s, %s, 0, %s)""",
                (
                    VERSAO, str(item["id"]),
                    Jsonb({"acao": d.acao, "motivo": d.motivo, "produtos": d.produtos,
                           "conferido": d.conferido, "aplicada": aplicada}),
                    d.confianca, Jsonb(d.conferido),
                    ("descartado" if d.acao == "descartar" else "publicado") if aplicada else "fila",
                    rodada_id,
                ),
            )  # fmt: skip
        if aplicada:
            resumo["resolvidos_sozinho"] += 1
        elif d.acao == "sugerir":
            resumo["sugestoes"] += 1
        else:
            resumo["para_voce"] += 1


def _mediana(conn, referencia: str, agora: datetime) -> int | None:
    produto = referencia.rsplit(":", 1)[-1]
    try:
        precos = [
            r["preco_centavos"]
            for r in conn.execute(
                """select preco_centavos from observacao_preco
                   where produto_id = %s and faixa = 'varejo' and observado_em >= %s""",
                (produto, agora - timedelta(days=30)),
            ).fetchall()
        ]
    except psycopg.errors.InvalidTextRepresentation:
        return None
    return int(statistics.median(precos)) if precos else None


def _ultima_coleta_ok(conn, referencia: str) -> datetime | None:
    rede = referencia.removeprefix("rede:")
    linha = conn.execute(
        """select max(e.terminada_em) as quando from execucao_coleta e join rede r on r.id = e.rede_id
           where r.nome = %s and e.status = 'ok'""",
        (rede,),
    ).fetchone()
    return linha["quando"] if linha else None


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        print(rodar(conn, ClienteHttp(), datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
