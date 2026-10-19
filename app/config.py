"""Configurações globais e caminhos da aplicação."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Sistema Contábil Pessoal"
APP_SLUG = "SistemaContabil"
APP_VERSION = "1.0.4"


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


# Marca gravada pelo script de demonstração na pasta de dados dele. Serve para o
# programa avisar na tela que aquilo é base fictícia — e nunca confundir com os
# dados de verdade do usuário.
DEMO_FLAG = DATA_DIR / "demonstracao.flag"


def empacotado() -> bool:
    """True quando rodando pelo .exe gerado pelo PyInstaller."""
    return getattr(sys, "frozen", False)


def modo_demonstracao() -> bool:
    """Base fictícia em uso.

    Só acontece rodando pelo código-fonte: o executável ignora a marca e sempre
    abre os dados do usuário.
    """
    return not empacotado() and DEMO_FLAG.exists()


def ensure_dirs() -> None:
    for path in (DATA_DIR, BACKUP_DIR, EXPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def resource_path(relative: str) -> Path:
    """Resolve arquivos embutidos pelo PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
