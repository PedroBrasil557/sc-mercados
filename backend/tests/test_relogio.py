from datetime import datetime
from zoneinfo import ZoneInfo

from quantofica.coleta.relogio import proxima

BRT = ZoneInfo("America/Sao_Paulo")


def test_todo_dia_as_5h():
    # Terça 28/10/2026, 9h -> quarta às 5h
    assert proxima(datetime(2026, 10, 28, 9, 0, tzinfo=BRT)) == datetime(2026, 10, 29, 5, 0, tzinfo=BRT)


def test_quinta_tambem_as_15h():
    # Quinta 29/10/2026, 10h -> mesma quinta às 15h; depois das 15h -> sexta às 5h
    assert proxima(datetime(2026, 10, 29, 10, 0, tzinfo=BRT)) == datetime(2026, 10, 29, 15, 0, tzinfo=BRT)
    assert proxima(datetime(2026, 10, 29, 15, 0, tzinfo=BRT)) == datetime(2026, 10, 30, 5, 0, tzinfo=BRT)


def test_aceita_horario_em_utc():
    # 07:59 UTC = 04:59 em Brasília -> 05:00 do mesmo dia
    utc = datetime(2026, 10, 30, 7, 59, tzinfo=ZoneInfo("UTC"))
    assert proxima(utc) == datetime(2026, 10, 30, 5, 0, tzinfo=BRT)
