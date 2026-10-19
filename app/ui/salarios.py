"""Salários e rendas fixas: de onde vem o dinheiro todo mês.

Cada fonte vive aqui com a sua história — inclusive as que acabaram. Trocar de
emprego não apaga nada: o salário antigo fica encerrado no último mês em que
entrou, e o novo passa a gerar os meses à frente.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import db, services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (Cabecalho, Cartao, CampoData, CampoValor, SeletorConta, Tabela,
                            centralizar)

SITUACOES = ("Todas", "Só as que ainda entram", "Só as encerradas")


class Salarios(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Salários e Rendas",
            "De onde vem o seu dinheiro todo mês. Trocou de emprego? Encerre a fonte antiga"
            " no último mês em que ela entrou e cadastre a nova — o histórico fica.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Nova fonte de renda", self.nova, "Primario.TButton")
        self.cabecalho.botao("Registrar recebimento", self.receber, "Sucesso.TButton")
        self.cabecalho.botao("Atualizar", self.recarregar)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(3, weight=1)

        grade = ttk.Frame(corpo)
        grade.grid(row=0, column=0, sticky="ew")
        for coluna in range(3):
            grade.columnconfigure(coluna, weight=1, uniform="cartoes")
        self.cartoes = {
            "mes": Cartao(grade, "Recebido neste mês"),
            "previsto": Cartao(grade, "Ainda a receber no mês"),
            "fontes": Cartao(grade, "Fontes ativas"),
        }
        for indice, cartao in enumerate(self.cartoes.values()):
            cartao.grid(row=0, column=indice, sticky="ew", padx=6, pady=6)

        acoes = ttk.Frame(corpo)
        acoes.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(acoes, text="Para a fonte selecionada:", style="Dica.TLabel").pack(side="left")
        ttk.Button(acoes, text="Editar", command=self.editar).pack(side="left", padx=8)
        ttk.Button(acoes, text="Histórico", command=self.historico).pack(side="left")
        ttk.Button(acoes, text="Pausar / voltar",
                   command=self.alternar).pack(side="left", padx=8)
        ttk.Button(acoes, text="Não recebo mais", style="Perigo.TButton",
                   command=self.encerrar).pack(side="left")

        filtros = ttk.Frame(corpo)
        filtros.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(filtros, text="Mostrar:", style="Campo.TLabel").pack(side="left")
        self.cb_situacao = ttk.Combobox(filtros, state="readonly", width=24, values=SITUACOES)
        self.cb_situacao.set(SITUACOES[0])
        self.cb_situacao.pack(side="left", padx=8)
        self.cb_situacao.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())

        self.tabela = Tabela(corpo, [
            ("fonte", "Fonte", 210, "w"),
            ("quem", "Quem paga", 160, "w"),
            ("valor", "Valor por mês", 115, "e"),
            ("dia", "Entra dia", 80, "center"),
            ("conta", "Cai na conta", 150, "w"),
            ("desde", "Recebendo desde", 125, "center"),
            ("ultimo", "Último recebimento", 135, "center"),
            ("recebido", "Total já recebido", 130, "e"),
            ("situacao", "Situação", 110, "center"),
        ], on_duplo_clique=lambda _i: self.historico(), largura_livre=True, altura=9)
        self.tabela.definir_texto_vazio(
            "Nenhuma fonte de renda cadastrada. Clique em 'Nova fonte de renda' para"
            " registrar o seu salário.")
        self.tabela.grid(row=3, column=0, sticky="nsew", pady=(12, 0))

        rodape = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        rodape.configure(relief="solid", borderwidth=1)
        rodape.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(rodape, text="De onde veio o dinheiro este mês",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        self.lbl_fontes = ttk.Label(rodape, style="DicaSuperficie.TLabel", justify="left")
        self.lbl_fontes.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------ #
    def ao_exibir(self) -> None:
        services.gerar_titulos_recorrentes()
        self.recarregar()

    def recarregar(self) -> None:
        escolha = self.cb_situacao.get()
        rendas = services.listar_rendas_fixas()
        if escolha == SITUACOES[1]:
            rendas = [r for r in rendas if not r["encerrada"]]
        elif escolha == SITUACOES[2]:
            rendas = [r for r in rendas if r["encerrada"]]

        self.tabela.limpar()
        for renda in rendas:
            desde = services.mes_curto(renda["inicio"])
            if renda["fim"]:
                desde += f" até {services.mes_curto(renda['fim'])}"
            ultimo = (services.para_br(renda["ultimo_pagamento"][:10])
                      if renda["ultimo_pagamento"] else "ainda não entrou")
            situacao = "Encerrada" if renda["encerrada"] else "Entrando"
            self.tabela.inserir(
                (renda["descricao"], renda["pessoa"] or "—",
                 services.moeda(renda["valor"]), renda["dia_vencimento"],
                 renda["conta_pagamento_nome"] or "— não definida —",
                 desde, ultimo, services.moeda(renda["recebido"]), situacao),
                iid=renda["id"],
                tags=("quitado",) if renda["encerrada"] else ("positivo",))
        self.tabela.finalizar()

        desde_mes, ate_mes = services.primeiro_dia_mes(), services.ultimo_dia_mes()
        fontes_mes = services.total_recebido_por_fonte(desde_mes, ate_mes)
        recebido = round(sum(f["total"] for f in fontes_mes), 2)
        ativas = [r for r in services.listar_rendas_fixas() if not r["encerrada"]]
        a_receber = round(sum(
            float(t["valor"]) for t in services.listar_titulos(
                tipo="RECEBER", status="ABERTO", desde=desde_mes, ate=ate_mes)), 2)

        self.cartoes["mes"].atualizar(
            services.moeda(recebido), CORES["sucesso"],
            f"{len(fontes_mes)} fonte(s) neste mês" if fontes_mes else "nada recebido ainda")
        self.cartoes["previsto"].atualizar(
            services.moeda(a_receber), CORES["texto"],
            "o que ainda deve entrar até o fim do mês")
        self.cartoes["fontes"].atualizar(
            str(len(ativas)), CORES["texto"],
            "somando " + services.moeda(round(sum(r["valor"] for r in ativas), 2)) + " por mês")

        if fontes_mes:
            self.lbl_fontes.configure(
                text="\n".join(f"{f['fonte'][:40]}: {services.moeda(f['total'])}"
                               f"  ({f['vezes']}x)" for f in fontes_mes[:6]))
        else:
            self.lbl_fontes.configure(
                text="Nenhum recebimento registrado neste mês. Use 'Registrar recebimento'"
                     " quando o dinheiro cair.")

    # ------------------------------------------------------------------ #
    def _selecionada(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Salários", "Escolha antes uma fonte da lista.", parent=self)
            return None
        return int(item)

    def nova(self) -> None:
        DialogoNovaRenda(self, self._apos)

    def editar(self) -> None:
        rec_id = self._selecionada()
        if rec_id:
            from app.ui.financeiro import DialogoReajuste
            DialogoReajuste(self, rec_id, self._apos)

    def encerrar(self) -> None:
        rec_id = self._selecionada()
        if rec_id:
            from app.ui.financeiro import DialogoEncerrarFixa
            DialogoEncerrarFixa(self, rec_id, self._apos)

    def alternar(self) -> None:
        rec_id = self._selecionada()
        if not rec_id:
            return
        rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (rec_id,))
        if rec["ativo"]:
            services.pausar_recorrencia(rec_id)
            self.app.notificar(f"'{rec['descricao']}' pausada: não gera novos meses.")
        else:
            services.reativar_recorrencia(rec_id)
            self.app.notificar(f"'{rec['descricao']}' voltou a entrar todo mês.")
        self._apos()

    def historico(self) -> None:
        rec_id = self._selecionada()
        if rec_id:
            JanelaHistoricoRenda(self, rec_id)

    def receber(self) -> None:
        """Dá baixa no recebimento em aberto mais antigo da fonte escolhida."""
        rec_id = self._selecionada()
        if not rec_id:
            return
        titulo = db.query_one(
            "SELECT * FROM titulo WHERE recorrencia_id = ? AND status = 'ABERTO'"
            " ORDER BY vencimento LIMIT 1", (rec_id,))
        if titulo is None:
            messagebox.showinfo("Registrar recebimento",
                                "Esta fonte não tem nenhum mês em aberto para receber.",
                                parent=self)
            return
        from app.ui.financeiro import DialogoBaixa
        DialogoBaixa(self, titulo["id"], self._apos)

    def _apos(self) -> None:
        self.recarregar()
        self.app.atualizar_dependentes()


# --------------------------------------------------------------------------- #
class DialogoNovaRenda(tk.Toplevel):
    """Cadastra uma fonte de renda que se repete todo mês."""

    def __init__(self, master, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_salvar = ao_salvar
        self.title("Nova fonte de renda")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="De onde vem o dinheiro?", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Salário, aluguel recebido, pensão, bolsa — o que entra todo mês.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Nome da fonte", style="Campo.TLabel").grid(
            row=0, column=0, sticky="w")
        self.var_desc = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_desc, width=28).grid(
            row=1, column=0, sticky="w", pady=(4, 14), padx=(0, 24))

        ttk.Label(corpo, text="Quem paga", style="Campo.TLabel").grid(
            row=0, column=1, sticky="w")
        self.var_pessoa = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_pessoa, width=28).grid(
            row=1, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Valor por mês (R$)", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=3, column=0, sticky="w", pady=(4, 14), padx=(0, 24))

        ttk.Label(corpo, text="Primeiro recebimento em", style="Campo.TLabel").grid(
            row=2, column=1, sticky="w")
        self.dt_inicio = CampoData(corpo, services.hoje_iso())
        self.dt_inicio.grid(row=3, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Categoria (de onde vem)", style="Campo.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w")
        self.sel_categoria = SeletorConta(corpo, tipos=("RECEITA",), width=50)
        self.sel_categoria.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 14))
        self._escolher_salario()

        ttk.Label(corpo, text="Em qual conta o dinheiro entra?", style="Campo.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("ATIVO",), width=50,
                                      rotulo_vazio="(decidir na hora)")
        self.sel_conta.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="O sistema já deixa os próximos 12 meses na lista de contas a"
                              " receber. Quando o dinheiro cair, marque como recebido —"
                              " dá para corrigir o valor na hora.",
                  style="Dica.TLabel", wraplength=520, justify="left").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(0, 14))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=9, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 660, 560)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _escolher_salario(self) -> None:
        """Salário é o caso comum: já vem escolhido."""
        try:
            self.sel_categoria.set_conta_id(services._conta_por_codigo("4.1.01"))
        except services.RegraNegocioError:  # pragma: no cover - plano alterado
            pass

    def salvar(self) -> None:
        try:
            descricao = self.var_desc.get().strip()
            if not descricao:
                raise services.RegraNegocioError("Dê um nome para a fonte (ex.: Salário).")
            categoria = self.sel_categoria.get_conta_id()
            if categoria is None:
                raise services.RegraNegocioError("Escolha a categoria da renda.")
            _rec, meses = services.criar_conta_fixa(
                "RECEBER", descricao, self.var_pessoa.get(), self.cp_valor.get_valor(),
                self.dt_inicio.get_iso(), categoria,
                conta_pagamento_id=self.sel_conta.get_conta_id())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        messagebox.showinfo(
            "Fonte cadastrada",
            f"'{descricao}' passa a entrar todo mês.\n\n{meses} mês(es) já foram lançados"
            " em Contas a Pagar e Receber.", parent=self.master)
        self.destroy()


# --------------------------------------------------------------------------- #
class JanelaHistoricoRenda(tk.Toplevel):
    """Mês a mês de uma fonte: o previsto, o que entrou e a diferença."""

    def __init__(self, master, recorrencia_id: int):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (recorrencia_id,))
        self.title(f"Histórico — {self.rec['descricao']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text=self.rec["descricao"], bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        situacao = "ativa" if self.rec["ativo"] else "encerrada"
        tk.Label(topo, text=f"{services.moeda(self.rec['valor'])} por mês · entra todo dia"
                            f" {self.rec['dia_vencimento']} · {situacao}",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        tabela = Tabela(corpo, [
            ("mes", "Mês", 120, "center"),
            ("vencimento", "Previsto para", 110, "center"),
            ("valor", "Previsto", 110, "e"),
            ("recebido", "Entrou", 110, "e"),
            ("diferenca", "Diferença", 110, "e"),
            ("quando", "Entrou em", 110, "center"),
            ("situacao", "Situação", 110, "center"),
        ], largura_livre=True, altura=12)
        tabela.pack(fill="both", expand=True)

        total = 0.0
        for item in services.historico_da_renda(recorrencia_id):
            recebido = item["recebido"]
            if recebido is not None:
                total += recebido
            diferenca = item["diferenca"]
            if diferenca is None or abs(diferenca) < 0.005:
                texto_dif, tag = "—", ()
            elif diferenca > 0:
                texto_dif, tag = f"+ {services.moeda(diferenca)}", ("positivo",)
            else:
                texto_dif, tag = f"- {services.moeda(abs(diferenca))}", ("negativo",)
            tabela.inserir(
                (services.mes_curto(item["competencia"] or item["vencimento"][:7]),
                 services.para_br(item["vencimento"]),
                 services.moeda(item["valor"]),
                 services.moeda(recebido) if recebido is not None else "—",
                 texto_dif,
                 services.para_br(item["liquidado_em"]) if item["liquidado_em"] else "—",
                 {"QUITADO": "Recebido", "CANCELADO": "Cancelado"}.get(item["status"],
                                                                      "A receber")),
                iid=item["id"], tags=tag)
        tabela.finalizar()

        ttk.Label(corpo, text=f"Total já recebido desta fonte: {services.moeda(total)}",
                  style="Secao.TLabel", foreground=CORES["sucesso"]).pack(anchor="w",
                                                                          pady=(10, 0))
        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(12, 0))
        centralizar(self, 940, 620)
        self.bind("<Escape>", lambda _e: self.destroy())
