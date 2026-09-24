"""Dívidas: tudo o que você deve hoje, com saldo devedor e parcelas."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from app import services
from app.ui.theme import CORES
from app.ui.widgets import Cabecalho, Cartao, Paginacao, Tabela


class Dividas(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Empréstimos e Dívidas",
            "Tudo o que você ainda deve. Cada pagamento registrado aqui abate o saldo.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Registrar pagamento", self.pagar, "Sucesso.TButton")
        self.cabecalho.botao("Nova dívida", self.nova_divida, "Primario.TButton")
        self.cabecalho.botao("Empréstimo com parcelas", self.novo_emprestimo)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(3, weight=1)

        # --- cartões de resumo -------------------------------------------
        grade = ttk.Frame(corpo)
        grade.grid(row=0, column=0, sticky="ew")
        for coluna in range(3):
            grade.columnconfigure(coluna, weight=1, uniform="cartoes")
        self.cartoes = {
            "total": Cartao(grade, "Total que você deve"),
            "parcelas": Cartao(grade, "Parcelas deste mês"),
            "quitado": Cartao(grade, "Já pago dessas dívidas"),
        }
        for indice, cartao in enumerate(self.cartoes.values()):
            cartao.grid(row=0, column=indice, sticky="ew", padx=6, pady=6)

        # --- ações sobre a dívida escolhida -------------------------------
        acoes = ttk.Frame(corpo)
        acoes.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(acoes, text="Para a dívida selecionada:", style="Dica.TLabel").pack(side="left")
        ttk.Button(acoes, text="Pagar uma parte", style="Sucesso.TButton",
                   command=self.pagar).pack(side="left", padx=8)
        ttk.Button(acoes, text="Extrato", command=self.ver_extrato).pack(side="left")
        ttk.Button(acoes, text="Ver parcelas", command=self.ver_parcelas).pack(side="left", padx=8)
        # Duas coisas bem diferentes, botões diferentes: corrigir quanto se deve
        # não é pagar, e quitar encerra a dívida de vez.
        ttk.Button(acoes, text="Alterar valor da dívida",
                   command=self.acertar).pack(side="left")
        ttk.Button(acoes, text="Quitar dívida", style="Sucesso.TButton",
                   command=self.quitar).pack(side="left", padx=8)
        ttk.Button(acoes, text="Apagar", style="Perigo.TButton",
                   command=self.excluir).pack(side="left")
        ttk.Button(acoes, text="Atualizar", command=self.recarregar).pack(side="right")
        ttk.Button(acoes, text="Dívidas quitadas",
                   command=self.abrir_quitadas).pack(side="right", padx=8)

        # --- procurar e paginar -------------------------------------------
        filtros = ttk.Frame(corpo)
        filtros.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(filtros, text="Procurar:", style="Campo.TLabel").pack(side="left")
        self.var_texto = tk.StringVar()
        entrada = ttk.Entry(filtros, textvariable=self.var_texto, width=26)
        entrada.pack(side="left", padx=8)
        entrada.bind("<KeyRelease>", lambda _e: self.recarregar())
        ttk.Label(filtros, text="Mostrar:", style="Campo.TLabel").pack(side="left", padx=(14, 0))
        self.cb_tipo = ttk.Combobox(filtros, state="readonly", width=24,
                                    values=["Todas", "Com parcelas", "Sem parcelas",
                                            "Com parcela atrasada"])
        self.cb_tipo.set("Todas")
        self.cb_tipo.pack(side="left", padx=8)
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        self.paginacao = Paginacao(filtros, self._desenhar, por_pagina=10, fundo="TFrame",
                                   nome_itens="dívidas")
        self.paginacao.pack(side="right")

        self.tabela = Tabela(corpo, [
            ("nome", "Dívida", 230, "w"),
            ("credor", "Com quem", 150, "w"),
            ("saldo", "Quanto ainda devo", 150, "e"),
            ("parcela", "Parcela", 110, "e"),
            ("andamento", "Parcelas", 100, "center"),
            ("juros", "Juros ao mês", 105, "center"),
            ("proxima", "Próximo vencimento", 145, "center"),
        ], on_duplo_clique=lambda _i: self.ver_parcelas(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhuma dívida registrada. Use 'Nova dívida' para cadastrar o que você deve hoje.")
        self.tabela.grid(row=3, column=0, sticky="nsew", pady=(12, 0))

        # --- próximas parcelas -------------------------------------------
        rodape = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        rodape.configure(relief="solid", borderwidth=1)
        rodape.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(rodape, text="Próximos vencimentos ligados a dívidas",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        self.lbl_proximas = ttk.Label(rodape, style="DicaSuperficie.TLabel", justify="left")
        self.lbl_proximas.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------ #
    def recarregar(self) -> None:
        dividas = services.listar_dividas()
        self.paginacao.definir(self._filtrar(dividas))

        resumo = services.resumo_dividas()
        pago = round(sum(d["pago"] for d in dividas), 2)
        self.cartoes["total"].atualizar(
            services.moeda(resumo["total"]),
            CORES["perigo"] if resumo["total"] > 0.005 else CORES["sucesso"],
            f"{resumo['quantidade']} dívida(s) em aberto")
        self.cartoes["parcelas"].atualizar(
            services.moeda(resumo["parcela_mensal"]), CORES["texto"],
            "soma das parcelas em andamento" if resumo["parcela_mensal"]
            else "nenhuma parcela cadastrada")
        self.cartoes["quitado"].atualizar(
            services.moeda(pago), CORES["sucesso"],
            "só o que saiu de conta — correção de valor não entra")

        proximas = []
        hoje = services.hoje_iso()
        for titulo in services.listar_titulos(tipo="PAGAR", status="ABERTO"):
            if not titulo["de_emprestimo"]:
                continue
            atraso = " (atrasada)" if titulo["vencimento"] < hoje else ""
            proximas.append(f"{services.para_br(titulo['vencimento'])} — "
                            f"{titulo['descricao'][:44]}: "
                            f"{services.moeda(titulo['valor'])}{atraso}")
        self.lbl_proximas.configure(
            text="\n".join(proximas[:6]) if proximas else
            "Nenhuma parcela cadastrada em Contas a Pagar. Dívidas sem parcelas mostram"
            " apenas o saldo devedor — registre cada pagamento para ele ir baixando.")

    def _filtrar(self, dividas: list[dict]) -> list[dict]:
        """Aplica a busca por nome/credor e o filtro de tipo."""
        texto = self.var_texto.get().strip().lower()
        if texto:
            dividas = [d for d in dividas
                       if texto in d["nome"].lower() or texto in (d["credor"] or "").lower()]
        escolha = self.cb_tipo.get()
        hoje = services.hoje_iso()
        if escolha == "Com parcelas":
            dividas = [d for d in dividas if d["parcelas"]]
        elif escolha == "Sem parcelas":
            dividas = [d for d in dividas if not d["parcelas"]]
        elif escolha == "Com parcela atrasada":
            dividas = [d for d in dividas if d["proxima"] and d["proxima"] < hoje]
        return dividas

    def _desenhar(self, dividas: list[dict]) -> None:
        self.tabela.limpar()
        hoje = services.hoje_iso()
        for divida in dividas:
            atrasada = divida["proxima"] and divida["proxima"] < hoje
            self.tabela.inserir(
                (divida["nome"], divida["credor"] or "—",
                 services.moeda(divida["saldo"]),
                 services.moeda(divida["valor_parcela"]) if divida["valor_parcela"] else "—",
                 f"{divida['pagas']}/{divida['parcelas']}" if divida["parcelas"] else "—",
                 f"{divida['juros_mes_pct']:.2f}%" if divida["juros_mes_pct"] else "—",
                 services.para_br(divida["proxima"]) if divida["proxima"] else "—"),
                iid=divida["conta_id"], tags=("vencido",) if atrasada else ("negativo",))
        self.tabela.finalizar()

    # ------------------------------------------------------------------ #
    def _selecionada(self) -> dict | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Dívidas", "Escolha antes uma dívida da lista.", parent=self)
            return None
        conta_id = int(item)
        return next((d for d in services.listar_dividas() if d["conta_id"] == conta_id), None)

    def nova_divida(self) -> None:
        from app.ui.financeiro import DialogoNovaDivida
        DialogoNovaDivida(self, self._apos)

    def novo_emprestimo(self) -> None:
        from app.ui.financeiro import DialogoEmprestimo
        DialogoEmprestimo(self, self._apos)

    def pagar(self) -> None:
        divida = self._selecionada()
        if divida:
            from app.ui.financeiro import DialogoPagarDivida
            DialogoPagarDivida(self, divida, self._apos)

    def acertar(self) -> None:
        divida = self._selecionada()
        if divida:
            from app.ui.financeiro import DialogoAcertarDivida
            DialogoAcertarDivida(self, divida, self._apos)

    def ver_extrato(self) -> None:
        divida = self._selecionada()
        if divida:
            from app.ui.financeiro import JanelaExtratoDivida
            JanelaExtratoDivida(self, divida)

    def quitar(self) -> None:
        divida = self._selecionada()
        if divida:
            from app.ui.financeiro import DialogoQuitarDivida
            DialogoQuitarDivida(self, divida, self._apos)

    def abrir_quitadas(self) -> None:
        from app.ui.financeiro import JanelaDividasQuitadas
        JanelaDividasQuitadas(self, self._apos)

    def ver_parcelas(self) -> None:
        divida = self._selecionada()
        if not divida:
            return
        if divida["emprestimo_id"] is None:
            messagebox.showinfo(
                "Parcelas",
                "Esta dívida não tem plano de parcelas.\n\nUse 'Registrar pagamento' a cada"
                " valor pago, ou 'Acertar saldo devedor' para informar quanto ainda falta.",
                parent=self)
            return
        from app.ui.financeiro import JanelaParcelas
        JanelaParcelas(self, divida["emprestimo_id"])

    def excluir(self) -> None:
        divida = self._selecionada()
        if not divida:
            return
        if divida["emprestimo_id"]:
            if not messagebox.askyesno(
                    "Apagar empréstimo",
                    "O empréstimo e as parcelas em aberto serão apagados.\n\nConfirma?",
                    parent=self):
                return
            try:
                services.excluir_emprestimo(divida["emprestimo_id"])
            except services.RegraNegocioError as erro:
                messagebox.showwarning("Não é possível apagar", str(erro), parent=self)
                return
        else:
            if not messagebox.askyesno(
                    "Apagar dívida",
                    f"Apagar '{divida['nome']}'?\n\nUse apenas se ela foi registrada por engano.",
                    parent=self):
                return
            try:
                services.excluir_conta_com_lancamentos(divida["conta_id"])
            except services.RegraNegocioError as erro:
                messagebox.showwarning("Não é possível apagar", str(erro), parent=self)
                return
        self._apos()

    def _apos(self) -> None:
        self.recarregar()
        self.app.atualizar_dependentes()
