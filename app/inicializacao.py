"""Abrir o programa junto com o Windows.

Usa a chave ``Run`` do usuário atual (HKCU) — não precisa de administrador e
vale só para quem está logado. Em modo empacotado o comando aponta para o
próprio .exe; rodando pelo código-fonte, para o Python com o main.py.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.config import APP_SLUG

CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOME_ENTRADA = APP_SLUG
ARGUMENTO_MINIMIZADO = "--minimizado"


def disponivel() -> bool:
    """Só o Windows tem a chave Run; em outros sistemas a opção fica escondida."""
    return sys.platform == "win32"


def _winreg():
    import winreg  # importado aqui: no Linux/macOS o módulo não existe
    return winreg


def comando(minimizado: bool = False) -> str:
    """Linha de comando gravada no registro, com as aspas necessárias."""
    if getattr(sys, "frozen", False):
        partes = [f'"{Path(sys.executable)}"']
    else:
        raiz = Path(__file__).resolve().parent.parent
        partes = [f'"{Path(sys.executable)}"', f'"{raiz / "main.py"}"']
    if minimizado:
        partes.append(ARGUMENTO_MINIMIZADO)
    return " ".join(partes)


def situacao() -> dict:
    """Como está hoje: se abre com o Windows e se abre já minimizado."""
    if not disponivel():
        return {"ativo": False, "minimizado": False, "comando": ""}
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN) as chave:
            valor, _tipo = winreg.QueryValueEx(chave, NOME_ENTRADA)
    except FileNotFoundError:
        return {"ativo": False, "minimizado": False, "comando": ""}
    except OSError:
        logging.exception("Não foi possível ler a inicialização automática")
        return {"ativo": False, "minimizado": False, "comando": ""}
    return {"ativo": True, "minimizado": ARGUMENTO_MINIMIZADO in valor, "comando": valor}


def ativo() -> bool:
    return situacao()["ativo"]


def definir(ligar: bool, minimizado: bool = False) -> bool:
    """Liga ou desliga a abertura automática. Devolve como ficou.

    Ligar duas vezes não duplica nada: a entrada tem nome fixo e é regravada.
    """
    if not disponivel():
        return False
    winreg = _winreg()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN) as chave:
        if ligar:
            winreg.SetValueEx(chave, NOME_ENTRADA, 0, winreg.REG_SZ, comando(minimizado))
            return True
        try:
            winreg.DeleteValue(chave, NOME_ENTRADA)
        except FileNotFoundError:
            pass
    return False


def sincronizar() -> None:
    """Corrige a entrada quando o programa mudou de lugar (nova pasta, novo .exe)."""
    estado = situacao()
    if not estado["ativo"]:
        return
    esperado = comando(estado["minimizado"])
    if estado["comando"] != esperado:
        definir(True, estado["minimizado"])
        logging.info("Inicialização automática atualizada para %s", esperado)
