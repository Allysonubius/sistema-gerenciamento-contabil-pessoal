"""Entradas e saídas: registro do dia a dia em linguagem simples."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import db, services
from app.services import Partida
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (AutoConsulta, BarraFiltro, Cabecalho, CampoData, CampoValor,
                            SeletorCentro, SeletorConta, Tabela, centralizar)

CONTAS_DINHEIRO = ("ATIVO", "PASSIVO")

# Primeira opção do filtro de conta/categoria: desfaz o filtro.
TODAS_AS_CONTAS = "(todas as contas e categorias)"


class Lancamentos(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Entradas e Saídas",
            "Tudo que você recebeu e tudo que você gastou. Clique duas vezes em uma linha"
            " para conferir ou corrigir.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Registrar", self.novo, "Primario.TButton")
        self.cabecalho.botao("Importar extrato", self.importar)
        self.cabecalho.botao("Corrigir", self.editar)
        self.cabecalho.botao("Apagar", self.excluir, "Perigo.TButton")
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)

        filtros = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        filtros.configure(relief="solid", borderwidth=1)
        filtros.pack(fill="x")

        linha1 = ttk.Frame(filtros, style="Superficie.TFrame")
        linha1.pack(fill="x")
        self.filtro = BarraFiltro(linha1, self.recarregar, fundo="Superficie.TFrame")
        self.filtro.pack(side="left")

        linha2 = ttk.Frame(filtros, style="Superficie.TFrame")
        linha2.pack(fill="x", pady=(12, 0))
        ttk.Label(linha2, text="Tipo:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_tipo = ttk.Combobox(linha2, state="readonly", width=15,
                                    values=["Tudo", "Só entradas", "Só saídas",
                                            "Só transferências"])
        self.cb_tipo.set("Tudo")
        self.cb_tipo.pack(side="left", padx=(8, 16))

        ttk.Label(linha2, text="Procurar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.var_texto = tk.StringVar()
        entrada = ttk.Entry(linha2, textvariable=self.var_texto, width=28)
        entrada.pack(side="left", padx=(8, 16))

        ttk.Label(linha2, text="Conta ou categoria:",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.sel_conta = SeletorConta(linha2, permitir_vazio=True, width=34,
                                      rotulo_vazio=TODAS_AS_CONTAS)
        self.sel_conta.pack(side="left", padx=8)
        ttk.Button(linha2, text="Limpar", command=self.limpar_filtros).pack(side="left")

        # --- conferência (bate com o extrato do banco) --------------------
        # Some da tela enquanto a conferência automática estiver ligada: não há
        # nada para marcar. Volta inteira se o usuário desligar a opção.
        self.area_conferencia = ttk.Frame(filtros, style="Superficie.TFrame")
        self.var_pendentes = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.area_conferencia, text="Só o que ainda não conferi",
                        variable=self.var_pendentes, command=self.recarregar,
                        style="Superficie.TCheckbutton").pack(side="left")
        self.lbl_conferencia = ttk.Label(self.area_conferencia, style="DicaSuperficie.TLabel")
        self.lbl_conferencia.pack(side="left", padx=16)
        ttk.Button(self.area_conferencia, text="Conferir tudo do período",
                   command=self.conferir_periodo).pack(side="right")
        ttk.Button(self.area_conferencia, text="Marcar / desmarcar conferido",
                   command=self.alternar_conferido).pack(side="right", padx=8)

        # Toda mudança de filtro consulta sozinha, sem botão de aplicar.
        self.auto = AutoConsulta(self, self.recarregar)
        self.auto.ligar_combos(self.cb_tipo, self.sel_conta)
        self.auto.ligar_textos(self.var_texto)
        self.sel_conta.bind("<KeyRelease>", self.auto.agendar, add="+")

        self.tabela = Tabela(corpo, [
            ("data", "Data", 90, "center"),
            ("tipo", "O que foi", 110, "center"),
            ("descricao", "Descrição", 250, "w"),
            ("categoria", "Categoria", 175, "w"),
            ("conta", "Conta usada", 165, "w"),
            ("valor", "Valor", 115, "e"),
            ("conferido", "Conferido", 90, "center"),
        ], on_duplo_clique=lambda _i: self.editar(), largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhum registro neste período. Clique em 'Registrar' para começar.")
        self.tabela.pack(fill="both", expand=True, pady=(14, 0))

        resumo = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        resumo.configure(relief="solid", borderwidth=1)
        resumo.pack(fill="x", pady=(12, 0))
        self.lbl_entrou = ttk.Label(resumo, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_entrou.pack(side="left", padx=(0, 28))
        self.lbl_saiu = ttk.Label(resumo, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_saiu.pack(side="left", padx=(0, 28))
        self.lbl_saldo = ttk.Label(resumo, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_saldo.pack(side="left")
        self.lbl_qtd = ttk.Label(resumo, style="DicaSuperficie.TLabel")
        self.lbl_qtd.pack(side="right")

    # ------------------------------------------------------------------ #
    def limpar_filtros(self) -> None:
        self.auto.pausar()
        self.var_texto.set("")
        self.sel_conta.set(TODAS_AS_CONTAS)
        self.cb_tipo.set("Tudo")
        self.auto.retomar()

    def ao_exibir(self) -> None:
        """Ao entrar na tela: atualiza a lista de contas e consulta."""
        self.sel_conta.recarregar()
        services.conferir_automatico()
        self.recarregar()

    def recarregar(self) -> None:
        # A lista do seletor não é repopulada aqui: isso desfaria o que o
        # usuário está digitando para procurar uma categoria.
        try:
            desde, ate = self.filtro.periodo()
        except services.RegraNegocioError:
            return  # data incompleta enquanto o usuário digita
        try:
            conta_id = self.sel_conta.get_conta_id()
        except services.RegraNegocioError:
            conta_id = None

        filtro_tipo = {"Só entradas": "ENTRADA", "Só saídas": "SAIDA",
                       "Só transferências": "TRANSFERENCIA"}.get(self.cb_tipo.get())

        self.tabela.limpar()
        entrou = saiu = 0.0
        movimentos = services.listar_movimentos(
            desde, ate, self.var_texto.get().strip(), conta_id, filtro_tipo,
            apenas_pendentes=self.var_pendentes.get())
        for mov in movimentos:
            if mov["tipo"] == "ENTRADA":
                entrou += mov["valor"]
                valor, tag = f"+ {services.moeda(mov['valor'])}", "positivo"
            elif mov["tipo"] == "SAIDA":
                saiu += mov["valor"]
                valor, tag = f"- {services.moeda(mov['valor'])}", "negativo"
            else:
                valor, tag = services.moeda(mov["valor"]), ""
            self.tabela.inserir(
                (services.para_br(mov["data"]), mov["rotulo"], mov["descricao"],
                 mov["categoria"], mov["conta"], valor,
                 "sim" if mov["conferido"] else "—"),
                iid=mov["id"], tags=(tag,) if tag else ())
        self.tabela.finalizar()

        self._ajustar_conferencia()
        if not services.conferencia_automatica():
            conferencia = services.resumo_conferencia(desde, ate, conta_id)
            if conferencia["pendentes"]:
                self.lbl_conferencia.configure(
                    text=f"{conferencia['pendentes']} de {conferencia['total']} ainda sem"
                         f" conferir ({services.moeda(conferencia['valor_pendente'])})",
                    foreground=CORES["alerta"])
            else:
                self.lbl_conferencia.configure(
                    text="tudo conferido neste período" if conferencia["total"] else "",
                    foreground=CORES["sucesso"])

        saldo = entrou - saiu
        self.lbl_entrou.configure(text=f"Entrou: {services.moeda(entrou)}",
                                  foreground=CORES["sucesso"])
        self.lbl_saiu.configure(text=f"Saiu: {services.moeda(saiu)}", foreground=CORES["perigo"])
        self.lbl_saldo.configure(
            text=f"Diferença: {services.moeda(saldo)}",
            foreground=CORES["sucesso"] if saldo >= 0 else CORES["perigo"])
        self.lbl_qtd.configure(text=f"{len(movimentos)} registro(s) no período")

    def _ajustar_conferencia(self) -> None:
        """Esconde os controles de conferência quando ela é automática."""
        automatica = services.conferencia_automatica()
        colunas = [c[0] for c in self.tabela.colunas]
        if automatica:
            self.area_conferencia.pack_forget()
            self.var_pendentes.set(False)
            colunas.remove("conferido")
        else:
            self.area_conferencia.pack(fill="x", pady=(12, 0))
        self.tabela.tree.configure(displaycolumns=colunas)

    # ------------------------------------------------------------------ #
    def alternar_conferido(self) -> None:
        """Marca ou desmarca a linha escolhida como já vista no extrato."""
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Conferir", "Escolha antes uma linha da lista.", parent=self)
            return
        atual = self.tabela.tree.set(item, "conferido") == "sim"
        try:
            services.marcar_conferido(int(item), not atual)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.recarregar()

    def conferir_periodo(self) -> None:
        """Marca de uma vez tudo o que está sendo mostrado no período."""
        try:
            desde, ate = self.filtro.periodo()
            conta_id = self.sel_conta.get_conta_id()
        except services.RegraNegocioError:
            return
        pendentes = services.resumo_conferencia(desde, ate, conta_id)["pendentes"]
        if not pendentes:
            messagebox.showinfo("Conferir", "Não há nada pendente neste período.", parent=self)
            return
        if not messagebox.askyesno(
                "Conferir tudo",
                f"Marcar {pendentes} movimento(s) do período como conferidos?\n\n"
                "Use isto quando já tiver comparado o período inteiro com o extrato do banco.",
                parent=self):
            return
        total = services.conferir_periodo(desde, ate, conta_id)
        self.recarregar()
        self.app.notificar(f"{total} movimento(s) marcados como conferidos.")

    def novo(self) -> None:
        DialogoMovimento(self, None, self._apos_salvar)

    def importar(self) -> None:
        from app.ui.importar import JanelaImportar
        JanelaImportar(self, self._apos_salvar)

    def editar(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Corrigir", "Escolha antes uma linha da lista.", parent=self)
            return
        DialogoMovimento(self, int(item), self._apos_salvar)

    def excluir(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Apagar", "Escolha antes uma linha da lista.", parent=self)
            return
        valores = self.tabela.tree.item(item, "values")
        if not messagebox.askyesno(
                "Apagar registro",
                f"Apagar este registro?\n\n{valores[0]} — {valores[2]}\n{valores[5]}\n\n"
                "Esta ação não pode ser desfeita.", parent=self):
            return
        try:
            services.excluir_lancamento(int(item))
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não é possível apagar aqui", str(erro), parent=self)
            return
        self._apos_salvar()
        self.app.notificar("Registro apagado.")

    def _apos_salvar(self) -> None:
        self.recarregar()
        self.app.atualizar_dependentes()


# --------------------------------------------------------------------------- #
class DialogoMovimento(tk.Toplevel):
    """Registro guiado: gastei, recebi, transferi, saldo inicial ou modo contábil."""

    ABAS = ["Gastei dinheiro", "Recebi dinheiro", "Transferi entre minhas contas",
            "Saldo inicial", "Modo contábil"]

    def __init__(self, master, lancamento_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.lancamento_id = lancamento_id
        self.ao_salvar = ao_salvar
        self.partidas: list[dict] = []
        self.title("Registrar entrada ou saída" if lancamento_id is None
                   else f"Corrigir registro nº {lancamento_id}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="O que aconteceu?", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Escolha a situação abaixo e preencha os campos. "
                            "O sistema cuida do resto.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=(20, 16))
        corpo.pack(fill="both", expand=True)

        # Os botões e os campos comuns são empacotados primeiro, a partir da base,
        # para que nunca fiquem fora da tela em telas pequenas.
        botoes = ttk.Frame(corpo)
        botoes.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Fechar", command=self.destroy).pack(side="right", padx=8)

        self.lbl_aviso = ttk.Label(corpo, style="Dica.TLabel", wraplength=820, justify="left")
        self.lbl_aviso.pack(side="bottom", anchor="w", pady=(10, 0))

        comuns = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        comuns.configure(relief="solid", borderwidth=1)
        comuns.pack(side="bottom", fill="x", pady=(14, 0))

        # Cada conta escolhida mostra, ao lado, quanto tem hoje e como fica
        # depois deste registro — é o que diz se o dinheiro está onde se pensa.
        self._saldos: list[tuple] = []

        self.notebook = ttk.Notebook(corpo)
        self.notebook.pack(side="top", fill="both", expand=True)
        self.notebook.add(self._aba_gasto(), text="  Gastei dinheiro  ")
        self.notebook.add(self._aba_receita(), text="  Recebi dinheiro  ")
        self.notebook.add(self._aba_transferencia(), text="  Transferi entre contas  ")
        self.notebook.add(self._aba_saldo(), text="  Saldo inicial  ")
        self.notebook.add(self._aba_avancada(), text="  Modo contábil  ")

        ttk.Label(comuns, text="Quando?", style="CampoSuperficie.TLabel").grid(
            row=0, column=0, sticky="w")
        self.dt_data = CampoData(comuns, services.hoje_iso())
        self.dt_data.grid(row=1, column=0, sticky="w", padx=(0, 20))

        ttk.Label(comuns, text="Quanto? (R$)", style="CampoSuperficie.TLabel").grid(
            row=0, column=1, sticky="w")
        quadro_valor = ttk.Frame(comuns, style="Superficie.TFrame")
        quadro_valor.grid(row=1, column=1, sticky="w", padx=(0, 20))
        self.cp_valor = CampoValor(quadro_valor, width=16)
        self.cp_valor.pack(side="left")
        ttk.Button(quadro_valor, text="Limpar", width=7,
                   command=self._limpar_valor).pack(side="left", padx=(6, 0))

        ttk.Label(comuns, text="Descrição (o que foi?)",
                  style="CampoSuperficie.TLabel").grid(row=0, column=2, sticky="w")
        self.var_hist = tk.StringVar()
        ttk.Entry(comuns, textvariable=self.var_hist, width=42).grid(
            row=1, column=2, sticky="we", padx=(0, 20))
        comuns.columnconfigure(2, weight=1)

        ttk.Label(comuns, text="Grupo (opcional)",
                  style="CampoSuperficie.TLabel").grid(row=0, column=3, sticky="w")
        self.sel_centro = SeletorCentro(comuns, width=18)
        self.sel_centro.grid(row=1, column=3, sticky="w")

        self.cp_valor.ao_mudar(self._atualizar_saldos)
        self.notebook.bind("<<NotebookTabChanged>>",
                           lambda _e: self._atualizar_saldos(), add="+")
        self.dt_data.bind("<FocusOut>", lambda _e: self._atualizar_saldos(), add="+")

        self._carregar()
        self._atualizar_saldos()
        centralizar(self, 920, 680)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Control-Return>", lambda _e: self.salvar())

    # ------------------------------------------------------------------ #
    def _quadro(self) -> ttk.Frame:
        return ttk.Frame(self.notebook, style="Superficie.TFrame", padding=20)

    def _campo(self, pai, linha: int, titulo: str, dica: str, widget) -> None:
        ttk.Label(pai, text=titulo, style="CampoSuperficie.TLabel").grid(
            row=linha, column=0, sticky="w", pady=(0, 2))
        ttk.Label(pai, text=dica, style="DicaSuperficie.TLabel").grid(
            row=linha + 1, column=0, sticky="w")
        widget.grid(row=linha + 2, column=0, sticky="w", pady=(4, 2))

    def _com_saldo(self, pai, linha: int, seletor, sinal: int) -> None:
        """Mostra o saldo da conta escolhida logo abaixo do seletor.

        ``sinal`` diz o que este registro faz com ela: -1 tira dinheiro,
        +1 põe, 0 só mostra o saldo de hoje. Em conta de onde o dinheiro sai, o
        saldo também é sugerido no valor — é o teto do que dá para gastar.
        """
        rotulo = ttk.Label(pai, style="SecaoSuperficie.TLabel")
        rotulo.grid(row=linha + 3, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self._saldos.append((seletor, rotulo, sinal))
        seletor.bind("<<ComboboxSelected>>",
                     lambda _e, s=seletor, i=sinal: self._conta_escolhida(s, i), add="+")
        seletor.bind("<KeyRelease>", lambda _e: self._atualizar_saldos(), add="+")

    def _conta_escolhida(self, seletor, sinal: int) -> None:
        """Trocou de conta: o campo recomeça com o saldo da conta escolhida.

        Manter o valor da conta anterior era pior do que apagar — ele não diz
        nada sobre a conta nova e passava despercebido.
        """
        if sinal >= 0:
            self._atualizar_saldos()
            return
        try:
            conta_id = seletor.get_conta_id()
        except Exception:
            conta_id = None
        self.cp_valor.limpar()
        if conta_id is not None:
            saldo = services.saldo_conta(conta_id, ate=self._data_segura())
            if saldo > 0.005:
                self.cp_valor.set_valor(saldo)
        self._atualizar_saldos()

    def _limpar_valor(self) -> None:
        """Apaga o valor sugerido para digitar outro."""
        self.cp_valor.limpar()
        self.cp_valor.focus_set()
        self._atualizar_saldos()

    def _data_segura(self) -> str:
        try:
            return self.dt_data.get_iso()
        except Exception:
            return services.hoje_iso()

    def _atualizar_saldos(self) -> None:
        """Redesenha os saldos: quanto a conta tem hoje e como fica depois."""
        # Isto só desenha um rótulo: campo pela metade ou mal digitado não pode
        # quebrar a janela no meio do preenchimento.
        try:
            valor = self.cp_valor.get_valor() if self.cp_valor.var.get().strip() else 0.0
        except Exception:
            valor = 0.0
        try:
            data = self.dt_data.get_iso()
        except Exception:
            data = services.hoje_iso()

        for seletor, rotulo, sinal in self._saldos:
            try:
                conta_id = seletor.get_conta_id()
            except Exception:
                conta_id = None
            if conta_id is None:
                rotulo.configure(text="")
                continue
            conta = services.obter_conta(conta_id)
            saldo = services.saldo_conta(conta_id, ate=data)
            divida = conta["tipo"] == "PASSIVO"
            texto = (f"deve {services.moeda(saldo)}" if divida
                     else f"tem {services.moeda(saldo)}")
            cor = CORES["perigo"] if (divida or saldo < 0) else CORES["texto"]
            if sinal and valor > 0.005:
                # No cartão de crédito, gastar aumenta a dívida em vez de baixar o saldo.
                depois = saldo + (valor * (-sinal if divida else sinal))
                texto += f"  →  fica {services.moeda(depois)}"
                if not divida and depois < 0:
                    texto += "  (fica negativa)"
                    cor = CORES["perigo"]
                elif divida:
                    cor = CORES["perigo"]
                else:
                    cor = CORES["sucesso"] if sinal > 0 else CORES["texto"]
            rotulo.configure(text=texto, foreground=cor)

    def _aba_gasto(self) -> ttk.Frame:
        aba = self._quadro()
        self.sel_gasto_cat = SeletorConta(aba, tipos=("DESPESA",), width=54)
        self._campo(aba, 0, "Com o que você gastou?",
                    "Ex.: Supermercado, Combustível, Aluguel.", self.sel_gasto_cat)
        self.sel_gasto_conta = SeletorConta(aba, tipos=CONTAS_DINHEIRO, width=54)
        self._campo(aba, 3, "De onde saiu o dinheiro?",
                    "Conta corrente, carteira, poupança ou cartão de crédito.",
                    self.sel_gasto_conta)
        self._com_saldo(aba, 3, self.sel_gasto_conta, -1)
        return aba

    def _aba_receita(self) -> ttk.Frame:
        aba = self._quadro()
        self.sel_rec_cat = SeletorConta(aba, tipos=("RECEITA",), width=54)
        self._campo(aba, 0, "De onde veio o dinheiro?",
                    "Ex.: Salário, Freelance, Aluguel recebido.", self.sel_rec_cat)
        self.sel_rec_conta = SeletorConta(aba, tipos=("ATIVO",), width=54)
        self._campo(aba, 3, "Onde o dinheiro entrou?",
                    "Conta corrente, poupança, carteira digital — ou 'Dinheiro em mãos',"
                    " quando o valor ficou em espécie com você.", self.sel_rec_conta)
        self._com_saldo(aba, 3, self.sel_rec_conta, +1)
        return aba

    def _aba_transferencia(self) -> ttk.Frame:
        aba = self._quadro()
        self.sel_tr_origem = SeletorConta(aba, tipos=CONTAS_DINHEIRO, width=54)
        self._campo(aba, 0, "De qual conta saiu?", "A conta que ficou com menos dinheiro.",
                    self.sel_tr_origem)
        self._com_saldo(aba, 0, self.sel_tr_origem, -1)
        self.sel_tr_destino = SeletorConta(aba, tipos=CONTAS_DINHEIRO, width=54)
        self._campo(aba, 3, "Para qual conta foi?", "A conta que ficou com mais dinheiro.",
                    self.sel_tr_destino)
        self._com_saldo(aba, 3, self.sel_tr_destino, +1)
        ttk.Label(aba, text="Transferência não é ganho nem gasto: seu total continua o mesmo.",
                  style="DicaSuperficie.TLabel").grid(row=6, column=0, sticky="w")
        return aba

    def _aba_saldo(self) -> ttk.Frame:
        aba = self._quadro()
        self.sel_saldo_conta = SeletorConta(aba, tipos=CONTAS_DINHEIRO, width=54)
        self._campo(aba, 0, "Qual conta você quer acertar?",
                    "Informe quanto já existe nela hoje — use só na primeira vez.",
                    self.sel_saldo_conta)
        self._com_saldo(aba, 0, self.sel_saldo_conta, 0)
        ttk.Label(aba, text="Se for uma conta de dívida (cartão, financiamento), o valor entra"
                            " como saldo devedor.",
                  style="DicaSuperficie.TLabel").grid(row=3, column=0, sticky="w")
        return aba

    def _aba_avancada(self) -> ttk.Frame:
        aba = self._quadro()
        ttk.Label(aba, text="Para quem conhece contabilidade: informe débitos e créditos.",
                  style="DicaSuperficie.TLabel").pack(anchor="w", pady=(0, 10))

        entrada = ttk.Frame(aba, style="Superficie.TFrame")
        entrada.pack(fill="x")
        self.sel_partida = SeletorConta(entrada, width=42)
        self.sel_partida.grid(row=0, column=0, padx=(0, 8))
        self.cb_dc = ttk.Combobox(entrada, state="readonly", width=10,
                                  values=["Débito", "Crédito"])
        self.cb_dc.set("Débito")
        self.cb_dc.grid(row=0, column=1, padx=(0, 8))
        self.cp_partida = CampoValor(entrada, width=14)
        self.cp_partida.grid(row=0, column=2, padx=(0, 8))
        ttk.Button(entrada, text="Adicionar", command=self.adicionar_partida).grid(row=0, column=3)
        ttk.Button(entrada, text="Remover", command=self.remover_partida).grid(
            row=0, column=4, padx=6)
        self.cp_partida.bind("<Return>", lambda _e: self.adicionar_partida())

        self.tab_partidas = Tabela(aba, [
            ("conta", "Conta", 330, "w"),
            ("debito", "Débito", 120, "e"),
            ("credito", "Crédito", 120, "e"),
        ], altura=6)
        self.tab_partidas.pack(fill="both", expand=True, pady=(12, 0))
        self.lbl_saldo_partidas = ttk.Label(aba, style="DicaSuperficie.TLabel")
        self.lbl_saldo_partidas.pack(anchor="e", pady=(8, 0))
        return aba

    # ------------------------------------------------------------------ #
    def adicionar_partida(self) -> None:
        try:
            conta_id = self.sel_partida.get_conta_id()
            if conta_id is None:
                raise services.RegraNegocioError("Escolha a conta.")
            valor = self.cp_partida.get_valor()
            if valor <= 0:
                raise services.RegraNegocioError("O valor deve ser maior que zero.")
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Partida", str(erro), parent=self)
            return
        self.partidas.append({"conta_id": conta_id,
                              "tipo": "D" if self.cb_dc.get() == "Débito" else "C",
                              "valor": valor})
        self.cp_partida.limpar()
        self.sel_partida.set("")
        self._render_partidas()

    def remover_partida(self) -> None:
        item = self.tab_partidas.selecionado()
        if item is None:
            return
        indice = int(item)
        if 0 <= indice < len(self.partidas):
            self.partidas.pop(indice)
            self._render_partidas()

    def _render_partidas(self) -> None:
        self.tab_partidas.limpar()
        debitos = creditos = 0.0
        for indice, partida in enumerate(self.partidas):
            conta = services.obter_conta(partida["conta_id"])
            debito = partida["valor"] if partida["tipo"] == "D" else 0.0
            credito = partida["valor"] if partida["tipo"] == "C" else 0.0
            debitos += debito
            creditos += credito
            self.tab_partidas.inserir(
                (f"{conta['nome']} ({conta['codigo']})",
                 services.moeda(debito) if debito else "",
                 services.moeda(credito) if credito else ""), iid=indice)
        self.tab_partidas.finalizar()
        diferenca = round(debitos - creditos, 2)
        self.lbl_saldo_partidas.configure(
            text=f"Débitos {services.moeda(debitos)}  ×  Créditos {services.moeda(creditos)}"
                 f"   →   diferença {services.moeda(diferenca)}",
            foreground=CORES["sucesso"] if abs(diferenca) < 0.005 else CORES["perigo"])

    # ------------------------------------------------------------------ #
    def _carregar(self) -> None:
        if self.lancamento_id is None:
            self.notebook.select(0)
            self.after(120, self.sel_gasto_cat.focus_set)
            return

        lanc = db.query_one("SELECT * FROM lancamento WHERE id = ?", (self.lancamento_id,))
        if lanc is None:
            return
        if lanc["origem"] != "MANUAL":
            self.lbl_aviso.configure(
                text="Este registro veio do pagamento de uma conta e não pode ser alterado aqui."
                     " Use a tela 'Contas a Pagar e Receber'.",
                foreground=CORES["perigo"])

        self.dt_data.set_iso(lanc["data"])
        self.var_hist.set(lanc["historico"])
        self.cp_valor.set_valor(float(lanc["valor"]))
        self.sel_centro.set_centro_id(lanc["centro_custo_id"])

        partidas = db.query(
            "SELECT p.conta_id, p.tipo, p.valor, c.nome, c.codigo, c.tipo AS tipo_conta"
            " FROM partida p JOIN conta c ON c.id = p.conta_id WHERE p.lancamento_id = ?",
            (self.lancamento_id,))
        self.partidas = [{"conta_id": p["conta_id"], "tipo": p["tipo"], "valor": float(p["valor"])}
                         for p in partidas]
        self._render_partidas()

        if len(partidas) != 2:
            self.notebook.select(4)
            return
        debito = next(p for p in partidas if p["tipo"] == "D")
        credito = next(p for p in partidas if p["tipo"] == "C")
        info = services.classificar_lancamento(partidas)
        if info["tipo"] == "SAIDA":
            self.notebook.select(0)
            self.sel_gasto_cat.set_conta_id(debito["conta_id"])
            self.sel_gasto_conta.set_conta_id(credito["conta_id"])
        elif info["tipo"] == "ENTRADA":
            self.notebook.select(1)
            self.sel_rec_cat.set_conta_id(credito["conta_id"])
            self.sel_rec_conta.set_conta_id(debito["conta_id"])
        elif info["tipo"] == "TRANSFERENCIA":
            self.notebook.select(2)
            self.sel_tr_origem.set_conta_id(credito["conta_id"])
            self.sel_tr_destino.set_conta_id(debito["conta_id"])
        elif info["tipo"] == "AJUSTE":
            self.notebook.select(3)
            conta = debito if debito["tipo_conta"] != "PATRIMONIO" else credito
            self.sel_saldo_conta.set_conta_id(conta["conta_id"])
        else:
            self.notebook.select(4)

    # ------------------------------------------------------------------ #
    def _conta_patrimonio(self) -> int:
        conta = db.query_one("SELECT id FROM conta WHERE codigo = '3.1'")
        if conta is None:
            raise services.RegraNegocioError(
                "A conta de patrimônio inicial (3.1) não existe no plano de contas.")
        return conta["id"]

    def _montar_partidas(self) -> list[Partida]:
        aba = self.notebook.index(self.notebook.select())
        if aba == 4:
            return [Partida(p["conta_id"], p["tipo"], p["valor"]) for p in self.partidas]

        valor = self.cp_valor.get_valor()
        if aba == 0:
            categoria = self._exigir(self.sel_gasto_cat, "Diga com o que você gastou.")
            conta = self._exigir(self.sel_gasto_conta, "Diga de onde saiu o dinheiro.")
            return [Partida(categoria, "D", valor), Partida(conta, "C", valor)]
        if aba == 1:
            categoria = self._exigir(self.sel_rec_cat, "Diga de onde veio o dinheiro.")
            conta = self._exigir(self.sel_rec_conta, "Diga onde o dinheiro entrou.")
            return [Partida(conta, "D", valor), Partida(categoria, "C", valor)]
        if aba == 2:
            origem = self._exigir(self.sel_tr_origem, "Diga de qual conta saiu.")
            destino = self._exigir(self.sel_tr_destino, "Diga para qual conta foi.")
            if origem == destino:
                raise services.RegraNegocioError("As duas contas não podem ser a mesma.")
            return [Partida(destino, "D", valor), Partida(origem, "C", valor)]

        conta_id = self._exigir(self.sel_saldo_conta, "Escolha a conta a acertar.")
        conta = services.obter_conta(conta_id)
        patrimonio = self._conta_patrimonio()
        if conta["tipo"] == "ATIVO":
            return [Partida(conta_id, "D", valor), Partida(patrimonio, "C", valor)]
        return [Partida(patrimonio, "D", valor), Partida(conta_id, "C", valor)]

    @staticmethod
    def _exigir(seletor: SeletorConta, mensagem: str) -> int:
        conta_id = seletor.get_conta_id()
        if conta_id is None:
            raise services.RegraNegocioError(mensagem)
        return conta_id

    def _descricao_padrao(self) -> str:
        texto = self.var_hist.get().strip()
        if texto:
            return texto
        aba = self.notebook.index(self.notebook.select())
        if aba == 0 and self.sel_gasto_cat.get():
            return self.sel_gasto_cat.get().split("  (")[0]
        if aba == 1 and self.sel_rec_cat.get():
            return self.sel_rec_cat.get().split("  (")[0]
        if aba == 2:
            return "Transferência entre contas"
        if aba == 3:
            return "Saldo inicial"
        return ""

    def salvar(self) -> None:
        try:
            partidas = self._montar_partidas()
            services.salvar_lancamento(
                self.lancamento_id,
                self.dt_data.get_iso(),
                self._descricao_padrao(),
                partidas,
                centro_custo_id=self.sel_centro.get_centro_id(),
            )
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return

        self.ao_salvar()
        # Ao cadastrar, a janela fica aberta para o próximo registro: só fecha
        # quando o usuário manda fechar. Em correção, salvar encerra a edição.
        if self.lancamento_id is None:
            self.cp_valor.limpar()
            self.var_hist.set("")
            self.partidas.clear()
            self._render_partidas()
            self.lbl_aviso.configure(text="Registro salvo. Pode lançar o próximo.",
                                     foreground=CORES["sucesso"])
            self.cp_valor.focus_set()
            return
        self.destroy()
