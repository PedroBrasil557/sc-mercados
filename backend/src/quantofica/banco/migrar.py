"""Aplica as migrações pendentes (db/migrations) e, com --dados, os dados iniciais (db/dados).

Roda sozinho a cada publicação na Fly.io (release_command), antes de a nova versão da API entrar no ar.
Cada migração roda numa transação e fica registrada em `migracao_aplicada`: publicar de novo não reaplica nada.
Os arquivos de db/dados são idempotentes (on conflict), então rodam sempre.

    python -m quantofica.banco.migrar [--dados] [--marcar-ate 0005]

--marcar-ate registra como aplicadas, sem rodar, as migrações até aquela (banco criado à mão antes deste script).
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

# No container, db/ fica ao lado do pacote; no repositório, dois níveis acima de backend/.
_CANDIDATAS = [Path("/app/db"), Path(__file__).resolve().parents[4] / "db"]
PASTA_DB = next((p for p in _CANDIDATAS if p.is_dir()), _CANDIDATAS[-1])


def pendentes(conn: psycopg.Connection, pasta: Path) -> list[Path]:
    conn.execute(
        "create table if not exists migracao_aplicada (nome text primary key, aplicada_em timestamptz not null default now())"
    )
    feitas = {r[0] for r in conn.execute("select nome from migracao_aplicada").fetchall()}
    return [f for f in sorted(pasta.glob("*.sql")) if f.name not in feitas]


def migrar(dsn: str, pasta_db: Path = PASTA_DB, dados: bool = False, marcar_ate: str | None = None) -> list[str]:
    aplicadas = []
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as conn:
        # Duas publicações ao mesmo tempo não podem migrar juntas.
        conn.execute("select pg_advisory_lock(hashtext('quantofica.migrar'))")
        for arquivo in pendentes(conn, pasta_db / "migrations"):
            so_registrar = bool(marcar_ate and arquivo.name[:4] <= marcar_ate)
            with conn.transaction():
                if not so_registrar:
                    conn.execute(arquivo.read_text(encoding="utf-8"))
                conn.execute("insert into migracao_aplicada (nome) values (%s)", (arquivo.name,))
            aplicadas.append(f"{arquivo.name} (só registrada)" if so_registrar else arquivo.name)
        if dados:
            for arquivo in sorted((pasta_db / "dados").glob("*.sql")):
                # Os arquivos de dados trazem o próprio begin/commit.
                conn.execute(arquivo.read_text(encoding="utf-8"))
                aplicadas.append(f"dados/{arquivo.name}")
    return aplicadas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aplica as migrações pendentes do banco")
    p.add_argument("--dados", action="store_true", help="também carrega db/dados (bairros, lojas, catálogo inicial)")
    p.add_argument("--marcar-ate", metavar="NNNN", help="registra sem rodar as migrações até este número")
    args = p.parse_args(argv)
    for nome in migrar(os.environ["DATABASE_URL"], dados=args.dados, marcar_ate=args.marcar_ate):
        print(nome)
    return 0


if __name__ == "__main__":
    sys.exit(main())
