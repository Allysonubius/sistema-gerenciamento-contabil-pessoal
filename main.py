"""Ponto de entrada do Sistema Contábil Pessoal."""
from __future__ import annotations

import logging
import sys
import traceback

from app import db, inicializacao, instancia
from app.config import APP_NAME, LOG_PATH, ensure_dirs


def _configurar_log() -> None:
    ensure_dirs()
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def _tratar_excecao(tipo, valor, tb) -> None:
    logging.error("Erro não tratado", exc_info=(tipo, valor, tb))
    try:
        from tkinter import messagebox
        messagebox.showerror(
            APP_NAME,
            f"Ocorreu um erro inesperado:\n\n{valor}\n\nDetalhes registrados em:\n{LOG_PATH}")
    except Exception:
        traceback.print_exception(tipo, valor, tb)


def main() -> int:
    _configurar_log()
    sys.excepthook = _tratar_excecao

    if instancia.ja_esta_aberto():
        # Já existe uma janela: pede para ela aparecer e encerra esta.
        instancia.pedir_para_abrir()
        logging.info("Instância já em execução — trazendo a janela existente para a frente")
        return 0

    logging.info("Iniciando %s", APP_NAME)
    db.get_connection()
    # Se o programa mudou de pasta, a entrada de inicialização é reapontada.
    try:
        inicializacao.sincronizar()
    except Exception:  # pragma: no cover - nunca impedir a abertura
        logging.exception("Falha ao conferir a inicialização automática")
    from app.ui.main_window import Aplicacao

    app = Aplicacao(iniciar_minimizado=inicializacao.ARGUMENTO_MINIMIZADO in sys.argv[1:])
    app.report_callback_exception = lambda *args: _tratar_excecao(*args)
    app.mainloop()
    db.fechar()
    instancia.liberar()
    logging.info("Encerrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
