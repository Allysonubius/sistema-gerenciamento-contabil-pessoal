"""Janela principal: menu lateral, troca de telas e integração com a bandeja."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from app import db, instancia
from app.config import APP_NAME, APP_VERSION, modo_demonstracao
from app.tray import BandejaSistema
from app.ui import theme
from app.ui.ajuda import JanelaAjuda
from app.ui.carteiras import Carteiras
from app.ui.cartoes import Cartoes
from app.ui.configuracoes import Configuracoes
from app.ui.dashboard import Dashboard
from app.ui.dividas import Dividas
from app.ui.financeiro import Financeiro
from app.ui.lancamentos import Lancamentos
from app.ui.orcamento import Orcamento
from app.ui.plano_contas import PlanoContas
from app.ui.relatorios import Relatorios
from app.ui.salarios import Salarios
from app.ui.theme import CORES
from app.ui.widgets import AreaRolavel

INICIO = "Início"
MOVIMENTOS = "Entradas e Saídas"
CARTEIRAS = "Minhas Contas"
CARTOES = "Meus Cartões"
CONTAS = "Contas a Pagar"
SALARIOS = "Salários e Rendas"
DIVIDAS = "Dívidas"
ORCAMENTO = "Orçamento"
CATEGORIAS = "Categorias"
RELATORIOS = "Relatórios"
AJUSTES = "Ajustes"

# De quanto em quanto tempo checamos se outra abertura pediu a janela de volta.
INTERVALO_SINAL_MS = 800

# De quanto em quanto tempo checamos se o dia virou (o programa fica aberto na
# bandeja por dias, e o painel fala sempre do mês corrente).
INTERVALO_VIRADA_DIA_MS = 5 * 60 * 1000

# O programa costuma ficar aberto na bandeja por dias: sem esta verificação
# periódica, a cópia do dia só sairia quando o usuário encerrasse de fato.
INTERVALO_BACKUP_MS = 30 * 60 * 1000


class Aplicacao(tk.Tk):
    def __init__(self, iniciar_minimizado: bool = False):
        super().__init__()
        self.title(f"{APP_NAME} — DEMONSTRAÇÃO (dados fictícios)" if modo_demonstracao()
                   else APP_NAME)
        self._abrir_no_monitor()
        theme.aplicar(self)
        self._definir_icone()

        self._telas: dict[str, ttk.Frame] = {}
        self._areas: dict[str, AreaRolavel] = {}
        self._botoes: dict[str, ttk.Button] = {}
        self._tela_atual: str | None = None
        self._encerrando = False
        self._estado_janela = "zoomed"

        self._montar_layout()
        self._montar_bandeja()

        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)
        self.bind("<Unmap>", self._ao_minimizar)
        self.bind("<Configure>", self._lembrar_estado, add="+")
        self.bind("<F5>", lambda _e: self.recarregar_tudo())
        self.bind("<F1>", lambda _e: self.abrir_ajuda())
        self.bind("<Control-n>", lambda _e: self._atalho_novo_lancamento())

        self._rotinas_de_abertura()
        self.mostrar(INICIO)
        self._vigiar_segunda_abertura()
        self._vigiar_backup()
        self._dia_em_tela = date.today()
        self.after(INTERVALO_VIRADA_DIA_MS, self._vigiar_virada_do_dia)
        # Aberto junto com o Windows: nasce perto do relógio, sem roubar a tela.
        if iniciar_minimizado:
            self.after(200, self.esconder_para_bandeja)

    def _abrir_no_monitor(self) -> None:
        """Abre ocupando o monitor inteiro, em modo janela (não tela cheia).

        A janela nasce maximizada e continua com barra de título, botões e
        possibilidade de restaurar/redimensionar. O tamanho de restauração é o
        do monitor menos uma folga, para caber em telas pequenas.
        """
        self.update_idletasks()
        largura = self.winfo_screenwidth()
        altura = self.winfo_screenheight()
        # Tamanho usado quando o usuário sai do modo maximizado.
        self.geometry(f"{int(largura * 0.9)}x{int(altura * 0.88)}+"
                      f"{int(largura * 0.05)}+{int(altura * 0.04)}")
        # Nunca exigir mais do que o monitor oferece: em telas pequenas um
        # mínimo grande demais deixa a janela maior que a área visível.
        self.minsize(min(1024, largura - 40), min(640, altura - 80))
        try:
            self.state("zoomed")            # Windows: maximizada, ainda em janela
        except tk.TclError:                 # pragma: no cover - outros sistemas
            self.attributes("-zoomed", True)

    def _rotinas_de_abertura(self) -> None:
        """Põe em dia o que depende da passagem do tempo."""
        from app import services
        try:
            services.gerar_titulos_recorrentes()
            # Antes dos encargos de atraso: fatura de cartão com saldo em garantia
            # não fica "atrasada" — é descontada da garantia.
            descontos = services.descontar_faturas_da_garantia()
            for d in descontos:
                texto = (f"Fatura de {services.mes_nome(d['competencia'])} do {d['cartao']}"
                         f" não foi paga: {services.moeda(d['valor'])} descontados de"
                         f" {d['garantia']}.")
                self.after(1200, lambda t=texto: self.notificar(t))
            # Débito automático: o que venceu já sai da conta escolhida, antes de
            # o sistema tratar essas contas como atrasadas.
            automaticos = services.pagar_automaticos()
            if automaticos["pagos"]:
                total = sum(p["valor"] for p in automaticos["pagos"])
                texto_auto = (f"Débito automático: {len(automaticos['pagos'])} conta(s)"
                              f" paga(s) — {services.moeda(total)}.")
                self.after(1300, lambda t=texto_auto: self.notificar(t))
            services.conferir_automatico()
            encargos = services.lancar_encargos_do_mes()
            if encargos:
                self.after(1500, lambda: self.notificar(
                    f"{encargos} conta(s) em atraso tiveram multa e juros lançados."))
            self.after(2500, self._avisar_vencimentos)
        except Exception:  # pragma: no cover - nunca impedir a abertura
            import logging
            logging.exception("Falha nas rotinas de abertura")

    def _vigiar_backup(self) -> None:
        """Garante a cópia do dia mesmo com o programa dias aberto na bandeja."""
        if self._encerrando:
            return
        if db.get_config("backup_ao_sair") == "1":
            try:
                caminho = db.backup_automatico()
                if caminho is not None:
                    self.notificar(f"Cópia de segurança do dia salva: {caminho.name}")
            except Exception:  # pragma: no cover - nunca atrapalhar o uso
                import logging
                logging.exception("Falha no backup automático")
        self.after(INTERVALO_BACKUP_MS, self._vigiar_backup)

    def _avisar_vencimentos(self) -> None:
        """Avisa na bandeja o que vence nos próximos dias ou já está atrasado."""
        from app import services
        try:
            hoje = services.hoje_iso()
            titulos = services.proximos_vencimentos(dias=7, limite=50)
        except Exception:  # pragma: no cover
            return
        a_pagar = [t for t in titulos if t["tipo"] == "PAGAR"]
        if not a_pagar:
            return
        atrasadas = [t for t in a_pagar if t["vencimento"] < hoje]
        total = round(sum(float(t["valor"]) for t in a_pagar), 2)

        partes = []
        if atrasadas:
            partes.append(f"{len(atrasadas)} atrasada(s)")
        proximas = len(a_pagar) - len(atrasadas)
        if proximas:
            partes.append(f"{proximas} vencendo em até 7 dias")
        mensagem = " e ".join(partes) + f" — {services.moeda(total)} no total."
        self.notificar(mensagem)
        self.bandeja.notificar(mensagem, "Contas a pagar")

    def _vigiar_segunda_abertura(self) -> None:
        """Se o usuário abrir o programa de novo, traz esta janela para a frente."""
        if not self._encerrando:
            if instancia.consumir_pedido():
                self.restaurar_da_bandeja()
            self.after(INTERVALO_SINAL_MS, self._vigiar_segunda_abertura)

    # ------------------------------------------------------------------ #
    def _definir_icone(self) -> None:
        try:
            from PIL import ImageTk
            from app.tray import criar_imagem
            self._icone_janela = ImageTk.PhotoImage(criar_imagem(64))
            self.iconphoto(True, self._icone_janela)
        except Exception:
            pass

    def _montar_layout(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        lateral = tk.Frame(container, bg=CORES["barra"], width=246)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)

        marca = tk.Frame(lateral, bg=CORES["barra"])
        marca.pack(fill="x", pady=(22, 18), padx=18)
        tk.Label(marca, text="Minhas Contas", bg=CORES["barra"], fg="#ffffff",
                 font=(theme.FONTE, 15, "bold"), anchor="w").pack(fill="x")
        tk.Label(marca, text="controle financeiro pessoal", bg=CORES["barra"],
                 fg=CORES["barra_texto"], font=(theme.FONTE, 9), anchor="w").pack(fill="x")

        # Base fictícia: a tarja deixa claro, em qualquer print ou gravação, que
        # aqueles números não são de ninguém. O executável nunca chega aqui.
        if modo_demonstracao():
            tarja = tk.Frame(lateral, bg=CORES["alerta"])
            tarja.pack(fill="x", padx=18, pady=(0, 14))
            tk.Label(tarja, text="DEMONSTRAÇÃO", bg=CORES["alerta"], fg="#1a1a1a",
                     font=(theme.FONTE, 10, "bold")).pack(pady=(6, 0))
            tk.Label(tarja, text="dados fictícios", bg=CORES["alerta"], fg="#1a1a1a",
                     font=(theme.FONTE, 9)).pack(pady=(0, 6))

        self._area = ttk.Frame(container)
        self._area.pack(side="right", fill="both", expand=True)

        telas = [
            ("⌂", INICIO, Dashboard),
            ("⇄", MOVIMENTOS, Lancamentos),
            ("▮", CARTEIRAS, Carteiras),
            ("▭", CARTOES, Cartoes),
            ("▤", CONTAS, Financeiro),
            ("₪", SALARIOS, Salarios),
            ("▼", DIVIDAS, Dividas),
            ("◑", ORCAMENTO, Orcamento),
            ("☰", CATEGORIAS, PlanoContas),
            ("▦", RELATORIOS, Relatorios),
            ("⚙", AJUSTES, Configuracoes),
        ]
        for icone, nome, classe in telas:
            # Cada tela vive dentro de uma área rolável: em janelas menores que
            # o conteúdo aparecem barras de rolagem, em vez de campos e botões
            # cortados pela borda.
            area = AreaRolavel(self._area)
            tela = classe(area.interno, self)
            tela.pack(fill="both", expand=True)
            self._areas[nome] = area
            self._telas[nome] = tela
            botao = ttk.Button(lateral, text=f"  {icone}   {nome}", style="Menu.TButton",
                               command=lambda n=nome: self.mostrar(n), takefocus=False)
            botao.pack(fill="x", padx=10, pady=2)
            self._botoes[nome] = botao

        rodape = tk.Frame(lateral, bg=CORES["barra"])
        rodape.pack(side="bottom", fill="x", pady=14, padx=10)
        ttk.Button(rodape, text="  ?   Como usar o sistema", style="Menu.TButton",
                   command=self.abrir_ajuda, takefocus=False).pack(fill="x", pady=(0, 6))
        self.lbl_status = tk.Label(rodape, text="Tudo pronto.", bg=CORES["barra"],
                                   fg=CORES["barra_texto"], font=(theme.FONTE, 9),
                                   wraplength=210, justify="left", anchor="w", padx=8)
        self.lbl_status.pack(fill="x")
        tk.Label(rodape, text=f"versão {APP_VERSION}", bg=CORES["barra"], fg="#475569",
                 font=(theme.FONTE, 8), anchor="w", padx=8).pack(fill="x", pady=(4, 0))

    def _montar_bandeja(self) -> None:
        self.bandeja = BandejaSistema(
            ao_restaurar=lambda: self.after(0, self.restaurar_da_bandeja),
            ao_sair=lambda: self.after(0, self.encerrar),
            acoes={
                "Registrar entrada ou saída": lambda: self.after(0, self._atalho_novo_lancamento),
                "Salvar cópia de segurança": lambda: self.after(0, self.backup_rapido),
            },
        )
        self.bandeja.iniciar()

    # ------------------------------------------------------------------ #
    def mostrar(self, nome: str) -> None:
        if nome not in self._telas:
            return
        if self._tela_atual:
            self._areas[self._tela_atual].pack_forget()
            self._botoes[self._tela_atual].configure(style="Menu.TButton")
        tela = self._telas[nome]
        self._areas[nome].pack(fill="both", expand=True)
        self._botoes[nome].configure(style="MenuAtivo.TButton")
        self._tela_atual = nome
        # Algumas telas fazem manutenção ao aparecer (gerar contas fixas, fechar
        # faturas); as consultas comuns ficam por conta dos próprios filtros.
        if hasattr(tela, "ao_exibir"):
            tela.ao_exibir()
        elif hasattr(tela, "recarregar"):
            tela.recarregar()

    def recarregar_tela_atual(self) -> None:
        if not self._tela_atual:
            return
        tela = self._telas[self._tela_atual]
        if hasattr(tela, "recarregar"):
            try:
                tela.recarregar()
            except Exception:  # pragma: no cover - nunca derrubar a janela
                import logging
                logging.exception("Falha ao recarregar %s", self._tela_atual)

    def recarregar_tudo(self) -> None:
        self.recarregar_tela_atual()
        self.notificar("Informações atualizadas.")

    def _vigiar_virada_do_dia(self) -> None:
        """Mantém a tela honesta quando o programa atravessa a meia-noite.

        Sem isto, quem deixa o sistema aberto na bandeja continua vendo "este
        mês" com as contas do dia em que abriu — inclusive depois de o mês virar.
        """
        if self._encerrando:
            return
        hoje = date.today()
        if hoje != self._dia_em_tela:
            self._dia_em_tela = hoje
            try:
                self._rotinas_de_abertura()
            except Exception:  # pragma: no cover
                import logging
                logging.exception("Falha nas rotinas da virada do dia")
            self.recarregar_tela_atual()
        self.after(INTERVALO_VIRADA_DIA_MS, self._vigiar_virada_do_dia)

    def atualizar_dependentes(self) -> None:
        """Mantém o painel coerente depois de gravações em outras telas."""
        if self._tela_atual == INICIO:
            self._telas[INICIO].recarregar()

    def notificar(self, mensagem: str) -> None:
        self.lbl_status.configure(text=mensagem)
        self.after(9000, lambda: self.lbl_status.configure(text="Tudo pronto."))

    def aplicar_preferencias(self) -> None:
        if db.get_config("minimizar_bandeja") == "1" or db.get_config("fechar_para_bandeja") == "1":
            self.bandeja.iniciar()

    def abrir_ajuda(self) -> None:
        JanelaAjuda(self)

    def abrir_relatorio(self, indice: int) -> None:
        self.mostrar(RELATORIOS)
        self._telas[RELATORIOS].selecionar(indice)

    def ir_para(self, nome: str) -> None:
        self.mostrar(nome)

    def _atalho_novo_lancamento(self) -> None:
        self.restaurar_da_bandeja()
        self.mostrar(MOVIMENTOS)
        self._telas[MOVIMENTOS].novo()

    def backup_rapido(self) -> None:
        caminho = db.backup_automatico()
        if caminho is None:
            self.notificar("Nada mudou desde a última cópia — nenhuma nova foi criada.")
            return
        self.notificar(f"Cópia de segurança salva: {caminho.name}")
        self.bandeja.notificar("Cópia de segurança salva com sucesso.")

    # ------------------------------------------------------------------ #
    def _lembrar_estado(self, evento) -> None:
        """Guarda se a janela está maximizada, para restaurá-la assim depois."""
        if evento.widget is self:
            estado = self.state()
            if estado in ("normal", "zoomed"):
                self._estado_janela = estado

    def _ao_minimizar(self, evento) -> None:
        if evento.widget is not self or self._encerrando:
            return
        if self.state() == "iconic" and db.get_config("minimizar_bandeja") == "1":
            self.after(120, self.esconder_para_bandeja)

    def esconder_para_bandeja(self) -> None:
        if not self.bandeja.ativo and not self.bandeja.iniciar():
            self.iconify()
            return
        self.withdraw()
        self.bandeja.notificar("O sistema continua aberto aqui, perto do relógio.")

    def restaurar_da_bandeja(self) -> None:
        # Voltar da bandeja refaz as contas da tela: o programa costuma passar
        # dias aberto, e números de ontem não servem para decidir nada hoje.
        self.recarregar_tela_atual()
        self.deiconify()
        # Volta como estava: quem deixou a janela maximizada não quer que ela
        # encolha só porque passou pela bandeja.
        if self._estado_janela == "zoomed":
            try:
                self.state("zoomed")
            except tk.TclError:  # pragma: no cover - outros sistemas
                pass
        self.lift()
        self.focus_force()

    def ao_fechar(self) -> None:
        if db.get_config("fechar_para_bandeja") == "1" and (
                self.bandeja.ativo or self.bandeja.iniciar()):
            self.esconder_para_bandeja()
            return
        self.encerrar()

    def encerrar(self) -> None:
        if self._encerrando:
            return
        if not messagebox.askyesno("Fechar o sistema",
                                   "Deseja fechar o sistema?\n\nSeus dados já estão salvos.",
                                   parent=self):
            return
        self._encerrando = True
        try:
            if db.get_config("backup_ao_sair") == "1":
                db.backup_automatico()
        except Exception:
            pass
        self.bandeja.parar()
        db.fechar()
        instancia.liberar()
        self.destroy()
