"""Perguntas e avisos com a cara da ferramenta, não a do Windows.

A caixa do sistema não respeita o tema, não cabe texto longo com folga, e põe
"Sim" como botão escolhido por padrão — o que faz a pessoa confirmar no
automático justamente onde ela não devia. Aqui o botão escolhido é o seguro, e
cada opção diz o que vai acontecer.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.config import APP_NAME
from app.ui.theme import CORES, FONTE
from app.ui.widgets import centralizar


class _Caixa(tk.Toplevel):
    """Base das caixas: mesmo visual, mesma teimosia de aparecer na frente."""

    def __init__(self, master, titulo: str, largura: int = 540, altura: int = 300):
        super().__init__(master)
        if master is not None and master.winfo_ismapped():
            self.transient(master.winfo_toplevel())
        self.title(f"{APP_NAME} — {titulo}")
        self.resizable(False, False)
        self.resposta = None
        self._tamanho = (largura, altura)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=22, pady=14)
        topo.pack(fill="x")
        tk.Label(topo, text=titulo, bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 14, "bold"), anchor="w").pack(fill="x")
        ttk.Separator(self).pack(fill="x")

        self.corpo = ttk.Frame(self, padding=(22, 16))
        self.corpo.pack(fill="both", expand=True)

    def apresentar(self, foco=None) -> None:
        centralizar(self, *self._tamanho)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        self.grab_set()
        (foco or self).focus_force()
        self.wait_window(self)

    def _texto(self, texto: str, destaque: bool = False) -> ttk.Label:
        rotulo = ttk.Label(self.corpo, text=texto, wraplength=480, justify="left",
                           style="Secao.TLabel" if destaque else "Dica.TLabel")
        rotulo.pack(anchor="w", pady=(0, 8))
        return rotulo


class CaixaDeAviso(_Caixa):
    """Só informa. Um botão, e pronto."""

    def __init__(self, master, titulo: str, texto: str, destaque: str = ""):
        super().__init__(master, titulo, 540, 280)
        if destaque:
            self._texto(destaque, destaque=True)
        self._texto(texto)
        acoes = ttk.Frame(self.corpo)
        acoes.pack(fill="x", pady=(10, 0))
        botao = ttk.Button(acoes, text="Entendi", style="Primario.TButton",
                           command=self.destroy)
        botao.pack(side="right")
        self.bind("<Return>", lambda _e: self.destroy())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.apresentar(botao)


class CaixaDeEscolha(_Caixa):
    """Duas saídas, cada uma dizendo o que faz — e a segura em destaque.

    ``opcoes`` é uma lista de (rótulo, explicação, valor). A primeira é a que
    recebe o foco: por isso a primeira tem de ser sempre a que não estraga
    nada se a pessoa apertar Enter sem ler.
    """

    def __init__(self, master, titulo: str, pergunta: str,
                 opcoes: list[tuple[str, str, object]], detalhe: str = ""):
        super().__init__(master, titulo, 580, 320 + 40 * len(opcoes))
        self._texto(pergunta, destaque=True)
        if detalhe:
            self._texto(detalhe)

        self.var = tk.StringVar(value=str(opcoes[0][2]))
        self._valores = {str(valor): valor for _r, _e, valor in opcoes}
        quadro = ttk.Frame(self.corpo, style="Superficie.TFrame", padding=(14, 12))
        quadro.configure(relief="solid", borderwidth=1)
        quadro.pack(fill="x", pady=(4, 0))
        for rotulo, explicacao, valor in opcoes:
            ttk.Radiobutton(quadro, text=rotulo, variable=self.var, value=str(valor),
                            style="Superficie.TRadiobutton").pack(anchor="w", pady=(4, 0))
            if explicacao:
                ttk.Label(quadro, text=f"        {explicacao}",
                          style="DicaSuperficie.TLabel", wraplength=480,
                          justify="left").pack(anchor="w")

        acoes = ttk.Frame(self.corpo)
        acoes.pack(fill="x", pady=(16, 0))
        confirmar = ttk.Button(acoes, text="Confirmar", style="Primario.TButton",
                               command=self._confirmar)
        confirmar.pack(side="right")
        ttk.Button(acoes, text="Cancelar", command=self.destroy).pack(side="right",
                                                                      padx=8)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.apresentar(confirmar)

    def _confirmar(self) -> None:
        self.resposta = self._valores.get(self.var.get())
        self.destroy()


def avisar(master, titulo: str, texto: str, destaque: str = "") -> None:
    CaixaDeAviso(master, titulo, texto, destaque)


def escolher(master, titulo: str, pergunta: str,
             opcoes: list[tuple[str, str, object]], detalhe: str = ""):
    """Devolve o valor da opção escolhida, ou None se a pessoa desistiu."""
    return CaixaDeEscolha(master, titulo, pergunta, opcoes, detalhe).resposta
