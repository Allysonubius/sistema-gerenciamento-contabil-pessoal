"""O arquivo de dados não pode morrer por um processo encerrado no meio.

Aconteceu duas vezes: o cabeçalho ficou dizendo que o banco tinha mais páginas
do que o arquivo realmente tinha — um checkpoint do WAL interrompido — e o
banco inteiro deixou de abrir.
"""
from __future__ import annotations

import sqlite3
import struct

import pytest


def paginas_no_cabecalho(caminho) -> int:
    with open(caminho, "rb") as arquivo:
        return struct.unpack(">I", arquivo.read(32)[28:32])[0]


def paginas_no_arquivo(caminho, tamanho_pagina: int = 4096) -> int:
    import os

    return os.path.getsize(caminho) // tamanho_pagina


# --------------------------------------------------------------------------- #
# Gravação que espera o disco
# --------------------------------------------------------------------------- #
def test_o_banco_espera_o_disco_confirmar(sistema):
    """Com NORMAL o SQLite não espera, e um checkpoint interrompido estraga tudo."""
    from app import db

    modo = db.get_connection().execute("PRAGMA synchronous").fetchone()[0]

    assert modo == 2, "synchronous precisa ser FULL (2), não NORMAL (1)"


def test_continua_em_wal(sistema):
    from app import db

    assert db.get_connection().execute(
        "PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_fechar_deixa_o_arquivo_inteiro(sistema, contas):
    """Depois de fechar, o cabeçalho e o arquivo têm de contar a mesma história."""
    from app import db

    caminho = db.DB_PATH
    db.fechar()

    assert paginas_no_cabecalho(caminho) == paginas_no_arquivo(caminho)


def test_fechar_nao_deixa_wal_pendurado(sistema, contas):
    from app import db

    caminho = db.DB_PATH
    db.fechar()
    wal = caminho.with_name(caminho.name + "-wal")

    assert not wal.exists() or wal.stat().st_size == 0


def test_fechar_duas_vezes_nao_quebra(sistema):
    from app import db

    db.fechar()
    db.fechar()          # não levanta


# --------------------------------------------------------------------------- #
# Voltar para uma cópia
# --------------------------------------------------------------------------- #
def test_restaurar_troca_o_banco_pela_copia(sistema, contas):
    from app import db

    copia = db.fazer_backup()
    antes = db.query_one("SELECT COUNT(*) AS n FROM conta")["n"]
    db.execute("DELETE FROM conta WHERE codigo = '5.9.09'")   # mexe em algo

    db.restaurar_copia(copia)

    assert db.query_one("SELECT COUNT(*) AS n FROM conta")["n"] == antes


def test_restaurar_guarda_o_arquivo_danificado(sistema):
    from app import db

    copia = db.fazer_backup()
    db.restaurar_copia(copia)
    guardados = list(db.BACKUP_DIR.glob("contabil_DANIFICADO_*.db"))

    assert guardados, "o arquivo de antes precisa ficar guardado"


def test_restaurar_recusa_uma_copia_tambem_danificada(sistema, tmp_path):
    """Trocar um arquivo quebrado por outro quebrado é piorar."""
    from app import db

    ruim = tmp_path / "ruim.db"
    ruim.write_bytes(b"SQLite format 3\x00" + b"\x00" * 2000)

    with pytest.raises(sqlite3.DatabaseError):
        db.restaurar_copia(ruim)


def test_restaurar_arquivo_inexistente(sistema, tmp_path):
    from app import db

    with pytest.raises(FileNotFoundError):
        db.restaurar_copia(tmp_path / "nao_existe.db")


def test_restaurar_limpa_o_wal_antigo(sistema, contas):
    """WAL do banco velho sobre o banco novo seria corrupção na certa."""
    from app import db

    copia = db.fazer_backup()
    wal = db.DB_PATH.with_name(db.DB_PATH.name + "-wal")
    wal.write_bytes(b"lixo do banco anterior")

    db.restaurar_copia(copia)

    assert not wal.exists()


# --------------------------------------------------------------------------- #
# Cópia forçada
# --------------------------------------------------------------------------- #
def test_copia_forcada_sai_mesmo_sem_mudanca(sistema):
    """Antes de trocar o executável, uma cópia de ontem não serve."""
    from app import db

    primeira = db.backup_automatico()
    assert db.backup_automatico() is None, "sem mudança, não repete a do dia"

    forcada = db.backup_automatico(forcar=True)

    assert forcada is not None
    assert forcada != primeira


def test_a_copia_forcada_esta_integra(sistema, contas):
    from app import db

    caminho = db.backup_automatico(forcar=True)
    conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    try:
        assert conexao.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert paginas_no_cabecalho(caminho) == paginas_no_arquivo(caminho)
    finally:
        conexao.close()


def test_a_troca_de_executavel_salva_copia_forcada(sistema, monkeypatch):
    """O momento mais arriscado da vida do programa merece cópia fresca."""
    import inspect

    from app.ui import main_window

    fonte = inspect.getsource(main_window.Aplicacao._trocar_para_a_copia_instalada)
    assert "backup_automatico(forcar=True)" in fonte
