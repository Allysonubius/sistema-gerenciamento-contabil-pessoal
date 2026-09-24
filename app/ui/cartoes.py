"""Cartões: crédito e pré-pago, com limite, garantia, validade e fatura em aberto."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from app import services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (CampoData, CampoValor, Cabecalho, Cartao, SeletorConta, Tabela,
                            centralizar)


class Cartoes(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Meus Cartões",
            "Crédito (paga a fatura depois) e pré-pago (carrega antes de usar).")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Novo cartão", self.novo, "Primario.TButton")
        self.cabecalho.botao("Editar cartão", self.editar)
        self.cabecalho.botao("Faturas", self.ver_faturas)
        self.cabecalho.botao("Parceladas", self.ver_parceladas)
        self.cabecalho.botao("Carregar", self.carregar_pre_pago)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(2, weight=1)

        grade = ttk.Frame(corpo)
        grade.grid(row=0, column=0, sticky="ew")
        for coluna in range(4):
            grade.columnconfigure(coluna, weight=1, uniform="cartoes")
        self.resumo = {
            "limite": Cartao(grade, "Limite total dos cartões"),
            "livre": Cartao(grade, "Ainda dá para gastar"),
            "fatura": Cartao(grade, "Faturas em aberto"),
            "pre_pago": Cartao(grade, "Saldo nos pré-pagos"),
        }
        for indice, cartao in enumerate(self.resumo.values()):
            cartao.grid(row=0, column=indice, sticky="ew", padx=6, pady=6)

        acoes = ttk.Frame(corpo)
        acoes.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(acoes, text="Para o cartão selecionado:", style="Dica.TLabel").pack(side="left")
        ttk.Button(acoes, text="Nova compra", style="Primario.TButton",
                   command=self.nova_compra).pack(side="left", padx=8)
        ttk.Button(acoes, text="Compras (corrigir / remover)",
                   command=self.ver_compras).pack(side="left", padx=(0, 8))
        ttk.Button(acoes, text="Pagar fatura", style="Sucesso.TButton",
                   command=self.pagar_fatura).pack(side="left")
        ttk.Button(acoes, text="Extrato", command=self.ver_extrato).pack(side="left", padx=8)
        ttk.Button(acoes, text="Atualizar", command=self.ao_exibir).pack(side="right")

        self.tabela = Tabela(corpo, [
            ("nome", "Cartão", 135, "w"),
            ("tipo", "Tipo", 105, "w"),
            ("limite", "Limite / saldo", 105, "e"),
            ("usado", "Usado", 90, "e"),
            ("livre", "Livre", 90, "e"),
            ("ciclo", "Fecha / vence", 100, "center"),
            ("fatura", "Fatura em aberto", 115, "e"),
            ("vence", "Fatura vence", 95, "center"),
            ("garantia", "Garantia", 125, "w"),
            ("validade", "Validade", 75, "center"),
        ], on_duplo_clique=lambda _i: self.editar(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhum cartão cadastrado. Clique em 'Novo cartão' para começar.")
        self.tabela.grid(row=2, column=0, sticky="nsew", pady=(12, 0))

        self.lbl_aviso = ttk.Label(corpo, style="Dica.TLabel", justify="left", wraplength=1000)
        self.lbl_aviso.grid(row=3, column=0, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def ao_exibir(self) -> None:
        descontos = services.descontar_faturas_da_garantia()   # já atualiza as faturas
        self.recarregar()
        for d in descontos:
            self.app.notificar(
                f"Fatura de {services.mes_nome(d['competencia'])} do {d['cartao']} não foi paga:"
                f" {services.moeda(d['valor'])} descontados de {d['garantia']}.")

    def recarregar(self) -> None:
        dados = services.resumo_cartoes()
        m = services.moeda

        self.resumo["limite"].atualizar(
            m(dados["limite_total"]), CORES["texto"],
            f"{len(dados['cartoes'])} cartão(ões) cadastrado(s)", CORES["primaria"])
        livre = dados["livre_total"]
        self.resumo["livre"].atualizar(
            m(livre), CORES["sucesso"] if livre > 0.005 else CORES["perigo"],
            f"já usados {m(dados['usado_total'])}")
        self.resumo["fatura"].atualizar(
            m(dados["fatura_aberta"]),
            CORES["perigo"] if dados["fatura_aberta"] > 0.005 else CORES["sucesso"],
            "a pagar nas próximas datas" if dados["fatura_aberta"] > 0.005
            else "nenhuma fatura em aberto")
        self.resumo["pre_pago"].atualizar(
            m(dados["saldo_pre_pago"]), CORES["texto"],
            "carregado e pronto para usar", CORES["primaria"])

        self.tabela.limpar()
        for cartao in dados["cartoes"]:
            if cartao["credito"]:
                limite = m(cartao["limite"]) if cartao["limite"] else "sem limite definido"
                usado = m(cartao["usado"])
                livre_txt = m(cartao["disponivel"]) if cartao["limite"] else "—"
                ciclo = (f"{cartao['dia_fechamento']} / {cartao['dia_vencimento']}"
                         if cartao["dia_fechamento"] else "não definido")
                fatura = m(cartao["fatura_aberta"]) if cartao["fatura_aberta"] else "—"
                vence = (services.para_br(cartao["fatura_vence"]) if cartao["fatura_vence"]
                         else "—")
                garantia = cartao["garantia_nome"] or "—"
            else:
                limite = m(cartao["saldo"])
                usado = livre_txt = ciclo = fatura = vence = garantia = "—"

            tags: tuple[str, ...] = ()
            if cartao["vencido"]:
                tags = ("negativo",)
            elif cartao["credito"] and cartao["limite"] and cartao["percentual"] >= 80:
                tags = ("destaque",)

            self.tabela.inserir(
                (cartao["nome"], cartao["tipo_texto"], limite, usado, livre_txt, ciclo,
                 fatura, vence, garantia,
                 cartao["validade"] or "—"),
                iid=cartao["id"], tags=tags)
        self.tabela.finalizar()

        avisos = []
        for cartao in dados["cartoes"]:
            if cartao["vencido"]:
                avisos.append(f"O {cartao['nome']} está com a validade vencida"
                              f" ({cartao['validade']}).")
            if cartao["credito"] and cartao["fatura_vence"]:
                avisos.append(
                    f"{cartao['nome']}: fatura atual de {m(cartao['fatura_aberta'])}, vence"
                    f" {services.para_br(cartao['fatura_vence'])}. Compras até o fechamento"
                    " entram nela.")
            if cartao["garantia_id"]:
                avisos.append(
                    f"{cartao['nome']} funciona com saldo em garantia de"
                    f" '{cartao['garantia_nome']}' ({m(cartao['limite'])}): se a fatura não for"
                    " paga até o vencimento, o valor é descontado dessa aplicação no dia"
                    " seguinte.")
        self.lbl_aviso.configure(text="\n".join(avisos))

    # ------------------------------------------------------------------ #
    def _selecionado(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Cartões", "Escolha antes um cartão da lista.", parent=self)
            return None
        return int(item)

    def novo(self) -> None:
        DialogoCartao(self, None, self._apos)

    def editar(self) -> None:
        conta_id = self._selecionado()
        if conta_id:
            DialogoCartao(self, conta_id, self._apos)

    def ver_faturas(self) -> None:
        conta_id = self._selecionado()
        if conta_id is None:
            return
        conta = services.obter_conta(conta_id)
        if conta["tipo"] != "PASSIVO":
            messagebox.showinfo("Faturas", "Cartão pré-pago não tem fatura: o saldo é"
                                           " descontado na hora da compra.", parent=self)
            return
        from app.ui.carteiras import JanelaFaturas
        JanelaFaturas(self, conta_id, self._apos)

    def ver_extrato(self) -> None:
        conta_id = self._selecionado()
        if conta_id:
            from app.ui.carteiras import JanelaExtrato
            JanelaExtrato(self, conta_id)

    def ver_parceladas(self) -> None:
        from app.ui.carteiras import JanelaParceladas
        JanelaParceladas(self, self._apos)

    def carregar_pre_pago(self) -> None:
        conta_id = self._selecionado()
        if conta_id is None:
            return
        conta = services.obter_conta(conta_id)
        if conta["tipo"] == "PASSIVO":
            messagebox.showinfo("Carregar", "Cartão de crédito não se carrega: você usa e"
                                            " paga a fatura depois.", parent=self)
            return
        from app.ui.carteiras import DialogoTransferencia
        DialogoTransferencia(self, None, self._apos)

    def pagar_fatura(self) -> None:
        conta_id = self._selecionado()
        if conta_id is None:
            return
        cartao = next((c for c in services.listar_cartoes() if c["id"] == conta_id), None)
        if cartao is None or not cartao["fatura_titulo_id"]:
            messagebox.showinfo(
                "Pagar fatura",
                "Este cartão não tem fatura em aberto. Confira se o dia de fechamento está"
                " definido em 'Editar cartão'.", parent=self)
            return
        from app.ui.financeiro import DialogoBaixa
        DialogoBaixa(self, cartao["fatura_titulo_id"], self._apos)

    def nova_compra(self) -> None:
        item = self.tabela.selecionado()
        cartao_id = int(item) if item else None
        if cartao_id is not None and services.obter_conta(cartao_id)["tipo"] != "PASSIVO":
            messagebox.showinfo(
                "Nova compra", "No pré-pago a compra é registrada em Entradas e Saídas, saindo"
                               " do saldo dele — não há fatura.", parent=self)
            return
        DialogoCompraCartao(self, cartao_id, self._apos)

    def ver_compras(self) -> None:
        conta_id = self._selecionado()
        if conta_id is None:
            return
        if services.obter_conta(conta_id)["tipo"] != "PASSIVO":
            messagebox.showinfo("Compras", "No pré-pago as compras ficam em Entradas e Saídas.",
                                parent=self)
            return
        JanelaComprasCartao(self, conta_id, self._apos)

    def _apos(self) -> None:
        self.recarregar()
        self.app.atualizar_dependentes()


# --------------------------------------------------------------------------- #
class JanelaComprasCartao(tk.Toplevel):
    """Compras de um cartão, fatura por fatura, para corrigir ou remover."""

    TODAS = "Todas as faturas"

    def __init__(self, master, cartao_id: int, ao_mudar, competencia: str | None = None):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.cartao_id = cartao_id
        self.ao_mudar = ao_mudar
        self.cartao = services.obter_conta(cartao_id)
        self.title(f"Compras — {self.cartao['nome']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=12)
        topo.pack(fill="x")
        tk.Label(topo, text=f"Compras no {self.cartao['nome']}", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Lançou errado? Selecione e corrija ou remova. Compras em fatura"
                            " já paga ficam travadas: elas já foram cobradas.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=(20, 12))
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 10))
        ttk.Label(acoes, text="Fatura:", style="Campo.TLabel").pack(side="left")
        self.cb_fatura = ttk.Combobox(acoes, state="readonly", width=26)
        self.cb_fatura.pack(side="left", padx=(8, 16))
        self.cb_fatura.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        ttk.Button(acoes, text="Nova compra", style="Primario.TButton",
                   command=self.nova).pack(side="left")
        ttk.Button(acoes, text="Remover", style="Perigo.TButton",
                   command=self.remover).pack(side="right")
        ttk.Button(acoes, text="Corrigir", command=self.corrigir).pack(side="right", padx=8)

        self.tabela = Tabela(corpo, [
            ("data", "Data", 95, "center"),
            ("descricao", "Descrição", 230, "w"),
            ("categoria", "Categoria", 170, "w"),
            ("parcela", "Parcela", 75, "center"),
            ("fatura", "Fatura", 130, "w"),
            ("valor", "Valor", 105, "e"),
            ("situacao", "Situação", 150, "center"),
        ], on_duplo_clique=lambda _i: self.corrigir(), largura_livre=True, altura=10)
        self.tabela.definir_texto_vazio("Nenhuma compra nesta fatura.")
        self.tabela.pack(fill="both", expand=True)

        rodape = ttk.Frame(corpo)
        rodape.pack(fill="x", pady=(10, 0))
        self.lbl_total = ttk.Label(rodape, style="Secao.TLabel")
        self.lbl_total.pack(side="left")
        ttk.Button(rodape, text="Fechar", command=self.destroy).pack(side="right")

        self._preencher_faturas(competencia)
        self.recarregar()
        centralizar(self, 1040, 600)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _preencher_faturas(self, escolhida: str | None = None) -> None:
        competencias = sorted({c["competencia"]
                               for c in services.listar_compras_cartao(self.cartao_id)},
                              reverse=True)
        atual = services.fatura_da_data(self.cartao_id, services.hoje_iso())
        self._rotulos = {self.TODAS: None}
        for comp in competencias:
            rotulo = services.mes_nome(comp).capitalize()
            if atual and comp == atual["competencia"]:
                rotulo += " (atual)"
            self._rotulos[rotulo] = comp
        self.cb_fatura["values"] = list(self._rotulos)
        alvo = escolhida or (atual["competencia"] if atual else None)
        rotulo = next((r for r, c in self._rotulos.items() if c == alvo), self.TODAS)
        self.cb_fatura.set(rotulo)

    def recarregar(self) -> None:
        competencia = self._rotulos.get(self.cb_fatura.get())
        self.tabela.limpar()
        total = 0.0
        for compra in services.listar_compras_cartao(self.cartao_id, competencia):
            total += compra["valor"]
            if compra["editavel"]:
                situacao = "Pode corrigir"
            elif compra["paga"]:
                situacao = "Fatura paga (travada)"
            elif compra["origem"] == "BAIXA":
                situacao = "Via Contas a Pagar"
            elif compra["origem"] == "ENCARGO":
                situacao = "Juros automáticos"
            else:
                situacao = "Corrigir em outra tela"
            self.tabela.inserir(
                (services.para_br(compra["data"]), compra["descricao"], compra["categoria"],
                 compra["parcela"] or "à vista",
                 services.mes_nome(compra["competencia"]).capitalize(),
                 services.moeda(compra["valor"]), situacao),
                iid=compra["id"], tags=() if compra["editavel"] else ("quitado",))
        self.tabela.finalizar()
        self.lbl_total.configure(text=f"Total cobrado nas compras listadas: {services.moeda(total)}")

    def _selecionada(self) -> dict | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Compras", "Escolha antes uma compra da lista.", parent=self)
            return None
        return next((c for c in services.listar_compras_cartao(self.cartao_id)
                     if c["id"] == int(item)), None)

    def nova(self) -> None:
        DialogoCompraCartao(self, self.cartao_id, self._apos)

    def corrigir(self) -> None:
        compra = self._selecionada()
        if compra is None:
            return
        if not compra["editavel"]:
            messagebox.showinfo("Não dá para corrigir aqui", compra["motivo"], parent=self)
            return
        DialogoCompraCartao(self, self.cartao_id, self._apos, lancamento_id=compra["id"])

    def remover(self) -> None:
        compra = self._selecionada()
        if compra is None:
            return
        if not compra["editavel"]:
            messagebox.showinfo("Não dá para remover aqui", compra["motivo"], parent=self)
            return
        if compra["compra_id"]:
            pergunta = (f"'{compra['descricao'].rsplit(' (', 1)[0]}' é parcelada. Remover a"
                        " compra inteira? Parcelas em faturas já pagas continuam no histórico.")
        else:
            pergunta = (f"Remover a compra '{compra['descricao']}' de"
                        f" {services.moeda(compra['valor'])}? A fatura será atualizada.")
        if not messagebox.askyesno("Remover compra", pergunta, parent=self):
            return
        try:
            resultado = services.remover_compra_cartao(compra["id"])
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self._apos()
        if resultado["mantidas"]:
            messagebox.showinfo("Compra removida",
                                f"{resultado['removidas']} parcela(s) removida(s);"
                                f" {resultado['mantidas']} em fatura paga continuam.", parent=self)

    def _apos(self) -> None:
        todas = self.cb_fatura.get() == self.TODAS
        competencia = self._rotulos.get(self.cb_fatura.get())
        self._preencher_faturas(competencia)
        if todas:
            self.cb_fatura.set(self.TODAS)
        self.recarregar()
        self.ao_mudar()


# --------------------------------------------------------------------------- #
class DialogoCompraCartao(tk.Toplevel):
    """Compra no cartão de crédito: à vista ou parcelada, direto na fatura certa."""

    def __init__(self, master, cartao_id: int | None, ao_salvar,
                 lancamento_id: int | None = None):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_salvar = ao_salvar
        self.lancamento_id = lancamento_id
        self.compra: dict | None = None          # preenchida no modo "corrigir"
        self._valor_original = 0.0
        self.title("Corrigir compra" if lancamento_id else "Compra no cartão")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=14)
        topo.pack(fill="x")
        tk.Label(topo, text="Corrigir compra no cartão" if lancamento_id else "Comprei no cartão",
                 bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="A compra entra na fatura pela data: até o dia do fechamento,"
                            " vai para a fatura atual.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=(20, 14))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)

        ttk.Label(corpo, text="Em qual cartão", style="Campo.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.sel_cartao = SeletorConta(corpo, tipos=("PASSIVO",), width=46)
        # Só cartões de crédito (os empréstimos também são passivos).
        cartoes = {c["id"] for c in services.listar_cartoes() if c["credito"]}
        self.sel_cartao._mapa = {rotulo: cid for rotulo, cid in self.sel_cartao._mapa.items()
                                 if cid in cartoes}
        self.sel_cartao._todos = list(self.sel_cartao._mapa)
        self.sel_cartao["values"] = self.sel_cartao._todos
        if cartao_id is None and len(cartoes) == 1:
            cartao_id = next(iter(cartoes))
        self.sel_cartao.set_conta_id(cartao_id)
        self.sel_cartao.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 10))
        self.sel_cartao.bind("<<ComboboxSelected>>", lambda _e: self._previa(), add="+")

        ttk.Label(corpo, text="O que você comprou", style="Campo.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        self.var_desc = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_desc, width=50).grid(
            row=3, column=0, columnspan=2, sticky="we", pady=(4, 10))

        ttk.Label(corpo, text="Categoria do gasto", style="Campo.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w")
        self.sel_categoria = SeletorConta(corpo, tipos=("DESPESA",), width=46)
        self.sel_categoria.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 10))

        linha = ttk.Frame(corpo)
        linha.grid(row=6, column=0, columnspan=2, sticky="w")
        bloco = ttk.Frame(linha)
        bloco.pack(side="left", padx=(0, 18))
        self.lbl_valor = ttk.Label(bloco, text="Valor (R$)", style="Campo.TLabel")
        self.lbl_valor.pack(anchor="w")
        self.cp_valor = CampoValor(bloco, width=16)
        self.cp_valor.pack(anchor="w", pady=(4, 10))
        self.cp_valor.ao_mudar(self._previa)

        bloco = ttk.Frame(linha)
        bloco.pack(side="left", padx=(0, 18))
        ttk.Label(bloco, text="Data da compra", style="Campo.TLabel").pack(anchor="w")
        self.dt_compra = CampoData(bloco, services.hoje_iso())
        self.dt_compra.pack(anchor="w", pady=(4, 10))
        self.dt_compra.var.trace_add("write", lambda *_a: self._previa())

        bloco = ttk.Frame(linha)
        bloco.pack(side="left")
        ttk.Label(bloco, text="Parcelas", style="Campo.TLabel").pack(anchor="w")
        self.var_parcelas = tk.StringVar(value="1")
        self.spin_parcelas = ttk.Spinbox(bloco, from_=1, to=48, width=6,
                                         textvariable=self.var_parcelas, command=self._previa)
        self.spin_parcelas.pack(anchor="w", pady=(4, 10))
        self.var_parcelas.trace_add("write", lambda *_a: self._previa())

        self.lbl_dica = ttk.Label(corpo, text="1 parcela = à vista: o valor inteiro entra na"
                                              " fatura.", style="Dica.TLabel", wraplength=520,
                                  justify="left")
        self.lbl_dica.grid(row=7, column=0, columnspan=2, sticky="w")

        self.lbl_previa = ttk.Label(corpo, style="Secao.TLabel", wraplength=520,
                                    justify="left")
        self.lbl_previa.grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self.lbl_limite = ttk.Label(corpo, style="Dica.TLabel", wraplength=520, justify="left")
        self.lbl_limite.grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 12))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=10, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Salvar correção" if lancamento_id else "Lançar compra",
                   style="Primario.TButton", command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)
        if lancamento_id:
            ttk.Button(botoes, text="Remover compra", style="Perigo.TButton",
                       command=self.remover).pack(side="right", padx=(0, 24))
            self._carregar_compra()

        self._previa()
        centralizar(self, 580, 560)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _parcelas(self) -> int:
        try:
            return max(1, min(48, int(self.var_parcelas.get() or 1)))
        except ValueError:
            return 1

    def _carregar_compra(self) -> None:
        """Modo corrigir: preenche com a compra e trava o que não pode mudar."""
        cartao_id = self.sel_cartao.get_conta_id()
        self.compra = next((c for c in services.listar_compras_cartao(cartao_id)
                            if c["id"] == self.lancamento_id), None)
        if self.compra is None:
            raise services.RegraNegocioError("Compra não encontrada.")
        self.sel_cartao.configure(state="disabled")
        self.spin_parcelas.configure(state="disabled")
        self.sel_categoria.set_conta_id(self.compra["categoria_id"])

        if self.compra["compra_id"]:
            parcelada = services.db.query_one("SELECT * FROM compra_parcelada WHERE id = ?",
                                              (self.compra["compra_id"],))
            self.var_desc.set(parcelada["descricao"])
            self.cp_valor.set_valor(float(parcelada["valor_total"]))
            self._valor_original = float(parcelada["valor_total"])
            self.var_parcelas.set(str(parcelada["parcelas"]))
            self.dt_compra.set_iso(parcelada["data_compra"])
            self.dt_compra.configure(state="disabled")
            self.lbl_valor.configure(text="Valor total da compra (R$)")
            self.lbl_dica.configure(
                text=f"Compra parcelada em {parcelada['parcelas']}x: a correção vale para a"
                     " compra inteira. Parcelas em faturas já fechadas mantêm o valor; o"
                     " restante é redividido entre as seguintes.")
        else:
            self.var_desc.set(self.compra["descricao"])
            self.cp_valor.set_valor(self.compra["valor"])
            self._valor_original = self.compra["valor"]
            self.dt_compra.set_iso(self.compra["data"])
            self.lbl_dica.configure(
                text="Mudar a data pode levar a compra para outra fatura — as duas são"
                     " atualizadas.")

    def _previa(self) -> None:
        """Mostra em qual fatura a compra cai e quanto do limite sobra."""
        try:
            cartao_id = self.sel_cartao.get_conta_id()
            data = self.dt_compra.get_iso()
        except services.RegraNegocioError:
            return
        if cartao_id is None:
            self.lbl_previa.configure(text="Escolha o cartão.", foreground=CORES["texto_suave"])
            self.lbl_limite.configure(text="")
            return
        info = services.fatura_da_data(cartao_id, data)
        try:
            valor = self.cp_valor.get_valor()
        except services.RegraNegocioError:
            valor = 0.0
        parcelas = self._parcelas()
        if info is None:
            self.lbl_previa.configure(
                text="Este cartão ainda não tem dia de fechamento: defina em 'Editar cartão'.",
                foreground=CORES["alerta"])
        else:
            dias = (date.fromisoformat(info["vencimento"]) - date.today()).days
            quando = ("vence hoje" if dias == 0 else f"vence em {dias} dia(s)" if dias > 0
                      else f"venceu há {abs(dias)} dia(s)")
            parcela = (f" — {parcelas}x de {services.moeda(valor / parcelas)}, a 1ª"
                       if parcelas > 1 and valor else "")
            texto = (f"Entra na fatura de {info['nome']}{parcela}: fecha"
                     f" {services.para_br(info['fechamento'])} e vence"
                     f" {services.para_br(info['vencimento'])} ({quando}).")
            if info["ja_paga"]:
                texto += " Essa fatura já foi paga — a compra vai para a próxima."
            self.lbl_previa.configure(
                text=texto, foreground=CORES["alerta"] if info["ja_paga"] else CORES["texto"])

        limite = services.limite_do_cartao(cartao_id)
        if limite["limite"] > 0.005:
            # Na correção, o valor antigo já está descontado do limite.
            sobra = round(limite["disponivel"] + self._valor_original - valor, 2)
            self.lbl_limite.configure(
                text=f"Livre no cartão: {services.moeda(limite['disponivel'])}"
                     + (f"  →  depois desta {'correção' if self.compra else 'compra'}:"
                        f" {services.moeda(sobra)}" if valor else "")
                     + (f"  ·  limite vem de '{limite['garantia_nome']}'"
                        if limite["garantia_id"] else ""),
                foreground=CORES["perigo"] if sobra < -0.005 else CORES["texto_suave"])
        else:
            self.lbl_limite.configure(text="", foreground=CORES["texto_suave"])

    def salvar(self) -> None:
        try:
            cartao_id = self.sel_cartao.get_conta_id()
            if cartao_id is None:
                raise services.RegraNegocioError("Escolha o cartão.")
            categoria_id = self.sel_categoria.get_conta_id()
            valor = self.cp_valor.get_valor()
            data = self.dt_compra.get_iso()
            limite = services.limite_do_cartao(cartao_id)
            acrescimo = valor - self._valor_original
            if limite["limite"] > 0.005 and acrescimo > limite["disponivel"] + 0.005:
                if not messagebox.askyesno(
                        "Passa do limite",
                        f"Com {services.moeda(valor)} a compra passa do que está livre no"
                        f" cartão ({services.moeda(limite['disponivel'])}).\n\n"
                        "Salvar mesmo assim?", parent=self):
                    return
            if self.compra and self.compra["compra_id"]:
                services.editar_compra_parcelada(self.compra["compra_id"], self.var_desc.get(),
                                                 categoria_id, valor)
                info = services.fatura_da_data(cartao_id, services.hoje_iso()) or {}
                titulo = "Compra corrigida"
            elif self.compra:
                info = services.editar_compra_cartao(self.lancamento_id, categoria_id, valor,
                                                     data, self.var_desc.get())
                titulo = "Compra corrigida"
            else:
                info = services.registrar_compra_cartao(
                    cartao_id, categoria_id, valor, data, self.var_desc.get(), self._parcelas())
                titulo = "Compra lançada"
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível salvar", str(erro), parent=self)
            return
        self.ao_salvar()
        if info and not (self.compra and self.compra["compra_id"]):
            messagebox.showinfo(
                titulo, f"{'Corrigida' if self.compra else 'Lançada'} na fatura de"
                        f" {info['nome']}, que vence em {services.para_br(info['vencimento'])}.",
                parent=self.master)
        self.destroy()

    def remover(self) -> None:
        if self.compra is None:
            return
        if self.compra["compra_id"]:
            pergunta = ("Esta compra é parcelada. Remover a compra inteira? Parcelas em faturas"
                        " já pagas continuam no histórico.")
        else:
            pergunta = (f"Remover a compra de {services.moeda(self.compra['valor'])}?"
                        " A fatura será atualizada.")
        if not messagebox.askyesno("Remover compra", pergunta, parent=self):
            return
        try:
            services.remover_compra_cartao(self.lancamento_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível remover", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


# --------------------------------------------------------------------------- #
class DialogoCartao(tk.Toplevel):
    """Cadastro do cartão: tipo, limite, ciclo da fatura, garantia e validade."""

    CREDITO = "Cartão de crédito (você paga a fatura depois)"
    PRE_PAGO = "Cartão pré-pago (você carrega antes de usar)"

    def __init__(self, master, conta_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.conta_id = conta_id
        self.ao_salvar = ao_salvar
        self.conta = services.obter_conta(conta_id) if conta_id else None
        self.title("Novo cartão" if conta_id is None else f"Cartão — {self.conta['nome']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=10)
        topo.pack(fill="x")
        tk.Label(topo, text="Dados do cartão", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="O crédito tem limite e fatura; o pré-pago tem saldo carregado.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=(20, 14))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)

        ttk.Label(corpo, text="Que tipo de cartão é?", style="Campo.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.cb_tipo = ttk.Combobox(corpo, state="readonly", width=48,
                                    values=[self.CREDITO, self.PRE_PAGO])
        self.cb_tipo.set(self.CREDITO)
        self.cb_tipo.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self._ajustar_tipo())

        ttk.Label(corpo, text="Nome do cartão", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.var_nome = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_nome, width=30).grid(
            row=3, column=0, sticky="we", pady=(4, 8), padx=(0, 16))

        ttk.Label(corpo, text="Banco / bandeira", style="Campo.TLabel").grid(
            row=2, column=1, sticky="w")
        self.var_banco = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_banco, width=30).grid(
            row=3, column=1, sticky="we", pady=(4, 8))

        self.area_credito = ttk.Frame(corpo)
        self.area_credito.grid(row=4, column=0, columnspan=2, sticky="we")
        self.area_credito.columnconfigure(3, weight=1)

        # --- de onde vem o limite: crédito do banco ou saldo em garantia ---
        ttk.Label(self.area_credito, text="Como funciona o limite deste cartão?",
                  style="Campo.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        self.var_modo = tk.StringVar(value="credito")
        modos = ttk.Frame(self.area_credito)
        modos.grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 10))
        ttk.Radiobutton(modos, variable=self.var_modo, value="credito",
                        command=self._ajustar_modo,
                        text="Crédito — o banco dá um limite fixo").pack(anchor="w")
        ttk.Radiobutton(modos, variable=self.var_modo, value="garantia",
                        command=self._ajustar_modo,
                        text="Saldo em garantia — o limite é o dinheiro aplicado"
                             " (ex.: CDB limite garantido)").pack(anchor="w")

        self.lbl_limite = ttk.Label(self.area_credito, text="Limite (R$)", style="Campo.TLabel")
        self.lbl_limite.grid(row=2, column=0, sticky="w")
        self.cp_limite = CampoValor(self.area_credito, width=14)
        self.cp_limite.grid(row=3, column=0, sticky="w", pady=(3, 6), padx=(0, 16))

        ttk.Label(self.area_credito, text="Fecha dia", style="Campo.TLabel").grid(
            row=2, column=1, sticky="w")
        self.var_fecha = tk.StringVar(value="")
        ttk.Spinbox(self.area_credito, from_=1, to=31, width=5,
                    textvariable=self.var_fecha).grid(row=3, column=1, sticky="w",
                                                      pady=(3, 6), padx=(0, 16))

        ttk.Label(self.area_credito, text="Vence dia", style="Campo.TLabel").grid(
            row=2, column=2, sticky="w")
        self.var_vence = tk.StringVar(value="")
        ttk.Spinbox(self.area_credito, from_=1, to=31, width=5,
                    textvariable=self.var_vence).grid(row=3, column=2, sticky="w",
                                                      pady=(3, 6), padx=(0, 16))

        ttk.Label(self.area_credito, text="Juros do rotativo (% ao mês)",
                  style="Campo.TLabel").grid(row=2, column=3, sticky="w")
        self.var_juros = tk.StringVar(value="0")
        ttk.Spinbox(self.area_credito, from_=0, to=100, increment=0.5, width=8,
                    textvariable=self.var_juros).grid(row=3, column=3, sticky="w", pady=(3, 6))
        ttk.Label(self.area_credito,
                  text="Compras até o dia do fechamento entram na fatura atual. Fecha e vence"
                       " no mesmo dia? Ela é cobrada no próprio dia.",
                  style="Dica.TLabel", wraplength=620, justify="left").grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(0, 6))

        self.area_garantia = ttk.Frame(self.area_credito)
        self.area_garantia.grid(row=5, column=0, columnspan=4, sticky="we")
        ttk.Label(self.area_garantia, text="Qual aplicação está em garantia?",
                  style="Campo.TLabel").pack(anchor="w")
        self.sel_garantia = SeletorConta(self.area_garantia, tipos=("ATIVO",), width=50,
                                         rotulo_vazio="(escolha a aplicação)")
        self.sel_garantia.pack(anchor="w", pady=(4, 2))
        self.sel_garantia.bind("<<ComboboxSelected>>", lambda _e: self._ajustar_garantia(),
                               add="+")
        ttk.Label(self.area_garantia,
                  text="Fatura não paga até o vencimento é descontada desta aplicação no dia"
                       " seguinte — e o limite diminui junto.",
                  style="Dica.TLabel", wraplength=620, justify="left").pack(
            anchor="w", pady=(0, 6))

        ttk.Label(self.area_credito, text="Qual conta paga a fatura?",
                  style="Campo.TLabel").grid(row=6, column=0, columnspan=4, sticky="w")
        self.sel_pagamento = SeletorConta(self.area_credito, tipos=("ATIVO",), width=50,
                                          rotulo_vazio="(decidir na hora de pagar)")
        self.sel_pagamento.grid(row=7, column=0, columnspan=4, sticky="w", pady=(3, 6))

        self.area_saldo = ttk.Frame(corpo)
        self.area_saldo.grid(row=5, column=0, columnspan=2, sticky="we")
        ttk.Label(self.area_saldo, text="Quanto está carregado hoje? (R$)",
                  style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        self.cp_saldo = CampoValor(self.area_saldo, width=14)
        self.cp_saldo.grid(row=1, column=0, sticky="w", pady=(4, 8), padx=(0, 16))
        ttk.Label(self.area_saldo, text="Nesta data", style="Campo.TLabel").grid(
            row=0, column=1, sticky="w")
        self.dt_saldo = CampoData(self.area_saldo, services.hoje_iso())
        self.dt_saldo.grid(row=1, column=1, sticky="w", pady=(4, 8))

        ttk.Label(corpo, text="Validade do cartão (MM/AAAA)", style="Campo.TLabel").grid(
            row=6, column=0, sticky="w")
        self.var_validade = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_validade, width=12).grid(
            row=7, column=0, sticky="w", pady=(4, 8))

        self.lbl_situacao = ttk.Label(corpo, style="Dica.TLabel", justify="left",
                                      wraplength=620)
        self.lbl_situacao.grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 12))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=9, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        self._carregar()
        self._ajustar_tipo()
        centralizar(self, 720, 640)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    # ------------------------------------------------------------------ #
    def _ajustar_tipo(self) -> None:
        credito = self.cb_tipo.get() == self.CREDITO
        if credito:
            self.area_credito.grid()
            self.area_saldo.grid_remove()
            self._ajustar_modo()
        else:
            self.area_credito.grid_remove()
            self.area_saldo.grid()

    def _ajustar_modo(self) -> None:
        if self.var_modo.get() == "garantia":
            self.area_garantia.grid()
        else:
            self.area_garantia.grid_remove()
            self.sel_garantia.set_conta_id(None)
        self._ajustar_garantia()

    def _ajustar_garantia(self) -> None:
        """Com garantia, o limite é o saldo dela — o campo de limite fica travado."""
        try:
            tem_garantia = (self.var_modo.get() == "garantia"
                            and self.sel_garantia.get_conta_id() is not None)
        except services.RegraNegocioError:
            return
        if tem_garantia:
            self.cp_limite.set_valor(services.saldo_conta(self.sel_garantia.get_conta_id()))
            self.cp_limite.configure(state="readonly")
            self.lbl_limite.configure(text="Limite (vem da garantia)")
        else:
            self.cp_limite.configure(state="normal")
            self.lbl_limite.configure(text="Limite (R$)")

    def _carregar(self) -> None:
        if self.conta is None:
            return
        credito = self.conta["tipo"] == "PASSIVO"
        self.cb_tipo.set(self.CREDITO if credito else self.PRE_PAGO)
        self.cb_tipo.configure(state="disabled")   # mudar o tipo mudaria a contabilidade
        self.var_nome.set(self.conta["nome"])
        self.var_banco.set(self.conta["instituicao"] or "")
        self.var_validade.set(self.conta["validade"] or "")
        self.var_fecha.set(str(self.conta["dia_fechamento"] or ""))
        self.var_vence.set(str(self.conta["dia_vencimento"] or ""))
        self.var_juros.set(str(self.conta["juros_rotativo"] or 0))
        if self.conta["conta_garantia_id"]:
            self.var_modo.set("garantia")
            self.sel_garantia.set_conta_id(self.conta["conta_garantia_id"])
        if self.conta["conta_pagamento_id"]:
            self.sel_pagamento.set_conta_id(self.conta["conta_pagamento_id"])
        if credito:
            dados = services.limite_do_cartao(self.conta["id"])
            self.cp_limite.set_valor(dados["limite"])
            self.lbl_situacao.configure(
                text=f"Hoje: usado {services.moeda(dados['usado'])} de"
                     f" {services.moeda(dados['limite'])}"
                     f" · livre {services.moeda(dados['disponivel'])}."
                     + (f" O limite vem da garantia '{dados['garantia_nome']}'."
                        if dados["garantia_id"] else ""))
        else:
            self.cp_saldo.set_valor(services.saldo_conta(self.conta["id"]))
            self.cp_saldo.configure(state="disabled")
            self.dt_saldo.configure(state="disabled")
            self.lbl_situacao.configure(
                text="Para mudar o saldo do pré-pago, use 'Carregar' ou 'Acertar saldo'"
                     " em Minhas Contas — assim o movimento fica registrado.")

    def salvar(self) -> None:
        try:
            credito = self.cb_tipo.get() == self.CREDITO
            nome = self.var_nome.get().strip()
            if not nome:
                raise services.RegraNegocioError("Dê um nome ao cartão.")
            validade = self.var_validade.get().strip()
            garantia_id = (self.sel_garantia.get_conta_id()
                           if credito and self.var_modo.get() == "garantia" else None)
            if credito and self.var_modo.get() == "garantia" and garantia_id is None:
                raise services.RegraNegocioError(
                    "Cartão de saldo em garantia: escolha a aplicação que está em garantia.")
            limite = (self.cp_limite.get_valor() if credito and self.cp_limite.var.get().strip()
                      else 0.0)

            if self.conta_id is None:
                saldo = (self.cp_saldo.get_valor()
                         if not credito and self.cp_saldo.var.get().strip() else 0.0)
                self.conta_id = services.criar_carteira(
                    nome, self.cb_tipo.get(), self.var_banco.get(),
                    saldo, self.dt_saldo.get_iso() if not credito else None)
            else:
                services.renomear_carteira(self.conta_id, nome, self.var_banco.get())

            services.definir_dados_do_cartao(self.conta_id, limite=limite, validade=validade)
            if credito:
                fecha = int(self.var_fecha.get()) if self.var_fecha.get().strip() else None
                vence = int(self.var_vence.get()) if self.var_vence.get().strip() else None
                juros = services.para_float(self.var_juros.get() or "0")
                services.configurar_cartao(self.conta_id, fecha, vence, juros)
                services.definir_garantia_cartao(self.conta_id, garantia_id)
                services.definir_conta_da_fatura(self.conta_id,
                                                 self.sel_pagamento.get_conta_id())
                services.descontar_faturas_da_garantia()
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()
