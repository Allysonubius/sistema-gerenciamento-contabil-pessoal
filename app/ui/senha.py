"""A porta: criar a senha no primeiro uso e pedi-la nas aberturas seguintes."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from app import seguranca
from app.config import APP_NAME
from app.ui.theme import CORES
from app.ui.widgets import centralizar

# O que a tranca faz e o que não faz, dito onde a pessoa decide usá-la.
AVISO_HONESTO = (
    "A senha impede que alguém abra o programa no seu computador. Ela não"
    " embaralha o arquivo dos seus dados: quem tiver acesso ao arquivo e souber"
    " abrir um banco SQLite ainda lê o conteúdo. É uma tranca na porta, não um"
    " cofre."
)


class _JanelaDeSenha(tk.Toplevel):
    """Base das duas janelas: mesmo visual, mesmo comportamento de teclado."""

    def __init__(self, master, titulo: str, largura: int, altura: int):
        super().__init__(master)
        # Transient de uma janela escondida nasce escondida junto: no Windows o
        # gerenciador segue o dono. A janela principal está retraída de
        # propósito enquanto a senha não confere, então aqui a dependência só
        # entra quando ela já está à vista.
        if master.winfo_ismapped():
            self.transient(master)
        self.title(f"{APP_NAME} — {titulo}")
        self.resizable(False, False)
        self.liberado = False

        self.corpo = ttk.Frame(self, padding=(26, 22))
        self.corpo.pack(fill="both", expand=True)

        self._largura, self._altura = largura, altura
        self.protocol("WM_DELETE_WINDOW", self.desistir)
        self.bind("<Escape>", lambda _e: self.desistir())

    def finalizar(self, primeiro_campo: ttk.Entry) -> None:
        centralizar(self, self._largura, self._altura)
        self.chamar_a_atencao()
        self.grab_set()
        primeiro_campo.focus_set()

    def chamar_a_atencao(self) -> None:
        """Garante que a janela apareça na frente e receba o teclado.

        Sem a janela principal visível atrás, esta é a única coisa na tela: se
        ela nascer atrás de outro programa, parece que o sistema não abriu.
        """
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        try:
            self.focus_force()
        except tk.TclError:          # pragma: no cover - janela já fechada
            pass

    def desistir(self) -> None:
        self.liberado = False
        self.destroy()

    def _titulo(self, texto: str) -> None:
        ttk.Label(self.corpo, text=texto, style="Secao.TLabel").pack(anchor="w")

    def _dica(self, texto: str, cor: str | None = None) -> ttk.Label:
        rotulo = ttk.Label(self.corpo, text=texto, style="Dica.TLabel", wraplength=420,
                           justify="left")
        if cor:
            rotulo.configure(foreground=cor)
        rotulo.pack(anchor="w", pady=(6, 0))
        return rotulo

    def _campo_senha(self, rotulo: str, ao_confirmar) -> tuple[tk.StringVar, ttk.Entry]:
        ttk.Label(self.corpo, text=rotulo, style="Campo.TLabel").pack(anchor="w",
                                                                      pady=(14, 2))
        variavel = tk.StringVar()
        campo = ttk.Entry(self.corpo, textvariable=variavel, show="•", width=34)
        campo.pack(anchor="w")
        campo.bind("<Return>", lambda _e: ao_confirmar())
        return variavel, campo


class DialogoCriarSenha(_JanelaDeSenha):
    """Primeiro uso: a senha nasce aqui, junto com o aviso do que ela protege."""

    def __init__(self, master, trocando: bool = False):
        super().__init__(master, "Senha de abertura", 500, 480)
        self.trocando = trocando

        self._titulo("Proteja o seu sistema com uma senha"
                     if not trocando else "Trocar a senha")
        self._dica("Ela será pedida toda vez que o programa abrir, e vale só neste"
                   " computador." if not trocando else
                   "Digite a senha de hoje e depois a nova.")

        self.var_atual = None
        if trocando:
            self.var_atual, primeiro = self._campo_senha("Senha atual", self.salvar)
        self.var_nova, campo_nova = self._campo_senha(
            "Nova senha" if trocando else "Senha", self.salvar)
        if not trocando:
            primeiro = campo_nova
        self.var_confirma, _ = self._campo_senha("Digite de novo para confirmar",
                                                 self.salvar)

        self.var_mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.corpo, text="Mostrar o que eu digito",
                        variable=self.var_mostrar,
                        command=self._alternar_visibilidade).pack(anchor="w", pady=(10, 0))

        self.lbl_erro = self._dica("", CORES["perigo"])
        self._dica(AVISO_HONESTO)

        acoes = ttk.Frame(self.corpo)
        acoes.pack(fill="x", pady=(18, 0))
        ttk.Button(acoes, text="Salvar senha", style="Primario.TButton",
                   command=self.salvar).pack(side="left")
        if trocando:
            ttk.Button(acoes, text="Cancelar", command=self.desistir).pack(side="left",
                                                                           padx=8)
        else:
            # Sem senha não se entra: a única saída daqui é fechar o programa.
            ttk.Button(acoes, text="Fechar o programa",
                       command=self.desistir).pack(side="right")

        self._campos = [c for c in self.corpo.winfo_children()
                        if isinstance(c, ttk.Entry)]
        self.finalizar(primeiro)

    def _alternar_visibilidade(self) -> None:
        for campo in self._campos:
            campo.configure(show="" if self.var_mostrar.get() else "•")

    def salvar(self) -> None:
        try:
            if self.trocando:
                seguranca.trocar_senha(self.var_atual.get(), self.var_nova.get(),
                                       self.var_confirma.get())
            else:
                seguranca.definir_senha(self.var_nova.get(), self.var_confirma.get())
        except ValueError as erro:
            self.lbl_erro.configure(text=str(erro))
            return
        self.liberado = True
        self.destroy()


class DialogoEntrar(_JanelaDeSenha):
    """Aberturas seguintes: a senha é pedida antes de qualquer número aparecer."""

    def __init__(self, master):
        super().__init__(master, "Entrar", 480, 400)
        self.tentativas = 0

        self._titulo("Digite a sua senha")
        self._dica("O programa abre assim que ela conferir.")

        self.var_senha, campo = self._campo_senha("Senha", self.entrar)
        self.var_mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.corpo, text="Mostrar o que eu digito",
                        variable=self.var_mostrar,
                        command=lambda: campo.configure(
                            show="" if self.var_mostrar.get() else "•")
                        ).pack(anchor="w", pady=(10, 0))

        self.lbl_erro = self._dica("", CORES["perigo"])

        acoes = ttk.Frame(self.corpo)
        acoes.pack(fill="x", pady=(18, 0))
        self.btn_entrar = ttk.Button(acoes, text="Entrar", style="Primario.TButton",
                                     command=self.entrar)
        self.btn_entrar.pack(side="left")
        ttk.Button(acoes, text="Esqueci a senha",
                   command=self.esqueci).pack(side="left", padx=8)
        ttk.Button(acoes, text="Fechar", command=self.desistir).pack(side="right")

        if not seguranca.maquina_confere():
            self.lbl_erro.configure(
                text="Estes dados foram protegidos em outro computador. A senha daquela"
                     " máquina não abre aqui — use 'Esqueci a senha' para destravar.")
        self.finalizar(campo)

    def entrar(self) -> None:
        if seguranca.conferir_senha(self.var_senha.get()):
            self.liberado = True
            self.destroy()
            return

        self.tentativas += 1
        espera = seguranca.espera_apos_erro(self.tentativas)
        self.var_senha.set("")
        self.lbl_erro.configure(
            text=f"Senha incorreta. Tente de novo em {espera:.0f} segundo(s)."
            if espera >= 1 else "Senha incorreta.")
        self._esperar(espera)

    def _esperar(self, segundos: float) -> None:
        """Trava o botão por um instante, para cansar quem fica chutando."""
        if segundos < 1:
            return
        self.btn_entrar.state(["disabled"])
        fim = time.monotonic() + segundos

        def soltar() -> None:
            if time.monotonic() >= fim:
                if self.btn_entrar.winfo_exists():
                    self.btn_entrar.state(["!disabled"])
                    self.lbl_erro.configure(text="Senha incorreta.")
                return
            self.after(250, soltar)

        self.after(250, soltar)

    def esqueci(self) -> None:
        DialogoEsqueci(self, self._apos_reset)

    def _apos_reset(self) -> None:
        if seguranca.tem_senha():
            return
        self.liberado = True
        self.destroy()


class DialogoEsqueci(tk.Toplevel):
    """A saída de quem esqueceu — explicada, não escondida."""

    def __init__(self, master, ao_apagar):
        super().__init__(master)
        self.transient(master)
        self.title("Esqueci a senha")
        self.resizable(False, False)
        self.ao_apagar = ao_apagar

        corpo = ttk.Frame(self, padding=(26, 22))
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Apagar a senha", style="Secao.TLabel").pack(anchor="w")
        ttk.Label(
            corpo,
            text="Os seus dados não se perdem: a senha é uma tranca na porta e o arquivo"
                 " continua inteiro do outro lado. Apagá-la devolve o acesso ao programa"
                 " e nada mais.\n\n"
                 "Esconder este caminho não protegeria coisa alguma — quem tem o arquivo"
                 " já tem os números — e só criaria o risco de você ficar trancado para"
                 " fora da sua própria vida financeira.\n\n"
                 f'Para confirmar, digite: {seguranca.PALAVRA_DE_RESET}',
            style="Dica.TLabel", wraplength=430, justify="left").pack(anchor="w",
                                                                      pady=(8, 0))

        self.var_palavra = tk.StringVar()
        campo = ttk.Entry(corpo, textvariable=self.var_palavra, width=34)
        campo.pack(anchor="w", pady=(14, 0))
        campo.bind("<Return>", lambda _e: self.apagar())

        self.lbl_erro = ttk.Label(corpo, text="", style="Dica.TLabel",
                                  foreground=CORES["perigo"], wraplength=430,
                                  justify="left")
        self.lbl_erro.pack(anchor="w", pady=(8, 0))

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(18, 0))
        ttk.Button(acoes, text="Apagar a senha", style="Perigo.TButton",
                   command=self.apagar).pack(side="left")
        ttk.Button(acoes, text="Voltar", command=self.destroy).pack(side="right")

        centralizar(self, 500, 420)
        self.grab_set()
        campo.focus_set()

    def apagar(self) -> None:
        try:
            seguranca.apagar_senha_esquecida(self.var_palavra.get())
        except ValueError as erro:
            self.lbl_erro.configure(text=str(erro))
            return
        self.destroy()
        self.ao_apagar()


INTERVALO_SEGUNDA_ABERTURA_MS = 800


def abrir_porta(janela: tk.Misc, ao_pedirem_de_novo=None) -> bool:
    """Deixa entrar? Cria a senha no primeiro uso e a pede nos demais.

    ``janela`` é a aplicação, ainda retraída: nenhum número aparece antes de a
    senha conferir. ``ao_pedirem_de_novo`` é chamado de tempos em tempos para
    atender quem clicou no ícone enquanto esta janela estava aberta.
    """
    dialogo = (DialogoCriarSenha(janela) if not seguranca.tem_senha()
               else DialogoEntrar(janela))

    if ao_pedirem_de_novo is not None:
        def vigiar() -> None:
            if not dialogo.winfo_exists():
                return
            ao_pedirem_de_novo(dialogo)
            dialogo.after(INTERVALO_SEGUNDA_ABERTURA_MS, vigiar)

        dialogo.after(INTERVALO_SEGUNDA_ABERTURA_MS, vigiar)

    janela.wait_window(dialogo)
    return bool(dialogo.liberado)
