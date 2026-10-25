"""A versão nova contada aqui dentro, sem mandar ninguém para o navegador.

Mandar a pessoa procurar um `.exe` numa página e achar o botão certo é pedir
para ela errar. O programa já sabe o que mudou e onde está o arquivo: ele conta
e, se mandarem, busca sozinho.
"""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from app import atualizacao, instalacao
from app.config import DATA_DIR
from app.ui.theme import CORES, FONTE
from app.ui.widgets import Cabecalho, centralizar


class JanelaNovaVersao(tk.Toplevel):
    """O que mudou, e o botão que traz a versão nova para cá."""

    def __init__(self, master, ao_trocar=None, ao_desistir=None):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.title("Versão nova")
        self.ao_trocar = ao_trocar
        self.ao_desistir = ao_desistir
        self.estado = atualizacao.estado_guardado()
        self.baixando = False
        self.baixado: Path | None = None
        # Enquanto houver versão a instalar, daqui só se sai atualizando. Vira
        # True quando não há o que instalar, quando a instalação acontece, ou
        # quando atualizar se mostra impossível — obrigatoriedade que impede a
        # pessoa de abrir a própria vida financeira é armadilha, não regra.
        self.liberado = not self.estado["ha_novidade"]

        novidade = self.estado["ha_novidade"]
        cabecalho = Cabecalho(
            self, f"Versão {self.estado['disponivel']}",
            (f"Você está na {self.estado['atual']}." if novidade
             else "É a versão que você está usando.") + self._quando())
        cabecalho.pack(fill="x")
        cabecalho.botao("Fechar", self.desistir)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(20, 16))
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="O que mudou", style="Secao.TLabel").pack(anchor="w")
        quadro = ttk.Frame(corpo, style="Superficie.TFrame", padding=1)
        quadro.configure(relief="solid", borderwidth=1)
        quadro.pack(fill="both", expand=True, pady=(6, 0))
        self.txt = tk.Text(quadro, wrap="word", font=(FONTE, 10), relief="flat",
                           bg=CORES["superficie"], fg=CORES["texto"], padx=14, pady=12,
                           height=16, highlightthickness=0)
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        self.txt.insert("1.0", atualizacao.em_texto(self.estado["notas"])
                        or "Esta versão não trouxe uma descrição do que mudou.")
        self.txt.configure(state="disabled")

        # --- baixar e trocar ---------------------------------------------
        rodape = ttk.Frame(corpo)
        rodape.pack(fill="x", pady=(14, 0))
        self.lbl_situacao = ttk.Label(rodape, style="Dica.TLabel", wraplength=560,
                                      justify="left")
        self.lbl_situacao.pack(anchor="w")
        self.barra_progresso = ttk.Progressbar(rodape, mode="determinate", maximum=100)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(12, 0))
        self.btn_baixar = ttk.Button(acoes, text="Baixar e atualizar",
                                     style="Primario.TButton", command=self.baixar)
        if novidade:
            # Atualizar deixou de ser opcional: daqui só se sai instalando, ou
            # fechando o programa.
            self.btn_baixar.pack(side="left")
            ttk.Button(acoes, text="Fechar o programa",
                       command=self.desistir).pack(side="right")
            self.protocol("WM_DELETE_WINDOW", self.desistir)
        else:
            ttk.Button(acoes, text="Fechar", style="Primario.TButton",
                       command=self.fechar).pack(side="left")

        self._explicar()
        centralizar(self, 680, 620)
        self.lift()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------ #
    def _quando(self) -> str:
        data = (self.estado.get("publicada_em") or "")[:10]
        if len(data) != 10:
            return ""
        ano, mes, dia = data.split("-")
        return f"   ·   publicada em {dia}/{mes}/{ano}"

    def _explicar(self) -> None:
        """Diz, antes de clicar, o que vai acontecer e quanto vai pesar."""
        if not self.estado["ha_novidade"]:
            self.lbl_situacao.configure(
                text="Você já está na versão mais recente. Isto aqui é só para"
                     " relembrar o que mudou nela.",
                foreground=CORES["sucesso"])
            return
        if not self.estado["arquivo"]:
            self._liberar("Esta versão não trouxe um arquivo para baixar.")
            return
        if not instalacao.disponivel():
            self._liberar("Rodando pelo código-fonte: para atualizar, use o git.")
            return
        peso = (f" ({self.estado['tamanho'] / 1048576:.1f} MB)"
                if self.estado["tamanho"] else "")
        self.lbl_situacao.configure(
            text=f"O programa baixa o arquivo{peso}, se instala por cima e reabre."
                 "  Os seus dados ficam onde estão.",
            foreground=CORES["texto_suave"])

    def baixar(self) -> None:
        if self.baixando:
            return
        self.baixando = True
        self.btn_baixar.state(["disabled"])
        self.barra_progresso.pack(fill="x", pady=(8, 0))
        self.barra_progresso["value"] = 0
        self.lbl_situacao.configure(text="Baixando...", foreground=CORES["texto_suave"])

        destino = DATA_DIR / "atualizacao" / f"SistemaContabil-{self.estado['disponivel']}.exe"

        def andar(vindos: int, total: int) -> None:
            # A rede corre noutra linha; mexer em widget só na linha da janela.
            self.after(0, self._mostrar_progresso, vindos, total)

        def trabalhar() -> None:
            try:
                caminho = atualizacao.baixar(destino, andar)
            except RuntimeError as erro:
                self.after(0, self._falhou, str(erro))
                return
            self.after(0, self._terminou, caminho)

        threading.Thread(target=trabalhar, daemon=True, name="baixar-versao").start()

    def _mostrar_progresso(self, vindos: int, total: int) -> None:
        if not self.winfo_exists():
            return
        if total:
            self.barra_progresso["value"] = vindos / total * 100
            self.lbl_situacao.configure(
                text=f"Baixando... {vindos / 1048576:.1f} de {total / 1048576:.1f} MB")
        else:
            self.lbl_situacao.configure(text=f"Baixando... {vindos / 1048576:.1f} MB")

    def _liberar(self, motivo: str) -> None:
        """Atualizar daqui é impossível: a saída se abre, e fica explicada.

        A atualização é obrigatória, mas obrigatoriedade que impede a pessoa de
        abrir a própria vida financeira por causa de um arquivo que não existe
        ou de uma rede fora do ar não é regra — é armadilha.
        """
        self.liberado = True
        self.lbl_situacao.configure(text=motivo, foreground=CORES["alerta"])
        self.btn_baixar.state(["disabled"])
        self._oferecer_saida()

    def _oferecer_saida(self) -> None:
        pai = self.btn_baixar.master
        if any(isinstance(f, ttk.Button) and f.cget("text") == "Continuar assim mesmo"
               for f in pai.winfo_children()):
            return
        ttk.Button(pai, text="Continuar assim mesmo",
                   command=self.fechar).pack(side="left", padx=8)

    def _falhou(self, motivo: str) -> None:
        if not self.winfo_exists():
            return
        self.baixando = False
        self.barra_progresso.pack_forget()
        self.btn_baixar.state(["!disabled"])
        self.lbl_situacao.configure(
            text=f"{motivo}  Tente de novo; insistindo em falhar, dá para seguir nesta"
                 " versão por enquanto.", foreground=CORES["perigo"])
        # Rede fora do ar não pode trancar ninguém fora das próprias contas.
        self.liberado = True
        self._oferecer_saida()

    def _terminou(self, caminho: Path) -> None:
        if not self.winfo_exists():
            return
        self.baixando = False
        self.baixado = caminho
        self.barra_progresso["value"] = 100
        self.lbl_situacao.configure(text="Baixado. Instalando...",
                                    foreground=CORES["sucesso"])
        self.update_idletasks()
        try:
            resultado = instalacao.instalar(origem=caminho)
        except (RuntimeError, OSError) as erro:
            self._falhou(f"Baixou, mas não consegui instalar: {erro}")
            return
        # Atualizar é trocar o arquivo no lugar que já era dele: a pasta e os
        # atalhos ficam como estão, sem perguntar de novo o que já foi dito.
        self.liberado = True
        if not messagebox.askyesno(
                "Pronto",
                f"Versão {self.estado['disponivel']} instalada.\n\n"
                "Quer fechar esta janela e abrir a versão nova agora?", parent=self):
            self.lbl_situacao.configure(
                text="Instalada. Ela entra na próxima vez que você abrir o programa.",
                foreground=CORES["sucesso"])
            return
        destino = resultado["caminho"]
        self.destroy()
        if self.ao_trocar:
            self.ao_trocar(destino)

    def desistir(self) -> None:
        """Sair daqui sem atualizar custa fechar o programa."""
        if self.baixando and not messagebox.askyesno(
                "Cancelar", "O download está em andamento. Cancelar mesmo assim?",
                parent=self):
            return
        if not self.liberado and not messagebox.askyesno(
                "Fechar o programa",
                f"A versão {self.estado['disponivel']} precisa ser instalada para"
                " continuar usando o sistema.\n\nFechar o programa agora?",
                parent=self):
            return
        desistiu = not self.liberado
        self.destroy()
        if desistiu and self.ao_desistir:
            self.ao_desistir()

    def fechar(self) -> None:
        self.destroy()
