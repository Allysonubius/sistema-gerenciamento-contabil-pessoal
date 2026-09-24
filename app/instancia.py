"""Garante que apenas uma janela do sistema fique aberta.

Ao abrir o programa uma segunda vez, a instância já em execução é trazida para a
frente (mesmo que esteja minimizada na bandeja) e a nova encerra em seguida.

Como funciona:
  * um mutex nomeado do Windows detecta se já existe uma instância;
  * um arquivo de sinal pede à instância existente que apareça — evita sockets e,
    com isso, qualquer aviso de firewall.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from app.config import DATA_DIR, ensure_dirs

NOME_MUTEX = "Global\\SistemaContabilPessoal_InstanciaUnica"
ARQUIVO_SINAL = "abrir_janela.sinal"
ARQUIVO_TRAVA = "instancia.lock"

_mutex = None


def _caminho(nome: str) -> Path:
    return DATA_DIR / nome


def ja_esta_aberto() -> bool:
    """True quando outra instância já está em execução."""
    global _mutex
    ensure_dirs()
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        _mutex = kernel32.CreateMutexW(None, False, NOME_MUTEX)
        return ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    # Outros sistemas: trava por arquivo com o PID.
    trava = _caminho(ARQUIVO_TRAVA)
    if trava.exists():
        try:
            pid = int(trava.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
    trava.write_text(str(os.getpid()), encoding="utf-8")
    return False


def pedir_para_abrir() -> None:
    """Sinaliza à instância existente que ela deve aparecer."""
    try:
        ensure_dirs()
        _caminho(ARQUIVO_SINAL).write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def consumir_pedido() -> bool:
    """True se houver um pedido pendente de exibição (e o consome)."""
    sinal = _caminho(ARQUIVO_SINAL)
    if not sinal.exists():
        return False
    try:
        sinal.unlink()
    except OSError:
        return False
    return True


def liberar() -> None:
    """Solta o mutex e limpa os arquivos de controle ao encerrar."""
    global _mutex
    if _mutex is not None and sys.platform == "win32":
        import ctypes
        ctypes.WinDLL("kernel32").CloseHandle(_mutex)
        _mutex = None
    for nome in (ARQUIVO_SINAL, ARQUIVO_TRAVA):
        try:
            _caminho(nome).unlink(missing_ok=True)
        except OSError:
            pass
