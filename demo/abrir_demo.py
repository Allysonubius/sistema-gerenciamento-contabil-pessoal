"""Abre o sistema com a base FICTÍCIA da pasta `demo`.

Só funciona rodando pelo código-fonte. O executável distribuído não conhece este
arquivo e abre sempre os dados reais do usuário.

Não passa pela trava de instância única: a demonstração pode rodar ao lado do
programa de verdade, e nenhum dos dois enxerga o banco do outro.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEMO_DIR = Path(os.environ.get("DEMO_DIR", RAIZ / "demo"))

if getattr(sys, "frozen", False):                       # pragma: no cover
    raise SystemExit("A demonstração não roda pelo executável — use o código-fonte.")

real = Path(os.environ.get("LOCALAPPDATA", "")) / "SistemaContabil"
if (DEMO_DIR / "SistemaContabil").resolve() == real.resolve():
    raise SystemExit("DEMO_DIR aponta para a pasta de dados real. Escolha outra.")

os.environ["LOCALAPPDATA"] = str(DEMO_DIR)
sys.path.insert(0, str(RAIZ))

from app import db                                     # noqa: E402
from app.config import DB_PATH, DEMO_FLAG              # noqa: E402

if not Path(DB_PATH).exists():
    raise SystemExit("A base de demonstração não existe. Rode 'python demo/popular_demo.py'.")
if not DEMO_FLAG.exists():
    raise SystemExit("Esta pasta não é uma base de demonstração (falta demonstracao.flag).")

db.get_connection()
from app.ui.main_window import Aplicacao               # noqa: E402

app = Aplicacao()
app.mainloop()
db.fechar()
