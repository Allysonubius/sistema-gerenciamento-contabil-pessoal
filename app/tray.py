"""Ícone na bandeja do sistema (área de notificação do Windows).

Usa pystray quando disponível; caso contrário a aplicação continua funcionando
apenas com minimização normal.
"""
from __future__ import annotations

import threading
from typing import Callable

try:  # pragma: no cover - depende do ambiente
    import pystray
    from PIL import Image, ImageDraw
    DISPONIVEL = True
except Exception:  # pragma: no cover
    pystray = None
    DISPONIVEL = False

from app.config import APP_NAME


def criar_imagem(tamanho: int = 64):
    """Ícone desenhado em tempo de execução: livro-razão estilizado."""
    from PIL import Image, ImageDraw  # import local para o caso de ausência da lib
    imagem = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle([2, 2, tamanho - 3, tamanho - 3], radius=12, fill=(20, 36, 61, 255))
    desenho.rectangle([12, 14, tamanho - 13, tamanho - 15], fill=(255, 255, 255, 255))
    desenho.line([tamanho // 2, 16, tamanho // 2, tamanho - 17], fill=(47, 111, 237, 255), width=2)
    for deslocamento in range(3):
        y = 22 + deslocamento * 8
        desenho.line([16, y, tamanho // 2 - 4, y], fill=(120, 134, 156, 255), width=2)
        desenho.line([tamanho // 2 + 4, y, tamanho - 17, y], fill=(120, 134, 156, 255), width=2)
    return imagem


class BandejaSistema:
    """Encapsula o ciclo de vida do ícone da bandeja em uma thread própria."""

    def __init__(self, ao_restaurar: Callable[[], None], ao_sair: Callable[[], None],
                 acoes: dict[str, Callable[[], None]] | None = None):
        self.ao_restaurar = ao_restaurar
        self.ao_sair = ao_sair
        self.acoes = acoes or {}
        self._icone = None
        self._thread: threading.Thread | None = None

    @property
    def ativo(self) -> bool:
        return self._icone is not None

    def iniciar(self) -> bool:
        if not DISPONIVEL or self._icone is not None:
            return False
        itens = [pystray.MenuItem("Abrir sistema", lambda: self.ao_restaurar(), default=True)]
        for rotulo, acao in self.acoes.items():
            itens.append(pystray.MenuItem(rotulo, (lambda a=acao: a())))
        itens.append(pystray.Menu.SEPARATOR)
        itens.append(pystray.MenuItem("Sair", lambda: self.ao_sair()))

        self._icone = pystray.Icon("sistemacontabil", criar_imagem(), APP_NAME, pystray.Menu(*itens))
        self._thread = threading.Thread(target=self._icone.run, daemon=True)
        self._thread.start()
        return True

    def notificar(self, mensagem: str, titulo: str = APP_NAME) -> None:
        if self._icone is not None:
            try:
                self._icone.notify(mensagem, titulo)
            except Exception:
                pass

    def parar(self) -> None:
        if self._icone is not None:
            try:
                self._icone.stop()
            except Exception:
                pass
            self._icone = None
