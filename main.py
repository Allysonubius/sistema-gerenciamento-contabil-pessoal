"""Ponto de entrada do Sistema Contábil Pessoal."""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime

from app import db, inicializacao, instalacao, instancia
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


def _avisar_banco_danificado(erro) -> int:
    """O arquivo de dados não abre: diz isso na cara, e oferece o conserto.

    Mandar a pessoa renomear arquivos no Explorador, justo quando ela acabou de
    levar um susto, é pedir para o estrago virar dois. O programa sabe onde
    estão as cópias e sabe qual delas está inteira: ele faz a troca.
    """
    from tkinter import messagebox

    logging.error("Banco danificado: %s", erro.motivo)
    copias = [c for c in erro.copias if not c.name.startswith("contabil_DANIFICADO")]
    if not copias:
        messagebox.showerror(
            APP_NAME,
            "O arquivo dos seus dados está danificado e não há nenhuma cópia de"
            f" segurança para voltar.\n\nDetalhe técnico: {erro.motivo}\n\n"
            f"O que houve ficou registrado em:\n{LOG_PATH}")
        return 1

    mais_nova = copias[0]
    quando = datetime.fromtimestamp(mais_nova.stat().st_mtime)
    if not messagebox.askyesno(
            APP_NAME,
            "O arquivo dos seus dados está danificado e não consegui consertá-lo.\n\n"
            "Mas os seus registros não se perderam: a cópia de segurança mais recente"
            f" é de {quando:%d/%m/%Y às %H:%M}.\n\n"
            "Quer que eu volte para ela agora?\n\n"
            "O arquivo danificado fica guardado ao lado das cópias, intacto, caso ainda"
            " dê para aproveitar alguma coisa dele."):
        messagebox.showinfo(
            APP_NAME,
            f"Tudo bem. As cópias estão em:\n{mais_nova.parent}\n\n"
            "Para voltar à mão, renomeie a escolhida para 'contabil.db' e coloque-a em:"
            f"\n{LOG_PATH.parent}\n\nO que houve ficou registrado em:\n{LOG_PATH}")
        return 1

    try:
        db.restaurar_copia(mais_nova)
    except Exception as falha:
        logging.exception("Falha ao restaurar a cópia")
        messagebox.showerror(
            APP_NAME,
            f"Não consegui voltar para a cópia:\n\n{falha}\n\n"
            f"As cópias continuam intactas em:\n{mais_nova.parent}")
        return 1

    messagebox.showinfo(
        APP_NAME,
        f"Pronto — os seus dados voltaram à cópia de {quando:%d/%m/%Y às %H:%M}.\n\n"
        "O programa vai abrir normalmente agora.")
    return 0


def _desinstalar() -> int:
    """Chamado pela lista de aplicativos do Windows, com --desinstalar."""
    from tkinter import messagebox

    apagar = messagebox.askyesnocancel(
        APP_NAME,
        "Remover o programa deste computador?\n\n"
        "Sim  — remove o programa E apaga os seus dados, sem volta.\n"
        "Não  — remove só o programa; os seus registros ficam guardados.\n\n"
        "Em Cancelar, nada acontece.")
    if apagar is None:
        return 0
    resultado = instalacao.desinstalar(apagar_dados=bool(apagar))
    messagebox.showinfo(
        APP_NAME,
        "Programa removido." + ("\n\nOs seus dados também foram apagados."
                                if resultado["dados_apagados"] else
                                "\n\nOs seus registros continuam guardados —"
                                " basta reinstalar para voltar a usá-los."))
    logging.info("Desinstalado (dados apagados: %s)", resultado["dados_apagados"])
    return 0


def main() -> int:
    _configurar_log()
    sys.excepthook = _tratar_excecao

    if instalacao.ARGUMENTO_DESINSTALAR in sys.argv[1:]:
        return _desinstalar()
    if instalacao.ARGUMENTO_INSTALAR in sys.argv[1:]:
        instalacao.instalar()
        logging.info("Instalado em modo silencioso")
        return 0

    if instancia.ja_esta_aberto():
        # Já existe uma janela: pede para ela aparecer e encerra esta.
        instancia.pedir_para_abrir()
        logging.info("Instância já em execução — trazendo a janela existente para a frente")
        return 0

    logging.info("Iniciando %s", APP_NAME)
    try:
        db.get_connection()
    except db.BancoDanificadoError as erro:
        if _avisar_banco_danificado(erro) != 0:
            return 1
        db.get_connection()          # agora abre: a cópia boa está no lugar
    # Se o programa mudou de pasta, a entrada de inicialização é reapontada.
    try:
        inicializacao.sincronizar()
    except Exception:  # pragma: no cover - nunca impedir a abertura
        logging.exception("Falha ao conferir a inicialização automática")
    from app.ui.main_window import Aplicacao

    app = Aplicacao(iniciar_minimizado=inicializacao.ARGUMENTO_MINIMIZADO in sys.argv[1:])
    if not app.liberado:
        # A senha não conferiu, ou o usuário desistiu de entrar.
        logging.info("Encerrado sem passar pela senha")
        app.destroy()
        db.fechar()
        instancia.liberar()
        return 0
    app.report_callback_exception = lambda *args: _tratar_excecao(*args)
    app.mainloop()
    db.fechar()
    instancia.liberar()
    logging.info("Encerrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
