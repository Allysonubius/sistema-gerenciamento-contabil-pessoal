"""A tela de instalação: dizer exatamente o que vai acontecer, antes de fazer.

Um instalador que pergunta "posso instalar?" e some é um instalador que deixa a
pessoa sem saber onde o programa foi parar. Aqui cada coisa está escrita: a
pasta, o tamanho, os atalhos, onde ficam os dados e o que a desinstalação faz.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app import inicializacao, instalacao
from app.config import APP_NAME, APP_VERSION, DATA_DIR
from app.ui.theme import CORES, FONTE
from app.ui.widgets import Cabecalho, centralizar


class DialogoInstalar(tk.Toplevel):
    """Escolher a pasta e os atalhos, vendo o que cada opção faz."""

    def __init__(self, master, origem=None, ao_instalar=None):
        super().__init__(master)
        if master.winfo_ismapped():
            self.transient(master.winfo_toplevel())
        self.title(f"Instalar {APP_NAME}")
        self.origem = Path(origem) if origem else instalacao.executavel_atual()
        self.ao_instalar = ao_instalar
        self.instalado = None

        cabecalho = Cabecalho(
            self, f"Instalar {APP_NAME}",
            f"Versão {APP_VERSION}. Não precisa de administrador, e nada sai do seu"
            " usuário neste computador.")
        cabecalho.pack(fill="x")
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(22, 18))
        corpo.pack(fill="both", expand=True)

        # --- onde ---------------------------------------------------------
        ttk.Label(corpo, text="Onde instalar", style="Secao.TLabel").pack(anchor="w")
        linha = ttk.Frame(corpo)
        linha.pack(fill="x", pady=(6, 0))
        self.var_pasta = tk.StringVar(value=str(instalacao.pasta_de_instalacao()))
        ttk.Entry(linha, textvariable=self.var_pasta, width=62).pack(side="left",
                                                                      fill="x",
                                                                      expand=True)
        ttk.Button(linha, text="Escolher outra...",
                   command=self.escolher_pasta).pack(side="left", padx=8)
        ttk.Button(linha, text="Usar a padrão",
                   command=self.pasta_padrao).pack(side="left")
        self.lbl_pasta = ttk.Label(corpo, style="Dica.TLabel", wraplength=640,
                                   justify="left")
        self.lbl_pasta.pack(anchor="w", pady=(6, 0))
        self.var_pasta.trace_add("write", lambda *_a: self._conferir_pasta())

        # --- atalhos ------------------------------------------------------
        ttk.Separator(corpo).pack(fill="x", pady=14)
        ttk.Label(corpo, text="Atalhos", style="Secao.TLabel").pack(anchor="w")
        self.var_menu = tk.BooleanVar(value=True)
        self.var_area = tk.BooleanVar(value=True)
        estado_inicio = inicializacao.situacao()
        self.var_windows = tk.BooleanVar(value=estado_inicio["ativo"])

        self._opcao(corpo, self.var_menu, "Atalho no menu Iniciar",
                    f"Cria: {instalacao.pasta_menu_iniciar() / (APP_NAME + '.lnk')}")
        self._opcao(corpo, self.var_area, "Atalho na área de trabalho",
                    f"Cria: {instalacao.pasta_area_trabalho() / (APP_NAME + '.lnk')}")
        if inicializacao.disponivel():
            self._opcao(corpo, self.var_windows, "Abrir junto com o Windows",
                        "Entra na lista de inicialização do seu usuário. Pode ser"
                        " desligado depois em Ajustes.")

        # --- o que mais acontece -------------------------------------------
        ttk.Separator(corpo).pack(fill="x", pady=14)
        ttk.Label(corpo, text="O que mais acontece", style="Secao.TLabel").pack(anchor="w")
        ttk.Label(corpo, text=self._explicacao(), style="Dica.TLabel", wraplength=640,
                  justify="left", font=(FONTE, 9)).pack(anchor="w", pady=(6, 0))

        self.lbl_erro = ttk.Label(corpo, text="", style="Dica.TLabel",
                                  foreground=CORES["perigo"], wraplength=640,
                                  justify="left")
        self.lbl_erro.pack(anchor="w", pady=(10, 0))

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(16, 0))
        ttk.Button(acoes, text="Instalar", style="Primario.TButton",
                   command=self.instalar).pack(side="left")
        ttk.Button(acoes, text="Agora não", command=self.destroy).pack(side="left",
                                                                       padx=8)

        self._conferir_pasta()
        centralizar(self, 760, 640)
        self.lift()
        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _opcao(pai, variavel, titulo: str, detalhe: str) -> None:
        ttk.Checkbutton(pai, text=titulo, variable=variavel).pack(anchor="w",
                                                                   pady=(8, 0))
        ttk.Label(pai, text=f"        {detalhe}", style="Dica.TLabel", wraplength=620,
                  justify="left", font=(FONTE, 9)).pack(anchor="w")

    def _explicacao(self) -> str:
        tamanho = (self.origem.stat().st_size / 1048576) if self.origem.is_file() else 0
        return (
            f"· O programa ({tamanho:.1f} MB) é copiado para a pasta escolhida.\n"
            f"· Ele passa a aparecer em Configurações do Windows → Aplicativos"
            f" instalados, com desinstalador próprio.\n"
            f"· Os seus dados NÃO mudam de lugar: eles ficam, como sempre, em\n"
            f"        {DATA_DIR}\n"
            f"  e sobrevivem a instalar, desinstalar e reinstalar.\n"
            f"· Desinstalando, o programa pergunta em separado se os seus registros"
            f" também devem ser apagados — e o padrão é mantê-los.\n"
            f"· Nada é gravado fora do seu usuário, e nenhuma permissão de"
            f" administrador é pedida.")

    def escolher_pasta(self) -> None:
        escolhida = filedialog.askdirectory(
            parent=self, title="Onde instalar o programa",
            initialdir=self.var_pasta.get() or str(instalacao.pasta_padrao()))
        if escolhida:
            self.var_pasta.set(str(Path(escolhida) / "SistemaContabil")
                               if Path(escolhida).name != "SistemaContabil"
                               else escolhida)

    def pasta_padrao(self) -> None:
        self.var_pasta.set(str(instalacao.pasta_padrao()))

    def _conferir_pasta(self) -> None:
        """Diz, enquanto a pessoa digita, se aquela pasta serve."""
        texto = self.var_pasta.get().strip()
        if not texto:
            self.lbl_pasta.configure(text="Escolha uma pasta.", foreground=CORES["perigo"])
            return
        pasta = Path(texto)
        destino = pasta / "SistemaContabil.exe"
        if pasta.exists():
            situacao = ("A pasta já existe e o programa será trocado por esta versão."
                        if destino.exists() else "A pasta já existe e será usada.")
            cor = CORES["texto_suave"]
        else:
            situacao = "A pasta ainda não existe e será criada."
            cor = CORES["texto_suave"]
        if any(parte.lower() == "program files" for parte in pasta.parts) or \
                any(parte.lower() == "program files (x86)" for parte in pasta.parts):
            situacao = ("Arquivos de Programas exige administrador e não é o lugar de"
                        " uma instalação de usuário. Prefira a pasta padrão.")
            cor = CORES["alerta"]
        self.lbl_pasta.configure(text=f"{situacao}\nO programa ficará em: {destino}",
                                 foreground=cor)

    def instalar(self) -> None:
        pasta = self.var_pasta.get().strip()
        if not pasta:
            self.lbl_erro.configure(text="Escolha onde instalar.")
            return
        try:
            resultado = instalacao.instalar(
                atalho_na_area_de_trabalho=bool(self.var_area.get()),
                atalho_no_menu=bool(self.var_menu.get()),
                origem=self.origem if self.origem != instalacao.executavel_atual() else None,
                pasta=pasta,
                abrir_com_windows=(bool(self.var_windows.get())
                                   if inicializacao.disponivel() else None))
        except (RuntimeError, OSError) as erro:
            self.lbl_erro.configure(text=str(erro))
            return

        self.instalado = resultado["caminho"]
        feitos = [nome for nome, ok in (("menu Iniciar", resultado["atalhos"]["menu"]),
                                        ("área de trabalho",
                                         resultado["atalhos"]["area_trabalho"])) if ok]
        atalhos = ("Atalho criado em: " + " e ".join(feitos) + "."
                   if feitos else "Nenhum atalho foi criado.")
        self.destroy()
        if self.ao_instalar:
            self.ao_instalar(self.instalado, atalhos)
        else:
            messagebox.showinfo("Pronto", f"Instalado em:\n{self.instalado}\n\n{atalhos}")
