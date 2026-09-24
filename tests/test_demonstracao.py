"""A base de demonstração nunca se mistura com os dados do usuário."""
from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture()
def config(tmp_path, monkeypatch):
    """Módulo `app.config` apontando para uma pasta de dados isolada."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    for nome in ("app.services", "app.db", "app.config"):
        sys.modules.pop(nome, None)
    modulo = importlib.import_module("app.config")
    modulo.ensure_dirs()
    return modulo


def test_sem_marca_nao_e_demonstracao(config):
    assert config.DEMO_FLAG.exists() is False
    assert config.modo_demonstracao() is False


def test_com_a_marca_o_programa_avisa(config):
    config.DEMO_FLAG.write_text("base ficticia", encoding="utf-8")
    assert config.modo_demonstracao() is True


def test_executavel_ignora_a_marca(config, monkeypatch):
    """Quem usa o .exe vê sempre os próprios dados, mesmo com a marca presente."""
    config.DEMO_FLAG.write_text("base ficticia", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert config.empacotado() is True
    assert config.modo_demonstracao() is False


def test_demonstracao_vive_em_outra_pasta(config):
    """A pasta de dados sai de LOCALAPPDATA — é assim que a demo se separa."""
    assert str(config.DATA_DIR).endswith("SistemaContabil")
    assert str(config.DB_PATH).startswith(str(config.DATA_DIR))


def test_scripts_da_demo_nao_estao_no_executavel():
    """O build empacota main.py; a pasta demo/ fica de fora de propósito."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    build = (raiz / "build.ps1").read_text(encoding="utf-8")
    assert "demo" not in build
    assert "main.py" in build
