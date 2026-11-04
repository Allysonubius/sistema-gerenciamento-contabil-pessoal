"""Investimentos: quanto está aplicado, quanto rendeu e como evoluiu."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import services
from app.ui import perguntas
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (CampoData, CampoValor, SeletorConta, Tabela, centralizar)


class JanelaInvestimentos(tk.Toplevel):
    def __init__(self, master, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_mudar = ao_mudar
        self.title("Investimentos")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Investimentos", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Quanto você aplicou, quanto rendeu e quanto tem hoje em cada"
                            " aplicação.", bg=CORES["superficie"], fg=CORES["texto_suave"],
                 font=(FONTE, 10), anchor="w").pack(fill="x", pady=(2, 0))
        self.lbl_totais = tk.Label(topo, bg=CORES["superficie"], fg=CORES["texto"],
                                   font=(FONTE, 12, "bold"), anchor="w")
        self.lbl_totais.pack(fill="x", pady=(10, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 12))
        ttk.Button(acoes, text="Nova aplicação", style="Primario.TButton",
                   command=self.nova).pack(side="left")
        ttk.Button(acoes, text="Aportar", style="Sucesso.TButton",
                   command=lambda: self.movimentar("aporte")).pack(side="left", padx=8)
        ttk.Button(acoes, text="Resgatar",
                   command=lambda: self.movimentar("resgate")).pack(side="left")
        ttk.Button(acoes, text="Lançar rendimento",
                   command=self.rendimento).pack(side="left", padx=8)
        ttk.Button(acoes, text="Usar conta existente",
                   command=self.marcar_existente).pack(side="right")
        # Aplicação que acabou precisa sair da lista sem levar o passado junto.
        ttk.Button(acoes, text="Encerrar aplicação", style="Perigo.TButton",
                   command=self.encerrar).pack(side="right", padx=8)
        # Um botão só, que lê a linha escolhida: desativar e reativar são o
        # mesmo gesto visto de dois lados, e dois botões deixariam um deles
        # sempre inútil na tela.
        self.btn_ativa = ttk.Button(acoes, text="Desativar", command=self.alternar_ativa)
        self.btn_ativa.pack(side="right")

        # --- o que mostrar ------------------------------------------------
        filtro = ttk.Frame(corpo)
        filtro.pack(fill="x", pady=(0, 10))
        ttk.Label(filtro, text="Mostrar:", style="Campo.TLabel").pack(side="left")
        self.var_mostrar = tk.StringVar(value="ativas")
        for rotulo, valor in (("Ativas", "ativas"), ("Inativas", "inativas"),
                              ("Todas", "todas")):
            ttk.Radiobutton(filtro, text=rotulo, value=valor, variable=self.var_mostrar,
                            command=self.recarregar).pack(side="left", padx=(10, 0))
        self.lbl_quantas = ttk.Label(filtro, style="Dica.TLabel")
        self.lbl_quantas.pack(side="right")

        self.tabela = Tabela(corpo, [
            ("nome", "Aplicação", 200, "w"),
            ("onde", "Onde", 140, "w"),
            ("aplicado", "Você aplicou", 130, "e"),
            ("rendimento", "Rendeu", 120, "e"),
            ("saldo", "Tem hoje", 130, "e"),
            ("rent", "Rentabilidade", 120, "e"),
            ("ultimo", "Último movimento", 130, "center"),
            ("situacao", "Situação", 100, "center"),
        ], on_duplo_clique=lambda _i: self.ver_extrato(), altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhuma aplicação ainda. Use 'Nova aplicação' ou 'Usar conta existente'"
            " para acompanhar seus investimentos.")
        self.tabela.pack(fill="both", expand=True)
        self.tabela.tree.bind("<<TreeviewSelect>>",
                              lambda _e: self._ajustar_botao_ativa(), add="+")

        self.lbl_evolucao = ttk.Label(corpo, style="Dica.TLabel", justify="left")
        self.lbl_evolucao.pack(anchor="w", pady=(10, 0))

        rodape = ttk.Frame(corpo)
        rodape.pack(fill="x", pady=(10, 0))
        ttk.Label(rodape, text="Clique duas vezes em uma aplicação para ver o extrato dela.",
                  style="Dica.TLabel").pack(side="left")
        ttk.Button(rodape, text="Fechar", command=self.destroy).pack(side="right")

        self.recarregar()
        centralizar(self, 1120, 620)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    # ------------------------------------------------------------------ #
    def recarregar(self) -> None:
        mostrar = self.var_mostrar.get()
        itens = services.listar_investimentos(incluir_inativas=True)
        ativas = [i for i in itens if i["ativa"]]
        inativas = [i for i in itens if not i["ativa"]]
        # Em "Todas", as ativas vêm primeiro: a lista continua respondendo
        # "onde está meu dinheiro hoje" na primeira olhada, com o que já foi
        # encerrado logo abaixo.
        visiveis = {"ativas": ativas, "inativas": inativas,
                    "todas": ativas + inativas}[mostrar]

        self.tabela.limpar()
        for item in visiveis:
            cor = ("positivo" if item["rendimento"] > 0.005
                   else "negativo" if item["rendimento"] < -0.005 else "")
            tags = ("inativa",) if not item["ativa"] else ((cor,) if cor else ())
            self.tabela.inserir(
                (item["nome"], item["instituicao"] or "—",
                 services.moeda(item["aplicado"]),
                 services.moeda(item["rendimento"]),
                 services.moeda(item["saldo"]),
                 f"{item['rentabilidade']:.2f}%" if item["aportes"] > 0.005 else "—",
                 services.para_br(item["ultimo_movimento"]) if item["ultimo_movimento"] else "—",
                 "Ativa" if item["ativa"] else "Inativa"),
                iid=item["id"], tags=tags)
        self.tabela.definir_texto_vazio(
            {"ativas": "Nenhuma aplicação ativa. Use 'Nova aplicação' ou 'Usar conta"
                       " existente' para acompanhar seus investimentos.",
             "inativas": "Nenhuma aplicação desativada.",
             "todas": "Nenhuma aplicação ainda."}[mostrar])
        self.tabela.finalizar()
        self.lbl_quantas.configure(
            text=f"{len(ativas)} ativa(s)  ·  {len(inativas)} inativa(s)")
        self._ajustar_botao_ativa()

        r = services.resumo_investimentos()
        self.lbl_totais.configure(
            text=f"Total aplicado hoje: {services.moeda(r['total'])}     ·     "
                 f"Rendimento acumulado: {services.moeda(r['rendimento'])}     ·     "
                 f"Rentabilidade: {r['rentabilidade']:.2f}%",
            fg=CORES["sucesso"] if r["rendimento"] >= 0 else CORES["perigo"])

        evolucao = [e for e in services.evolucao_investimentos(6) if e["saldo"] > 0.005]
        if evolucao:
            self.lbl_evolucao.configure(
                text="Saldo no fim de cada mês:   " + "     ".join(
                    f"{e['mes'][5:7]}/{e['mes'][2:4]} {services.moeda(e['saldo'])}"
                    for e in evolucao))
        else:
            self.lbl_evolucao.configure(text="")

    def _ajustar_botao_ativa(self) -> None:
        """O botão diz o que vai acontecer com a linha escolhida."""
        item = self.tabela.selecionado()
        ativa = True
        if item:
            conta = services.obter_conta(int(item))
            ativa = bool(conta["ativo"]) if conta else True
        self.btn_ativa.configure(text="Desativar" if ativa else "Reativar")

    def alternar_ativa(self) -> None:
        """Desativa a aplicação escolhida — ou devolve ao uso a que está parada.

        Desativar não apaga nada: saldo e histórico continuam, e por isso é o
        caminho seguro para a aplicação que acabou. O que some é a presença
        dela nos seletores e nas somas do dia a dia.
        """
        conta_id = self._selecionada()
        if conta_id is None:
            return
        conta = services.obter_conta(conta_id)
        ativa = bool(conta["ativo"])
        if ativa:
            saldo = services.saldo_conta(conta_id)
            aviso = (f"'{conta['nome']}' ainda tem {services.moeda(saldo)} aplicados."
                     " O saldo continua guardado, mas a aplicação sai das somas do dia a"
                     " dia até ser reativada." if abs(saldo) > 0.005 else
                     f"'{conta['nome']}' sai dos seletores e das somas. O histórico fica"
                     " guardado e dá para reativar aqui mesmo.")
            escolha = perguntas.escolher(
                self, "Desativar aplicação", aviso,
                [("Deixar como está", "Nada muda.", "nada"),
                 ("Desativar", "Some das listas do dia a dia; nada é apagado.", "sim")])
            if escolha != "sim":
                return
        try:
            services.definir_conta_ativa(conta_id, not ativa)
        except services.RegraNegocioError as erro:
            perguntas.avisar(self, "Não foi possível", str(erro))
            return
        if not ativa:
            # Quem acabou de reativar quer ver o resultado, e o filtro em
            # "Inativas" esconderia justamente a linha que mudou.
            self.var_mostrar.set("ativas")
        self._apos()
        perguntas.avisar(self, "Pronto",
                         f"'{conta['nome']}' foi desativada." if ativa else
                         f"'{conta['nome']}' voltou para a lista de aplicações ativas.")

    def _selecionada(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Investimentos", "Escolha antes uma aplicação da lista.",
                                parent=self)
            return None
        return int(item)

    def nova(self) -> None:
        DialogoNovaAplicacao(self, self._apos)

    def marcar_existente(self) -> None:
        DialogoMarcarInvestimento(self, self._apos)

    def movimentar(self, modo: str) -> None:
        conta_id = self._selecionada()
        if conta_id:
            DialogoMovimentoInvestimento(self, conta_id, modo, self._apos)

    def rendimento(self) -> None:
        conta_id = self._selecionada()
        if conta_id:
            DialogoRendimento(self, conta_id, self._apos)

    def ver_extrato(self) -> None:
        conta_id = self._selecionada()
        if conta_id:
            from app.ui.carteiras import JanelaExtrato
            JanelaExtrato(self, conta_id)

    def encerrar(self) -> None:
        """Tira a aplicação da lista — desativando ou apagando, conforme o caso.

        Aplicação com saldo ou com histórico não se apaga: apagar levaria junto
        os aportes e resgates que explicam de onde o dinheiro veio. Desativar
        resolve o que a pessoa quer (sumir da lista) sem apagar o passado.
        """
        conta_id = self._selecionada()
        if conta_id is None:
            return
        conta = services.obter_conta(conta_id)
        saldo = services.saldo_conta(conta_id)
        uso = services.uso_da_conta(conta_id)

        if abs(saldo) > 0.005:
            escolha = perguntas.escolher(
                self, "Tirar da lista de investimentos",
                f"'{conta['nome']}' ainda tem {services.moeda(saldo)} aplicados.",
                [("Deixar como está", "Nada muda.", "nada"),
                 ("Tirar só da lista de investimentos",
                  "A conta continua existindo em Minhas Contas, com o saldo intacto —"
                  " ela só deixa de ser acompanhada como aplicação.", "desmarcar"),
                 ("Desativar a conta",
                  "Ela some dos seletores e das somas. O saldo e o histórico ficam"
                  " guardados, e dá para reativar em Categorias.", "desativar")])
        elif uso["lancamentos"]:
            escolha = perguntas.escolher(
                self, "Tirar da lista de investimentos",
                f"'{conta['nome']}' está zerada, mas tem"
                f" {uso['lancamentos']} movimento(s) registrados.",
                [("Deixar como está", "Nada muda.", "nada"),
                 ("Desativar a conta",
                  "Ela some dos seletores e das somas. O histórico fica guardado, e dá"
                  " para reativar em Categorias.", "desativar"),
                 ("Tirar só da lista de investimentos",
                  "A conta continua ativa em Minhas Contas; só deixa de ser acompanhada"
                  " como aplicação.", "desmarcar")])
        else:
            escolha = perguntas.escolher(
                self, "Apagar a aplicação",
                f"'{conta['nome']}' está zerada e nunca foi usada.",
                [("Desativar a conta",
                  "Ela some dos seletores, mas continua existindo.", "desativar"),
                 ("Apagar de vez",
                  "Como nada foi lançado nela, não há histórico a perder. Não dá para"
                  " desfazer.", "apagar")])

        if escolha in (None, "nada"):
            return
        try:
            if escolha == "desmarcar":
                services.marcar_como_investimento(conta_id, False)
                recado = f"'{conta['nome']}' saiu da lista de investimentos."
            elif escolha == "desativar":
                services.definir_conta_ativa(conta_id, False)
                recado = f"'{conta['nome']}' foi desativada."
            else:
                services.excluir_conta(conta_id)
                recado = f"'{conta['nome']}' foi apagada."
        except services.RegraNegocioError as erro:
            perguntas.avisar(self, "Não foi possível", str(erro))
            return
        self._apos()
        perguntas.avisar(self, "Pronto", recado)

    def _apos(self) -> None:
        self.recarregar()
        self.ao_mudar()


# --------------------------------------------------------------------------- #
class DialogoNovaAplicacao(tk.Toplevel):
    def __init__(self, master, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.ao_salvar = ao_salvar
        self.title("Nova aplicação")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Onde você aplicou o dinheiro?",
                  style="Secao.TLabel").grid(row=0, column=0, columnspan=2, sticky="w",
                                             pady=(0, 14))

        ttk.Label(corpo, text="Nome da aplicação", style="Campo.TLabel").grid(
            row=1, column=0, sticky="w")
        ttk.Label(corpo, text="Ex.: Tesouro Selic, CDB Nubank, Bitcoin na Binance.",
                  style="Dica.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")
        self.var_nome = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_nome, width=46).grid(
            row=3, column=0, columnspan=2, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Instituição (opcional)", style="Campo.TLabel").grid(
            row=4, column=0, sticky="w")
        self.var_onde = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_onde, width=46).grid(
            row=5, column=0, columnspan=2, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Quanto já tem aplicado (R$)", style="Campo.TLabel").grid(
            row=6, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=7, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Nesta data", style="Campo.TLabel").grid(row=6, column=1, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=7, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="De qual conta saiu esse dinheiro?",
                  style="Campo.TLabel").grid(row=8, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text="O valor é descontado dessa conta — investimento não conta"
                              " como dinheiro disponível.",
                  style="Dica.TLabel", wraplength=440, justify="left").grid(
            row=9, column=0, columnspan=2, sticky="w")
        self.sel_origem = SeletorConta(
            corpo, tipos=("ATIVO",), width=44,
            rotulo_vazio="(não descontar — só registrar o que já tenho aplicado)")
        self.sel_origem.grid(row=10, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Deixe o valor em branco se ainda não aplicou nada — depois use"
                              " 'Aportar' para registrar as aplicações.",
                  style="Dica.TLabel", wraplength=440, justify="left").grid(
            row=11, column=0, columnspan=2, sticky="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=12, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Criar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 600, 560)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            saldo = self.cp_valor.get_valor() if self.cp_valor.var.get().strip() else 0.0
            services.criar_carteira(self.var_nome.get(), "Investimento", self.var_onde.get(),
                                    saldo, self.dt_data.get_iso(),
                                    conta_origem_id=self.sel_origem.get_conta_id())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


class DialogoMarcarInvestimento(tk.Toplevel):
    """Transforma uma conta já existente (ex.: Binance) em aplicação acompanhada."""

    def __init__(self, master, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.ao_salvar = ao_salvar
        self.title("Usar conta existente")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Qual conta é uma aplicação?", style="Secao.TLabel").pack(
            anchor="w", pady=(0, 6))
        ttk.Label(corpo, text="A conta passa a aparecer nesta tela, com aportes, rendimento e"
                              " rentabilidade.", style="Dica.TLabel", wraplength=420,
                  justify="left").pack(anchor="w", pady=(0, 14))

        self.sel_conta = SeletorConta(corpo, tipos=("ATIVO",), width=44)
        self.sel_conta.pack(anchor="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Confirmar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 520, 280)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            conta_id = self.sel_conta.get_conta_id()
            if conta_id is None:
                raise services.RegraNegocioError("Escolha a conta.")
            services.marcar_como_investimento(conta_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


class DialogoMovimentoInvestimento(tk.Toplevel):
    """Aporte (dinheiro entra na aplicação) ou resgate (volta para a conta)."""

    def __init__(self, master, conta_id: int, modo: str, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.conta_id = conta_id
        self.modo = modo
        self.ao_salvar = ao_salvar
        conta = services.obter_conta(conta_id)
        aporte = modo == "aporte"
        self.title("Aportar" if aporte else "Resgatar")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=("Aplicar dinheiro em " if aporte else "Resgatar de ")
                               + conta["nome"], style="Secao.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Label(corpo, text="De qual conta sai o dinheiro?" if aporte
                              else "Para qual conta vai o dinheiro?",
                  style="Campo.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("ATIVO",), width=44)
        self.sel_conta.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Valor (R$)", style="Campo.TLabel").grid(row=3, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=4, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Quando", style="Campo.TLabel").grid(row=3, column=1, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=4, column=1, sticky="w", pady=(4, 14))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Confirmar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 540, 340)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            outra = self.sel_conta.get_conta_id()
            if outra is None:
                raise services.RegraNegocioError("Escolha a conta.")
            valor = self.cp_valor.get_valor()
            data = self.dt_data.get_iso()
            if self.modo == "aporte":
                services.transferir(outra, self.conta_id, valor, data, "Aplicação")
            else:
                services.transferir(self.conta_id, outra, valor, data, "Resgate")
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


class DialogoRendimento(tk.Toplevel):
    def __init__(self, master, conta_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.conta_id = conta_id
        self.ao_salvar = ao_salvar
        conta = services.obter_conta(conta_id)
        saldo = services.saldo_conta(conta_id)
        self.title("Rendimento")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=f"Rendimento de {conta['nome']}", style="Secao.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text=f"Saldo registrado hoje: {services.moeda(saldo)}",
                  style="Dica.TLabel").grid(row=1, column=0, columnspan=2, sticky="w",
                                            pady=(2, 14))

        ttk.Label(corpo, text="Quanto rendeu (R$)", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=3, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Quando", style="Campo.TLabel").grid(row=2, column=1, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=3, column=1, sticky="w", pady=(4, 14))

        self.var_prejuizo = tk.BooleanVar(value=False)
        ttk.Checkbutton(corpo, text="Foi prejuízo (o valor caiu)",
                        variable=self.var_prejuizo).grid(row=4, column=0, columnspan=2,
                                                         sticky="w", pady=(0, 8))
        ttk.Label(corpo, text="O rendimento entra como receita e aumenta o saldo da aplicação.",
                  style="Dica.TLabel", wraplength=420, justify="left").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Lançar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 540, 360)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            valor = self.cp_valor.get_valor()
            if self.var_prejuizo.get():
                valor = -valor
            services.registrar_rendimento(self.conta_id, valor, self.dt_data.get_iso())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()
