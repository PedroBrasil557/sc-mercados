"""Relógio da coleta: processo sempre de pé que dispara a coleta nos horários combinados.

Hoje a coleta roda pelo GitHub Actions (.github/workflows/coleta.yml); este relógio serve para um servidor próprio.

Todo dia às 5h e na quinta às 15h (horário de Brasília), quando os encartes da semana entram nos sites.
    python -m quantofica.coleta.relogio [--agora]
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import agendador

FUSO = ZoneInfo("America/Sao_Paulo")
HORARIOS = [(None, 5), (3, 15)]  # (dia da semana: 0 = segunda ... 3 = quinta; None = todo dia, hora)


def proxima(agora: datetime) -> datetime:
    """Próximo horário de coleta estritamente depois de `agora` (com fuso)."""
    local = agora.astimezone(FUSO)
    candidatas = []
    for dias in range(8):
        dia = (local + timedelta(days=dias)).date()
        for semana, hora in HORARIOS:
            if semana is None or dia.weekday() == semana:
                quando = datetime(dia.year, dia.month, dia.day, hora, tzinfo=FUSO)
                if quando > local:
                    candidatas.append(quando)
    return min(candidatas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Dispara a coleta nos horários combinados")
    p.add_argument("--agora", action="store_true", help="coleta uma vez ao iniciar")
    args = p.parse_args(argv)
    if args.agora:
        agendador.main([])
    while True:
        alvo = proxima(datetime.now(FUSO))
        print(f"próxima coleta: {alvo:%d/%m %H:%M} (Brasília)", flush=True)
        while (falta := (alvo - datetime.now(FUSO)).total_seconds()) > 0:
            time.sleep(min(falta, 600))  # acorda a cada 10 min: relógio da máquina pode ser ajustado
        try:
            agendador.main([])
        except Exception as erro:  # um dia ruim não derruba o relógio; o monitor acusa "coletor parado"
            print(f"coleta falhou: {erro!r}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    sys.exit(main())
