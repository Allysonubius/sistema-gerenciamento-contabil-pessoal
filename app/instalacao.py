"""Instalar o programa neste computador, em vez de um .exe solto na pasta.

A instalação é só do usuário: copia o executável para dentro de
``%LOCALAPPDATA%\\Programs``, cria os atalhos e se cadastra na lista de
aplicativos do Windows. Nada de administrador, nada de Arquivos de Programas —
e desinstalar não deixa restos.

Os seus dados **não** moram aqui: eles ficam em ``%LOCALAPPDATA%\\SistemaContabil``
e sobrevivem a instalar, desinstalar e reinstalar.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import APP_NAME, APP_SLUG, APP_VERSION

CHAVE_DESINSTALAR = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall" "\\" + APP_SLUG)
ARGUMENTO_DESINSTALAR = "--desinstalar"
ARGUMENTO_INSTALAR = "--instalar"

# Sem janela preta piscando ao criar os atalhos.
_SEM_JANELA = 0x08000000 if sys.platform == "win32" else 0


def disponivel() -> bool:
    """Só faz sentido no Windows e rodando pelo executável."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def pasta_de_instalacao() -> Path:
    raiz = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(raiz) / "Programs" / APP_SLUG


def caminho_instalado() -> Path:
    return pasta_de_instalacao() / f"{APP_SLUG}.exe"


def executavel_atual() -> Path:
    return Path(sys.executable).resolve()


def instalado() -> bool:
    return caminho_instalado().is_file()


def portatil() -> bool:
    """Modo pen drive: os dados ficam ao lado do .exe e nada deve ser movido."""
    return (executavel_atual().parent / "portable.flag").exists()


def rodando_do_local_instalado() -> bool:
    try:
        return executavel_atual() == caminho_instalado().resolve()
    except OSError:
        return False


def deve_oferecer_instalacao() -> bool:
    """Vale convidar a instalar? Só uma vez, e nunca no modo portátil."""
    return (disponivel() and not portatil() and not rodando_do_local_instalado()
            and not _convite_recusado())


def _convite_recusado() -> bool:
    from app import db

    return db.get_config("instalacao_recusada", "") == "1"


def recusar_convite() -> None:
    from app import db

    db.set_config("instalacao_recusada", "1")


def pasta_menu_iniciar() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def pasta_area_trabalho() -> Path:
    perfil = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    for nome in ("Desktop", "Área de Trabalho"):
        caminho = Path(perfil) / nome
        if caminho.is_dir():
            return caminho
    return Path(perfil) / "Desktop"


def criar_atalho(destino: Path, alvo: Path, descricao: str = APP_NAME) -> bool:
    """Cria um .lnk pelo PowerShell.

    É o caminho sem dependência nova: o WScript.Shell existe em todo Windows,
    e assim o projeto não precisa de pywin32 só para dois atalhos.
    """
    if sys.platform != "win32":
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    comando = (
        "$a = (New-Object -ComObject WScript.Shell)."
        f"CreateShortcut('{destino}');"
        f"$a.TargetPath = '{alvo}';"
        f"$a.WorkingDirectory = '{alvo.parent}';"
        f"$a.Description = '{descricao}';"
        f"$a.IconLocation = '{alvo}';"
        "$a.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            check=True, capture_output=True, timeout=30, creationflags=_SEM_JANELA)
        return destino.exists()
    except (OSError, subprocess.SubprocessError) as erro:
        logging.warning("Não foi possível criar o atalho %s: %s", destino, erro)
        return False


def _registrar_na_lista_de_programas(alvo: Path) -> None:
    """Faz o programa aparecer em 'Aplicativos instalados' do Windows."""
    if sys.platform != "win32":
        return
    import winreg

    tamanho_kb = int(alvo.stat().st_size / 1024) if alvo.exists() else 0
    valores = {
        "DisplayName": APP_NAME,
        "DisplayVersion": APP_VERSION,
        "Publisher": "Allyson de Oliveira Brandão",
        "DisplayIcon": str(alvo),
        "InstallLocation": str(alvo.parent),
        "UninstallString": f'"{alvo}" {ARGUMENTO_DESINSTALAR}',
        "URLInfoAbout": "https://github.com/Allysonubius/"
                        "sistema-gerenciamento-contabil-pessoal",
    }
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE_DESINSTALAR) as chave:
            for nome, valor in valores.items():
                winreg.SetValueEx(chave, nome, 0, winreg.REG_SZ, valor)
            winreg.SetValueEx(chave, "EstimatedSize", 0, winreg.REG_DWORD, tamanho_kb)
            for nome in ("NoModify", "NoRepair"):
                winreg.SetValueEx(chave, nome, 0, winreg.REG_DWORD, 1)
    except OSError:
        logging.exception("Não foi possível cadastrar o programa na lista do Windows")


def _apagar_da_lista_de_programas() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CHAVE_DESINSTALAR)
    except FileNotFoundError:
        pass
    except OSError:
        logging.exception("Não foi possível tirar o programa da lista do Windows")


def instalar(atalho_na_area_de_trabalho: bool = True) -> dict:
    """Copia o executável para a pasta do usuário e cria os atalhos.

    Devolve o que foi feito. Instalar por cima de uma versão já instalada
    apenas troca o arquivo — é assim que a atualização manual funciona.
    """
    if not disponivel():
        raise RuntimeError("A instalação só existe no executável do Windows.")
    if portatil():
        raise RuntimeError(
            "Este é o modo portátil: o programa e os dados andam juntos na mesma"
            " pasta e não devem ser instalados.")

    origem = executavel_atual()
    destino = caminho_instalado()
    destino.parent.mkdir(parents=True, exist_ok=True)

    if origem != destino:
        antigo = destino.with_suffix(".old")
        if destino.exists():
            # Não dá para sobrescrever um .exe em uso, mas dá para renomeá-lo.
            antigo.unlink(missing_ok=True)
            destino.rename(antigo)
        shutil.copy2(origem, destino)

    atalhos = {
        "menu": criar_atalho(pasta_menu_iniciar() / f"{APP_NAME}.lnk", destino),
        "area_trabalho": (criar_atalho(pasta_area_trabalho() / f"{APP_NAME}.lnk", destino)
                          if atalho_na_area_de_trabalho else False),
    }
    _registrar_na_lista_de_programas(destino)
    limpar_restos()
    logging.info("Instalado em %s", destino)
    return {"caminho": destino, "atalhos": atalhos}


def desinstalar(apagar_dados: bool = False) -> dict:
    """Tira os atalhos, o cadastro e o executável. Os dados ficam, salvo pedido.

    O executável em uso não se apaga sozinho: ele é renomeado e some na próxima
    vez que alguém passar por aqui.
    """
    removidos = []
    for atalho in (pasta_menu_iniciar() / f"{APP_NAME}.lnk",
                   pasta_area_trabalho() / f"{APP_NAME}.lnk"):
        try:
            if atalho.exists():
                atalho.unlink()
                removidos.append(str(atalho))
        except OSError:
            logging.warning("Não foi possível apagar o atalho %s", atalho)

    _apagar_da_lista_de_programas()
    try:
        from app import inicializacao

        inicializacao.definir(False)
    except Exception:  # pragma: no cover - desinstalar nunca pode falhar aqui
        logging.exception("Falha ao desligar a inicialização automática")

    alvo = caminho_instalado()
    if alvo.exists():
        try:
            if alvo.resolve() == executavel_atual():
                alvo.rename(alvo.with_suffix(".old"))   # em uso: sai no fim
            else:
                alvo.unlink()
        except OSError:
            logging.warning("Não foi possível remover %s agora", alvo)

    dados_apagados = False
    if apagar_dados:
        from app.config import DATA_DIR

        try:
            shutil.rmtree(DATA_DIR)
            dados_apagados = True
        except OSError:
            logging.exception("Não foi possível apagar a pasta de dados")

    return {"atalhos": removidos, "dados_apagados": dados_apagados}


def limpar_restos() -> int:
    """Apaga os .old deixados por uma troca anterior do executável."""
    apagados = 0
    pasta = pasta_de_instalacao()
    if not pasta.is_dir():
        return 0
    for resto in pasta.glob("*.old"):
        try:
            resto.unlink()
            apagados += 1
        except OSError:
            pass            # ainda em uso: sai na próxima abertura
    return apagados


def situacao() -> dict:
    """Tudo o que a tela precisa saber para falar de instalação."""
    return {
        "disponivel": disponivel(),
        "portatil": portatil(),
        "instalado": instalado(),
        "aqui": rodando_do_local_instalado(),
        "caminho_atual": str(executavel_atual()),
        "caminho_instalado": str(caminho_instalado()),
        "oferecer": deve_oferecer_instalacao(),
    }
