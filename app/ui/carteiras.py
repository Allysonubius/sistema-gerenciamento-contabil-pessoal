"""Minhas Contas: saldo e movimento de cada lugar onde o seu dinheiro fica."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (BarraFiltro, Cabecalho, CampoData, CampoValor, Paginacao,
                            SeletorConta, Tabela, centralizar)


class Carteiras(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Minhas Contas",
            "O saldo de cada banco, carteira, cartão ou vale que você usa.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Nova conta", self.nova, "Primario.TButton")
        self.cabecalho.botao("Transferir", self.transferir)
        self.cabecalho.botao("Acertar", self.acertar)
        # Faturas e compras parceladas vivem na tela "Meus Cartões": é lá que
        # elas fazem sentido, e aqui os botões espremiam o cabeçalho.
        self.cabecalho.botao("Extrato", self.ver_extrato)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(2, weight=1)

        # --- totais -------------------------------------------------------
        totais = ttk.Frame(corpo, style="Superficie.TFrame", padding=16)
        totais.configure(relief="solid", borderwidth=1)
        totais.grid(row=0, column=0, sticky="ew")
        self.lbl_tem = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_tem.pack(side="left", padx=(0, 22))
        self.lbl_investido = ttk.Label(totais, style="Total.TLabel",
                                       background=CORES["superficie"])
        self.lbl_investido.pack(side="left", padx=(0, 22))
        self.lbl_outros = ttk.Label(totais, style="Total.TLabel",
                                    background=CORES["superficie"])
        self.lbl_outros.pack(side="left", padx=(0, 22))
        self.lbl_deve = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_deve.pack(side="left", padx=(0, 22))
        self.lbl_liquido = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_liquido.pack(side="left")
        ttk.Label(totais, text="Só as contas marcadas como dinheiro somam no total.",
                  style="DicaSuperficie.TLabel").pack(side="right")

        # --- filtro de período -------------------------------------------
        filtros = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        filtros.configure(relief="solid", borderwidth=1)
        filtros.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.filtro = BarraFiltro(filtros, self.recarregar, fundo="Superficie.TFrame")
        self.filtro.pack(side="left")
        self.var_vazias = tk.BooleanVar(value=False)
        ttk.Checkbutton(filtros, text="Mostrar contas sem saldo e sem uso",
                        variable=self.var_vazias, command=self.recarregar,
                        style="Superficie.TCheckbutton").pack(side="right")

        self.tabela = Tabela(corpo, [
            ("nome", "Conta", 150, "w"),
            ("tipo", "Tipo", 125, "w"),
            ("onde", "Banco / empresa", 110, "w"),
            ("conta_dinheiro", "É dinheiro?", 120, "center"),
            ("entrou", "Entrou", 95, "e"),
            ("saiu", "Saiu", 95, "e"),
            ("saldo", "Saldo hoje", 120, "e"),
            ("ultimo", "Último uso", 90, "center"),
        ], on_duplo_clique=lambda _i: self.ver_extrato(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhuma conta cadastrada. Clique em 'Nova conta' para começar.")
        self.tabela.grid(row=2, column=0, sticky="nsew", pady=(12, 0))

        rodape = ttk.Frame(corpo)
        rodape.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(rodape, text="Clique duas vezes em uma conta para ver o extrato dela.",
                  style="Dica.TLabel").pack(side="left")
        ttk.Button(rodape, text="Contar / não contar como dinheiro",
                   command=self.alternar_dinheiro).pack(side="right")

    # ------------------------------------------------------------------ #
    def recarregar(self) -> None:
        try:
            desde, ate = self.filtro.periodo()
        except services.RegraNegocioError:
            return  # data incompleta enquanto o usuário digita

        self.tabela.limpar()
        for item in services.resumo_carteiras(desde, ate):
            conta = services.obter_conta(item["id"])
            saldo = item["saldo"]
            nunca_usada = item["ultimo_movimento"] is None and abs(saldo) < 0.005
            if nunca_usada and not self.var_vazias.get():
                continue
            tipo = conta["observacao"] or ("Cartão de crédito" if item["divida"]
                                           else "Conta de dinheiro")
            tipo = tipo.split(" (")[0]   # "Carteira digital (Pix, PicPay...)" → "Carteira digital"
            if item["divida"]:
                # Limite e saldo livre ficam na tela "Meus Cartões": aqui o
                # texto longo estourava a coluna.
                texto_saldo = f"deve {services.moeda(saldo)}" if saldo > 0.005 else "sem dívida"
                tags = ("negativo",) if saldo > 0.005 else ()
            else:
                texto_saldo = services.moeda(saldo)
                tags = ("negativo",) if saldo < -0.005 else ()
            rotulo_grupo = {"disponivel": "Sim", "investimento": "Não · aplicação",
                            "outro": "Não", "divida": "—"}[item["grupo"]]
            self.tabela.inserir(
                (item["nome"], tipo, item["instituicao"] or "—", rotulo_grupo,
                 services.moeda(item["entrou"]) if item["entrou"] else "—",
                 services.moeda(item["saiu"]) if item["saiu"] else "—",
                 texto_saldo,
                 services.para_br(item["ultimo_movimento"]) if item["ultimo_movimento"] else "—"),
                iid=item["id"], tags=tags)
        self.tabela.finalizar()

        totais = services.total_disponivel()
        self.lbl_tem.configure(text=f"Dinheiro: {services.moeda(totais['tem'])}",
                               foreground=CORES["sucesso"])
        self.lbl_investido.configure(
            text=f"Investido: {services.moeda(totais['investido'])}",
            foreground=CORES["texto"] if totais["investido"] > 0.005 else CORES["texto_suave"])
        self.lbl_outros.configure(
            text=f"Outros saldos: {services.moeda(totais['outros'])}",
            foreground=CORES["texto"] if totais["outros"] > 0.005 else CORES["texto_suave"])
        self.lbl_deve.configure(text=f"Deve: {services.moeda(totais['deve'])}",
                                foreground=CORES["perigo"] if totais["deve"] > 0.005
                                else CORES["texto_suave"])
        self.lbl_liquido.configure(
            text=f"Sobra: {services.moeda(totais['liquido'])}",
            foreground=CORES["sucesso"] if totais["liquido"] >= 0 else CORES["perigo"])

    def _selecionada(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Minhas Contas", "Escolha antes uma conta da lista.", parent=self)
            return None
        return int(item)

    def nova(self) -> None:
        DialogoNovaConta(self, self._apos)

    def alternar_dinheiro(self) -> None:
        """Liga/desliga a conta selecionada no total de dinheiro disponível."""
        conta_id = self._selecionada()
        if conta_id is None:
            return
        conta = services.obter_conta(conta_id)
        entra = not conta["entra_no_disponivel"]
        try:
            services.definir_conta_dinheiro(conta_id, entra)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não dá para marcar", str(erro), parent=self)
            return
        self._apos()
        self.app.notificar(
            f"'{conta['nome']}' passou a contar como dinheiro disponível." if entra
            else f"'{conta['nome']}' saiu do dinheiro disponível — o saldo continua"
                 " visível na lista.")

    def acertar(self) -> None:
        conta_id = self._selecionada()
        if conta_id:
            DialogoAcerto(self, conta_id, self._apos)

    def transferir(self) -> None:
        DialogoTransferencia(self, self._selecionada_silenciosa(), self._apos)

    def _selecionada_silenciosa(self) -> int | None:
        item = self.tabela.selecionado()
        return int(item) if item else None

    def ver_extrato(self) -> None:
        conta_id = self._selecionada()
        if conta_id:
            JanelaExtrato(self, conta_id)

    def _apos(self) -> None:
        self.recarregar()
        self.app.atualizar_dependentes()


# --------------------------------------------------------------------------- #
class DialogoNovaConta(tk.Toplevel):
    """Assistente simples para cadastrar mais uma conta de dinheiro."""

    def __init__(self, master, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_salvar = ao_salvar
        self.title("Nova conta")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Onde fica esse dinheiro?", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Cadastre cada banco, carteira ou cartão separadamente para"
                            " acompanhar o saldo de cada um.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)

        ttk.Label(corpo, text="Que tipo de conta é?", style="Campo.TLabel").grid(
            row=0, column=0, sticky="w")
        self.cb_tipo = ttk.Combobox(corpo, state="readonly", width=52,
                                    values=list(services.TIPOS_CARTEIRA))
        self.cb_tipo.set("Conta corrente")
        self.cb_tipo.grid(row=1, column=0, sticky="w", pady=(4, 4))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self._explicar())
        self.lbl_explica = ttk.Label(corpo, style="Dica.TLabel", wraplength=520, justify="left")
        self.lbl_explica.grid(row=2, column=0, sticky="w", pady=(0, 14))

        ttk.Label(corpo, text="Nome que você reconhece", style="Campo.TLabel").grid(
            row=3, column=0, sticky="w")
        ttk.Label(corpo, text="Ex.: Nubank, Conta do salário, Vale refeição, Cartão da Ana.",
                  style="Dica.TLabel").grid(row=4, column=0, sticky="w")
        self.var_nome = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_nome, width=52).grid(
            row=5, column=0, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Banco ou empresa (opcional)", style="Campo.TLabel").grid(
            row=6, column=0, sticky="w")
        self.var_instituicao = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_instituicao, width=52).grid(
            row=7, column=0, sticky="we", pady=(4, 14))

        linha = ttk.Frame(corpo)
        linha.grid(row=8, column=0, sticky="w")
        bloco_saldo = ttk.Frame(linha)
        bloco_saldo.pack(side="left", padx=(0, 24))
        self.lbl_saldo = ttk.Label(bloco_saldo, text="Quanto tem nela hoje? (R$)",
                                   style="Campo.TLabel")
        self.lbl_saldo.pack(anchor="w")
        self.cp_saldo = CampoValor(bloco_saldo, width=16)
        self.cp_saldo.pack(anchor="w", pady=(4, 0))

        bloco_data = ttk.Frame(linha)
        bloco_data.pack(side="left")
        ttk.Label(bloco_data, text="Nesta data", style="Campo.TLabel").pack(anchor="w")
        self.dt_data = CampoData(bloco_data, services.hoje_iso())
        self.dt_data.pack(anchor="w", pady=(4, 0))

        ttk.Label(corpo, text="Deixe o valor em branco se a conta está zerada ou se você prefere"
                              " lançar o saldo depois.", style="Dica.TLabel",
                  wraplength=520, justify="left").grid(row=9, column=0, sticky="w", pady=(10, 12))

        # Só aparece para cartão de crédito
        self.quadro_ciclo = ttk.Labelframe(corpo, text=" Ciclo da fatura ")
        linha_ciclo = ttk.Frame(self.quadro_ciclo, style="Superficie.TFrame")
        linha_ciclo.pack(fill="x")
        ttk.Label(linha_ciclo, text="Fecha dia", style="CampoSuperficie.TLabel").pack(side="left")
        self.var_fechamento = tk.IntVar(value=20)
        ttk.Spinbox(linha_ciclo, from_=1, to=31, width=5,
                    textvariable=self.var_fechamento).pack(side="left", padx=6)
        ttk.Label(linha_ciclo, text="vence dia",
                  style="CampoSuperficie.TLabel").pack(side="left", padx=(10, 0))
        self.var_vencimento = tk.IntVar(value=28)
        ttk.Spinbox(linha_ciclo, from_=1, to=31, width=5,
                    textvariable=self.var_vencimento).pack(side="left", padx=6)
        ttk.Label(linha_ciclo, text="juros do rotativo",
                  style="CampoSuperficie.TLabel").pack(side="left", padx=(10, 0))
        self.var_rotativo = tk.StringVar(value="0")
        ttk.Spinbox(linha_ciclo, from_=0, to=100, increment=0.5, width=6,
                    textvariable=self.var_rotativo).pack(side="left", padx=6)
        ttk.Label(linha_ciclo, text="% ao mês", style="CampoSuperficie.TLabel").pack(side="left")
        ttk.Label(self.quadro_ciclo,
                  text="Na data de fechamento o sistema gera a fatura como uma conta a pagar."
                       " O que não for pago continua na dívida e entra na fatura seguinte,"
                       " com os juros do rotativo.",
                  style="DicaSuperficie.TLabel", wraplength=520,
                  justify="left").pack(anchor="w", pady=(8, 0))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=11, column=0, sticky="e", pady=(14, 0))
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        self._explicar()
        centralizar(self, 620, 620)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _explicar(self) -> None:
        tipo = self.cb_tipo.get()
        if tipo.startswith("Cartão de crédito"):
            self.quadro_ciclo.grid(row=10, column=0, sticky="we", pady=(0, 6))
        else:
            self.quadro_ciclo.grid_remove()
        if tipo.startswith("Cartão de crédito"):
            texto = ("O saldo aqui é o quanto você já gastou e ainda vai pagar. Compras no cartão"
                     " aumentam essa dívida; pagar a fatura diminui.")
            self.lbl_saldo.configure(text="Quanto você já deve nele hoje? (R$)")
        elif tipo.startswith("Cartão pré-pago") or tipo.startswith("Vale"):
            texto = ("Você coloca dinheiro antes de usar. Recarregar é uma transferência da sua"
                     " conta para este cartão; gastar com ele é uma saída daqui.")
            self.lbl_saldo.configure(text="Quanto tem de saldo hoje? (R$)")
        elif tipo == "Investimento":
            texto = "Aplicações que você quer acompanhar junto com as contas do dia a dia."
            self.lbl_saldo.configure(text="Quanto está aplicado hoje? (R$)")
        else:
            texto = "O saldo é o dinheiro que está disponível para usar."
            self.lbl_saldo.configure(text="Quanto tem nela hoje? (R$)")
        self.lbl_explica.configure(text=texto)

    def salvar(self) -> None:
        try:
            saldo = self.cp_saldo.get_valor() if self.cp_saldo.var.get().strip() else 0.0
            conta_id = services.criar_carteira(
                self.var_nome.get(), self.cb_tipo.get(), self.var_instituicao.get(),
                saldo, self.dt_data.get_iso())
            if self.cb_tipo.get().startswith("Cartão de crédito"):
                services.configurar_cartao(
                    conta_id, int(self.var_fechamento.get()), int(self.var_vencimento.get()),
                    services.para_float(self.var_rotativo.get() or "0"))
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        conta = services.obter_conta(conta_id)
        messagebox.showinfo(
            "Conta criada",
            f"'{conta['nome']}' já pode ser usada nos registros de entrada e saída.",
            parent=self)
        self.destroy()


# --------------------------------------------------------------------------- #
class DialogoAcerto(tk.Toplevel):
    """Acerta a conta pelo saldo real do extrato, lançando só a diferença."""

    def __init__(self, master, conta_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.conta_id = conta_id
        self.ao_salvar = ao_salvar
        self.conta = services.obter_conta(conta_id)
        self.title("Acertar saldo")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        atual = services.saldo_conta(conta_id)
        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Acertar pelo extrato", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text=f"{self.conta['nome']} — o sistema tem hoje"
                            f" {services.moeda(atual)}",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Qual o saldo real? (R$)", style="Campo.TLabel").grid(
            row=0, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.set_valor(atual)
        self.cp_valor.grid(row=1, column=0, sticky="w", pady=(4, 16), padx=(0, 24))

        ttk.Label(corpo, text="Nesta data", style="Campo.TLabel").grid(row=0, column=1, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=1, column=1, sticky="w", pady=(4, 16))

        ttk.Label(corpo, text="Motivo (opcional)", style="Campo.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        self.var_motivo = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_motivo, width=46).grid(
            row=3, column=0, columnspan=2, sticky="we", pady=(4, 12))

        ttk.Label(corpo, text="O sistema lança apenas a diferença entre o que ele tem registrado"
                              " e o saldo real, sem apagar nada do que você já registrou.",
                  style="Dica.TLabel", wraplength=440, justify="left").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Acertar", style="Primario.TButton",
                   command=self.aplicar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 540, 380)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def aplicar(self) -> None:
        try:
            lancamento = services.ajustar_saldo(
                self.conta_id, self.cp_valor.get_valor(), self.dt_data.get_iso(),
                self.var_motivo.get())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        if lancamento is None:
            messagebox.showinfo("Tudo certo", "O saldo já estava correto — nada foi lançado.",
                                parent=self)
        self.destroy()


# --------------------------------------------------------------------------- #
class DialogoTransferencia(tk.Toplevel):
    def __init__(self, master, origem_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_salvar = ao_salvar
        self.title("Transferir entre contas")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Transferir entre minhas contas", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Serve também para recarregar um cartão pré-pago ou pagar a fatura"
                            " do cartão de crédito.", bg=CORES["superficie"],
                 fg=CORES["texto_suave"], font=(FONTE, 10), anchor="w",
                 justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="De qual conta sai?", style="Campo.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.sel_origem = SeletorConta(corpo, tipos=("ATIVO", "PASSIVO"), width=52)
        self.sel_origem.set_conta_id(origem_id)
        self.sel_origem.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Para qual conta vai?", style="Campo.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        self.sel_destino = SeletorConta(corpo, tipos=("ATIVO", "PASSIVO"), width=52)
        self.sel_destino.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Valor (R$)", style="Campo.TLabel").grid(row=4, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=5, column=0, sticky="w", pady=(4, 14), padx=(0, 24))

        ttk.Label(corpo, text="Quando", style="Campo.TLabel").grid(row=4, column=1, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=5, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Descrição (opcional)", style="Campo.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w")
        self.var_desc = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_desc, width=52).grid(
            row=7, column=0, columnspan=2, sticky="we", pady=(4, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=8, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Transferir", style="Primario.TButton",
                   command=self.aplicar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 600, 470)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def aplicar(self) -> None:
        try:
            origem = self.sel_origem.get_conta_id()
            destino = self.sel_destino.get_conta_id()
            if origem is None or destino is None:
                raise services.RegraNegocioError("Escolha a conta de origem e a de destino.")
            services.transferir(origem, destino, self.cp_valor.get_valor(),
                                self.dt_data.get_iso(), self.var_desc.get())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


# --------------------------------------------------------------------------- #
class DialogoCompraParcelada(tk.Toplevel):
    """Compra em N vezes no cartão: cada parcela cai em uma fatura."""

    def __init__(self, master, cartao_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_salvar = ao_salvar
        self.title("Compra parcelada")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Comprei parcelado no cartão", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="O sistema divide a compra pelas próximas faturas, uma parcela por"
                            " mês — em vez de jogar tudo em um mês só.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)

        ttk.Label(corpo, text="O que você comprou", style="Campo.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.var_desc = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_desc, width=52).grid(
            row=1, column=0, columnspan=2, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Em qual cartão", style="Campo.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        self.sel_cartao = SeletorConta(corpo, tipos=("PASSIVO",), width=46)
        self.sel_cartao.set_conta_id(cartao_id)
        self.sel_cartao.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Categoria do gasto", style="Campo.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w")
        self.sel_categoria = SeletorConta(corpo, tipos=("DESPESA",), width=46)
        self.sel_categoria.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Valor total (R$)", style="Campo.TLabel").grid(
            row=6, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=7, column=0, sticky="w", pady=(4, 14), padx=(0, 16))
        self.cp_valor.ao_mudar(self._simular)

        ttk.Label(corpo, text="Em quantas vezes", style="Campo.TLabel").grid(
            row=6, column=1, sticky="w")
        self.var_parcelas = tk.IntVar(value=10)
        ttk.Spinbox(corpo, from_=1, to=48, width=8, textvariable=self.var_parcelas,
                    command=self._simular).grid(row=7, column=1, sticky="w", pady=(4, 14))
        self.var_parcelas.trace_add("write", lambda *_a: self._simular())

        ttk.Label(corpo, text="Data da compra", style="Campo.TLabel").grid(
            row=8, column=0, sticky="w")
        self.dt_compra = CampoData(corpo, services.hoje_iso())
        self.dt_compra.grid(row=9, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Primeira parcela em", style="Campo.TLabel").grid(
            row=8, column=1, sticky="w")
        self.dt_primeira = CampoData(corpo, services.hoje_iso())
        self.dt_primeira.grid(row=9, column=1, sticky="w", pady=(4, 14))

        self.lbl_previa = ttk.Label(corpo, style="Secao.TLabel")
        self.lbl_previa.grid(row=10, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(corpo, text="Compras sem juros: o valor é apenas dividido. Se houver juros,"
                              " informe o total já com eles.",
                  style="Dica.TLabel", wraplength=480, justify="left").grid(
            row=11, column=0, columnspan=2, sticky="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=12, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Lançar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 620, 620)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _simular(self) -> None:
        try:
            valor = self.cp_valor.get_valor()
            parcelas = max(int(self.var_parcelas.get()), 1)
        except (services.RegraNegocioError, ValueError, tk.TclError):
            self.lbl_previa.configure(text="")
            return
        self.lbl_previa.configure(
            text=f"{parcelas}x de {services.moeda(round(valor / parcelas, 2))}",
            foreground=CORES["texto"])

    def salvar(self) -> None:
        try:
            cartao_id = self.sel_cartao.get_conta_id()
            categoria_id = self.sel_categoria.get_conta_id()
            if cartao_id is None:
                raise services.RegraNegocioError("Escolha o cartão usado na compra.")
            if categoria_id is None:
                raise services.RegraNegocioError("Escolha a categoria do gasto.")
            services.criar_compra_parcelada(
                self.var_desc.get(), cartao_id, categoria_id, self.cp_valor.get_valor(),
                int(self.var_parcelas.get()), self.dt_primeira.get_iso()[:7],
                self.dt_compra.get_iso())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


class JanelaParceladas(tk.Toplevel):
    """Compras parceladas em andamento e quanto elas comprometem as faturas."""

    def __init__(self, master, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_mudar = ao_mudar
        self.title("Compras parceladas")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Compras parceladas", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="O que você ainda vai pagar nas próximas faturas.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 12))
        ttk.Button(acoes, text="Nova compra parcelada", style="Primario.TButton",
                   command=self.nova).pack(side="left")
        ttk.Button(acoes, text="Mudar o valor",
                   command=self.mudar_valor).pack(side="left", padx=8)
        ttk.Button(acoes, text="Cancelar parcelas futuras", style="Perigo.TButton",
                   command=self.cancelar).pack(side="left")
        self.var_todas = tk.BooleanVar(value=False)
        ttk.Checkbutton(acoes, text="Mostrar também as já quitadas", variable=self.var_todas,
                        command=self.recarregar).pack(side="left", padx=8)

        self.tabela = Tabela(corpo, [
            ("descricao", "Compra", 230, "w"),
            ("cartao", "Cartão", 150, "w"),
            ("categoria", "Categoria", 160, "w"),
            ("total", "Valor total", 120, "e"),
            ("parcela", "Parcela", 110, "e"),
            ("andamento", "Lançadas", 100, "center"),
            ("falta", "Ainda vai pagar", 140, "e"),
        ], altura=8)
        self.tabela.definir_texto_vazio("Nenhuma compra parcelada em andamento.")
        self.tabela.pack(fill="both", expand=True)

        self.lbl_comprometido = ttk.Label(corpo, style="Dica.TLabel", justify="left")
        self.lbl_comprometido.pack(anchor="w", pady=(10, 0))

        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(10, 0))
        self.recarregar()
        centralizar(self, 1080, 560)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        self.tabela.limpar()
        for compra in services.listar_compras_parceladas(not self.var_todas.get()):
            self.tabela.inserir(
                (compra["descricao"], compra["cartao"], compra["categoria"],
                 services.moeda(compra["valor_total"]),
                 services.moeda(compra["valor_parcela"]),
                 f"{compra['lancadas']}/{compra['parcelas']}",
                 services.moeda(compra["falta"])),
                iid=compra["id"], tags=() if compra["falta"] > 0.005 else ("quitado",))
        self.tabela.finalizar()

        partes = []
        for cartao in services.listar_carteiras():
            if cartao["tipo"] != "PASSIVO":
                continue
            meses = services.comprometido_por_mes(cartao["id"], 4)
            if any(m["parcelas"] > 0.005 for m in meses):
                resumo = "   ".join(f"{m['mes'][5:7]}/{m['mes'][2:4]}"
                                    f" {services.moeda(m['parcelas'])}" for m in meses)
                partes.append(f"{cartao['nome']}:   {resumo}")
        self.lbl_comprometido.configure(
            text="Já comprometido nas próximas faturas —\n" + "\n".join(partes)
            if partes else "Nenhuma parcela pendente nas próximas faturas.")

    def nova(self) -> None:
        DialogoCompraParcelada(self, None, self._apos)

    def mudar_valor(self) -> None:
        """Corrige o valor total: só as parcelas ainda não faturadas mudam."""
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Compras parceladas", "Escolha antes uma compra da lista.",
                                parent=self)
            return
        DialogoValorParcelada(self, int(item), self._apos)

    def cancelar(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Compras parceladas", "Escolha antes uma compra da lista.",
                                parent=self)
            return
        if not messagebox.askyesno(
                "Cancelar parcelas futuras",
                "As parcelas que ainda não venceram serão apagadas. As que já foram lançadas"
                " continuam no histórico.\n\nConfirma?", parent=self):
            return
        removidas = services.excluir_compra_parcelada(int(item))
        self._apos()
        messagebox.showinfo("Pronto", f"{removidas} parcela(s) futura(s) removida(s).",
                            parent=self)

    def _apos(self) -> None:
        self.recarregar()
        self.ao_mudar()


class DialogoValorParcelada(tk.Toplevel):
    """Novo valor total de uma compra parcelada, preservando o que já foi faturado."""

    def __init__(self, master, compra_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.compra_id = compra_id
        self.ao_salvar = ao_salvar
        self.compra = next(c for c in services.listar_compras_parceladas(False)
                           if c["id"] == compra_id)
        self.title("Mudar o valor da compra")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Mudar o valor da compra", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text=f"{self.compra['descricao']} — hoje"
                            f" {services.moeda(self.compra['valor_total'])} em"
                            f" {self.compra['parcelas']}x",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Novo valor total (R$)", style="Campo.TLabel").pack(anchor="w")
        self.cp_valor = CampoValor(corpo, width=18)
        self.cp_valor.set_valor(self.compra["valor_total"])
        self.cp_valor.pack(anchor="w", pady=(4, 14))

        ttk.Label(corpo, text="As parcelas que já entraram em faturas fechadas não mudam:"
                              " elas já foram cobradas. O que sobra é redividido entre as"
                              " parcelas seguintes.",
                  style="Dica.TLabel", wraplength=440, justify="left").pack(anchor="w",
                                                                           pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 520, 340)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            recalculadas = services.ajustar_compra_parcelada(self.compra_id,
                                                             self.cp_valor.get_valor())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        messagebox.showinfo("Pronto", f"{recalculadas} parcela(s) futura(s) foram"
                                      " recalculadas.", parent=self.master)
        self.destroy()


# --------------------------------------------------------------------------- #
class JanelaFaturas(tk.Toplevel):
    """Faturas fechadas de um cartão, com o que rolou de um mês para o outro."""

    def __init__(self, master, conta_id: int, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.conta_id = conta_id
        self.ao_mudar = ao_mudar
        self.conta = services.obter_conta(conta_id)
        self.title(f"Faturas — {self.conta['nome']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=12)
        topo.pack(fill="x")
        tk.Label(topo, text=f"Faturas do {self.conta['nome']}", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        self.lbl_resumo = tk.Label(topo, bg=CORES["superficie"], fg=CORES["texto_suave"],
                                   font=(FONTE, 10), anchor="w", justify="left")
        self.lbl_resumo.pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=(20, 12))
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 12))
        ttk.Button(acoes, text="Ajustar ciclo da fatura", style="Primario.TButton",
                   command=self.configurar).pack(side="left")
        ttk.Button(acoes, text="Adicionar compra",
                   command=self.adicionar_compra).pack(side="left", padx=8)
        ttk.Button(acoes, text="Compras (corrigir / remover)",
                   command=self.ver_compras).pack(side="left")
        ttk.Label(acoes, text="A fatura atual recebe as compras até o fechamento. O pagamento"
                              " é feito em Contas a Pagar.",
                  style="Dica.TLabel").pack(side="left", padx=12)

        # Duas visões em abas: as duas tabelas juntas não caberiam em telas
        # de 768px de altura.
        abas = ttk.Notebook(corpo)
        abas.pack(fill="both", expand=True)
        aba_fechadas = ttk.Frame(abas, padding=10)
        aba_futuras = ttk.Frame(abas, padding=10)
        abas.add(aba_fechadas, text="  Faturas fechadas  ")
        abas.add(aba_futuras, text="  Próximas faturas  ")

        self.tabela = Tabela(aba_fechadas, [
            ("mes", "Fatura de", 150, "w"),
            ("fecha", "Fechou em", 105, "center"),
            ("vence", "Vence em", 105, "center"),
            ("anterior", "Veio do mês anterior", 150, "e"),
            ("compras", "Compras do mês", 140, "e"),
            ("pagamentos", "Você pagou", 120, "e"),
            ("encargos", "Juros do rotativo", 130, "e"),
            ("total", "Total da fatura", 130, "e"),
            ("situacao", "Situação", 165, "center"),
        ], on_duplo_clique=lambda _i: self.ver_compras(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhuma fatura fechada ainda. Defina o dia de fechamento para o sistema"
            " começar a gerá-las.")
        self.tabela.pack(fill="both", expand=True)

        # --- o que já está agendado para as próximas faturas ---------------
        ttk.Label(aba_futuras, text="O que já está lançado para cair em cada fatura que ainda"
                                    " vai fechar: parcelas de compras, contas fixas pagas"
                                    " neste cartão e o que está em aberto agora.",
                  style="Dica.TLabel", wraplength=1100,
                  justify="left").pack(anchor="w", pady=(0, 8))
        self.tab_futuras = Tabela(aba_futuras, [
            ("mes", "Fatura de", 140, "w"),
            ("fecha", "Fecha em", 100, "center"),
            ("vence", "Vence em", 100, "center"),
            ("atual", "Já lançado", 120, "e"),
            ("parcelas", "Parcelas", 110, "e"),
            ("fixas", "Contas fixas", 120, "e"),
            ("previsto", "Previsão", 120, "e"),
        ], largura_livre=True, altura=5)
        self.tab_futuras.definir_texto_vazio(
            "Defina o dia de fechamento para o sistema projetar as próximas faturas.")
        self.tab_futuras.pack(fill="both", expand=True)

        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(10, 0))
        self.recarregar()
        centralizar(self, 1270, 660)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        self.conta = services.obter_conta(self.conta_id)
        self.tabela.limpar()
        for f in services.listar_faturas(self.conta_id):
            situacao = {"QUITADO": "Paga", "CANCELADO": "Cancelada"}.get(
                f["status_titulo"], "Em aberto" if f["titulo_id"] else "Sem cobrança")
            if not f["fechada"] and f["status_titulo"] != "QUITADO":
                situacao = "Fatura atual (recebendo compras)"
            # Pagou menos que o total: o restante rolou para a fatura seguinte.
            if (f["status_titulo"] == "QUITADO" and f["valor_liquidado"] is not None
                    and float(f["valor_liquidado"]) < float(f["total"]) - 0.005):
                situacao = f"Paga em parte ({services.moeda(f['valor_liquidado'])})"
            self.tabela.inserir(
                (services.mes_nome(f["competencia"]).capitalize(),
                 services.para_br(f["fechamento"]), services.para_br(f["vencimento"]),
                 services.moeda(f["saldo_anterior"]), services.moeda(f["compras"]),
                 services.moeda(f["pagamentos"]),
                 services.moeda(f["encargos"]) if f["encargos"] > 0.005 else "—",
                 services.moeda(f["total"]), situacao),
                iid=f["id"],
                tags=("quitado",) if f["status_titulo"] == "QUITADO" else ())
        self.tabela.finalizar()

        aberta = services.resumo_fatura_aberta(self.conta_id)
        if self.conta["dia_fechamento"]:
            ciclo = (f"Fecha todo dia {self.conta['dia_fechamento']}, vence dia"
                     f" {self.conta['dia_vencimento']}"
                     f"  ·  rotativo {float(self.conta['juros_rotativo'] or 0):.2f}% ao mês")
        else:
            ciclo = "Ciclo não configurado — as faturas ainda não são geradas."
        self.lbl_resumo.configure(
            text=f"{ciclo}\nDívida total hoje: {services.moeda(aberta['saldo_total'])}"
                 f"  ·  compras desde o último fechamento:"
                 f" {services.moeda(aberta['compras'])}"
                 + (f"  ·  próximo fechamento em"
                    f" {services.para_br(aberta['proximo_fechamento'])}"
                    if aberta["proximo_fechamento"] else ""))

        self.tab_futuras.limpar()
        for linha in services.previsao_faturas(self.conta_id, meses=6):
            self.tab_futuras.inserir(
                (services.mes_nome(linha["mes"]).capitalize(),
                 services.para_br(linha["fechamento"]), services.para_br(linha["vencimento"]),
                 services.moeda(linha["saldo_atual"]) if linha["saldo_atual"] else "—",
                 services.moeda(linha["parcelas"]) if linha["parcelas"] else "—",
                 services.moeda(linha["contas_fixas"]) if linha["contas_fixas"] else "—",
                 services.moeda(linha["previsto"])),
                tags=("destaque",) if linha["previsto"] > 0.005 else ())
        self.tab_futuras.finalizar()

    def configurar(self) -> None:
        DialogoCicloFatura(self, self.conta_id, self._apos)

    def adicionar_compra(self) -> None:
        from app.ui.cartoes import DialogoCompraCartao
        DialogoCompraCartao(self, self.conta_id, self._apos)

    def ver_compras(self) -> None:
        """Abre as compras da fatura selecionada (ou da atual, se nenhuma)."""
        from app.ui.cartoes import JanelaComprasCartao
        competencia = None
        item = self.tabela.selecionado()
        if item:
            linha = services.db.query_one("SELECT competencia FROM fatura WHERE id = ?",
                                          (int(item),))
            competencia = linha["competencia"] if linha else None
        JanelaComprasCartao(self, self.conta_id, self._apos, competencia=competencia)

    def _apos(self) -> None:
        self.recarregar()
        self.ao_mudar()


class DialogoCicloFatura(tk.Toplevel):
    def __init__(self, master, conta_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.conta_id = conta_id
        self.ao_salvar = ao_salvar
        conta = services.obter_conta(conta_id)
        self.title("Ciclo da fatura")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=f"Ciclo da fatura — {conta['nome']}",
                  style="Secao.TLabel").grid(row=0, column=0, columnspan=3, sticky="w",
                                             pady=(0, 12))

        ttk.Label(corpo, text="Fecha todo dia", style="Campo.TLabel").grid(
            row=1, column=0, sticky="w")
        self.var_fech = tk.IntVar(value=int(conta["dia_fechamento"] or 20))
        ttk.Spinbox(corpo, from_=1, to=31, width=6, textvariable=self.var_fech).grid(
            row=2, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Vence todo dia", style="Campo.TLabel").grid(
            row=1, column=1, sticky="w")
        self.var_venc = tk.IntVar(value=int(conta["dia_vencimento"] or 28))
        ttk.Spinbox(corpo, from_=1, to=31, width=6, textvariable=self.var_venc).grid(
            row=2, column=1, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Juros do rotativo (% ao mês)", style="Campo.TLabel").grid(
            row=1, column=2, sticky="w")
        self.var_rot = tk.StringVar(value=str(conta["juros_rotativo"] or 0))
        ttk.Spinbox(corpo, from_=0, to=100, increment=0.5, width=8,
                    textvariable=self.var_rot).grid(row=2, column=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Limite do cartão (R$)", style="Campo.TLabel").grid(
            row=3, column=0, sticky="w")
        self.cp_limite = CampoValor(corpo, width=16)
        self.cp_limite.set_valor(float(conta["limite"] or 0))
        self.cp_limite.grid(row=4, column=0, sticky="w", pady=(4, 14))
        ttk.Label(corpo, text="Deixe 0 se não quiser acompanhar o limite.",
                  style="Dica.TLabel").grid(row=4, column=1, columnspan=2, sticky="w",
                                            pady=(4, 14))

        ttk.Label(corpo, text="O rotativo é cobrado apenas sobre o que sobrar sem pagar da"
                              " fatura anterior.", style="Dica.TLabel", wraplength=460,
                  justify="left").grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=6, column=0, columnspan=3, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 560, 300)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            services.configurar_cartao(self.conta_id, int(self.var_fech.get()),
                                       int(self.var_venc.get()),
                                       services.para_float(self.var_rot.get() or "0"))
            limite = self.cp_limite.get_valor() if self.cp_limite.var.get().strip() else 0.0
            from app import db as _db
            _db.execute("UPDATE conta SET limite = ? WHERE id = ?", (limite, self.conta_id))
            services.fechar_faturas()
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


# --------------------------------------------------------------------------- #
class JanelaExtrato(tk.Toplevel):
    """Extrato de uma conta, com saldo passo a passo e evolução mensal."""

    def __init__(self, master, conta_id: int):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.conta_id = conta_id
        self.conta = services.obter_conta(conta_id)
        self.title(f"Extrato — {self.conta['nome']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text=self.conta["nome"], bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        self.lbl_saldo = tk.Label(topo, bg=CORES["superficie"], fg=CORES["texto_suave"],
                                  font=(FONTE, 11), anchor="w")
        self.lbl_saldo.pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        barra = ttk.Frame(corpo)
        barra.pack(fill="x", pady=(0, 12))
        self.filtro = BarraFiltro(barra, self.recarregar)
        self.filtro.pack(side="left")

        ttk.Label(barra, text="Ordem:", style="Campo.TLabel").pack(side="left", padx=(20, 6))
        self.cb_ordem = ttk.Combobox(barra, state="readonly", width=22,
                                     values=["Do mais novo para o mais antigo",
                                             "Do mais antigo para o mais novo"])
        self.cb_ordem.set("Do mais novo para o mais antigo")
        self.cb_ordem.pack(side="left")
        self.cb_ordem.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_pagina())

        self.lbl_anterior = ttk.Label(corpo, style="Dica.TLabel")
        self.lbl_anterior.pack(anchor="w", pady=(0, 6))

        self.tabela = Tabela(corpo, [
            ("data", "Data", 95, "center"),
            ("historico", "Descrição", 280, "w"),
            ("contra", "Categoria / outra conta", 230, "w"),
            ("entrou", "Entrou", 115, "e"),
            ("saiu", "Saiu", 115, "e"),
            ("saldo", "Saldo depois", 125, "e"),
        ], altura=8)
        self.tabela.definir_texto_vazio("Nenhum movimento nesta conta no período.")
        self.tabela.pack(fill="both", expand=True)

        self._linhas: list = []
        self.paginacao = Paginacao(corpo, self._desenhar, por_pagina=8, fundo="TFrame",
                                   nome_itens="movimentos")
        self.paginacao.pack(fill="x", pady=(8, 0))

        self.lbl_evolucao = ttk.Label(corpo, style="Dica.TLabel")
        self.lbl_evolucao.pack(anchor="w", pady=(10, 0))

        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(10, 0))

        self.recarregar()
        centralizar(self, 1080, 660)
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        try:
            desde, ate = self.filtro.periodo()
        except services.RegraNegocioError:
            return
        anterior, linhas = services.razao(self.conta_id, desde, ate)
        self._linhas = linhas
        self.lbl_anterior.configure(
            text=f"Saldo antes de {services.para_br(desde)}: {services.moeda(anterior)}"
                 f"   ·   depois destes movimentos: "
                 f"{services.moeda(linhas[-1]['saldo'] if linhas else anterior)}")
        self._mostrar_pagina()

        saldo_hoje = services.saldo_conta(self.conta_id)
        rotulo = "Deve hoje" if self.conta["tipo"] == "PASSIVO" else "Saldo hoje"
        self.lbl_saldo.configure(text=f"{rotulo}: {services.moeda(saldo_hoje)}"
                                      f"   ·   {len(linhas)} movimento(s) no período")
        evolucao = services.evolucao_carteira(self.conta_id, 6)
        if evolucao:
            self.lbl_evolucao.configure(
                text="Saldo no fim de cada mês:   " + "     ".join(
                    f"{e['mes'][5:7]}/{e['mes'][2:4]} {services.moeda(e['saldo'])}"
                    for e in evolucao))

    def _mostrar_pagina(self) -> None:
        """Aplica a ordem escolhida e entrega a lista à paginação."""
        do_novo = self.cb_ordem.get().startswith("Do mais novo")
        self.paginacao.definir(list(reversed(self._linhas)) if do_novo else self._linhas)

    def _desenhar(self, linhas: list) -> None:
        self.tabela.limpar()
        for linha in linhas:
            entrou = linha["debito"] if self.conta["natureza"] == "D" else linha["credito"]
            saiu = linha["credito"] if self.conta["natureza"] == "D" else linha["debito"]
            self.tabela.inserir(
                (services.para_br(linha["data"]), linha["historico"], linha["contrapartida"],
                 services.moeda(entrou) if entrou else "",
                 services.moeda(saiu) if saiu else "",
                 services.moeda(linha["saldo"])),
                tags=("positivo",) if entrou else ())
        self.tabela.finalizar()

