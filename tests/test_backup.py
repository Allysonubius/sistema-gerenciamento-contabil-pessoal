"""Cópias de segurança: arquivo único, cópia externa e rotação."""
from __future__ import annotations

import importlib
from pathlib import Path


def _db(sistema):
    return importlib.import_module("app.db")


def test_backup_gera_arquivo_unico(sistema, contas):
    db = _db(sistema)
    caminho = db.fazer_backup()

    assert caminho.exists()
    # WAL consolidado: nada de -wal/-shm sobrando ao lado da cópia.
    assert not caminho.with_name(caminho.name + "-wal").exists()
    assert not caminho.with_name(caminho.name + "-shm").exists()


def test_backup_automatico_so_repete_quando_algo_muda(sistema, contas):
    db = _db(sistema)
    assert db.backup_automatico() is not None
    assert db.backup_automatico() is None, "sem mudanças, não deve criar outra cópia"

    sistema.salvar_lancamento(
        None, "2026-02-02", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 10.0),
         sistema.Partida(contas["banco"], "C", 10.0)])
    assert db.backup_automatico() is not None


def test_copia_externa_leva_o_arquivo_para_a_pasta_escolhida(sistema, contas, tmp_path):
    db = _db(sistema)
    nuvem = tmp_path / "OneDrive" / "Backups"
    db.definir_pasta_backup_nuvem(nuvem)

    caminho = db.backup_automatico()
    copia = nuvem / caminho.name

    assert copia.exists()
    assert copia.stat().st_size == caminho.stat().st_size
    assert db.get_config("ultimo_backup_nuvem") != ""


def test_sem_pasta_configurada_nao_copia_nada(sistema, contas):
    db = _db(sistema)
    db.definir_pasta_backup_nuvem(None)
    assert db.copiar_para_nuvem(db.fazer_backup()) is None


def test_pasta_inacessivel_nao_derruba_o_backup(sistema, contas, monkeypatch):
    db = _db(sistema)
    db.definir_pasta_backup_nuvem(Path("Z:/pasta/que/nao/existe"))

    # O backup local continua acontecendo mesmo com a pasta externa fora do ar.
    caminho = db.backup_automatico()
    assert caminho is not None and caminho.exists()


def test_copia_externa_mantem_no_maximo_quinze(sistema, contas, tmp_path):
    db = _db(sistema)
    nuvem = tmp_path / "nuvem"
    nuvem.mkdir()
    for indice in range(20):
        (nuvem / f"contabil_2026010{indice:02d}.db").write_bytes(b"x")
    db.definir_pasta_backup_nuvem(nuvem)

    db.copiar_para_nuvem(db.fazer_backup())
    assert len(list(nuvem.glob("contabil_*.db"))) == 15


def test_deteccao_de_pastas_nao_inventa_caminho(sistema, monkeypatch, tmp_path):
    db = _db(sistema)
    monkeypatch.setenv("OneDrive", str(tmp_path / "não-existe"))
    for pasta in db.pastas_de_nuvem_detectadas():
        assert pasta.is_dir()
