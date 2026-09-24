"""Contas e categorias: onde você guarda dinheiro e como classifica ganhos e gastos."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import db, services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import Cabecalho, Tabela, centralizar

GRUPOS = {
    "ATIVO": "Onde você guarda dinheiro e o que você tem",
    "PASSIVO": "Dívidas, cartões e financiamentos",
    "PATRIMONIO": "Patrimônio",
    "RECEITA": "De onde vem o seu dinheiro",
    "DESPESA": "Tipos de gasto",
}
GRUPOS_INVERSO = {v: k for k, v in GRUPOS.items()}


class PlanoContas(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Contas e Categorias",
            "Suas contas de dinheiro (banco, carteira, cartão) e as categorias usadas para"
            " classificar ganhos e gastos. Já vem tudo pronto — só ajuste se precisar.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Criar nova", self.nova, "Primario.TButton")
        self.cabecalho.botao("Alterar", self.editar)
        self.cabecalho.botao("Grupos", self.abrir_centros)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)

        filtros = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        filtros.configure(relief="solid", borderwidth=1)
        filtros.pack(fill="x")

        ttk.Label(filtros, text="Mostrar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_tipo = ttk.Combobox(filtros, state="readonly", width=38,
                                    values=["Tudo"] + list(GRUPOS.values()))
        self.cb_tipo.set("Tudo")
        self.cb_tipo.pack(side="left", padx=(8, 16))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())

        ttk.Label(filtros, text="Procurar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.var_busca = tk.StringVar()
        entrada = ttk.Entry(filtros, textvariable=self.var_busca, width=26)
        entrada.pack(side="left", padx=8)
        entrada.bind("<KeyRelease>", lambda _e: self.recarregar())

        self.var_inativas = tk.BooleanVar(value=False)
        ttk.Checkbutton(filtros, text="Mostrar as desativadas", variable=self.var_inativas,
                        command=self.recarregar,
                        style="Superficie.TCheckbutton").pack(side="left", padx=12)
        self.lbl_total = ttk.Label(filtros, style="DicaSuperficie.TLabel")
        self.lbl_total.pack(side="right")

        self.tabela = Tabela(corpo, [
            ("nome", "Nome", 320, "w"),
            ("grupo", "Serve para", 300, "w"),
            ("codigo", "Código", 100, "w"),
            ("classe", "Tipo", 130, "center"),
            ("situacao", "Situação", 100, "center"),
            ("saldo", "Saldo hoje", 140, "e"),
        ], on_duplo_clique=lambda _i: self.editar(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio("Nenhuma conta ou categoria encontrada.")
        self.tabela.pack(fill="both", expand=True, pady=(14, 0))

        ttk.Label(corpo, text="As linhas em negrito são apenas títulos de grupo — você não lança"
                              " valores nelas.", style="Dica.TLabel").pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def recarregar(self) -> None:
        self.tabela.limpar()
        termo = self.var_busca.get().strip().lower()
        tipo = GRUPOS_INVERSO.get(self.cb_tipo.get())
        hoje = services.hoje_iso()
        total = 0
        for conta in services.listar_contas():
            if not conta["ativo"] and not self.var_inativas.get():
                continue
            if tipo and conta["tipo"] != tipo:
                continue
            if termo and termo not in f"{conta['codigo']} {conta['nome']}".lower():
                continue
            saldo = services.saldo_com_filhos(conta["id"], ate=hoje)
            sintetica = not conta["aceita_lancamento"]
            self.tabela.inserir(
                (conta["nome"], GRUPOS[conta["tipo"]], conta["codigo"],
                 "Título de grupo" if sintetica else "Usa nos registros",
                 "Ativa" if conta["ativo"] else "Desativada",
                 services.moeda(saldo) if abs(saldo) > 0.005 else "—"),
                iid=conta["id"], tags=("sintetica",) if sintetica else ())
            total += 1
        self.tabela.finalizar()
        self.lbl_total.configure(text=f"{total} item(ns)")

    def nova(self) -> None:
        DialogoConta(self, None, self.recarregar)

    def editar(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Alterar", "Escolha antes uma linha da lista.", parent=self)
            return
        DialogoConta(self, int(item), self.recarregar)

    def abrir_centros(self) -> None:
        DialogoCentros(self)


# --------------------------------------------------------------------------- #
class DialogoConta(tk.Toplevel):
    def __init__(self, master, conta_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.conta_id = conta_id
        self.ao_salvar = ao_salvar
        self.title("Nova conta ou categoria" if conta_id is None else "Alterar")
        self.resizable(False, False)
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Conta ou categoria", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Dê um nome fácil de reconhecer e escolha para que ela serve.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)

        ttk.Label(corpo, text="Nome", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(corpo, text="Ex.: Banco do Brasil, Farmácia, Bicos e freelas.",
                  style="Dica.TLabel").grid(row=1, column=0, sticky="w")
        self.var_nome = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_nome, width=52).grid(
            row=2, column=0, sticky="we", pady=(4, 16))

        ttk.Label(corpo, text="Para que serve", style="Campo.TLabel").grid(
            row=3, column=0, sticky="w")
        self.cb_tipo = ttk.Combobox(corpo, state="readonly", width=48, values=list(GRUPOS.values()))
        self.cb_tipo.grid(row=4, column=0, sticky="w", pady=(4, 16))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self._sugerir())

        ttk.Label(corpo, text="Código", style="Campo.TLabel").grid(row=5, column=0, sticky="w")
        ttk.Label(corpo, text="O sistema sugere um código livre. Mantenha o número inicial:"
                              " ele define o grupo.", style="Dica.TLabel").grid(
            row=6, column=0, sticky="w")
        self.var_codigo = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_codigo, width=18).grid(
            row=7, column=0, sticky="w", pady=(4, 16))

        self.var_ativa = tk.BooleanVar(value=True)
        ttk.Checkbutton(corpo, text="Ativa (aparece nas listas de escolha)",
                        variable=self.var_ativa).grid(row=8, column=0, sticky="w")
        self.var_analitica = tk.BooleanVar(value=True)
        ttk.Checkbutton(corpo, text="Uso esta conta ao registrar valores"
                                    " (desmarque se for só um título de grupo)",
                        variable=self.var_analitica).grid(row=9, column=0, sticky="w", pady=(0, 16))

        ttk.Label(corpo, text="Observação (opcional)", style="Campo.TLabel").grid(
            row=10, column=0, sticky="w")
        self.txt_obs = tk.Text(corpo, height=3, width=52, font=(FONTE, 10), relief="solid",
                               borderwidth=1)
        self.txt_obs.grid(row=11, column=0, sticky="we", pady=(4, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=12, column=0, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)
        self.btn_excluir = ttk.Button(botoes, text="Apagar", style="Perigo.TButton",
                                      command=self.excluir)

        self._carregar()
        centralizar(self, 620, 620)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _tipo(self) -> str:
        return GRUPOS_INVERSO.get(self.cb_tipo.get(), "DESPESA")

    def _sugerir(self) -> None:
        if self.conta_id is not None:
            return
        self.var_codigo.set(self._proximo_codigo(self._tipo()))

    @staticmethod
    def _proximo_codigo(tipo: str) -> str:
        """Sugere o próximo código livre dentro do primeiro subgrupo do tipo."""
        prefixos = {"ATIVO": "1.1", "PASSIVO": "2.1", "PATRIMONIO": "3",
                    "RECEITA": "4.3", "DESPESA": "5.9"}
        base = prefixos[tipo]
        usados = [c["codigo"] for c in db.query(
            "SELECT codigo FROM conta WHERE codigo LIKE ?", (f"{base}.%",))]
        finais = []
        for codigo in usados:
            sufixo = codigo[len(base) + 1:]
            if sufixo.isdigit():
                finais.append(int(sufixo))
        return f"{base}.{max(finais, default=0) + 1:02d}"

    def _carregar(self) -> None:
        if self.conta_id is None:
            self.cb_tipo.set(GRUPOS["DESPESA"])
            self._sugerir()
            return
        conta = services.obter_conta(self.conta_id)
        self.var_codigo.set(conta["codigo"])
        self.var_nome.set(conta["nome"])
        self.cb_tipo.set(GRUPOS[conta["tipo"]])
        self.var_analitica.set(bool(conta["aceita_lancamento"]))
        self.var_ativa.set(bool(conta["ativo"]))
        self.txt_obs.insert("1.0", conta["observacao"])
        self.btn_excluir.pack(side="left")

    def salvar(self) -> None:
        try:
            tipo = self._tipo()
            services.salvar_conta(
                self.conta_id, self.var_codigo.get(), self.var_nome.get(), tipo,
                services.NATUREZA_PADRAO[tipo], self.var_analitica.get(), self.var_ativa.get(),
                self.txt_obs.get("1.0", "end").strip())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()

    def excluir(self) -> None:
        conta = services.obter_conta(self.conta_id)
        if not messagebox.askyesno(
                "Apagar",
                f"Apagar {conta['nome']}?\n\nSe ela já foi usada em algum registro, o sistema"
                " não deixa apagar — nesse caso, desmarque 'Ativa' para escondê-la.",
                parent=self):
            return
        try:
            services.excluir_conta(self.conta_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não é possível apagar", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


# --------------------------------------------------------------------------- #
class DialogoCentros(tk.Toplevel):
    """Grupos livres (ex.: Pessoal, Família, Trabalho) para separar os registros."""

    def __init__(self, master):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.title("Grupos")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Grupos", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Use para separar seus registros — por exemplo, Pessoal, Família"
                            " e Trabalho.", bg=CORES["superficie"], fg=CORES["texto_suave"],
                 font=(FONTE, 10), anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        linha = ttk.Frame(corpo)
        linha.pack(fill="x")
        self.var_nome = tk.StringVar()
        ttk.Entry(linha, textvariable=self.var_nome, width=30).pack(side="left")
        ttk.Button(linha, text="Adicionar", style="Primario.TButton",
                   command=self.adicionar).pack(side="left", padx=8)
        ttk.Button(linha, text="Ativar/desativar", command=self.alternar).pack(side="left")
        ttk.Button(linha, text="Apagar", style="Perigo.TButton",
                   command=self.excluir).pack(side="left", padx=8)

        self.tabela = Tabela(corpo, [
            ("nome", "Grupo", 240, "w"),
            ("situacao", "Situação", 110, "center"),
            ("lanc", "Registros", 100, "e"),
        ], altura=10)
        self.tabela.definir_texto_vazio("Nenhum grupo cadastrado.")
        self.tabela.pack(fill="both", expand=True, pady=(14, 0))

        self.recarregar()
        centralizar(self, 580, 440)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        self.tabela.limpar()
        for centro in services.listar_centros():
            qtd = db.query_one("SELECT COUNT(*) AS c FROM lancamento WHERE centro_custo_id = ?",
                               (centro["id"],))["c"]
            self.tabela.inserir((centro["nome"], "Ativo" if centro["ativo"] else "Desativado", qtd),
                                iid=centro["id"])
        self.tabela.finalizar()

    def adicionar(self) -> None:
        try:
            services.salvar_centro(None, self.var_nome.get())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Grupos", str(erro), parent=self)
            return
        self.var_nome.set("")
        self.recarregar()

    def alternar(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            return
        centro = db.query_one("SELECT * FROM centro_custo WHERE id = ?", (int(item),))
        services.salvar_centro(int(item), centro["nome"], not centro["ativo"])
        self.recarregar()

    def excluir(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            return
        try:
            services.excluir_centro(int(item))
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não é possível apagar", str(erro), parent=self)
            return
        self.recarregar()
