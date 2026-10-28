from pathlib import Path

import pytest

from quantofica.banco.migrar import achar_pasta_db, migrar


def test_pasta_sem_migracoes_falha_em_vez_de_passar_em_silencio(tmp_path: Path):
    (tmp_path / "migrations").mkdir()
    with pytest.raises(FileNotFoundError):
        migrar("postgresql://nao-conecta", pasta_db=tmp_path)


def test_acha_db_rodando_de_dentro_de_backend(monkeypatch):
    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(raiz / "backend")
    assert achar_pasta_db() == raiz / "db"
