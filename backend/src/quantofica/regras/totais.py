"""Regras R7 (total justo), R8 (melhor divisão) e R14 (distância pelo centro do bairro)."""

import math
from dataclasses import dataclass, field
from itertools import combinations

LIMITE_PARCIAL = 0.20  # mercado sem mais de 20% dos itens: "comparação parcial"
MINIMO_NUCLEO = 0.5  # loja com metade ou menos dos itens da melhor fica fora do total justo
FOLGA_DIVISAO_CENTAVOS = 1000  # R8: a economia precisa superar o deslocamento + 10 reais

Precos = dict[str, dict[str, int]]  # loja -> produto -> centavos


@dataclass
class Comparacao:
    comuns: list[str]
    totais: dict[str, int]  # loja -> centavos (só itens comuns)
    fora_da_soma: dict[str, list[str]]
    parcial: dict[str, bool]
    ordem: list[str] = field(default_factory=list)  # lojas da mais barata para a mais cara


def comparar(lista: dict[str, int], precos: Precos, distancia_km: dict[str, float] | None = None) -> Comparacao:
    """Total da lista em cada loja, somando só o que todas vendem (R7).

    `lista` é produto -> quantidade. Empate de total desempata pela distância (R10).
    """
    lojas = list(precos)
    produtos = list(lista)
    comuns = [p for p in produtos if all(p in precos[loja] for loja in lojas)]
    totais = {loja: sum(precos[loja][p] * lista[p] for p in comuns) for loja in lojas}
    fora = {loja: [p for p in produtos if p not in precos[loja]] for loja in lojas}
    parcial = {loja: len(fora[loja]) > LIMITE_PARCIAL * len(produtos) for loja in lojas}
    dist = distancia_km or {}
    ordem = sorted(lojas, key=lambda loja: (totais[loja], dist.get(loja, 0.0)))
    return Comparacao(comuns, totais, fora, parcial, ordem)


def nucleo(lista: dict[str, int], precos: Precos) -> set[str]:
    """Lojas que entram no total justo (R7): as que têm mais da metade dos itens que a melhor tem.

    Uma loja com poucos itens (só os do encarte, por exemplo) encolheria os itens comuns de todas; ela
    aparece à parte, com o total só do que tem.
    """
    cobertura = {loja: sum(1 for p in lista if p in precos[loja]) for loja in precos}
    melhor = max(cobertura.values(), default=0)
    return {loja for loja, n in cobertura.items() if n and n > MINIMO_NUCLEO * melhor}


@dataclass
class Divisao:
    lojas: tuple[str, str]
    total_centavos: int
    economia_centavos: int
    custo_deslocamento_centavos: int
    compensa: bool


def melhor_divisao(lista: dict[str, int], precos: Precos, custo_extra_centavos: dict[tuple[str, str], int]) -> Divisao | None:
    """Melhor par de lojas comprando cada item onde é mais barato (R8, no máximo 2 lojas).

    `custo_extra_centavos[(a, b)]` é o custo do deslocamento extra para ir às duas.
    """
    comp = comparar(lista, precos)
    if len(precos) < 2 or not comp.comuns:
        return None
    melhor_unica = comp.totais[comp.ordem[0]]
    melhor: Divisao | None = None
    for a, b in combinations(sorted(precos), 2):
        total = sum(min(precos[a][p], precos[b][p]) * lista[p] for p in comp.comuns)
        custo = custo_extra_centavos.get((a, b), custo_extra_centavos.get((b, a), 0))
        economia = melhor_unica - total
        candidata = Divisao((a, b), total, economia, custo, economia > custo + FOLGA_DIVISAO_CENTAVOS)
        if melhor is None or total < melhor.total_centavos:
            melhor = candidata
    return melhor


@dataclass(frozen=True)
class Recomendacao:
    loja: str
    mais_perto: str
    economia_na_prateleira_centavos: int  # da recomendada frente à mais perto (0 se for a mesma)


def recomendar(
    totais: dict[str, int], distancia_km: dict[str, float], custo_km_centavos: int, base: str | None = None
) -> Recomendacao | None:
    """A melhor loja para a casa (R8 aplicada a uma loja só): a mais perto, a menos que outra economize
    mais do que a ida e volta a mais custa, com a folga de 10 reais.

    Caso real (28/10/2026, Itoupavazinha, rancho): Angeloni Velha 122,77 a 7,1 km; Cooper Mafisa 135,49 a 2,3 km.
    O Angeloni economiza 12,72, mas a viagem a mais custa 8,64 (+10 de folga): fica a Cooper Mafisa.
    """
    if not totais:
        return None
    # A base é o seu mercado (onde a casa já compra); sem ele, a loja mais perto.
    perto = base if base in totais else min(totais, key=lambda loja: (distancia_km.get(loja, 0.0), totais[loja]))
    melhor, ganho_melhor = perto, 0
    for loja, total in totais.items():
        economia = totais[perto] - total
        viagem_a_mais = custo_deslocamento_centavos(
            max(0.0, distancia_km.get(loja, 0.0) - distancia_km.get(perto, 0.0)), custo_km_centavos
        )
        ganho = economia - viagem_a_mais
        if economia > viagem_a_mais + FOLGA_DIVISAO_CENTAVOS and ganho > ganho_melhor:
            melhor, ganho_melhor = loja, ganho
    return Recomendacao(melhor, perto, totais[perto] - totais[melhor])


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta (haversine) do centro do bairro até a loja (R14)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def custo_deslocamento_centavos(distancia_extra_km: float, custo_por_km_centavos: int) -> int:
    """Ida e volta (R14)."""
    return round(distancia_extra_km * 2 * custo_por_km_centavos)
