"""Aplica as migrações pendentes (db/migrations) e, com --dados, os dados iniciais (db/dados).

Roda no GitHub Actions (.github/workflows/banco.yml) sempre que as migrações ou os dados mudam na main.
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


def achar_pasta_db() -> Path:
    """Onde estão db/migrations: no container (/app/db), rodando da raiz ou de backend/, ou no checkout do pacote.

    Instalado com `pip install .` (GitHub Actions), o __file__ fica em site-packages, longe do repositório:
    por isso a pasta de trabalho vem antes.
    """
    candidatas = [Path("/app/db"), Path.cwd() / "db", Path.cwd().parent / "db", Path(__file__).resolve().parents[4] / "db"]
    for pasta in candidatas:
        if (pasta / "migrations").is_dir():
            return pasta
    raise FileNotFoundError("não achei db/migrations; informe com --pasta")


def pendentes(conn: psycopg.Connection, pasta: Path) -> list[Path]:
    conn.execute(
        "create table if not exists migracao_aplicada (nome text primary key, aplicada_em timestamptz not null default now())"
    )
    feitas = {r[0] for r in conn.execute("select nome from migracao_aplicada").fetchall()}
    return [f for f in sorted(pasta.glob("*.sql")) if f.name not in feitas]


def migrar(dsn: str, pasta_db: Path | None = None, dados: bool = False, marcar_ate: str | None = None) -> list[str]:
    pasta_db = pasta_db or achar_pasta_db()
    if not any((pasta_db / "migrations").glob("*.sql")):
        # Pasta errada não pode passar como "nada pendente": foi assim que a 1ª publicação não criou nenhuma tabela.
        raise FileNotFoundError(f"nenhuma migração em {pasta_db / 'migrations'}")
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
    p.add_argument("--pasta", type=Path, help="pasta db/ com migrations e dados (padrão: procurada automaticamente)")
    args = p.parse_args(argv)
    aplicadas = migrar(os.environ["DATABASE_URL"], pasta_db=args.pasta, dados=args.dados, marcar_ate=args.marcar_ate)
    for nome in aplicadas:
        print(nome)
    if not any(n.endswith(".sql") and not n.startswith("dados/") for n in aplicadas):
        print("nenhuma migração pendente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
