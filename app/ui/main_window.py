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
from app.ui.widgets import AreaRolavel, FaixaAviso

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
        # A janela nasce escondida: nenhum número aparece antes da senha.
        self.withdraw()
        self.title(f"{APP_NAME} — DEMONSTRAÇÃO (dados fictícios)" if modo_demonstracao()
                   else APP_NAME)
        theme.aplicar(self)
        self._definir_icone()

        # Abrindo junto com o Windows a senha fica para quando a janela for
        # chamada: pedi-la a cada boot, numa janela que nem vai aparecer, só
        # ensinaria o usuário a desligar uma das duas coisas.
        self._porta_aberta = False
        self.liberado = True
        if not iniciar_minimizado:
            self.liberado = self._abrir_a_porta()
            if not self.liberado:
                return

        self._abrir_no_monitor()
        if not iniciar_minimizado:
            self.deiconify()

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
        self._cuidar_da_instalacao()
        self._vigiar_versao_nova()
        self._conferir_notas_da_atualizacao()
        self.conferir_fechamento()
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
            # Índice fora de sincronia faz gasto de uma categoria aparecer em
            # outra; conferir na abertura é barato e evita número errado na tela.
            problema = db.reparar_indices()
            if problema:
                self.after(900, lambda: self.notificar(
                    "Encontrei um índice fora de sincronia no arquivo de dados e já"
                    " reconstruí. Seus registros estão todos lá."))
            # Dívida que voltou a existir não pode seguir no histórico de quitadas.
            services.limpar_quitacoes_incoerentes()
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
        # Faixas do alto: nascem escondidas e só ocupam espaço quando há o que
        # dizer. A do fechamento vem por cima, porque fala dos seus números.
        self.faixa_novidade = FaixaAviso(self, CORES["alerta"])
        self.faixa_novidade.acoes([
            ("Dispensar", self.faixa_novidade.esconder),
            ("Não avisar desta versão", self._ignorar_versao),
            ("Ver o que mudou", self.abrir_versao_nova),
        ])

        self.corpo = ttk.Frame(self)
        self.corpo.pack(fill="both", expand=True)
        container = ttk.Frame(self.corpo)
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

    def _abrir_a_porta(self) -> bool:
        """Pede (ou cria) a senha. False quando o usuário desistiu de entrar."""
        if modo_demonstracao():
            self._porta_aberta = True
            return True
        from app.ui.senha import abrir_porta

        self._porta_aberta = abrir_porta(self, self._atender_segunda_abertura)
        return self._porta_aberta

    def _atender_segunda_abertura(self, dialogo) -> None:
        """Clicou no ícone de novo enquanto a senha estava sendo pedida.

        Sem isto, a segunda abertura só avisava a primeira — que estava parada
        na senha e não ouvia ninguém — e dava a impressão de que o programa
        tinha deixado de abrir.
        """
        if instancia.consumir_pedido() and dialogo.winfo_exists():
            dialogo.chamar_a_atencao()

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
            self._reacertar_periodos()
            self.conferir_fechamento()
            self.recarregar_tela_atual()
        self.after(INTERVALO_VIRADA_DIA_MS, self._vigiar_virada_do_dia)

    def _reacertar_periodos(self) -> int:
        """Põe os filtros de período de volta no dia de hoje.

        Alcança todas as telas já montadas, não só a que está à vista: a
        próxima que o usuário abrir também precisa falar do mês certo.
        """
        reacertados = 0
        for tela in self._telas.values():
            filtro = getattr(tela, "filtro", None)
            if filtro is not None and hasattr(filtro, "revalidar"):
                reacertados += bool(filtro.revalidar())
        return reacertados

    # ------------------------------------------------------------------ #
    def _vigiar_versao_nova(self) -> None:
        """Pergunta ao GitHub, numa linha separada, se saiu versão nova.

        Em linha separada porque a consulta vai à rede: numa máquina sem
        internet o programa esperaria o tempo limite inteiro antes de desenhar
        a primeira tela.
        """
        from app import atualizacao

        if not atualizacao.esta_na_hora():
            if atualizacao.deve_avisar():
                self.after(1500, self._anunciar_versao_nova)
            return

        import threading

        def consultar() -> None:
            estado = atualizacao.verificar()
            if estado["ha_novidade"] and not estado["ignorada"]:
                self.after(0, self._anunciar_versao_nova)

        threading.Thread(target=consultar, daemon=True, name="versao").start()

    def _anunciar_versao_nova(self) -> None:
        """Mostra a faixa no topo e avisa também pelo ícone do relógio."""
        if self._encerrando:
            return
        from app import atualizacao

        estado = atualizacao.estado_guardado()
        if not estado["ha_novidade"] or estado["ignorada"]:
            return
        self.faixa_novidade.mostrar(
            f"Saiu a versão {estado['disponivel']} — você está na {estado['atual']}.",
            acima_de=self.corpo)
        self.bandeja.notificar(
            f"A versão {estado['disponivel']} está disponível para baixar.")

    def _ignorar_versao(self) -> None:
        from app import atualizacao

        atualizacao.ignorar(atualizacao.estado_guardado()["disponivel"])
        self.faixa_novidade.esconder()
        self.notificar("Tudo bem — aviso de novo quando sair outra versão.")

    # ------------------------------------------------------------------ #
    def conferir_fechamento(self) -> None:
        """Lembra, no mês seguinte, que o anterior ficou por fechar.

        O fechamento só vale se acontecer. Deixar para quando lembrar é o mesmo
        que não ter, então quem lembra é o programa — e lembra numa janela, não
        numa tarja: tarja no alto da tela é fácil demais de não ver.
        """
        from app import services

        if self._encerrando or not services.deve_lembrar_fechamento():
            return
        self.after(600, self._abrir_aviso_de_fechamento)

    def _abrir_aviso_de_fechamento(self) -> None:
        from app import services

        if self._encerrando or not services.deve_lembrar_fechamento():
            return
        from app.ui.avisos import DialogoFechamento

        DialogoFechamento(self, self._depois_do_fechamento)

    def _depois_do_fechamento(self, recado: str) -> None:
        self.notificar(recado)
        self.recarregar_tela_atual()

    def _conferir_notas_da_atualizacao(self) -> None:
        """Acabou de atualizar? Conta o que veio junto.

        Em linha separada porque pode precisar da rede, e marcando a versão
        como vista antes de abrir a janela: se a busca falhar, o aviso não fica
        voltando a cada abertura.
        """
        from app import atualizacao

        if not atualizacao.versao_mudou():
            atualizacao.marcar_versao_vista()
            return
        anterior = atualizacao.versao_anterior()
        atualizacao.marcar_versao_vista()

        import threading

        def buscar() -> None:
            notas = atualizacao.notas_desta_versao()
            if notas:
                self.after(0, self._mostrar_notas, notas, anterior)

        threading.Thread(target=buscar, daemon=True, name="notas-versao").start()

    def _mostrar_notas(self, notas: str, anterior: str) -> None:
        if self._encerrando:
            return
        from app.ui.avisos import DialogoNotasAtualizacao

        DialogoNotasAtualizacao(self, notas, anterior)

    def abrir_versao_nova(self) -> None:
        """Conta a novidade aqui dentro — ninguém precisa abrir navegador."""
        from app.ui.versao import JanelaNovaVersao

        self.faixa_novidade.esconder()
        JanelaNovaVersao(self, self._trocar_para_a_copia_instalada)

    # ------------------------------------------------------------------ #
    def _cuidar_da_instalacao(self) -> None:
        """Limpa restos da última troca e convida a instalar, uma vez só."""
        from app import instalacao

        try:
            instalacao.limpar_restos()
        except Exception:  # pragma: no cover - nunca atrapalhar a abertura
            import logging
            logging.exception("Falha ao limpar restos da instalação")
        if instalacao.deve_oferecer_instalacao():
            self.after(900, self._convidar_a_instalar)

    def _convidar_a_instalar(self) -> None:
        from app import instalacao

        if self._encerrando or not instalacao.deve_oferecer_instalacao():
            return
        self.instalar_no_computador(convite=True)

    def instalar_no_computador(self, convite: bool = False, origem=None) -> None:
        """Abre a tela de instalação, com pasta e atalhos à escolha."""
        from app import instalacao
        from app.ui.instalador import DialogoInstalar

        dialogo = DialogoInstalar(self, origem=origem, ao_instalar=self._apos_instalar)
        self.wait_window(dialogo)
        if dialogo.instalado is None and convite:
            # Recusou o convite: não insiste nas próximas aberturas.
            instalacao.recusar_convite()

    def _apos_instalar(self, destino, atalhos: str) -> None:
        if not messagebox.askyesno(
                "Pronto",
                f"Instalado em:\n{destino}\n\n{atalhos}\n\n"
                "Quer que eu feche esta janela e abra a cópia instalada agora?",
                parent=self):
            self.notificar("Programa instalado neste computador.")
            return
        self._trocar_para_a_copia_instalada(destino)

    def _trocar_para_a_copia_instalada(self, destino) -> None:
        """Fecha esta janela e sobe a cópia instalada — nessa ordem.

        A ordem é o ponto. A trava de instância única é um mutex preso a este
        processo: subindo a cópia instalada antes, ela se enxerga como segunda
        janela, avisa esta e encerra sozinha. Somado a um `encerrando` ligado
        cedo demais, que fazia `encerrar` voltar na primeira linha, o resultado
        era a instalação parecer não ter acontecido: nada novo abria, e nada
        fechava.
        """
        import logging
        import subprocess

        self._encerrando = True
        try:
            if db.get_config("backup_ao_sair") == "1":
                db.backup_automatico()
        except Exception:
            logging.exception("Falha ao salvar a cópia antes de trocar de executável")
        try:
            self.bandeja.parar()
        except Exception:
            logging.exception("Falha ao encerrar o ícone da bandeja")
        db.fechar()
        instancia.liberar()
        try:
            subprocess.Popen([str(destino)], close_fds=True)
            logging.info("Cópia instalada iniciada: %s", destino)
        except OSError as erro:
            logging.exception("Não foi possível abrir a cópia instalada")
            messagebox.showwarning(
                "Não foi possível abrir",
                f"O programa foi instalado, mas não consegui abri-lo:\n\n{erro}\n\n"
                "Use o atalho no menu Iniciar.", parent=self)
        self.destroy()

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
        # Quem abriu junto com o Windows ainda não passou pela senha.
        if not self._porta_aberta and not self._abrir_a_porta():
            return
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
