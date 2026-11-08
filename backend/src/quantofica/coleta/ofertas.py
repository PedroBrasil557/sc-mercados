"""Calcula as ofertas reais de todas as lojas e guarda pronto para a tela (rodar depois de cada coleta).

Rodar:  python -m quantofica.coleta.ofertas
"""

import os
import sys
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from ..api.detalhes import gravar_ofertas


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        print(f"ofertas calculadas: {gravar_ofertas(conn, datetime.now(UTC))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
