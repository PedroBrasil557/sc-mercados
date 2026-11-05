"""Quanto custa ir ao mercado (R8), por meio de transporte.

Só serve para a SUGESTÃO de mercado: o app nunca soma a viagem ao preço (os valores na tela são os do caixa) e
quem decide aonde ir é sempre a pessoa. Valores de Blumenau (04/11/2026):
- carro e moto: custo por km (combustível e desgaste), como antes;
- Uber/99: não há tabela oficial; estimativa de mercado por perna: maior entre a tarifa mínima e base + km;
- táxi: Decreto municipal 15.419/2024 (bandeirada R$ 5,35; R$ 4,36 por km na bandeira 1);
- ônibus: passagem com cartão R$ 5,50 (2026), igual para qualquer mercado; perto (até 1 km) se vai a pé;
- a pé: nada.
Táxi e aplicativo cobram pelo trajeto nas ruas: a distância em linha reta (R14) é multiplicada por FATOR_RUA.
"""

from dataclasses import dataclass
from enum import StrEnum

FATOR_RUA = 1.3
A_PE_ATE_KM = 1.0


class Modo(StrEnum):
    CARRO = "carro"
    MOTO = "moto"
    APLICATIVO = "aplicativo"
    TAXI = "taxi"
    ONIBUS = "onibus"
    A_PE = "a_pe"


@dataclass(frozen=True)
class Corrida:
    base_centavos: int
    km_centavos: int
    minimo_centavos: int = 0


POR_KM = {Modo.CARRO: 90, Modo.MOTO: 40}  # centavos por km, sem fator de rua (como sempre foi)
CORRIDAS = {
    Modo.APLICATIVO: Corrida(base_centavos=250, km_centavos=180, minimo_centavos=750),
    Modo.TAXI: Corrida(base_centavos=535, km_centavos=436),
}
PASSAGEM_ONIBUS_CENTAVOS = 550


def perna(modo: Modo, km: float) -> int:
    """Custo de uma ida (ou de uma volta), em centavos."""
    km = max(0.0, km)
    if modo in POR_KM:
        return round(km * POR_KM[modo])
    if modo in CORRIDAS:
        c = CORRIDAS[modo]
        return max(c.minimo_centavos, round(c.base_centavos + c.km_centavos * km * FATOR_RUA))
    if modo is Modo.ONIBUS:
        return 0 if km <= A_PE_ATE_KM else PASSAGEM_ONIBUS_CENTAVOS
    return 0


def ida_e_volta(modo: Modo, km: float) -> int:
    return 2 * perna(modo, km)


def rota(modo: Modo, pernas_km: list[float]) -> int:
    """Casa -> mercado A -> mercado B -> casa: cada perna paga a sua corrida (ou passagem)."""
    return sum(perna(modo, km) for km in pernas_km)
