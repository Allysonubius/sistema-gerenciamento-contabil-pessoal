"""Importar extrato do banco ou fatura do cartão, sem digitar tudo à mão."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app import importacao, services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import SeletorCentro, SeletorConta, Tabela, centralizar


class JanelaImportar(tk.Toplevel):
    def __init__(self, master, ao_importar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_importar = ao_importar
        self.itens: list[importacao.ItemExtrato] = []
        self.title("Importar extrato")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Importar extrato ou fatura", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Baixe o arquivo OFX no site do seu banco (ou um CSV) e traga aqui."
                            " O sistema adivinha a categoria de cada linha — você só confere.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        # --- passo 1: arquivo e conta ------------------------------------
        passo1 = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        passo1.configure(relief="solid", borderwidth=1)
        passo1.pack(fill="x")

        linha = ttk.Frame(passo1, style="Superficie.TFrame")
        linha.pack(fill="x")
        ttk.Button(linha, text="Escolher arquivo...", style="Primario.TButton",
                   command=self.escolher).pack(side="left")
        self.lbl_arquivo = ttk.Label(linha, text="Nenhum arquivo escolhido.",
                                     style="DicaSuperficie.TLabel")
        self.lbl_arquivo.pack(side="left", padx=12)

        linha2 = ttk.Frame(passo1, style="Superficie.TFrame")
        linha2.pack(fill="x", pady=(12, 0))
        ttk.Label(linha2, text="Este extrato é de qual conta?",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.sel_conta = SeletorConta(linha2, tipos=("ATIVO", "PASSIVO"), width=40)
        self.sel_conta.pack(side="left", padx=8)
        ttk.Label(linha2, text="Grupo (opcional):",
                  style="CampoSuperficie.TLabel").pack(side="left", padx=(12, 0))
        self.sel_centro = SeletorCentro(linha2, width=18)
        self.sel_centro.pack(side="left", padx=8)

        # --- passo 2: conferência ----------------------------------------
        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(14, 8))
        ttk.Label(acoes, text="Confira as categorias antes de gravar:",
                  style="Campo.TLabel").pack(side="left")
        ttk.Button(acoes, text="Mudar categoria", command=self.mudar_categoria).pack(
            side="left", padx=12)
        ttk.Button(acoes, text="Incluir / deixar de fora", command=self.alternar).pack(side="left")
        self.lbl_contagem = ttk.Label(acoes, style="Dica.TLabel")
        self.lbl_contagem.pack(side="right")

        self.tabela = Tabela(corpo, [
            ("marcado", "Importar", 80, "center"),
            ("data", "Data", 95, "center"),
            ("descricao", "Descrição no extrato", 300, "w"),
            ("valor", "Valor", 120, "e"),
            ("categoria", "Vai entrar como", 200, "w"),
            ("origem", "Sugestão", 110, "center"),
            ("situacao", "Situação", 130, "center"),
        ], on_duplo_clique=lambda _i: self.mudar_categoria(), altura=10)
        self.tabela.definir_texto_vazio("Escolha um arquivo para ver os lançamentos.")
        self.tabela.pack(fill="both", expand=True)

        rodape = ttk.Frame(corpo)
        rodape.pack(fill="x", pady=(12, 0))
        ttk.Label(rodape, text="Nada é gravado duas vezes: itens já importados antes aparecem"
                               " marcados e são ignorados.", style="Dica.TLabel").pack(side="left")
        ttk.Button(rodape, text="Importar", style="Primario.TButton",
                   command=self.importar).pack(side="right")
        ttk.Button(rodape, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 1150, 740)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    # ------------------------------------------------------------------ #
    def escolher(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self, title="Escolha o extrato",
            filetypes=[("Extrato do banco (OFX)", "*.ofx *.qfx"),
                       ("Planilha (CSV)", "*.csv *.txt"),
                       ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            self.itens = importacao.preparar(caminho)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível ler", str(erro), parent=self)
            return
        self.lbl_arquivo.configure(text=Path(caminho).name)
        self._render()

    def _render(self) -> None:
        self.tabela.limpar()
        for indice, item in enumerate(self.itens):
            if item.ja_importado:
                situacao, tags = "Já importado", ("quitado",)
            elif item.categoria_id is None:
                situacao, tags = "Escolha a categoria", ("negativo",)
            else:
                situacao, tags = "Pronto", ()
            self.tabela.inserir(
                ("Sim" if item.importar else "Não", services.para_br(item.data),
                 item.descricao[:70],
                 ("+ " if item.valor > 0 else "- ") + services.moeda(abs(item.valor)),
                 item.categoria_nome or "—", item.origem_sugestao or "—", situacao),
                iid=indice,
                tags=tags + (("positivo",) if item.valor > 0 and not item.ja_importado else ()))
        self.tabela.finalizar()
        marcados = sum(1 for i in self.itens if i.importar and not i.ja_importado)
        self.lbl_contagem.configure(
            text=f"{marcados} de {len(self.itens)} serão importados")

    def _selecionado(self) -> int | None:
        item = self.tabela.selecionado()
        if item is None:
            messagebox.showinfo("Importar", "Escolha antes uma linha da lista.", parent=self)
            return None
        return int(item)

    def alternar(self) -> None:
        indice = self._selecionado()
        if indice is None:
            return
        item = self.itens[indice]
        if item.ja_importado:
            messagebox.showinfo("Importar", "Este lançamento já existe no sistema.", parent=self)
            return
        item.importar = not item.importar
        self._render()

    def mudar_categoria(self) -> None:
        indice = self._selecionado()
        if indice is None:
            return
        DialogoCategoria(self, self.itens[indice], self._render)

    def importar(self) -> None:
        if not self.itens:
            messagebox.showinfo("Importar", "Escolha um arquivo primeiro.", parent=self)
            return
        try:
            conta_id = self.sel_conta.get_conta_id()
            if conta_id is None:
                raise services.RegraNegocioError(
                    "Diga de qual conta é este extrato (conta corrente, cartão...).")
            resultado = importacao.importar(self.itens, conta_id,
                                            self.sel_centro.get_centro_id())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível importar", str(erro), parent=self)
            return
        self.ao_importar()
        messagebox.showinfo(
            "Pronto",
            f"{resultado['criados']} lançamento(s) importados."
            + (f"\n{resultado['ignorados']} ficaram de fora (já existiam ou sem categoria)."
               if resultado["ignorados"] else ""), parent=self)
        self.destroy()


class DialogoCategoria(tk.Toplevel):
    """Escolhe a categoria de um item do extrato."""

    def __init__(self, master, item: importacao.ItemExtrato, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.item = item
        self.ao_salvar = ao_salvar
        self.title("Categoria do lançamento")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text=item.descricao[:60], style="Secao.TLabel").pack(anchor="w")
        ttk.Label(corpo, text=f"{services.para_br(item.data)}   ·   "
                              f"{'entrada' if item.valor > 0 else 'saída'} de"
                              f" {services.moeda(abs(item.valor))}",
                  style="Dica.TLabel").pack(anchor="w", pady=(2, 14))

        ttk.Label(corpo, text="Vai entrar como", style="Campo.TLabel").pack(anchor="w")
        tipos = ("RECEITA",) if item.valor > 0 else ("DESPESA",)
        self.sel_conta = SeletorConta(corpo, tipos=tipos, width=46)
        self.sel_conta.set_conta_id(item.categoria_id)
        self.sel_conta.pack(anchor="w", pady=(4, 12))

        self.var_lembrar = tk.BooleanVar(value=True)
        ttk.Checkbutton(corpo, variable=self.var_lembrar,
                        text="Lembrar desta escolha para lançamentos parecidos").pack(anchor="w")

        botoes = ttk.Frame(corpo)
        botoes.pack(fill="x", pady=(16, 0))
        ttk.Button(botoes, text="Confirmar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 540, 300)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            conta_id = self.sel_conta.get_conta_id()
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Categoria", str(erro), parent=self)
            return
        if conta_id is None:
            messagebox.showwarning("Categoria", "Escolha uma categoria.", parent=self)
            return
        self.item.categoria_id = conta_id
        conta = services.obter_conta(conta_id)
        self.item.categoria_nome = conta["nome"]
        self.item.origem_sugestao = "você escolheu"
        self.item.importar = True
        if self.var_lembrar.get():
            importacao.aprender_categoria(self.item.descricao, conta_id)
        self.ao_salvar()
        self.destroy()

