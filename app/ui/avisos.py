"""Os dois avisos que param na frente do usuário: fechar o mês e o que mudou.

Faixa no alto da janela é fácil de não ver. Estas duas coisas merecem um passo
a mais: fechar a competência é o que mantém o passado reproduzível, e saber o
que mudou na versão evita a pessoa estranhar sozinha uma tela diferente.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import atualizacao, services
from app.config import APP_VERSION
from app.ui.theme import CORES, FONTE
from app.ui.widgets import Cabecalho, centralizar


class _Popup(tk.Toplevel):
    """Base dos dois: mesmo visual, mesma teimosia de aparecer na frente."""

    def __init__(self, master, titulo: str, subtitulo: str, largura: int, altura: int):
        super().__init__(master)
        if master.winfo_ismapped():
            self.transient(master.winfo_toplevel())
        self.title(titulo)
        self._tamanho = (largura, altura)

        cabecalho = Cabecalho(self, titulo, subtitulo)
        cabecalho.pack(fill="x")
        ttk.Separator(self).pack(fill="x")
        self.corpo = ttk.Frame(self, padding=(22, 18))
        self.corpo.pack(fill="both", expand=True)

    def apresentar(self) -> None:
        centralizar(self, *self._tamanho)
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        self.grab_set()
        self.focus_force()

    def _texto_rolavel(self, conteudo: str, altura: int = 15) -> tk.Text:
        quadro = ttk.Frame(self.corpo, style="Superficie.TFrame", padding=1)
        quadro.configure(relief="solid", borderwidth=1)
        quadro.pack(fill="both", expand=True)
        texto = tk.Text(quadro, wrap="word", font=(FONTE, 10), relief="flat",
                        bg=CORES["superficie"], fg=CORES["texto"], padx=14, pady=12,
                        height=altura, highlightthickness=0)
        barra = ttk.Scrollbar(quadro, orient="vertical", command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        texto.pack(side="left", fill="both", expand=True)
        texto.insert("1.0", conteudo)
        texto.configure(state="disabled")
        return texto


class DialogoFechamento(_Popup):
    """Há mês encerrado e aberto: fechar agora, depois, ou nunca mais."""

    def __init__(self, master, ao_fechar=None):
        self.lembrete = services.lembrete_de_fechamento()
        super().__init__(master, "Fechar o mês",
                         "Um mês que já terminou continua aceitando alteração.",
                         600, 460)
        self.ao_fechar = ao_fechar
        self.fechou = False

        ttk.Label(self.corpo, text=self._manchete(), style="Secao.TLabel",
                  wraplength=520, justify="left").pack(anchor="w")
        ttk.Label(
            self.corpo,
            text="Fechar um mês é dizer que ele já virou relatório: nada mais entra, sai"
                 " ou muda de valor dentro dele. É o que garante que o balanço de um mês"
                 " passado continue o mesmo se você olhar de novo daqui a um ano.\n\n"
                 "Reabrir é possível a qualquer momento, em Ajustes.",
            style="Dica.TLabel", wraplength=520, justify="left").pack(anchor="w",
                                                                      pady=(10, 0))

        self.lbl_erro = ttk.Label(self.corpo, text="", style="Dica.TLabel",
                                  foreground=CORES["perigo"], wraplength=520,
                                  justify="left")
        self.lbl_erro.pack(anchor="w", pady=(10, 0))

        acoes = ttk.Frame(self.corpo)
        acoes.pack(fill="x", pady=(18, 0))
        ttk.Button(acoes, text=f"Fechar {self.lembrete['nome']}",
                   style="Primario.TButton",
                   command=self.fechar_um).pack(side="left")
        if self.lembrete["quantos"] > 1:
            ttk.Button(acoes, text=f"Fechar os {self.lembrete['quantos']} meses",
                       command=self.fechar_todos).pack(side="left", padx=8)
        ttk.Button(acoes, text="Depois", command=self.depois).pack(side="right")
        ttk.Button(acoes, text="Não avisar mais",
                   command=self.nunca_mais).pack(side="right", padx=8)

        self.protocol("WM_DELETE_WINDOW", self.depois)
        self.apresentar()

    def _manchete(self) -> str:
        resto = (f" e outros {self.lembrete['quantos'] - 1} mês(es) antes dele"
                 if self.lembrete["quantos"] > 1 else "")
        return (f"{self.lembrete['nome'].capitalize()}{resto} já terminou e continua"
                f" aberto.\n{self.lembrete['lancamentos']} registro(s) ainda podem ser"
                " alterados.")

    def fechar_um(self) -> None:
        self._fechar([self.lembrete["primeiro"]])

    def fechar_todos(self) -> None:
        self._fechar(self.lembrete["meses"])

    def _fechar(self, meses: list[str]) -> None:
        try:
            for mes in meses:
                services.fechar_competencia(mes)
        except services.RegraNegocioError as erro:
            self.lbl_erro.configure(text=str(erro))
            return
        self.fechou = True
        ultimo = services.mes_nome(meses[-1])
        self.destroy()
        if self.ao_fechar:
            self.ao_fechar(f"Competência fechada até {ultimo}.")

    def depois(self) -> None:
        volta = services.adiar_lembrete()
        self.destroy()
        if self.ao_fechar:
            self.ao_fechar(f"Tudo bem — volto a lembrar em {services.para_br(volta)}.")

    def nunca_mais(self) -> None:
        if not messagebox.askyesno(
                "Não avisar mais",
                "Paro de avisar sobre fechamento de competência.\n\n"
                "Dá para religar a qualquer momento em Ajustes. Fechar mesmo assim?",
                parent=self):
            return
        services.definir_lembrete(False)
        self.destroy()
        if self.ao_fechar:
            self.ao_fechar("Não aviso mais sobre fechamento. Dá para religar em Ajustes.")


class DialogoNotasAtualizacao(_Popup):
    """Depois de atualizar: o que esta versão trouxe."""

    def __init__(self, master, notas: str, anterior: str = ""):
        veio_de = f"Você estava na {anterior}." if anterior else ""
        super().__init__(master, f"Agora você está na versão {APP_VERSION}",
                         f"{veio_de} Veja o que mudou.".strip(), 660, 560)

        ttk.Label(self.corpo, text="O que mudou nesta versão",
                  style="Secao.TLabel").pack(anchor="w", pady=(0, 6))
        self.txt = self._texto_rolavel(
            atualizacao.em_texto(notas)
            or "Esta versão não trouxe uma descrição do que mudou.")

        ttk.Label(self.corpo,
                  text="Dá para reler isto quando quiser, em Ajustes.",
                  style="Dica.TLabel").pack(anchor="w", pady=(10, 0))
        acoes = ttk.Frame(self.corpo)
        acoes.pack(fill="x", pady=(14, 0))
        ttk.Button(acoes, text="Entendi", style="Primario.TButton",
                   command=self.destroy).pack(side="left")

        self.apresentar()
