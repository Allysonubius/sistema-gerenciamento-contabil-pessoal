"""Planejamento: quanto posso gastar em cada coisa e objetivos de poupança."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from app import services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (Cabecalho, CampoData, CampoValor, SeletorConta,
                            Tabela, centralizar)


class Orcamento(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.competencia = services.mes_atual()

        self.cabecalho = Cabecalho(
            self, "Orçamento",
            "Defina quanto pretende gastar em cada categoria e acompanhe o quanto já foi.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Definir teto", self.definir, "Primario.TButton")
        self.cabecalho.botao("Sugerir pela média", self.sugerir_todos)
        self.cabecalho.botao("Meus objetivos", self.abrir_metas)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(2, weight=1)

        # --- mês e resumo -------------------------------------------------
        topo = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        topo.configure(relief="solid", borderwidth=1)
        topo.grid(row=0, column=0, sticky="ew")

        navegacao = ttk.Frame(topo, style="Superficie.TFrame")
        navegacao.pack(side="left")
        ttk.Button(navegacao, text="◀", width=3, takefocus=False,
                   command=lambda: self.mudar_mes(-1)).pack(side="left")
        self.lbl_mes = ttk.Label(navegacao, style="SecaoSuperficie.TLabel", width=20,
                                 anchor="center")
        self.lbl_mes.pack(side="left", padx=8)
        ttk.Button(navegacao, text="▶", width=3, takefocus=False,
                   command=lambda: self.mudar_mes(1)).pack(side="left")
        ttk.Button(navegacao, text="Mês atual", takefocus=False,
                   command=self.mes_atual).pack(side="left", padx=12)

        self.lbl_resumo = ttk.Label(topo, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_resumo.pack(side="right")

        # --- barra geral --------------------------------------------------
        barra = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        barra.configure(relief="solid", borderwidth=1)
        barra.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.canvas_barra = tk.Canvas(barra, height=34, bg=CORES["superficie"],
                                      highlightthickness=0)
        self.canvas_barra.pack(fill="x")
        self.canvas_barra.bind("<Configure>", lambda _e: self._desenhar_barra())
        self.lbl_aviso = ttk.Label(barra, style="DicaSuperficie.TLabel", justify="left")
        self.lbl_aviso.pack(anchor="w", pady=(8, 0))
        self._dados_barra = (0.0, 0.0)

        self.tabela = Tabela(corpo, [
            ("nome", "Categoria", 230, "w"),
            ("teto", "Posso gastar", 130, "e"),
            ("gasto", "Já gastei", 130, "e"),
            ("barra", "Consumo", 150, "w"),
            ("restante", "Ainda posso", 130, "e"),
            ("dia", "Por dia até o fim", 130, "e"),
            ("projecao", "Ritmo do mês", 130, "e"),
        ], on_duplo_clique=lambda _i: self.definir(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhuma categoria com teto ou gasto neste mês. Clique em 'Sugerir pela média'"
            " para começar.")
        self.tabela.grid(row=2, column=0, sticky="nsew", pady=(12, 0))

        ttk.Label(corpo, text="Clique duas vezes em uma categoria para mudar o teto. O teto vale"
                              " para todos os meses, salvo se você ajustar só este.",
                  style="Dica.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def mudar_mes(self, passos: int) -> None:
        base = date.fromisoformat(f"{self.competencia}-01")
        self.competencia = services.somar_meses(base, passos).strftime("%Y-%m")
        self.recarregar()

    def mes_atual(self) -> None:
        self.competencia = services.mes_atual()
        self.recarregar()

    def recarregar(self) -> None:
        self.lbl_mes.configure(text=services.mes_nome(self.competencia).capitalize())
        resumo = services.resumo_orcamento(self.competencia)

        self.tabela.limpar()
        for linha in resumo["categorias"]:
            if linha["teto"] > 0:
                consumo = self._barrinha(linha["percentual"])
                teto = services.moeda(linha["teto"]) + (" *" if linha["ajuste_do_mes"] else "")
                restante = services.moeda(linha["restante"])
                por_dia = (services.moeda(linha["por_dia_restante"])
                           if linha["por_dia_restante"] else "—")
            else:
                consumo, teto, restante, por_dia = "sem teto", "—", "—", "—"

            tags: tuple[str, ...] = ()
            if linha["estourou"]:
                tags = ("negativo",)
            elif linha["risco"]:
                tags = ("destaque",)

            self.tabela.inserir(
                (linha["nome"], teto, services.moeda(linha["gasto"]), consumo, restante,
                 por_dia, services.moeda(linha["projecao"]) if linha["projecao"] else "—"),
                iid=linha["conta_id"], tags=tags)
        self.tabela.finalizar()

        sobra = resumo["restante"]
        self.lbl_resumo.configure(
            text=f"Planejado: {services.moeda(resumo['previsto'])}   ·   "
                 f"Gasto: {services.moeda(resumo['gasto'])}   ·   "
                 f"{'Ainda posso gastar' if sobra >= 0 else 'Passei do planejado em'}:"
                 f" {services.moeda(abs(sobra))}",
            foreground=CORES["sucesso"] if sobra >= 0 else CORES["perigo"])

        avisos = []
        if resumo["estouradas"]:
            avisos.append("Estourou o teto em: "
                          + ", ".join(l["nome"] for l in resumo["estouradas"][:4]))
        if resumo["em_risco"]:
            avisos.append("No ritmo atual vai estourar: "
                          + ", ".join(l["nome"] for l in resumo["em_risco"][:4]))
        if resumo["sem_teto"] > 0.005:
            avisos.append(f"{services.moeda(resumo['sem_teto'])} gastos em categorias sem teto.")
        self.lbl_aviso.configure(
            text="\n".join(avisos) or "Tudo dentro do planejado até aqui.",
            foreground=CORES["perigo"] if resumo["estouradas"] else CORES["texto_suave"])

        self._dados_barra = (resumo["previsto"], resumo["gasto"])
        self._desenhar_barra()

    @staticmethod
    def _barrinha(percentual: float) -> str:
        cheios = min(int(round(percentual / 10)), 10)
        return "█" * cheios + "░" * (10 - cheios) + f" {percentual:.0f}%"

    def _desenhar_barra(self) -> None:
        canvas = self.canvas_barra
        canvas.delete("all")
        largura = canvas.winfo_width()
        if largura < 50:
            return
        previsto, gasto = self._dados_barra
        canvas.create_rectangle(0, 8, largura, 30, fill=CORES["superficie_suave"], outline="")
        if previsto <= 0:
            canvas.create_text(largura / 2, 19, text="Nenhum teto definido ainda",
                               fill=CORES["texto_suave"], font=(FONTE, 9))
            return
        fracao = min(gasto / previsto, 1.0)
        cor = (CORES["sucesso"] if fracao < 0.8
               else CORES["alerta"] if fracao <= 1.0 else CORES["perigo"])
        if gasto > previsto:
            cor = CORES["perigo"]
        canvas.create_rectangle(0, 8, largura * fracao, 30, fill=cor, outline="")
        canvas.create_text(8, 19, anchor="w", font=(FONTE, 9, "bold"), fill="#ffffff"
                           if fracao > 0.15 else CORES["texto"],
                           text=f"{gasto / previsto * 100:.0f}% do orçamento do mês")

    # ------------------------------------------------------------------ #
    def definir(self) -> None:
        item = self.tabela.selecionado()
        DialogoTeto(self, int(item) if item else None, self.competencia, self.recarregar)

    def sugerir_todos(self) -> None:
        if not messagebox.askyesno(
                "Sugerir tetos",
                "O sistema vai propor um teto para cada categoria com base na média dos"
                " últimos 3 meses.\n\nCategorias que já têm teto não são alteradas."
                "\n\nContinuar?", parent=self):
            return
        criados = 0
        for conta in services.listar_contas(apenas_ativas=True, apenas_analiticas=True):
            if conta["tipo"] != "DESPESA":
                continue
            teto, _ = services.teto_da_categoria(conta["id"], self.competencia)
            if teto > 0:
                continue
            media = services.sugerir_orcamento(conta["id"])
            if media > 0.005:
                services.definir_orcamento(conta["id"], media)
                criados += 1
        self.recarregar()
        messagebox.showinfo("Pronto", f"{criados} categoria(s) receberam um teto sugerido."
                                      "\nAjuste os valores como preferir.", parent=self)

    def abrir_metas(self) -> None:
        JanelaMetas(self, self.recarregar)


# --------------------------------------------------------------------------- #
class DialogoTeto(tk.Toplevel):
    def __init__(self, master, conta_id: int | None, competencia: str, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.competencia = competencia
        self.ao_salvar = ao_salvar
        self.title("Teto de gasto")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Quanto pretendo gastar?", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Um limite mensal para a categoria. O sistema avisa quando você"
                            " estiver perto ou passar dele.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Categoria", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("DESPESA",), width=48)
        self.sel_conta.set_conta_id(conta_id)
        self.sel_conta.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 6))
        self.sel_conta.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_media())

        self.lbl_media = ttk.Label(corpo, style="Dica.TLabel")
        self.lbl_media.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Label(corpo, text="Posso gastar por mês (R$)", style="Campo.TLabel").grid(
            row=3, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=4, column=0, sticky="w", pady=(4, 14))
        ttk.Button(corpo, text="Usar a média", command=self._usar_media).grid(
            row=4, column=1, sticky="w", padx=8, pady=(4, 14))

        self.var_so_este = tk.BooleanVar(value=False)
        ttk.Checkbutton(corpo, variable=self.var_so_este,
                        text=f"Valer só para {services.mes_nome(competencia)}"
                             " (nos outros meses continua o teto normal)").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(corpo, text="Deixe o valor em 0 para remover o teto da categoria.",
                  style="Dica.TLabel").grid(row=6, column=0, columnspan=2, sticky="w",
                                            pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=7, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        if conta_id:
            teto, ajuste = services.teto_da_categoria(conta_id, competencia)
            if teto:
                self.cp_valor.set_valor(teto)
            self.var_so_este.set(ajuste)
            self._mostrar_media()

        centralizar(self, 600, 460)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _media(self) -> float:
        conta_id = self.sel_conta.get_conta_id()
        return services.sugerir_orcamento(conta_id) if conta_id else 0.0

    def _mostrar_media(self) -> None:
        media = self._media()
        self.lbl_media.configure(
            text=f"Você gastou em média {services.moeda(media)} por mês nos últimos 3 meses."
                 if media else "Ainda não há histórico suficiente para essa categoria.")

    def _usar_media(self) -> None:
        media = self._media()
        if media:
            self.cp_valor.set_valor(media)

    def salvar(self) -> None:
        try:
            conta_id = self.sel_conta.get_conta_id()
            if conta_id is None:
                raise services.RegraNegocioError("Escolha a categoria.")
            valor = self.cp_valor.get_valor() if self.cp_valor.var.get().strip() else 0.0
            competencia = self.competencia if self.var_so_este.get() else ""
            services.definir_orcamento(conta_id, valor, competencia)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


# --------------------------------------------------------------------------- #
class JanelaMetas(tk.Toplevel):
    """Objetivos de poupança com acompanhamento do progresso."""

    def __init__(self, master, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_mudar = ao_mudar
        self.title("Meus objetivos")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Meus objetivos", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Escolha a conta onde o dinheiro é guardado: o progresso é medido"
                            " pelo que entrou nela depois que o objetivo foi criado.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 12))
        ttk.Button(acoes, text="Novo objetivo", style="Primario.TButton",
                   command=self.novo).pack(side="left")
        ttk.Button(acoes, text="Alterar", command=self.editar).pack(side="left", padx=8)
        ttk.Button(acoes, text="Apagar", style="Perigo.TButton",
                   command=self.excluir).pack(side="left")

        self.tabela = Tabela(corpo, [
            ("nome", "Objetivo", 220, "w"),
            ("alvo", "Quanto quero", 130, "e"),
            ("guardado", "Já guardei", 130, "e"),
            ("barra", "Progresso", 160, "w"),
            ("falta", "Falta", 130, "e"),
            ("prazo", "Até quando", 110, "center"),
            ("mes", "Por mês", 120, "e"),
        ], on_duplo_clique=lambda _i: self.editar(), altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhum objetivo ainda. Ex.: reserva de emergência, viagem, troca de carro.")
        self.tabela.pack(fill="both", expand=True)

        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(12, 0))
        self.recarregar()
        centralizar(self, 1120, 520)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        self.tabela.limpar()
        for meta in services.listar_metas():
            cheios = min(int(round(meta["percentual"] / 10)), 10)
            barra = "█" * cheios + "░" * (10 - cheios) + f" {meta['percentual']:.0f}%"
            if meta["concluida"]:
                prazo, por_mes, tags = "concluído", "—", ("positivo",)
            elif meta["atrasada"]:
                prazo = services.para_br(meta["data_alvo"])
                por_mes = services.moeda(meta["por_mes"])
                tags = ("negativo",)
            else:
                prazo = services.para_br(meta["data_alvo"]) if meta["data_alvo"] else "sem prazo"
                por_mes = services.moeda(meta["por_mes"]) if meta["meses_restantes"] else "—"
                tags = ()
            self.tabela.inserir(
                (meta["nome"], services.moeda(meta["valor_alvo"]),
                 services.moeda(meta["guardado"]), barra, services.moeda(meta["falta"]),
                 prazo, por_mes),
                iid=meta["id"], tags=tags)
        self.tabela.finalizar()

    def _selecionada(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Objetivos", "Escolha antes um objetivo da lista.", parent=self)
            return None
        return int(item)

    def novo(self) -> None:
        DialogoMeta(self, None, self._apos)

    def editar(self) -> None:
        meta_id = self._selecionada()
        if meta_id:
            DialogoMeta(self, meta_id, self._apos)

    def excluir(self) -> None:
        meta_id = self._selecionada()
        if not meta_id:
            return
        if not messagebox.askyesno("Apagar objetivo",
                                   "O objetivo será apagado. O dinheiro guardado continua na"
                                   " conta.\n\nConfirma?", parent=self):
            return
        services.excluir_meta(meta_id)
        self._apos()

    def _apos(self) -> None:
        self.recarregar()
        self.ao_mudar()


class DialogoMeta(tk.Toplevel):
    def __init__(self, master, meta_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.meta_id = meta_id
        self.ao_salvar = ao_salvar
        self.title("Objetivo")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="O que você quer conquistar?", style="Secao.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Label(corpo, text="Nome do objetivo", style="Campo.TLabel").grid(
            row=1, column=0, sticky="w")
        self.var_nome = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_nome, width=44).grid(
            row=2, column=0, columnspan=2, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Quanto quero juntar (R$)", style="Campo.TLabel").grid(
            row=3, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=4, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Até quando (opcional)", style="Campo.TLabel").grid(
            row=3, column=1, sticky="w")
        self.dt_alvo = CampoData(corpo)
        self.dt_alvo.grid(row=4, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Onde o dinheiro fica guardado", style="Campo.TLabel").grid(
            row=5, column=0, columnspan=2, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("ATIVO",), width=44)
        self.sel_conta.grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="O progresso conta o que entrar nessa conta a partir de agora.",
                  style="Dica.TLabel", wraplength=420, justify="left").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=8, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        if meta_id:
            from app import db
            meta = db.query_one("SELECT * FROM meta WHERE id = ?", (meta_id,))
            self.var_nome.set(meta["nome"])
            self.cp_valor.set_valor(float(meta["valor_alvo"]))
            if meta["data_alvo"]:
                self.dt_alvo.set_iso(meta["data_alvo"])
            self.sel_conta.set_conta_id(meta["conta_id"])

        centralizar(self, 560, 440)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            data_alvo = self.dt_alvo.get_iso() if self.dt_alvo.var.get().strip() else None
            services.salvar_meta(self.meta_id, self.var_nome.get(), self.cp_valor.get_valor(),
                                 data_alvo, self.sel_conta.get_conta_id())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()



