"""Configurações globais e caminhos da aplicação."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Sistema Contábil Pessoal"
APP_SLUG = "SistemaContabil"
APP_VERSION = "1.0.0"


def _base_dir() -> Path:
    """Diretório de dados do usuário (funciona em modo script e empacotado)."""
    portable = Path(sys.executable).parent / "portable.flag"
    if getattr(sys, "frozen", False) and portable.exists():
        return Path(sys.executable).parent / "dados"
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(root) / APP_SLUG


DATA_DIR = _base_dir()
DB_PATH = DATA_DIR / "contabil.db"
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exportacoes"
LOG_PATH = DATA_DIR / "app.log"


def ensure_dirs() -> None:
    for path in (DATA_DIR, BACKUP_DIR, EXPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def resource_path(relative: str) -> Path:
    """Resolve arquivos embutidos pelo PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
