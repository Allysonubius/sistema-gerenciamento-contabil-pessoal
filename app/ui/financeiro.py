"""Contas a pagar e a receber, com registro automático do pagamento."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

from app import db, services
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (AutoConsulta, Cabecalho, CampoData, CampoValor, Paginacao,
                            SeletorCentro, SeletorConta, Tabela, centralizar)

ROTULO_STATUS = {"ABERTO": "Em aberto", "QUITADO": "Já pago", "CANCELADO": "Cancelada"}

# Períodos de vencimento oferecidos no filtro.
PERIODOS = ("Este mês", "Mês passado", "Próximo mês", "Próximos 3 meses",
            "Últimos 3 meses", "Este ano", "Só as atrasadas", "Tudo", "Escolher datas")

# Primeira opção do filtro de categoria: desfaz o filtro.
TODAS_AS_CATEGORIAS = "(todas as categorias)"


class Financeiro(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Contas a Pagar e Receber",
            "Boletos, mensalidades e parcelas. Ao marcar como pago, o gasto entra sozinho"
            " nas suas movimentações.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Cadastrar conta", self.novo, "Primario.TButton")
        # Um botão só: vira "Marcar como não pago" quando a linha escolhida já está paga.
        self.btn_pagamento = self.cabecalho.botao("Marcar como pago", self.alternar_pagamento,
                                                  "Sucesso.TButton")
        self.cabecalho.botao("Corrigir", self.editar)
        # Conta fixa: liga e desliga a repetição direto daqui, que é onde se olha.
        self.btn_fixa = self.cabecalho.botao("Desativar", self.alternar_fixa)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)

        filtros = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        filtros.configure(relief="solid", borderwidth=1)
        filtros.pack(fill="x")

        # --- linha 1: o que mostrar e de qual período ---------------------
        linha1 = ttk.Frame(filtros, style="Superficie.TFrame")
        linha1.pack(fill="x")

        ttk.Label(linha1, text="Mostrar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_tipo = ttk.Combobox(linha1, state="readonly", width=14,
                                    values=["Todas", "Que eu pago", "Que eu recebo"])
        self.cb_tipo.set("Todas")
        self.cb_tipo.pack(side="left", padx=(8, 14))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())

        self.cb_status = ttk.Combobox(linha1, state="readonly", width=13,
                                      values=["Em aberto", "Já pagas", "Canceladas", "Todas"])
        self.cb_status.set("Em aberto")
        self.cb_status.pack(side="left", padx=(0, 14))
        self.cb_status.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())

        ttk.Label(linha1, text="Filtrar por:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_criterio = ttk.Combobox(linha1, state="readonly", width=16,
                                        values=["Data de vencimento", "Mês de referência"])
        self.cb_criterio.set("Data de vencimento")
        self.cb_criterio.pack(side="left", padx=(8, 14))

        self.cb_periodo = ttk.Combobox(linha1, state="readonly", width=16,
                                       values=list(PERIODOS))
        self.cb_periodo.set("Este mês")
        self.cb_periodo.pack(side="left", padx=8)
        self.cb_periodo.bind("<<ComboboxSelected>>", lambda _e: self._aplicar_periodo())

        ttk.Button(linha1, text="◀", width=3, takefocus=False,
                   command=lambda: self.mudar_mes(-1)).pack(side="left")
        self.lbl_periodo = ttk.Label(linha1, style="CampoSuperficie.TLabel", width=18,
                                     anchor="center")
        self.lbl_periodo.pack(side="left", padx=4)
        ttk.Button(linha1, text="▶", width=3, takefocus=False,
                   command=lambda: self.mudar_mes(1)).pack(side="left")

        self.area_datas = ttk.Frame(linha1, style="Superficie.TFrame")
        ttk.Label(self.area_datas, text="de", style="CampoSuperficie.TLabel").pack(side="left")
        self.dt_inicio = CampoData(self.area_datas, services.primeiro_dia_mes())
        self.dt_inicio.pack(side="left", padx=6)
        ttk.Label(self.area_datas, text="até", style="CampoSuperficie.TLabel").pack(side="left")
        self.dt_fim = CampoData(self.area_datas, services.ultimo_dia_mes())
        self.dt_fim.pack(side="left", padx=6)
        self.dt_inicio.ligar_intervalo(self.dt_fim)   # o fim nunca vem antes do início

        # --- linha 2: filtros finos ---------------------------------------
        linha2 = ttk.Frame(filtros, style="Superficie.TFrame")
        linha2.pack(fill="x", pady=(10, 0))

        ttk.Label(linha2, text="Tipo de conta:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_origem = ttk.Combobox(linha2, state="readonly", width=14,
                                      values=["Todas", "Avulsas", "Contas fixas",
                                              "Parcelas de empréstimo", "Faturas de cartão"])
        self.cb_origem.set("Todas")
        self.cb_origem.pack(side="left", padx=(8, 14))
        self.cb_origem.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())

        ttk.Label(linha2, text="Categoria:", style="CampoSuperficie.TLabel").pack(side="left")
        self.sel_categoria = SeletorConta(linha2, permitir_vazio=True, width=22,
                                          rotulo_vazio=TODAS_AS_CATEGORIAS)
        self.sel_categoria.pack(side="left", padx=8)
        self.sel_categoria.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())

        ttk.Label(linha2, text="Valor de", style="CampoSuperficie.TLabel").pack(
            side="left", padx=(14, 0))
        self.cp_min = CampoValor(linha2, width=8)
        self.cp_min.pack(side="left", padx=6)
        ttk.Label(linha2, text="até", style="CampoSuperficie.TLabel").pack(side="left")
        self.cp_max = CampoValor(linha2, width=8)
        self.cp_max.pack(side="left", padx=6)

        ttk.Label(linha2, text="Procurar:", style="CampoSuperficie.TLabel").pack(
            side="left", padx=(14, 0))
        self.var_texto = tk.StringVar()
        entrada = ttk.Entry(linha2, textvariable=self.var_texto, width=14)
        entrada.pack(side="left", padx=8)
        entrada.bind("<Return>", lambda _e: self.recarregar())

        # "Limpar" fica na primeira linha: a segunda já é a mais cheia e o botão
        # ali dentro empurrava a tela toda para além da largura da janela.
        ttk.Button(linha1, text="Limpar", command=self.limpar_filtros).pack(side="right")

        # Consulta automática: qualquer filtro alterado já refaz a busca.
        self.auto = AutoConsulta(self, self.recarregar)
        self.auto.ligar_combos(self.cb_tipo, self.cb_status, self.cb_origem,
                               self.sel_categoria, self.cb_criterio)
        self.auto.ligar_textos(self.var_texto)
        self.auto.ligar_campos(self.cp_min, self.cp_max, self.dt_inicio, self.dt_fim)
        self.sel_categoria.bind("<KeyRelease>", self.auto.agendar, add="+")

        self._aplicar_periodo(recarregar=False)

        self.tabela = Tabela(corpo, [
            ("venc", "Vence em", 85, "center"),
            ("mes", "Referente a", 90, "center"),
            ("situacao", "Situação", 100, "center"),
            ("tipo", "O que é", 90, "center"),
            ("descricao", "Descrição", 160, "w"),
            ("pessoa", "Sai / entra na conta", 120, "w"),
            ("automatico", "Pagamento", 95, "center"),
            ("categoria", "Categoria", 100, "w"),
            ("valor", "Valor", 90, "e"),
            ("atualizado", "Com juros hoje", 105, "e"),
            ("pago", "Pago em", 80, "center"),
        ], on_duplo_clique=lambda _i: self.editar(), largura_livre=True, altura=10)
        self.tabela.definir_texto_vazio(
            "Nenhuma conta encontrada. Clique em 'Cadastrar conta' para incluir um boleto.")
        self.tabela.pack(fill="both", expand=True, pady=(14, 0))
        self.tabela.tree.bind("<<TreeviewSelect>>", lambda _e: self._ajustar_botao_pagamento(),
                              add="+")

        # Barra "desfazer": aparece logo depois de marcar como pago, para o clique
        # sem querer — a conta some da lista de "Em aberto" e seria difícil achá-la.
        self.barra_desfazer = ttk.Frame(corpo, style="Superficie.TFrame", padding=(14, 8))
        self.barra_desfazer.configure(relief="solid", borderwidth=1)
        self.lbl_desfazer = ttk.Label(self.barra_desfazer, style="CampoSuperficie.TLabel")
        self.lbl_desfazer.pack(side="left")
        ttk.Button(self.barra_desfazer, text="Fechar aviso",
                   command=self._esconder_desfazer).pack(side="right")
        ttk.Button(self.barra_desfazer, text="Desfazer (marcar como não pago)",
                   style="Perigo.TButton", command=self._desfazer_ultimo).pack(side="right", padx=8)
        self._ultimo_pago: int | None = None
        self._timer_desfazer: str | None = None

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(10, 0))
        ttk.Button(acoes, text="Contas fixas", command=self.abrir_fixas).pack(side="left")
        ttk.Button(acoes, text="Dívidas",
                   command=self.abrir_emprestimos).pack(side="left", padx=8)
        ttk.Button(acoes, text="Investimentos",
                   command=self.abrir_investimentos).pack(side="left")

        # Ações da linha selecionada, à direita. Sem rótulo: em telas menores
        # ele empurrava o botão "Apagar" para fora da janela.
        selecionada = ttk.Frame(acoes)
        selecionada.pack(side="right")
        ttk.Button(selecionada, text="Apagar", style="Perigo.TButton",
                   command=self.excluir).pack(side="right")
        ttk.Button(selecionada, text="Cancelar conta",
                   command=self.cancelar).pack(side="right", padx=8)
        ttk.Button(selecionada, text="Marcar como não pago",
                   command=self.estornar).pack(side="right")
        self.btn_automatico = ttk.Button(selecionada, text="Débito automático",
                                         command=self.alternar_automatico)
        self.btn_automatico.pack(side="right", padx=8)

        rodape = ttk.Frame(corpo, style="Superficie.TFrame", padding=14)
        rodape.configure(relief="solid", borderwidth=1)
        rodape.pack(fill="x", pady=(10, 0))

        totais = ttk.Frame(rodape, style="Superficie.TFrame")
        totais.pack(fill="x")
        self.lbl_pagar = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_pagar.pack(side="left", padx=(0, 28))
        self.lbl_receber = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_receber.pack(side="left", padx=(0, 28))
        self.lbl_saldo = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_saldo.pack(side="left", padx=(0, 28))
        # O que já entrou no período: os outros três totais falam só do que falta.
        self.lbl_entrou = ttk.Label(totais, style="Total.TLabel", background=CORES["superficie"])
        self.lbl_entrou.pack(side="left")
        self.var_atrasadas = tk.BooleanVar(value=True)
        ttk.Checkbutton(totais, text="Trazer as atrasadas dos meses anteriores",
                        variable=self.var_atrasadas, command=self.recarregar,
                        style="Superficie.TCheckbutton").pack(side="right")

        # Linha própria para a soma das pendências: aparece só quando existem.
        self.lbl_pendencias = ttk.Label(corpo, style="Secao.TLabel", foreground=CORES["perigo"],
                                        wraplength=1000, justify="left")


    # ------------------------------------------------------------------ #
    def abrir_fixas(self) -> None:
        JanelaContasFixas(self, self._apos)

    def abrir_emprestimos(self) -> None:
        """Leva para a aba Dívidas, no menu lateral."""
        from app.ui.main_window import DIVIDAS
        self.app.ir_para(DIVIDAS)

    def abrir_investimentos(self) -> None:
        from app.ui.investimentos import JanelaInvestimentos
        JanelaInvestimentos(self, self._apos)

    # --- período -------------------------------------------------------- #
    def _aplicar_periodo(self, recarregar: bool = True) -> None:
        """Traduz a opção escolhida em um intervalo de datas."""
        opcao = self.cb_periodo.get()
        hoje = date.today()
        self._so_vencidas = opcao == "Só as atrasadas"

        if opcao == "Escolher datas":
            self.lbl_periodo.configure(text="")
            self.area_datas.pack(side="left", padx=(8, 0))
            if recarregar:
                self.recarregar()
            return
        self.area_datas.pack_forget()

        if opcao == "Este mês":
            inicio, fim = services.primeiro_dia_mes(), services.ultimo_dia_mes()
        elif opcao == "Mês passado":
            anterior = hoje.replace(day=1) - timedelta(days=1)
            inicio, fim = services.primeiro_dia_mes(anterior), services.ultimo_dia_mes(anterior)
        elif opcao == "Próximo mês":
            proximo = services.somar_meses(hoje.replace(day=1), 1)
            inicio, fim = services.primeiro_dia_mes(proximo), services.ultimo_dia_mes(proximo)
        elif opcao == "Próximos 3 meses":
            inicio = services.primeiro_dia_mes()
            fim = services.ultimo_dia_mes(services.somar_meses(hoje.replace(day=1), 2))
        elif opcao == "Últimos 3 meses":
            inicio = services.primeiro_dia_mes(services.somar_meses(hoje.replace(day=1), -2))
            fim = services.ultimo_dia_mes()
        elif opcao == "Este ano":
            inicio = hoje.replace(month=1, day=1).isoformat()
            fim = hoje.replace(month=12, day=31).isoformat()
        elif opcao == "Só as atrasadas":
            inicio, fim = "1900-01-01", hoje.isoformat()
        else:  # Tudo
            inicio, fim = "1900-01-01", "2999-12-31"

        self.dt_inicio.set_iso(inicio)
        self.dt_fim.set_iso(fim)
        self._atualizar_rotulo_periodo()
        if recarregar:
            self.recarregar()

    def _atualizar_rotulo_periodo(self) -> None:
        try:
            inicio, fim = self.dt_inicio.get_iso(), self.dt_fim.get_iso()
        except services.RegraNegocioError:
            return
        if inicio <= "1900-01-01" and fim >= "2999-12-31":
            texto = "todo o período"
        elif self._so_vencidas:
            texto = "até hoje"
        elif inicio[:7] == fim[:7] and inicio[8:] == "01":
            texto = services.mes_nome(inicio[:7]).capitalize()
        else:
            texto = f"{services.para_br(inicio)} a {services.para_br(fim)}"
        self.lbl_periodo.configure(text=texto)

    def mudar_mes(self, passos: int) -> None:
        """Setas: andam de mês em mês a partir do período atual."""
        try:
            inicio = date.fromisoformat(self.dt_inicio.get_iso())
        except services.RegraNegocioError:
            inicio = date.today()
        novo = services.somar_meses(inicio.replace(day=1), passos)
        self.cb_periodo.set("Escolher datas")
        self._so_vencidas = False
        self.area_datas.pack_forget()
        self.dt_inicio.set_iso(services.primeiro_dia_mes(novo))
        self.dt_fim.set_iso(services.ultimo_dia_mes(novo))
        self._atualizar_rotulo_periodo()
        self.recarregar()

    def limpar_filtros(self) -> None:
        self.auto.pausar()
        self.cb_tipo.set("Todas")
        self.cb_status.set("Em aberto")
        self.cb_origem.set("Todas")
        self.sel_categoria.set(TODAS_AS_CATEGORIAS)
        self.cp_min.limpar()
        self.cp_max.limpar()
        self.var_texto.set("")
        self.cb_periodo.set("Este mês")
        self.cb_criterio.set("Data de vencimento")
        self.auto.retomar(consultar=False)
        self._aplicar_periodo()

    # ------------------------------------------------------------------ #
    def ao_exibir(self) -> None:
        """Ao entrar na tela: põe as contas em dia e consulta."""
        self.recarregar(manutencao=True)

    def recarregar(self, manutencao: bool = False) -> None:
        """Refaz a consulta. As rotinas de manutenção só rodam ao abrir a tela."""
        if manutencao:
            services.gerar_titulos_recorrentes()
            services.fechar_faturas()
            services.lancar_encargos_do_mes()
            self._rodar_automaticos()
        tipo = {"Que eu pago": "PAGAR", "Que eu recebo": "RECEBER"}.get(self.cb_tipo.get())
        status = {"Em aberto": "ABERTO", "Já pagas": "QUITADO",
                  "Canceladas": "CANCELADO"}.get(self.cb_status.get())
        origem = {"Avulsas": "AVULSA", "Contas fixas": "FIXA",
                  "Parcelas de empréstimo": "EMPRESTIMO",
                  "Faturas de cartão": "FATURA"}.get(self.cb_origem.get())
        try:
            desde, ate = self.dt_inicio.get_iso(), self.dt_fim.get_iso()
            categoria = self.sel_categoria.get_conta_id()
            valor_min = self.cp_min.get_valor() if self.cp_min.var.get().strip() else None
            valor_max = self.cp_max.get_valor() if self.cp_max.var.get().strip() else None
        except services.RegraNegocioError:
            return  # filtro ainda incompleto: espera o usuário terminar
        self._atualizar_rotulo_periodo()

        # Conta fixa não acaba: ao olhar um mês mais distante que os 12 já
        # lançados, os meses até lá são lançados agora ("Tudo" não força isso).
        if ate < "2999-01-01" and ate[:7] > services.mes_atual():
            services.gerar_titulos_recorrentes(ate_competencia=ate)

        # A linha escolhida volta a ficar marcada depois de recarregar: sem isso,
        # cada ação (como ligar o débito automático) exigia clicar na conta de novo.
        selecionada_antes = self.tabela.selecionado()
        self.tabela.limpar()
        hoje = services.hoje_iso()
        total_pagar = total_receber = total_encargos = 0.0
        # O que já entrou no período não depende do filtro de situação: mesmo
        # vendo só as contas em aberto, o usuário quer saber quanto recebeu.
        entrou = db.query_one(
            "SELECT IFNULL(SUM(IFNULL(valor_liquidado, valor)), 0) AS total FROM titulo"
            " WHERE tipo = 'RECEBER' AND status = 'QUITADO' AND liquidado_em BETWEEN ? AND ?",
            (desde, ate))
        total_entrou = float(entrou["total"] or 0)
        # Pendências de antes do período, somadas à parte.
        atrasadas = {"PAGAR": 0.0, "RECEBER": 0.0, "encargos": 0.0, "quantidade": 0,
                     "desde": None}
        criterio = ("competencia" if self.cb_criterio.get() == "Mês de referência"
                    else "vencimento")
        # Ao olhar o mês atual ou um futuro, o que ficou sem pagar antes vem junto:
        # a conta atrasada não some da lista só porque o mês virou.
        trazer = (self.var_atrasadas.get() and not self._so_vencidas
                  and desde > "1900-01-01" and ate >= hoje and status in (None, "ABERTO"))
        for t in services.titulos_com_encargos(
                tipo=tipo, status=None if self._so_vencidas else status,
                desde=desde, ate=ate, texto=self.var_texto.get().strip(),
                conta_id=categoria, origem=origem, valor_min=valor_min, valor_max=valor_max,
                apenas_vencidas=self._so_vencidas, criterio=criterio,
                trazer_atrasadas=trazer):
            vencido = t["status"] == "ABERTO" and t["vencimento"] < hoje
            carregada = trazer and vencido and t["vencimento"] < desde
            dias = (date.fromisoformat(t["vencimento"]) - date.today()).days
            if t["status"] == "QUITADO":
                situacao, tags = "Já pago", ("quitado",)
            elif t["status"] == "CANCELADO":
                situacao, tags = "Cancelada", ("quitado",)
            elif carregada:
                situacao, tags = f"Atrasada · {abs(dias)} dia(s)", ("vencido",)
            elif vencido:
                situacao, tags = f"Atrasada há {abs(dias)} dia(s)", ("vencido",)
            elif dias == 0:
                situacao, tags = "Vence hoje", ("destaque",)
            else:
                situacao, tags = f"Faltam {dias} dia(s)", ()

            encargos = t["encargos"]["total"]
            if t["status"] == "ABERTO":
                if t["tipo"] == "PAGAR":
                    total_pagar += float(t["valor"])
                    total_encargos += encargos
                else:
                    total_receber += float(t["valor"])
                if carregada:
                    atrasadas[t["tipo"]] += float(t["valor"])
                    atrasadas["quantidade"] += 1
                    if t["tipo"] == "PAGAR":
                        atrasadas["encargos"] += encargos
                    atrasadas["desde"] = min(atrasadas["desde"] or t["vencimento"],
                                             t["vencimento"])

            quem = "Você paga" if t["tipo"] == "PAGAR" else "Você recebe"
            if t["de_emprestimo"]:
                quem += " · parcela"
            elif t["de_fatura"]:
                quem += " · fatura"
            elif t["recorrencia_id"]:
                quem += " · fixa"
            # Uma conta de agosto pode vencer em setembro: mostrar o mês de
            # referência evita a impressão de que há duas contas no mesmo mês.
            competencia = t["competencia"] or t["vencimento"][:7]
            mes_ref = services.mes_curto(competencia)
            if competencia != t["vencimento"][:7]:
                tags = tags + ("destaque",) if "destaque" not in tags else tags

            self.tabela.inserir(
                (services.para_br(t["vencimento"]), mes_ref, situacao, quem,
                 t["descricao"], t["conta_pagamento_nome"] or "— não definida —",
                 self._texto_pagamento(t),
                 t["conta_nome"] or "",
                 services.moeda(t["valor"]),
                 services.moeda(t["valor_atualizado"]) if encargos > 0.005 else "—",
                 services.para_br(t["liquidado_em"])),
                iid=t["id"], tags=tags)
        self.tabela.finalizar()
        if selecionada_antes and self.tabela.tree.exists(selecionada_antes):
            self.tabela.tree.selection_set(selecionada_antes)

        saldo = total_receber - total_pagar - total_encargos
        texto_pagar = f"A pagar: {services.moeda(total_pagar)}"
        if total_encargos > 0.005:
            texto_pagar += f"  (+ {services.moeda(total_encargos)} de multa e juros)"
        self.lbl_pagar.configure(text=texto_pagar, foreground=CORES["perigo"])

        if atrasadas["quantidade"]:
            do_periodo = round(total_pagar - atrasadas["PAGAR"], 2)
            partes = [f"Pendências de meses anteriores: {atrasadas['quantidade']} conta(s),"
                      f" {services.moeda(atrasadas['PAGAR'])}"]
            if atrasadas["encargos"] > 0.005:
                partes.append(f"+ {services.moeda(atrasadas['encargos'])} de multa e juros")
            partes.append(f"(desde {services.para_br(atrasadas['desde'])})")
            texto = " ".join(partes)
            texto += (f"   ·   do período: {services.moeda(do_periodo)}"
                      f"   ·   total a pagar: {services.moeda(total_pagar + total_encargos)}")
            if atrasadas["RECEBER"] > 0.005:
                texto += f"   ·   a receber atrasado: {services.moeda(atrasadas['RECEBER'])}"
            self.lbl_pendencias.configure(text=texto)
            self.lbl_pendencias.pack(fill="x", pady=(8, 0))
        else:
            self.lbl_pendencias.pack_forget()
        self.lbl_receber.configure(text=f"A receber: {services.moeda(total_receber)}",
                                   foreground=CORES["sucesso"])
        self.lbl_saldo.configure(
            text=f"Diferença: {services.moeda(saldo)}",
            foreground=CORES["sucesso"] if saldo >= 0 else CORES["perigo"])
        self.lbl_entrou.configure(text=f"Entrou: {services.moeda(total_entrou)}",
                                  foreground=CORES["sucesso"])

    def _rodar_automaticos(self) -> None:
        """Desconta as contas de débito automático já vencidas e avisa o usuário."""
        resultado = services.pagar_automaticos()
        if resultado["pagos"]:
            total = sum(p["valor"] for p in resultado["pagos"])
            nomes = ", ".join(p["descricao"] for p in resultado["pagos"][:3])
            if len(resultado["pagos"]) > 3:
                nomes += f" e mais {len(resultado['pagos']) - 3}"
            self.app.notificar(f"Débito automático: {len(resultado['pagos'])} conta(s) paga(s)"
                               f" — {services.moeda(total)} ({nomes}).")
        if resultado["pendentes"]:
            nomes = "\n".join(f"• {p['descricao']} — vence em {services.para_br(p['vencimento'])}"
                              f" ({p['motivo']})" for p in resultado["pendentes"])
            messagebox.showwarning(
                "Débito automático pendente",
                "Estas contas estão marcadas como automáticas, mas o sistema não conseguiu"
                f" descontar:\n\n{nomes}\n\nCorrija o cadastro ou marque como paga na mão.",
                parent=self)

    @staticmethod
    def _texto_pagamento(titulo) -> str:
        """Como esta conta é paga: no débito automático ou na mão."""
        if not titulo["pagamento_automatico"]:
            return "Manual" if titulo["status"] == "ABERTO" else "Manual ✓"
        return "Automático" if titulo["status"] == "ABERTO" else "Automático ✓"

    # ------------------------------------------------------------------ #
    def _selecionado(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Contas", "Escolha antes uma linha da lista.", parent=self)
            return None
        return int(item)

    def novo(self) -> None:
        DialogoTitulo(self, None, self._apos)

    def editar(self) -> None:
        titulo_id = self._selecionado()
        if titulo_id:
            DialogoTitulo(self, titulo_id, self._apos)

    def _titulo_selecionado(self):
        item = self.tabela.selecionado()
        return services.obter_titulo(int(item)) if item else None

    def _status_selecionado(self) -> str | None:
        titulo = self._titulo_selecionado()
        return titulo["status"] if titulo else None

    def _ajustar_botao_pagamento(self) -> None:
        titulo = self._titulo_selecionado()
        if titulo is not None and titulo["status"] == "QUITADO":
            self.btn_pagamento.configure(text="Marcar como não pago", style="Perigo.TButton")
        else:
            self.btn_pagamento.configure(text="Marcar como pago", style="Sucesso.TButton")
        automatica = titulo is not None and titulo["pagamento_automatico"]
        self.btn_automatico.configure(
            text="Tirar do débito automático" if automatica else "Pôr no débito automático")
        # Só faz sentido ligar/desligar o que se repete todo mês.
        regra = self._regra_da_linha(titulo)
        if regra is None:
            self.btn_fixa.configure(text="Desativar", state="disabled")
        elif regra["ativo"]:
            self.btn_fixa.configure(text="Desativar", state="normal",
                                    style="Perigo.TButton")
        else:
            self.btn_fixa.configure(text="Ativar", state="normal",
                                    style="Sucesso.TButton")

    @staticmethod
    def _regra_da_linha(titulo):
        """A conta fixa por trás da linha escolhida, se houver."""
        if titulo is None or not titulo["recorrencia_id"]:
            return None
        return db.query_one("SELECT * FROM recorrencia WHERE id = ?",
                            (titulo["recorrencia_id"],))

    def alternar_fixa(self) -> None:
        """Liga ou desliga a repetição da conta fixa da linha escolhida.

        Desativada, os meses seguintes saem da lista na hora; o mês atual e o
        histórico ficam. Ativada de novo, os meses à frente voltam.
        """
        titulo = self._titulo_selecionado()
        if titulo is None:
            messagebox.showinfo("Contas", "Escolha antes uma linha da lista.", parent=self)
            return
        regra = self._regra_da_linha(titulo)
        if regra is None:
            messagebox.showinfo(
                "Não é uma conta fixa",
                f"'{titulo['descricao']}' é uma conta avulsa: ela só existe neste mês.\n\n"
                "Para tirá-la da lista use 'Cancelar conta' ou 'Apagar'.", parent=self)
            return

        recebe = titulo["tipo"] == "RECEBER"
        if not regra["ativo"]:
            if not messagebox.askyesno(
                    "Ativar",
                    f"'{titulo['descricao']}' volta a"
                    f" {'entrar' if recebe else 'ser cobrada'} todo mês, a partir deste.\n\n"
                    "Os próximos meses voltam para a lista.\n\nConfirma?", parent=self):
                return
            criados = services.reativar_recorrencia(regra["id"])
            self._apos()
            self.app.notificar(f"'{titulo['descricao']}' ativada: {criados} mês(es)"
                               " voltaram para a lista.")
            return

        em_aberto = db.query_one(
            "SELECT COUNT(*) AS c FROM titulo WHERE recorrencia_id = ?"
            " AND status = 'ABERTO' AND competencia >= ?",
            (titulo["recorrencia_id"], services.mes_atual()))["c"]
        if not messagebox.askyesno(
                "Desativar",
                f"'{titulo['descricao']}' deixa de"
                f" {'entrar' if recebe else 'ser cobrada'} deste mês em diante.\n\n"
                f"{em_aberto} mês(es) em aberto saem da lista agora, incluindo o mês atual."
                f" Tudo o que já foi {'recebido' if recebe else 'pago'} continua no"
                " histórico.\n\nConfirma?", parent=self):
            return
        removidos = services.pausar_recorrencia(titulo["recorrencia_id"])
        self._apos()
        self.app.notificar(
            f"'{titulo['descricao']}' desativada: {removidos} mês(es) em aberto saíram da"
            " lista, deste mês em diante. Para voltar, use o botão 'Ativar'.")

    def alternar_automatico(self) -> None:
        """Liga ou desliga o débito automático da conta escolhida."""
        titulo = self._titulo_selecionado()
        if titulo is None:
            messagebox.showinfo("Contas", "Escolha antes uma linha da lista.", parent=self)
            return
        ligar = not titulo["pagamento_automatico"]
        propagar = False
        if titulo["recorrencia_id"]:
            propagar = messagebox.askyesno(
                "Débito automático",
                f"'{titulo['descricao']}' é uma conta fixa.\n\n"
                + ("Valer também para os próximos meses?" if ligar
                   else "Tirar também dos próximos meses?"),
                parent=self)
        try:
            services.definir_pagamento_automatico(titulo["id"], ligar, propagar_fixa=propagar)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Débito automático", str(erro), parent=self)
            return
        self._apos()
        if ligar:
            self.app.notificar(f"'{titulo['descricao']}' entra no débito automático:"
                               " o desconto acontece sozinho no vencimento.")
        else:
            self.app.notificar(f"'{titulo['descricao']}' volta a ser paga por você.")

    def alternar_pagamento(self) -> None:
        if self._status_selecionado() == "QUITADO":
            self.estornar()
        else:
            self.baixar()

    def baixar(self) -> None:
        titulo_id = self._selecionado()
        if not titulo_id:
            return
        if self._status_selecionado() == "CANCELADO":
            messagebox.showinfo("Marcar como pago", "Esta conta está cancelada.", parent=self)
            return
        DialogoBaixa(self, titulo_id, lambda: self._apos_pagar(titulo_id))

    def _apos_pagar(self, titulo_id: int) -> None:
        self._apos()
        titulo = services.obter_titulo(titulo_id)
        if titulo is None or titulo["status"] != "QUITADO":
            return
        self._ultimo_pago = titulo_id
        self.lbl_desfazer.configure(
            text=f"'{titulo['descricao']}' marcada como paga"
                 f" ({services.moeda(titulo['valor_liquidado'])}"
                 f" em {services.para_br(titulo['liquidado_em'])}). Foi sem querer?")
        self.barra_desfazer.pack(fill="x", pady=(10, 0), before=self.tabela)
        if self._timer_desfazer:
            self.after_cancel(self._timer_desfazer)
        self._timer_desfazer = self.after(30000, self._esconder_desfazer)

    def _esconder_desfazer(self) -> None:
        self.barra_desfazer.pack_forget()
        self._ultimo_pago = None
        if self._timer_desfazer:
            self.after_cancel(self._timer_desfazer)
            self._timer_desfazer = None

    def _desfazer_ultimo(self) -> None:
        titulo_id = self._ultimo_pago
        self._esconder_desfazer()
        if titulo_id is None:
            return
        try:
            resultado = services.estornar_titulo(titulo_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Marcar como não pago", str(erro), parent=self)
            return
        self._apos()
        self._notificar_estorno(resultado)

    def estornar(self) -> None:
        titulo_id = self._selecionado()
        if not titulo_id:
            return
        if self._status_selecionado() != "QUITADO":
            messagebox.showinfo("Marcar como não pago",
                                "Esta conta ainda não está paga. Para ver as pagas, escolha"
                                " 'Já pagas' (ou 'Todas') no filtro.", parent=self)
            return
        if not messagebox.askyesno(
                "Marcar como não pago",
                "A conta volta a ficar em aberto, o dinheiro volta para a conta de onde saiu e"
                " o registro criado pelo pagamento é removido. Se foi um pagamento parcial, a"
                " conta com o que faltou também sai.\n\nConfirma?", parent=self):
            return
        try:
            resultado = services.estornar_titulo(titulo_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Marcar como não pago", str(erro), parent=self)
            return
        self._apos()
        self._notificar_estorno(resultado)

    def _notificar_estorno(self, resultado: dict) -> None:
        texto = "Conta marcada como não paga: voltou para Em aberto."
        if resultado.get("sobras_removidas"):
            texto += " A conta com o que faltou também foi removida."
        self.app.notificar(texto)
        self._ajustar_botao_pagamento()

    def cancelar(self) -> None:
        titulo_id = self._selecionado()
        if not titulo_id:
            return
        if not messagebox.askyesno(
                "Cancelar conta",
                "A conta fica guardada no histórico, mas deixa de ser cobrada nos totais."
                "\n\nConfirma?", parent=self):
            return
        try:
            services.cancelar_titulo(titulo_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Cancelar conta", str(erro), parent=self)
            return
        self._apos()

    def excluir(self) -> None:
        titulo_id = self._selecionado()
        if not titulo_id:
            return
        if not messagebox.askyesno(
                "Apagar conta",
                "A conta será apagada definitivamente.\n"
                "Se ela já foi paga, desfaça o pagamento antes.\n\nConfirma?", parent=self):
            return
        try:
            services.excluir_titulo(titulo_id)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não é possível apagar", str(erro), parent=self)
            return
        self._apos()

    def _apos(self) -> None:
        self.recarregar()
        self.app.atualizar_dependentes()
        self._ajustar_botao_pagamento()


# --------------------------------------------------------------------------- #
class DialogoTitulo(tk.Toplevel):
    def __init__(self, master, titulo_id: int | None, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.titulo_id = titulo_id
        self.ao_salvar = ao_salvar
        self.recorrencia_id: int | None = None
        self.competencia = services.mes_atual()
        self.valor_original = 0.0
        self.title("Cadastrar conta" if titulo_id is None else f"Corrigir conta nº {titulo_id}")
        self.configure(bg=CORES["fundo"])
        # Formulário longo: quem tiver tela pequena pode esticar a janela.
        self.resizable(True, True)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=12)
        topo.pack(fill="x")
        tk.Label(topo, text="Conta a pagar ou a receber", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Cadastre agora e marque como pago quando acontecer de verdade.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=(20, 14))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(2, weight=1)

        ttk.Label(corpo, text="Esta conta é...", style="Campo.TLabel").grid(
            row=0, column=0, sticky="w")
        self.cb_tipo = ttk.Combobox(corpo, state="readonly", width=18,
                                    values=["Para eu pagar", "Para eu receber"])
        self.cb_tipo.set("Para eu pagar")
        self.cb_tipo.grid(row=1, column=0, sticky="w", pady=(3, 9), padx=(0, 16))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self._ajustar_categorias())

        ttk.Label(corpo, text="Vence em", style="Campo.TLabel").grid(row=0, column=1, sticky="w")
        self.dt_venc = CampoData(corpo, services.hoje_iso())
        self.dt_venc.grid(row=1, column=1, sticky="w", pady=(3, 9), padx=(0, 16))

        ttk.Label(corpo, text="Valor (R$)", style="Campo.TLabel").grid(row=0, column=2, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=1, column=2, sticky="w", pady=(3, 9))

        ttk.Label(corpo, text="Descrição", style="Campo.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(corpo, text="Ex.: Conta de luz de março, Mensalidade da faculdade.",
                  style="Dica.TLabel").grid(row=3, column=0, columnspan=3, sticky="w")
        self.var_desc = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_desc).grid(
            row=4, column=0, columnspan=3, sticky="we", pady=(3, 9))

        self.lbl_pagamento = ttk.Label(corpo, text="De qual conta vai sair o dinheiro?",
                                       style="Campo.TLabel")
        self.lbl_pagamento.grid(row=5, column=0, columnspan=3, sticky="w")
        ttk.Label(corpo, text="Conta corrente, carteira, poupança ou cartão. Já vem"
                              " pré-escolhida na hora de dar baixa.",
                  style="Dica.TLabel").grid(row=6, column=0, columnspan=3, sticky="w")
        self.sel_pagamento = SeletorConta(corpo, tipos=("ATIVO", "PASSIVO"), width=56,
                                          rotulo_vazio="(decidir na hora do pagamento)")
        self.sel_pagamento.grid(row=7, column=0, columnspan=2, sticky="w", pady=(3, 9))
        # Débito automático: o sistema desconta sozinho no vencimento, sem você
        # precisar marcar como pago.
        self.var_automatico = tk.BooleanVar(value=False)
        ttk.Checkbutton(corpo, variable=self.var_automatico,
                        text="É débito automático nesta conta").grid(
            row=7, column=2, sticky="w", pady=(3, 9))
        # Mantido apenas para preservar o que já foi cadastrado antes deste campo.
        self.var_pessoa = tk.StringVar()

        self.lbl_categoria = ttk.Label(corpo, text="Categoria do gasto", style="Campo.TLabel")
        self.lbl_categoria.grid(row=8, column=0, sticky="w")
        self.lbl_categoria_dica = ttk.Label(
            corpo, text="Serve para o sistema saber em que grupo lançar quando você pagar.",
            style="Dica.TLabel")
        self.lbl_categoria_dica.grid(row=9, column=0, columnspan=3, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("DESPESA",), width=60)
        self.sel_conta.grid(row=10, column=0, columnspan=3, sticky="w", pady=(3, 9))

        ttk.Label(corpo, text="Grupo (opcional)", style="Campo.TLabel").grid(
            row=11, column=0, sticky="w")
        self.sel_centro = SeletorCentro(corpo)
        self.sel_centro.grid(row=12, column=0, sticky="w", pady=(3, 9))

        self.quadro_fixa = ttk.Frame(corpo)
        self.quadro_fixa.grid(row=11, column=1, columnspan=2, rowspan=2, sticky="w")
        self.var_fixa = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.quadro_fixa, variable=self.var_fixa, command=self._alternar_fixa,
                        text="É uma conta fixa: repete todo mês até eu desmarcar").pack(anchor="w")
        self.linha_fixa = ttk.Frame(self.quadro_fixa)
        ttk.Label(self.linha_fixa, text="Por", style="Campo.TLabel").pack(side="left")
        self.var_meses = tk.IntVar(value=0)
        ttk.Spinbox(self.linha_fixa, from_=0, to=120, textvariable=self.var_meses,
                    width=5).pack(side="left", padx=6)
        ttk.Label(self.linha_fixa, text="meses  (0 = sem prazo, repete até você encerrar)",
                  style="Dica.TLabel").pack(side="left")

        atraso = ttk.Frame(corpo)
        atraso.grid(row=13, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(atraso, text="Se atrasar:", style="Campo.TLabel").pack(side="left")
        ttk.Label(atraso, text="multa de", style="Dica.TLabel").pack(side="left", padx=(10, 4))
        self.var_multa = tk.StringVar(value=db.get_config("multa_padrao", "0"))
        ttk.Spinbox(atraso, from_=0, to=100, increment=0.5, width=6,
                    textvariable=self.var_multa).pack(side="left")
        ttk.Label(atraso, text="%  e juros de", style="Dica.TLabel").pack(side="left", padx=4)
        self.var_juros = tk.StringVar(value=db.get_config("juros_padrao", "0"))
        ttk.Spinbox(atraso, from_=0, to=100, increment=0.5, width=6,
                    textvariable=self.var_juros).pack(side="left")
        ttk.Label(atraso, text="% ao mês (0 = não cobrar nada)",
                  style="Dica.TLabel").pack(side="left", padx=4)

        ttk.Label(corpo, text="Observação (opcional)", style="Campo.TLabel").grid(
            row=14, column=0, sticky="w")
        self.txt_obs = tk.Text(corpo, height=2, font=(FONTE, 10), relief="solid", borderwidth=1)
        self.txt_obs.grid(row=15, column=0, columnspan=3, sticky="we", pady=(3, 9))

        self.lbl_fixa = ttk.Label(corpo, style="Dica.TLabel", wraplength=680, justify="left")
        self.lbl_fixa.grid(row=16, column=0, columnspan=3, sticky="w", pady=(0, 10))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=17, column=0, columnspan=3, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        self._carregar()
        centralizar(self, 780, 660)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _ajustar_categorias(self) -> None:
        pagar = self.cb_tipo.get() == "Para eu pagar"
        self.sel_conta._tipos = ("DESPESA",) if pagar else ("RECEITA",)
        self.sel_conta.set("")
        self.sel_conta.recarregar()
        self.lbl_categoria.configure(
            text="Categoria do gasto" if pagar else "Origem do dinheiro")
        self.lbl_pagamento.configure(
            text="De qual conta vai sair o dinheiro?" if pagar
                 else "Em qual conta o dinheiro vai entrar?")

    def _alternar_fixa(self) -> None:
        # Em conta que já é fixa, o prazo não se escolhe aqui: desmarcar encerra.
        if self.var_fixa.get() and not self.recorrencia_id:
            self.linha_fixa.pack(anchor="w", pady=(6, 0))
        else:
            self.linha_fixa.pack_forget()
        if self.recorrencia_id and not self.var_fixa.get():
            self.lbl_fixa.configure(
                text=f"Ao salvar, esta conta deixa de se repetir: {services.mes_nome(self.competencia)}"
                     " fica na lista e os meses seguintes ainda não pagos são removidos.",
                foreground=CORES["perigo"])
        elif self.recorrencia_id:
            self._aviso_fixa()

    def _carregar(self) -> None:
        if self.titulo_id is None:
            return
        t = db.query_one("SELECT * FROM titulo WHERE id = ?", (self.titulo_id,))
        if t is None:
            return
        self.recorrencia_id = t["recorrencia_id"]
        self.competencia = t["competencia"] or t["vencimento"][:7]
        self.valor_original = float(t["valor"])
        self.cb_tipo.set("Para eu pagar" if t["tipo"] == "PAGAR" else "Para eu receber")
        self._ajustar_categorias()
        self.dt_venc.set_iso(t["vencimento"])
        self.cp_valor.set_valor(float(t["valor"]))
        self.var_desc.set(t["descricao"])
        self.var_pessoa.set(t["pessoa"])
        if t["conta_pagamento_id"]:
            self.sel_pagamento.set_conta_id(t["conta_pagamento_id"])
        self.sel_conta.set_conta_id(t["conta_id"])
        self.sel_centro.set_centro_id(t["centro_custo_id"])
        self.txt_obs.insert("1.0", t["observacao"])
        self.var_multa.set(str(t["multa_pct"] or 0))
        self.var_juros.set(str(t["juros_mes_pct"] or 0))
        self.var_automatico.set(bool(t["pagamento_automatico"]))
        # A opção continua visível ao editar: marcada se a conta é fixa (desmarcar
        # encerra a repetição), desmarcada se é avulsa (marcar passa a repetir).
        self.var_fixa.set(bool(self.recorrencia_id))
        if self.recorrencia_id:
            self._aviso_fixa()

    def _aviso_fixa(self) -> None:
        self.lbl_fixa.configure(
            text="Esta é uma conta fixa e se repete até você desmarcar. O que você mudar aqui"
                 f" vale para {services.mes_nome(self.competencia)} e para todos os meses"
                 " seguintes que ainda não foram pagos. Os meses já pagos não mudam.",
            foreground=CORES["alerta"])

    def salvar(self) -> None:
        try:
            tipo = "PAGAR" if self.cb_tipo.get() == "Para eu pagar" else "RECEBER"
            valor = self.cp_valor.get_valor()
            vencimento = self.dt_venc.get_iso()
            conta_id = self.sel_conta.get_conta_id()
            if conta_id is None:
                raise services.RegraNegocioError(
                    "Escolha a categoria — é ela que diz onde o valor será lançado no pagamento.")
            descricao = self.var_desc.get().strip() or self.sel_conta.get().split("  (")[0]
            observacao = self.txt_obs.get("1.0", "end").strip()
            centro_id = self.sel_centro.get_centro_id()
            multa = services.para_float(self.var_multa.get() or "0")
            juros = services.para_float(self.var_juros.get() or "0")
            pagamento_id = self.sel_pagamento.get_conta_id()
            automatico = bool(self.var_automatico.get())
            if automatico and pagamento_id is None:
                raise services.RegraNegocioError(
                    "No débito automático o sistema precisa saber de qual conta o dinheiro"
                    " sai. Escolha a conta ou desmarque a opção.")

            # Conta fixa desmarcada: salva este mês e encerra a repetição.
            if self.recorrencia_id and not self.var_fixa.get():
                if not messagebox.askyesno(
                        "Deixar de ser conta fixa",
                        f"'{descricao}' deixa de se repetir depois de"
                        f" {services.mes_nome(self.competencia)}.\n\n"
                        "Os meses seguintes que ainda não foram pagos serão removidos."
                        " Os meses já pagos continuam no histórico.\n\nConfirma?",
                        parent=self):
                    return
                services.salvar_titulo(self.titulo_id, tipo, descricao, self.var_pessoa.get(),
                                       valor, vencimento, conta_id, centro_id, observacao,
                                       multa, juros, conta_pagamento_id=pagamento_id,
                                       pagamento_automatico=automatico)
                removidos = services.encerrar_recorrencia(self.recorrencia_id,
                                                          ultimo_mes=self.competencia)
                self.ao_salvar()
                messagebox.showinfo(
                    "Conta fixa encerrada",
                    f"'{descricao}' não se repete mais. {removidos} mês(es) futuro(s) removido(s).",
                    parent=self.master)
                self.destroy()
                return

            # Conta avulsa marcada como fixa: ela vira o primeiro mês da série.
            if self.titulo_id is not None and not self.recorrencia_id and self.var_fixa.get():
                services.salvar_titulo(self.titulo_id, tipo, descricao, self.var_pessoa.get(),
                                       valor, vencimento, conta_id, centro_id, observacao,
                                       multa, juros, conta_pagamento_id=pagamento_id,
                                       pagamento_automatico=automatico)
                criados = services.tornar_recorrente(self.titulo_id,
                                                     int(self.var_meses.get() or 0))
                self.ao_salvar()
                messagebox.showinfo(
                    "Agora é conta fixa",
                    f"'{descricao}' passa a se repetir todo mês e continua até você desmarcar."
                    f"\n\n{criados} mês(es) seguinte(s) já foram lançados.", parent=self.master)
                self.destroy()
                return

            # Conta fixa em edição: propaga deste mês em diante.
            if self.recorrencia_id:
                services.salvar_titulo(self.titulo_id, tipo, descricao, self.var_pessoa.get(),
                                       valor, vencimento, conta_id, centro_id, observacao,
                                       multa, juros, conta_pagamento_id=pagamento_id,
                                       pagamento_automatico=automatico)
                services.aplicar_conta_pagamento(self.recorrencia_id, self.competencia,
                                                 pagamento_id)
                services.aplicar_pagamento_automatico(self.recorrencia_id, self.competencia,
                                                      automatico)
                atingidos = services.aplicar_reajuste(
                    self.recorrencia_id, self.competencia, valor, descricao,
                    self.var_pessoa.get().strip(), conta_id, centro_id)
                self.ao_salvar()
                # Só é reajuste quando o valor mudou. Trocar a conta de desconto
                # ou a categoria é uma correção de cadastro: salva e pronto.
                if abs(valor - self.valor_original) > 0.005:
                    messagebox.showinfo(
                        "Conta fixa atualizada",
                        f"O novo valor de {services.moeda(valor)} passa a valer a partir de"
                        f" {services.mes_nome(self.competencia)}.\n\n"
                        f"{atingidos} mês(es) em aberto foram atualizados."
                        " Os meses já pagos continuam com o valor antigo.", parent=self)
                self.destroy()
                return

            # Nova conta fixa: cria a regra e gera os meses.
            if self.titulo_id is None and self.var_fixa.get():
                base = date.fromisoformat(vencimento)
                meses = int(self.var_meses.get() or 0)
                _rec_id, criados = services.criar_conta_fixa(
                    tipo, descricao, self.var_pessoa.get(), valor, vencimento, conta_id,
                    centro_id, observacao, meses, multa_pct=multa, juros_mes_pct=juros,
                    conta_pagamento_id=pagamento_id, pagamento_automatico=automatico)
                self.ao_salvar()
                messagebox.showinfo(
                    "Conta fixa criada",
                    f"'{descricao}' passa a ser gerada todo dia {base.day}.\n\n"
                    f"{criados} mês(es) já foram lançados."
                    + ("" if meses else "\nEla continua até você desmarcar."),
                    parent=self.master)
                self.destroy()
                return

            services.salvar_titulo(self.titulo_id, tipo, descricao, self.var_pessoa.get(),
                                   valor, vencimento, conta_id, centro_id, observacao,
                                   multa, juros, conta_pagamento_id=pagamento_id,
                                   pagamento_automatico=automatico)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


# --------------------------------------------------------------------------- #
class JanelaContasFixas(tk.Toplevel):
    """Gestão das contas que se repetem todo mês."""

    def __init__(self, master, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_mudar = ao_mudar
        self.title("Contas fixas")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Contas fixas e salários", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="O que se repete todo mês: aluguel, luz, internet, mensalidades"
                            " — e também o que entra, como salário e aluguel recebido."
                            " Trocou de emprego? Edite o valor ou encerre no último mês em"
                            " que o dinheiro entrou.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 12))
        ttk.Button(acoes, text="Editar", style="Primario.TButton",
                   command=self.reajustar).pack(side="left")
        ttk.Button(acoes, text="Ativar / pausar", command=self.alternar).pack(side="left", padx=8)
        ttk.Button(acoes, text="Débito automático",
                   command=self.alternar_automatico).pack(side="left", padx=(0, 8))
        ttk.Button(acoes, text="Encerrar", style="Perigo.TButton",
                   command=self.encerrar).pack(side="left")
        ttk.Label(acoes, text="Editar vale de um mês em diante. Encerrar tira só os meses"
                              " futuros — o histórico fica.",
                  style="Dica.TLabel").pack(side="left", padx=12)

        self.tabela = Tabela(corpo, [
            ("descricao", "Descrição", 200, "w"),
            ("tipo", "O que é", 90, "center"),
            ("valor", "Valor atual", 100, "e"),
            ("dia", "Vence dia", 75, "center"),
            ("categoria", "Categoria", 150, "w"),
            ("conta", "Sai da conta", 120, "w"),
            ("automatico", "Pagamento", 95, "center"),
            ("desde", "Cobrando desde", 115, "center"),
            ("ultimo", "Último pagamento", 125, "center"),
            ("proxima", "Próxima cobrança", 125, "center"),
            ("situacao", "Situação", 85, "center"),
        ], on_duplo_clique=lambda _i: self.reajustar(), altura=8)
        self.tabela.definir_texto_vazio(
            "Nada fixo por enquanto. Ao cadastrar uma conta a pagar ou a receber"
            " (salário, por exemplo), marque 'É uma conta fixa: repete todo mês'.")
        self.tabela.pack(fill="both", expand=True)

        self.recarregar()
        centralizar(self, 1280, 560)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        self.tabela.limpar()
        for rec in services.listar_recorrencias():
            # Gasto fixo não tem parcelas: mostra desde quando é cobrado, o
            # último pagamento e a próxima cobrança — sem contagem "x de y".
            desde = services.mes_curto(rec["inicio"])
            if rec["fim"]:
                desde += f" até {services.mes_curto(rec['fim'])}"
            ultimo = (services.para_br(rec["ultimo_pagamento"][:10])
                      if rec["ultimo_pagamento"] else "ainda não pago")
            proxima = (services.para_br(rec["proxima_cobranca"]) if rec["proxima_cobranca"]
                       else "—")
            self.tabela.inserir(
                (rec["descricao"],
                 "Você paga" if rec["tipo"] == "PAGAR" else "Você recebe",
                 services.moeda(rec["valor"]), rec["dia_vencimento"],
                 rec["conta_nome"] or "",
                 rec["conta_pagamento_nome"] or "— não definida —",
                 "Automático" if rec["pagamento_automatico"] else "Manual",
                 desde, ultimo, proxima,
                 "Ativa" if rec["ativo"] else "Encerrada"),
                iid=rec["id"], tags=() if rec["ativo"] else ("quitado",))
        self.tabela.finalizar()

    def _selecionada(self) -> int | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Contas fixas", "Escolha antes uma linha da lista.", parent=self)
            return None
        return int(item)

    def reajustar(self) -> None:
        rec_id = self._selecionada()
        if rec_id:
            DialogoReajuste(self, rec_id, self._apos)

    def alternar(self) -> None:
        rec_id = self._selecionada()
        if not rec_id:
            return
        rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (rec_id,))
        if rec["ativo"]:
            removidos = services.pausar_recorrencia(rec_id)
            if removidos:
                messagebox.showinfo(
                    "Pausada",
                    f"'{rec['descricao']}' não gera mais meses.\n\n{removidos} mês(es) em"
                    " aberto saíram de Contas a Pagar e Receber, a partir do mês atual."
                    " O que já foi pago continua no histórico.", parent=self)
        else:
            # Reativar limpa um fim já passado: senão ela ficaria ativa sem gerar nada.
            services.reativar_recorrencia(rec_id)
        self._apos()

    def alternar_automatico(self) -> None:
        """Liga/desliga o débito automático da fixa, deste mês em diante."""
        rec_id = self._selecionada()
        if not rec_id:
            return
        rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (rec_id,))
        ligar = not rec["pagamento_automatico"]
        if ligar and not rec["conta_pagamento_id"]:
            messagebox.showwarning(
                "Débito automático",
                "Defina antes de qual conta o dinheiro sai (botão 'Mudar o valor'):"
                " sem isso o sistema não tem de onde descontar.", parent=self)
            return
        atingidos = services.aplicar_pagamento_automatico(rec_id, services.mes_atual(), ligar)
        self._apos()
        messagebox.showinfo(
            "Débito automático",
            (f"'{rec['descricao']}' passa a ser descontada sozinha no vencimento."
             if ligar else f"'{rec['descricao']}' volta a ser paga por você.")
            + f"\n\n{atingidos} mês(es) em aberto atualizado(s). Os meses já pagos não mudam.",
            parent=self)

    def encerrar(self) -> None:
        rec_id = self._selecionada()
        if rec_id:
            # A janela pergunta até qual mês valeu: trocar de emprego encerra o
            # salário antigo no último mês em que ele entrou, não hoje.
            DialogoEncerrarFixa(self, rec_id, self._apos)

    def _apos(self) -> None:
        self.recarregar()
        self.ao_mudar()


class DialogoReajuste(tk.Toplevel):
    """Edita uma conta fixa — inclusive salário — de um mês em diante.

    Serve para o caso real de trocar de emprego: o salário novo é cadastrado
    como renda fixa, e o antigo se encerra no mês em que parou de entrar.
    """

    def __init__(self, master, recorrencia_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.recorrencia_id = recorrencia_id
        self.ao_salvar = ao_salvar
        self.rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (recorrencia_id,))
        self.recebe = self.rec["tipo"] == "RECEBER"
        recebe = self.recebe
        self.title("Editar renda fixa" if recebe else "Editar conta fixa")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Mudou o valor ou a fonte?" if recebe else "Subiu de preço?",
                 bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text=f"{self.rec['descricao']} — hoje"
                            f" {services.moeda(self.rec['valor'])} todo dia"
                            f" {self.rec['dia_vencimento']}",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Descrição", style="Campo.TLabel").grid(
            row=0, column=0, sticky="w")
        self.var_desc = tk.StringVar(value=self.rec["descricao"])
        ttk.Entry(corpo, textvariable=self.var_desc, width=28).grid(
            row=1, column=0, sticky="w", pady=(4, 14), padx=(0, 24))

        ttk.Label(corpo, text="Quem paga" if recebe else "Para quem",
                  style="Campo.TLabel").grid(row=0, column=1, sticky="w")
        self.var_pessoa = tk.StringVar(value=self.rec["pessoa"] or "")
        ttk.Entry(corpo, textvariable=self.var_pessoa, width=28).grid(
            row=1, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Novo valor (R$)", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.set_valor(float(self.rec["valor"]))
        self.cp_valor.grid(row=3, column=0, sticky="w", pady=(4, 14), padx=(0, 24))

        ttk.Label(corpo, text="Entra todo dia" if recebe else "Vence todo dia",
                  style="Campo.TLabel").grid(row=2, column=1, sticky="w")
        self.var_dia = tk.IntVar(value=int(self.rec["dia_vencimento"]))
        ttk.Spinbox(corpo, from_=1, to=31, textvariable=self.var_dia, width=6).grid(
            row=3, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Origem do dinheiro" if recebe else "Categoria do gasto",
                  style="Campo.TLabel").grid(row=4, column=0, columnspan=2, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("RECEITA",) if recebe else ("DESPESA",),
                                      width=50)
        self.sel_conta.set_conta_id(self.rec["conta_id"])
        self.sel_conta.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Em qual conta o dinheiro entra?" if recebe
                              else "De qual conta sai o dinheiro?",
                  style="Campo.TLabel").grid(row=6, column=0, columnspan=2, sticky="w")
        self.sel_pagamento = SeletorConta(corpo, tipos=("ATIVO", "PASSIVO"), width=50,
                                          rotulo_vazio="(decidir na hora)")
        if self.rec["conta_pagamento_id"]:
            self.sel_pagamento.set_conta_id(self.rec["conta_pagamento_id"])
        self.sel_pagamento.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="A partir de qual mês?", style="Campo.TLabel").grid(
            row=8, column=0, sticky="w")
        self.cb_mes = ttk.Combobox(corpo, state="readonly", width=24)
        meses = self._meses_disponiveis()
        self.cb_mes["values"] = [services.mes_nome(m).capitalize() for m in meses]
        self._meses = meses
        self.cb_mes.current(meses.index(services.mes_atual()) if services.mes_atual() in meses
                            else 0)
        self.cb_mes.grid(row=9, column=0, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Os meses anteriores e todos os que já foram"
                              f" {'recebidos' if recebe else 'pagos'} continuam como estavam"
                              " — seu histórico não muda.",
                  style="Dica.TLabel", wraplength=520, justify="left").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(0, 14))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=11, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Salvar", style="Primario.TButton",
                   command=self.aplicar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 660, 620)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _meses_disponiveis(self) -> list[str]:
        meses = [t["competencia"] for t in db.query(
            "SELECT DISTINCT competencia FROM titulo WHERE recorrencia_id = ?"
            " AND status = 'ABERTO' ORDER BY competencia", (self.recorrencia_id,))]
        return meses or [services.mes_atual()]

    def aplicar(self) -> None:
        try:
            valor = self.cp_valor.get_valor()
            competencia = self._meses[self.cb_mes.current()]
            descricao = self.var_desc.get().strip()
            if not descricao:
                raise services.RegraNegocioError("Escreva a descrição.")
            conta_id = self.sel_conta.get_conta_id()
            if conta_id is None:
                raise services.RegraNegocioError(
                    "Escolha a origem do dinheiro." if self.recebe
                    else "Escolha a categoria do gasto.")
            pagamento_id = self.sel_pagamento.get_conta_id()
            dia = int(self.var_dia.get() or self.rec["dia_vencimento"])

            # A regra passa a valer com os dados novos: os meses que ainda serão
            # gerados já nascem assim.
            services.salvar_recorrencia(
                self.recorrencia_id, self.rec["tipo"], descricao, self.var_pessoa.get(),
                valor, dia, conta_id, self.rec["centro_custo_id"], self.rec["inicio"],
                self.rec["fim"], self.rec["observacao"], bool(self.rec["ativo"]),
                conta_pagamento_id=pagamento_id,
                pagamento_automatico=bool(self.rec["pagamento_automatico"]))
            # E os meses já lançados, deste em diante, são corrigidos.
            atingidos = services.aplicar_reajuste(
                self.recorrencia_id, competencia, valor, descricao,
                self.var_pessoa.get().strip(), conta_id)
            services.aplicar_conta_pagamento(self.recorrencia_id, competencia, pagamento_id)
            if dia != int(self.rec["dia_vencimento"]):
                services.ajustar_dia_recorrencia(self.recorrencia_id, dia, competencia)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        messagebox.showinfo(
            "Pronto",
            f"A partir de {services.mes_nome(competencia)}: {descricao},"
            f" {services.moeda(valor)}, todo dia {dia}.\n\n"
            f"{atingidos} mês(es) em aberto foram atualizados.", parent=self)
        self.destroy()


class DialogoEncerrarFixa(tk.Toplevel):
    """Encerra uma conta ou renda fixa a partir do mês escolhido.

    É o caso de trocar de emprego: o salário antigo vai até o último mês em que
    entrou e some dos meses seguintes, sem apagar o histórico.
    """

    def __init__(self, master, recorrencia_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.recorrencia_id = recorrencia_id
        self.ao_salvar = ao_salvar
        self.rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (recorrencia_id,))
        recebe = self.rec["tipo"] == "RECEBER"
        self.title("Não recebo mais daqui" if recebe else "Encerrar conta fixa")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Até quando entrou?" if recebe else "Até quando foi paga?",
                 bg=CORES["superficie"], fg=CORES["texto"], font=(FONTE, 16, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(topo, text=f"{self.rec['descricao']} —"
                            f" {services.moeda(self.rec['valor'])} por mês",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Último mês em que" + (" entrou" if recebe else " foi paga"),
                  style="Campo.TLabel").pack(anchor="w")
        self._meses = self._meses_possiveis()
        self.cb_mes = ttk.Combobox(corpo, state="readonly", width=28,
                                   values=[services.mes_nome(m).capitalize()
                                           for m in self._meses])
        self.cb_mes.current(len(self._meses) - 1)
        self.cb_mes.pack(anchor="w", pady=(4, 14))

        ttk.Label(corpo, text="Os meses até aí continuam no histórico, do jeito que foram"
                              f" {'recebidos' if recebe else 'pagos'}. Os meses seguintes que"
                              " ainda estão em aberto saem da lista.",
                  style="Dica.TLabel", wraplength=480, justify="left").pack(anchor="w",
                                                                            pady=(0, 16))

        botoes = ttk.Frame(corpo)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Encerrar", style="Perigo.TButton",
                   command=self.aplicar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 580, 380)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _meses_possiveis(self) -> list[str]:
        """Meses já lançados até o atual — não faz sentido encerrar no futuro."""
        atual = services.mes_atual()
        meses = sorted({t["competencia"] for t in db.query(
            "SELECT competencia FROM titulo WHERE recorrencia_id = ?", (self.recorrencia_id,))
            if t["competencia"] <= atual})
        return meses or [atual]

    def aplicar(self) -> None:
        ultimo = self._meses[self.cb_mes.current()]
        try:
            removidos = services.encerrar_recorrencia(self.recorrencia_id, ultimo_mes=ultimo)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        messagebox.showinfo(
            "Pronto",
            f"'{self.rec['descricao']}' vai até {services.mes_nome(ultimo)}.\n\n"
            f"{removidos} mês(es) seguinte(s) saíram da lista. O histórico continua.",
            parent=self)
        self.destroy()


# --------------------------------------------------------------------------- #
class JanelaEmprestimos(tk.Toplevel):
    """Dívidas ativas: empréstimos, financiamentos e o que mais você deve."""

    def __init__(self, master, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_mudar = ao_mudar
        self.title("Empréstimos e dívidas")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Empréstimos e dívidas", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Tudo o que você ainda deve, com o saldo devedor de cada dívida."
                            " Cada pagamento registrado aqui abate o valor.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w", justify="left").pack(fill="x", pady=(2, 0))
        self.lbl_total = tk.Label(topo, bg=CORES["superficie"], font=(FONTE, 13, "bold"),
                                  anchor="w")
        self.lbl_total.pack(fill="x", pady=(10, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        acoes = ttk.Frame(corpo)
        acoes.pack(fill="x", pady=(0, 12))
        ttk.Button(acoes, text="Registrar pagamento", style="Sucesso.TButton",
                   command=self.pagar).pack(side="left")
        ttk.Button(acoes, text="Nova dívida que já tenho", style="Primario.TButton",
                   command=self.nova_divida).pack(side="left", padx=8)
        ttk.Button(acoes, text="Novo empréstimo com parcelas",
                   command=self.novo).pack(side="left")
        ttk.Button(acoes, text="Ver parcelas", command=self.ver_parcelas).pack(side="left", padx=8)
        ttk.Button(acoes, text="Acertar saldo devedor", command=self.acertar).pack(side="left")
        ttk.Button(acoes, text="Apagar", style="Perigo.TButton",
                   command=self.excluir).pack(side="right")

        self.tabela = Tabela(corpo, [
            ("nome", "Dívida", 220, "w"),
            ("credor", "Com quem", 140, "w"),
            ("saldo", "Quanto ainda devo", 150, "e"),
            ("parcela", "Parcela", 110, "e"),
            ("andamento", "Parcelas", 100, "center"),
            ("juros", "Juros ao mês", 100, "center"),
            ("proxima", "Próximo vencimento", 140, "center"),
        ], on_duplo_clique=lambda _i: self.ver_parcelas(), altura=8)
        self.tabela.definir_texto_vazio(
            "Nenhuma dívida registrada. Use 'Nova dívida que já tenho' para cadastrar"
            " o que você deve hoje.")
        self.tabela.pack(fill="both", expand=True)

        self.lbl_detalhe = ttk.Label(corpo, style="Dica.TLabel", justify="left")
        self.lbl_detalhe.pack(anchor="w", pady=(10, 0))
        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(10, 0))

        self.recarregar()
        centralizar(self, 1180, 600)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        self.tabela.limpar()
        for divida in services.listar_dividas():
            self.tabela.inserir(
                (divida["nome"], divida["credor"] or "—",
                 services.moeda(divida["saldo"]),
                 services.moeda(divida["valor_parcela"]) if divida["valor_parcela"] else "—",
                 f"{divida['pagas']}/{divida['parcelas']}" if divida["parcelas"] else "—",
                 f"{divida['juros_mes_pct']:.2f}%" if divida["juros_mes_pct"] else "—",
                 services.para_br(divida["proxima"]) if divida["proxima"] else "—"),
                iid=divida["conta_id"], tags=("negativo",))
        self.tabela.finalizar()

        resumo = services.resumo_dividas()
        self.lbl_total.configure(
            text=f"Total que você deve hoje: {services.moeda(resumo['total'])}"
                 + (f"     ·     parcelas do mês: {services.moeda(resumo['parcela_mensal'])}"
                    if resumo["parcela_mensal"] else ""),
            fg=CORES["perigo"] if resumo["total"] > 0.005 else CORES["sucesso"])
        self.lbl_detalhe.configure(
            text="Dívidas sem parcelas cadastradas mostram só o saldo devedor — use"
                 " 'Registrar pagamento' a cada valor pago para ele ir baixando.")

    def _selecionada(self) -> dict | None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Dívidas", "Escolha antes uma dívida da lista.", parent=self)
            return None
        conta_id = int(item)
        return next((d for d in services.listar_dividas() if d["conta_id"] == conta_id), None)

    def nova_divida(self) -> None:
        DialogoNovaDivida(self, self._apos)

    def novo(self) -> None:
        DialogoEmprestimo(self, self._apos)

    def pagar(self) -> None:
        divida = self._selecionada()
        if divida:
            DialogoPagarDivida(self, divida, self._apos)

    def acertar(self) -> None:
        divida = self._selecionada()
        if divida:
            DialogoAcertarDivida(self, divida, self._apos)

    def ver_parcelas(self) -> None:
        divida = self._selecionada()
        if not divida:
            return
        if divida["emprestimo_id"] is None:
            messagebox.showinfo("Parcelas", "Esta dívida não tem um plano de parcelas"
                                            " cadastrado.", parent=self)
            return
        JanelaParcelas(self, divida["emprestimo_id"])

    def excluir(self) -> None:
        divida = self._selecionada()
        if not divida:
            return
        if divida["emprestimo_id"]:
            if not messagebox.askyesno(
                    "Apagar empréstimo",
                    "O empréstimo e todas as parcelas em aberto serão apagados.\n\nConfirma?",
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
                    f"Apagar '{divida['nome']}' e todos os lançamentos dela?\n\n"
                    "Use isto apenas se a dívida foi registrada por engano.", parent=self):
                return
            try:
                services.excluir_conta_com_lancamentos(divida["conta_id"])
            except services.RegraNegocioError as erro:
                messagebox.showwarning("Não é possível apagar", str(erro), parent=self)
                return
        self._apos()

    def _apos(self) -> None:
        self.recarregar()
        self.ao_mudar()


class DialogoNovaDivida(tk.Toplevel):
    """Cadastra uma dívida que já existe, pelo saldo devedor de hoje."""

    def __init__(self, master, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.ao_salvar = ao_salvar
        self.title("Nova dívida")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="O que você deve hoje?", style="Secao.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text="Para dívidas que já existem: informe apenas quanto falta pagar."
                              " Nada é lançado como dinheiro recebido.",
                  style="Dica.TLabel", wraplength=440, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 14))

        ttk.Label(corpo, text="Nome da dívida", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.var_nome = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_nome, width=44).grid(
            row=3, column=0, columnspan=2, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Com quem (banco, financeira, pessoa)",
                  style="Campo.TLabel").grid(row=4, column=0, sticky="w")
        self.var_credor = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_credor, width=44).grid(
            row=5, column=0, columnspan=2, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Quanto ainda devo (R$)", style="Campo.TLabel").grid(
            row=6, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=7, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Desde quando", style="Campo.TLabel").grid(row=6, column=1,
                                                                        sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=7, column=1, sticky="w", pady=(4, 14))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=8, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Cadastrar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 560, 420)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            services.criar_divida(self.var_nome.get(), self.var_credor.get(),
                                  self.cp_valor.get_valor(), self.dt_data.get_iso())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


class DialogoPagarDivida(tk.Toplevel):
    def __init__(self, master, divida: dict, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.divida = divida
        self.ao_salvar = ao_salvar
        self.title("Registrar pagamento")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=f"Pagamento — {divida['nome']}", style="Secao.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text=f"Você ainda deve {services.moeda(divida['saldo'])}",
                  style="Dica.TLabel").grid(row=1, column=0, columnspan=2, sticky="w",
                                            pady=(2, 14))

        ttk.Label(corpo, text="Quanto pagou (R$)", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        if divida["valor_parcela"]:
            self.cp_valor.set_valor(divida["valor_parcela"])
        self.cp_valor.grid(row=3, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Quando", style="Campo.TLabel").grid(row=2, column=1, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=3, column=1, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="De qual conta saiu", style="Campo.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("ATIVO",), width=44)
        self.sel_conta.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Quanto disso foi juros (opcional)",
                  style="Campo.TLabel").grid(row=6, column=0, sticky="w")
        self.cp_juros = CampoValor(corpo, width=16)
        self.cp_juros.grid(row=7, column=0, sticky="w", pady=(4, 10))
        ttk.Label(corpo, text="Os juros viram despesa; o restante abate a dívida.",
                  style="Dica.TLabel").grid(row=7, column=1, sticky="w", pady=(4, 10))

        # Mostra na hora quanto ainda vai faltar: é o que a pessoa quer saber ao
        # pagar só um pedaço da dívida.
        self.lbl_previsao = ttk.Label(corpo, style="Secao.TLabel", wraplength=520,
                                      justify="left")
        self.lbl_previsao.grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 10))
        self.cp_valor.ao_mudar(self._prever)
        self.cp_juros.ao_mudar(self._prever)
        self._prever()

        botoes = ttk.Frame(corpo)
        botoes.grid(row=9, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(botoes, text="Registrar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)
        ttk.Button(botoes, text="Pagar tudo o que falta",
                   command=self._pagar_tudo).pack(side="right", padx=8)

        centralizar(self, 640, 520)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _valores(self) -> tuple[float, float]:
        valor = self.cp_valor.get_valor() if self.cp_valor.var.get().strip() else 0.0
        juros = self.cp_juros.get_valor() if self.cp_juros.var.get().strip() else 0.0
        return valor, juros

    def _prever(self) -> None:
        try:
            valor, juros = self._valores()
        except services.RegraNegocioError:
            return
        abate = round(valor - juros, 2)
        falta = round(self.divida["saldo"] - abate, 2)
        if abate <= 0:
            self.lbl_previsao.configure(
                text="Informe quanto você pagou para ver quanto ainda vai faltar.",
                foreground=CORES["texto_suave"])
        elif falta > 0.005:
            self.lbl_previsao.configure(
                text=f"Abate {services.moeda(abate)} — ainda vão faltar"
                     f" {services.moeda(falta)}.", foreground=CORES["texto"])
        elif falta >= -0.005:
            self.lbl_previsao.configure(
                text="Isto paga a dívida inteira. Ao registrar, ela será encerrada e entra"
                     " no histórico de dívidas quitadas.", foreground=CORES["sucesso"])
        else:
            self.lbl_previsao.configure(
                text=f"Este valor passa {services.moeda(abs(falta))} do que você deve"
                     f" ({services.moeda(self.divida['saldo'])}).",
                foreground=CORES["perigo"])

    def _pagar_tudo(self) -> None:
        self.cp_juros.limpar()
        self.cp_valor.set_valor(self.divida["saldo"])
        self._prever()

    def salvar(self) -> None:
        try:
            conta = self.sel_conta.get_conta_id()
            if conta is None:
                raise services.RegraNegocioError("Escolha a conta de onde saiu o dinheiro.")
            valor, juros = self._valores()
            data = self.dt_data.get_iso()
            abate = round(valor - juros, 2)
            saldo = round(self.divida["saldo"], 2)
            if abate > saldo + 0.005:
                raise services.RegraNegocioError(
                    f"Você deve {services.moeda(saldo)} e está abatendo"
                    f" {services.moeda(abate)}. Corrija o valor — pagar mais do que se deve"
                    " não abate dívida nenhuma.")
            # Pagou tudo: encerra pelo caminho da quitação, para a dívida entrar
            # no histórico em vez de ficar zerada e solta na lista.
            if abate >= saldo - 0.005:
                services.quitar_divida(self.divida["conta_id"], "PAGAMENTO", conta, data,
                                       juros=juros)
                quitou = True
            else:
                services.pagar_divida(self.divida["conta_id"], valor, conta, data, juros)
                quitou = False
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        if quitou:
            messagebox.showinfo(
                "Dívida quitada",
                f"'{self.divida['nome']}' foi paga por inteiro e entrou no histórico"
                " (botão 'Dívidas quitadas').", parent=self.master)
        self.destroy()


class DialogoAcertarDivida(tk.Toplevel):
    """Corrige quanto se deve. Não é pagamento: nada sai de conta nenhuma."""

    def __init__(self, master, divida: dict, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.divida = divida
        self.ao_salvar = ao_salvar
        self.title("Alterar o valor da dívida")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=f"Alterar o valor — {divida['nome']}",
                  style="Secao.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text=f"O sistema tem {services.moeda(divida['saldo'])}."
                              " Informe o valor que o credor diz que você deve — juros,"
                              " correção ou renegociação.\n\nIsto não é pagamento: nada sai"
                              " da sua conta. Para encerrar a dívida use 'Quitar dívida'.",
                  style="Dica.TLabel", wraplength=420, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 14))

        ttk.Label(corpo, text="Devo hoje (R$)", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.set_valor(divida["saldo"])
        self.cp_valor.grid(row=3, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Nesta data", style="Campo.TLabel").grid(row=2, column=1,
                                                                      sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=3, column=1, sticky="w", pady=(4, 14))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Alterar valor", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 580, 380)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def salvar(self) -> None:
        try:
            services.alterar_valor_divida(self.divida["conta_id"], self.cp_valor.get_valor(),
                                          self.dt_data.get_iso())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        self.destroy()


class DialogoQuitarDivida(tk.Toplevel):
    """Encerra a dívida: zera o saldo e guarda a linha no histórico."""

    def __init__(self, master, divida: dict, ao_salvar):
        super().__init__(master)
        self.transient(master)
        self.divida = divida
        self.ao_salvar = ao_salvar
        self.title("Quitar dívida")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=f"Quitar — {divida['nome']}", style="Secao.TLabel").pack(anchor="w")
        ttk.Label(corpo, text=f"Falta {services.moeda(divida['saldo'])}. Ao quitar, a dívida"
                              " zera, sai da lista e entra no histórico de dívidas quitadas.",
                  style="Dica.TLabel", wraplength=460, justify="left").pack(anchor="w",
                                                                           pady=(2, 14))

        self.var_forma = tk.StringVar(value="PAGAMENTO")
        ttk.Radiobutton(corpo, text="Paguei o que faltava", value="PAGAMENTO",
                        variable=self.var_forma, command=self._ajustar).pack(anchor="w")
        ttk.Radiobutton(corpo, text="Foi perdoada / baixada sem eu pagar", value="PERDAO",
                        variable=self.var_forma, command=self._ajustar).pack(anchor="w",
                                                                             pady=(2, 12))

        self.area_pagamento = ttk.Frame(corpo)
        self.area_pagamento.pack(fill="x")
        ttk.Label(self.area_pagamento, text="De qual conta saiu",
                  style="Campo.TLabel").pack(anchor="w")
        self.sel_conta = SeletorConta(self.area_pagamento, tipos=("ATIVO",), width=44)
        self.sel_conta.pack(anchor="w", pady=(4, 10))

        linha = ttk.Frame(corpo)
        linha.pack(fill="x", pady=(4, 12))
        ttk.Label(linha, text="Quando", style="Campo.TLabel").pack(side="left")
        self.dt_data = CampoData(linha, services.hoje_iso())
        self.dt_data.pack(side="left", padx=10)

        ttk.Label(corpo, text="Observação (opcional)", style="Campo.TLabel").pack(anchor="w")
        self.var_obs = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_obs).pack(fill="x", pady=(4, 14))

        botoes = ttk.Frame(corpo)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Quitar", style="Sucesso.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 600, 520)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _ajustar(self) -> None:
        """Perdoada não tem conta de onde sai o dinheiro."""
        if self.var_forma.get() == "PAGAMENTO":
            self.area_pagamento.pack(fill="x", before=self.dt_data.master)
        else:
            self.area_pagamento.pack_forget()

    def salvar(self) -> None:
        forma = self.var_forma.get()
        try:
            conta = self.sel_conta.get_conta_id() if forma == "PAGAMENTO" else None
            resultado = services.quitar_divida(
                self.divida["conta_id"], forma, conta, self.dt_data.get_iso(),
                observacao=self.var_obs.get())
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.ao_salvar()
        messagebox.showinfo(
            "Dívida quitada",
            f"'{self.divida['nome']}' foi quitada: {services.moeda(resultado['valor'])}.\n\n"
            "Ela saiu da lista e está no histórico (botão 'Dívidas quitadas').",
            parent=self.master)
        self.destroy()


class JanelaExtratoDivida(tk.Toplevel):
    """Tudo o que já mexeu numa dívida: pagamentos e correções, separados."""

    def __init__(self, master, divida: dict):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.divida = divida
        self.title(f"Extrato — {divida['nome']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text=divida["nome"], bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text=f"Você ainda deve {services.moeda(divida['saldo'])}"
                            f"  ·  com {divida['credor'] or 'sem credor informado'}",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        filtros = ttk.Frame(corpo)
        filtros.pack(fill="x", pady=(0, 8))
        ttk.Label(filtros, text="Mostrar:", style="Campo.TLabel").pack(side="left")
        self.cb_tipo = ttk.Combobox(filtros, state="readonly", width=22,
                                    values=["Tudo", "Só pagamentos", "Só correções de valor"])
        self.cb_tipo.set("Tudo")
        self.cb_tipo.pack(side="left", padx=8)
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        self.lbl_resumo = ttk.Label(filtros, style="Dica.TLabel")
        self.lbl_resumo.pack(side="left", padx=14)

        self.tabela = Tabela(corpo, [
            ("data", "Quando", 100, "center"),
            ("tipo", "O que foi", 150, "w"),
            ("historico", "Descrição", 280, "w"),
            ("conta", "Saiu da conta", 150, "w"),
            ("valor", "Valor", 120, "e"),
            ("saldo", "Dívida depois", 130, "e"),
        ], largura_livre=True, altura=10)
        self.tabela.definir_texto_vazio("Nenhum movimento nesta dívida ainda.")
        self.tabela.pack(fill="both", expand=True)

        self.paginacao = Paginacao(corpo, self._desenhar, por_pagina=10, fundo="TFrame",
                                   nome_itens="movimentos")
        self.paginacao.pack(fill="x", pady=(8, 0))
        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(12, 0))

        self.recarregar()
        centralizar(self, 1080, 620)
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        movimentos = services.extrato_da_divida(self.divida["conta_id"])
        pago = round(sum(m["valor"] for m in movimentos if m["tipo"] == "Pagamento"), 2)
        escolha = self.cb_tipo.get()
        if escolha == "Só pagamentos":
            movimentos = [m for m in movimentos if m["tipo"] == "Pagamento"]
        elif escolha == "Só correções de valor":
            movimentos = [m for m in movimentos if "Correção" in m["tipo"]
                          or m["tipo"] == "Aumentou o valor"]
        self.lbl_resumo.configure(text=f"já pago de verdade: {services.moeda(pago)}")
        self.paginacao.definir(movimentos)

    def _desenhar(self, movimentos: list) -> None:
        self.tabela.limpar()
        for indice, mov in enumerate(movimentos):
            sinal = "+" if mov["aumentou"] else "−"
            self.tabela.inserir(
                (services.para_br(mov["data"]), mov["tipo"], mov["historico"],
                 mov["conta_dinheiro"] or "—",
                 f"{sinal} {services.moeda(mov['valor'])}",
                 services.moeda(mov["saldo_depois"])),
                iid=f"{mov['lancamento_id']}-{indice}",
                tags=("negativo",) if mov["aumentou"] else ("positivo",))
        self.tabela.finalizar()


class JanelaDividasQuitadas(tk.Toplevel):
    """Histórico do que já terminou de pagar."""

    def __init__(self, master, ao_mudar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_mudar = ao_mudar
        self.title("Dívidas quitadas")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Dívidas quitadas", bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="O que você já terminou de pagar. Nada aqui entra nas contas do"
                            " mês: é só a memória de cada dívida encerrada.",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 10),
                 anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        filtros = ttk.Frame(corpo)
        filtros.pack(fill="x", pady=(0, 10))
        ttk.Label(filtros, text="Procurar:", style="Campo.TLabel").pack(side="left")
        self.var_texto = tk.StringVar()
        entrada = ttk.Entry(filtros, textvariable=self.var_texto, width=28)
        entrada.pack(side="left", padx=8)
        entrada.bind("<KeyRelease>", lambda _e: self.recarregar())
        ttk.Label(filtros, text="Como terminou:", style="Campo.TLabel").pack(side="left",
                                                                            padx=(14, 0))
        self.cb_forma = ttk.Combobox(filtros, state="readonly", width=26,
                                     values=["Todas", *services.FORMAS_QUITACAO.values()])
        self.cb_forma.set("Todas")
        self.cb_forma.pack(side="left", padx=8)
        self.cb_forma.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        ttk.Button(filtros, text="Reabrir a dívida escolhida",
                   command=self.reabrir).pack(side="right")

        self.tabela = Tabela(corpo, [
            ("data", "Quitada em", 110, "center"),
            ("nome", "Dívida", 230, "w"),
            ("credor", "Com quem", 150, "w"),
            ("valor", "Quanto faltava", 130, "e"),
            ("forma", "Como terminou", 200, "w"),
            ("conta", "Saiu da conta", 150, "w"),
            ("observacao", "Observação", 200, "w"),
        ], largura_livre=True, altura=8)
        self.tabela.definir_texto_vazio("Nenhuma dívida quitada por aqui ainda.")
        self.tabela.pack(fill="both", expand=True)

        self.paginacao = Paginacao(corpo, self._desenhar, por_pagina=10,
                                   fundo="TFrame", nome_itens="dívidas")
        self.paginacao.pack(fill="x", pady=(8, 0))
        self.lbl_total = ttk.Label(corpo, style="Secao.TLabel")
        self.lbl_total.pack(anchor="w", pady=(8, 0))

        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(12, 0))
        self.recarregar()
        centralizar(self, 1180, 620)
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        itens = services.listar_dividas_quitadas(self.var_texto.get())
        escolha = self.cb_forma.get()
        if escolha != "Todas":
            itens = [i for i in itens if i["forma_texto"] == escolha]
        self.paginacao.definir(itens)
        total = round(sum(i["valor"] for i in itens), 2)
        self.lbl_total.configure(
            text=f"{len(itens)} dívida(s) quitada(s) · {services.moeda(total)} no total",
            foreground=CORES["sucesso"])

    def _desenhar(self, itens: list) -> None:
        self.tabela.limpar()
        for item in itens:
            self.tabela.inserir(
                (services.para_br(item["data"]), item["nome"], item["credor"] or "—",
                 services.moeda(item["valor"]), item["forma_texto"],
                 item["conta_dinheiro_nome"] or "—", item["observacao"] or ""),
                iid=item["id"], tags=("quitado",))
        self.tabela.finalizar()

    def reabrir(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            messagebox.showinfo("Dívidas quitadas", "Escolha antes uma linha da lista.",
                                parent=self)
            return
        if not messagebox.askyesno(
                "Reabrir dívida",
                "A dívida volta para a lista com o valor que tinha e o registro do"
                " pagamento é desfeito.\n\nConfirma?", parent=self):
            return
        try:
            services.desfazer_quitacao(int(item))
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.recarregar()
        self.ao_mudar()


class DialogoEmprestimo(tk.Toplevel):
    def __init__(self, master, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.ao_salvar = ao_salvar
        self.title("Novo empréstimo")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Quanto você pegou emprestado?", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Informe o valor, os juros e o número de parcelas. O sistema faz o"
                            " resto.", bg=CORES["superficie"], fg=CORES["texto_suave"],
                 font=(FONTE, 10), anchor="w").pack(fill="x", pady=(2, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(2, weight=1)

        ttk.Label(corpo, text="Descrição", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        self.var_desc = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_desc, width=60).grid(
            row=1, column=0, columnspan=3, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Com quem (banco, pessoa)", style="Campo.TLabel").grid(
            row=2, column=0, sticky="w")
        self.var_credor = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_credor, width=60).grid(
            row=3, column=0, columnspan=3, sticky="we", pady=(4, 14))

        ttk.Label(corpo, text="Valor pego (R$)", style="Campo.TLabel").grid(
            row=4, column=0, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.grid(row=5, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Juros ao mês (%)", style="Campo.TLabel").grid(
            row=4, column=1, sticky="w")
        self.var_juros = tk.StringVar(value="2")
        ttk.Spinbox(corpo, from_=0, to=100, increment=0.1, width=8,
                    textvariable=self.var_juros).grid(row=5, column=1, sticky="w",
                                                      pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="Em quantas vezes", style="Campo.TLabel").grid(
            row=4, column=2, sticky="w")
        self.var_parcelas = tk.IntVar(value=12)
        ttk.Spinbox(corpo, from_=1, to=480, width=8, textvariable=self.var_parcelas).grid(
            row=5, column=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Primeira parcela vence em", style="Campo.TLabel").grid(
            row=6, column=0, sticky="w")
        self.dt_primeira = CampoData(corpo, services.hoje_iso())
        self.dt_primeira.grid(row=7, column=0, sticky="w", pady=(4, 14), padx=(0, 16))

        ttk.Label(corpo, text="O dinheiro entrou em", style="Campo.TLabel").grid(
            row=6, column=1, columnspan=2, sticky="w")
        self.sel_conta = SeletorConta(corpo, tipos=("ATIVO",), permitir_vazio=True, width=34)
        self.sel_conta.grid(row=7, column=1, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(corpo, text="Deixe em branco se o dinheiro não passou pela sua conta"
                              " (ex.: financiamento de um bem).",
                  style="Dica.TLabel", wraplength=560, justify="left").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.lbl_previa = ttk.Label(corpo, style="SecaoSuperficie.TLabel",
                                    background=CORES["fundo"], wraplength=560, justify="left")
        self.lbl_previa.grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 12))
        for var in (self.var_juros, self.var_parcelas):
            var.trace_add("write", lambda *_a: self._simular())
        self.cp_valor.ao_mudar(self._simular)

        botoes = ttk.Frame(corpo)
        botoes.grid(row=10, column=0, columnspan=3, sticky="e")
        ttk.Button(botoes, text="Criar", style="Primario.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 660, 620)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _simular(self) -> None:
        try:
            valor = self.cp_valor.get_valor()
            juros = services.para_float(self.var_juros.get() or "0")
            parcelas = int(self.var_parcelas.get())
            plano = services.tabela_price(valor, juros, parcelas)
        except (services.RegraNegocioError, ValueError, tk.TclError):
            self.lbl_previa.configure(text="")
            return
        total = round(sum(p["total"] for p in plano), 2)
        self.lbl_previa.configure(
            text=f"{parcelas}x de {services.moeda(plano[0]['total'])}   ·   "
                 f"total a pagar {services.moeda(total)}   ·   "
                 f"juros {services.moeda(total - valor)}",
            foreground=CORES["texto"])

    def salvar(self) -> None:
        try:
            primeira = self.dt_primeira.get_iso()
            services.criar_emprestimo(
                self.var_desc.get(), self.var_credor.get(), self.cp_valor.get_valor(),
                services.para_float(self.var_juros.get() or "0"), int(self.var_parcelas.get()),
                primeira[:7], int(primeira[8:10]), self.sel_conta.get_conta_id(), primeira)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Falta uma informação", str(erro), parent=self)
            return
        self.ao_salvar()
        messagebox.showinfo("Pronto", "Empréstimo criado. As parcelas já estão na tela"
                                      " Contas a Pagar.", parent=self)
        self.destroy()


class JanelaParcelas(tk.Toplevel):
    def __init__(self, master, emprestimo_id: int):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        emp = db.query_one("SELECT * FROM emprestimo WHERE id = ?", (emprestimo_id,))
        self.title(f"Parcelas — {emp['descricao']}")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text=emp["descricao"], bg=CORES["superficie"], fg=CORES["texto"],
                 font=(FONTE, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text=f"{emp['parcelas']}x de {services.moeda(emp['valor_parcela'])}"
                            f"  ·  juros de {emp['juros_mes_pct']:.2f}% ao mês"
                            f"  ·  valor pego {services.moeda(emp['valor_contratado'])}",
                 bg=CORES["superficie"], fg=CORES["texto_suave"], font=(FONTE, 11),
                 anchor="w").pack(fill="x", pady=(4, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Cada parcela é parte juros e parte abatimento da dívida."
                              " O pagamento é feito na tela Contas a Pagar.",
                  style="Dica.TLabel").pack(anchor="w", pady=(0, 10))

        self.emprestimo_id = emprestimo_id
        filtros = ttk.Frame(corpo)
        filtros.pack(fill="x", pady=(0, 8))
        ttk.Label(filtros, text="Mostrar:", style="Campo.TLabel").pack(side="left")
        self.cb_situacao = ttk.Combobox(filtros, state="readonly", width=16,
                                        values=["Todas", "Em aberto", "Pagas", "Atrasadas"])
        self.cb_situacao.set("Todas")
        self.cb_situacao.pack(side="left", padx=8)
        self.cb_situacao.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        self.lbl_resumo = ttk.Label(filtros, style="Dica.TLabel")
        self.lbl_resumo.pack(side="left", padx=14)

        self.tabela = Tabela(corpo, [
            ("numero", "Nº", 60, "center"),
            ("venc", "Vence em", 110, "center"),
            ("juros", "Juros", 120, "e"),
            ("amortizacao", "Abate da dívida", 140, "e"),
            ("total", "Parcela", 120, "e"),
            ("saldo", "Falta depois dela", 140, "e"),
            ("situacao", "Situação", 120, "center"),
        ], altura=10)
        self.tabela.pack(fill="both", expand=True)
        self.paginacao = Paginacao(corpo, self._desenhar, por_pagina=10, fundo="TFrame",
                                   nome_itens="parcelas")
        self.paginacao.pack(fill="x", pady=(8, 0))

        self.recarregar()
        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(12, 0))
        centralizar(self, 940, 640)
        self.bind("<Escape>", lambda _e: self.destroy())

    def recarregar(self) -> None:
        hoje = services.hoje_iso()
        parcelas = list(services.parcelas_do_emprestimo(self.emprestimo_id))
        escolha = self.cb_situacao.get()
        if escolha == "Em aberto":
            filtradas = [p for p in parcelas if p["status"] == "ABERTO"]
        elif escolha == "Pagas":
            filtradas = [p for p in parcelas if p["status"] == "QUITADO"]
        elif escolha == "Atrasadas":
            filtradas = [p for p in parcelas
                         if p["status"] == "ABERTO" and p["vencimento"] < hoje]
        else:
            filtradas = parcelas

        pagas = sum(1 for p in parcelas if p["status"] == "QUITADO")
        falta = round(sum(float(p["total"]) for p in parcelas if p["status"] == "ABERTO"), 2)
        self.lbl_resumo.configure(text=f"{pagas} de {len(parcelas)} paga(s) · faltam"
                                       f" {services.moeda(falta)}")
        self.paginacao.definir(filtradas)

    def _desenhar(self, parcelas: list) -> None:
        hoje = services.hoje_iso()
        self.tabela.limpar()
        for p in parcelas:
            situacao = {"QUITADO": "Paga", "CANCELADO": "Cancelada"}.get(p["status"], "Em aberto")
            atrasada = p["status"] == "ABERTO" and p["vencimento"] < hoje
            if atrasada:
                situacao = "Atrasada"
            self.tabela.inserir(
                (p["numero"], services.para_br(p["vencimento"]), services.moeda(p["juros"]),
                 services.moeda(p["amortizacao"]), services.moeda(p["total"]),
                 services.moeda(p["saldo_depois"]), situacao),
                iid=p["numero"],
                tags=("quitado",) if p["status"] == "QUITADO"
                else ("vencido",) if atrasada else ())
        self.tabela.finalizar()


# --------------------------------------------------------------------------- #
class DialogoBaixa(tk.Toplevel):
    def __init__(self, master, titulo_id: int, ao_salvar):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.titulo_id = titulo_id
        self.ao_salvar = ao_salvar
        self.titulo = db.query_one("SELECT * FROM titulo WHERE id = ?", (titulo_id,))
        pagar = self.titulo["tipo"] == "PAGAR"
        self.title("Marcar como pago" if pagar else "Marcar como recebido")
        self.configure(bg=CORES["fundo"])
        self.resizable(False, False)

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=16)
        topo.pack(fill="x")
        tk.Label(topo, text="Você já pagou esta conta?" if pagar
                            else "Você já recebeu este valor?",
                 bg=CORES["superficie"], fg=CORES["texto"], font=(FONTE, 16, "bold"),
                 anchor="w").pack(fill="x")
        self.encargos = services.encargos_do_titulo(self.titulo)
        resumo = f"{self.titulo['descricao']} — {services.moeda(self.titulo['valor'])}"
        tk.Label(topo, text=resumo, bg=CORES["superficie"], fg=CORES["texto_suave"],
                 font=(FONTE, 11), anchor="w").pack(fill="x", pady=(4, 0))
        if self.encargos["total"] > 0.005:
            detalhe = (f"Atrasada há {self.encargos['dias']} dia(s):"
                       f" multa {services.moeda(self.encargos['multa'])}"
                       f" + juros {services.moeda(self.encargos['juros'])}"
                       f"  →  total hoje {services.moeda(self.encargos['valor_atualizado'])}")
            tk.Label(topo, text=detalhe, bg=CORES["superficie"], fg=CORES["perigo"],
                     font=(FONTE, 10, "bold"), anchor="w").pack(fill="x", pady=(6, 0))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Em que dia?", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        self.dt_data = CampoData(corpo, services.hoje_iso())
        self.dt_data.grid(row=1, column=0, sticky="w", pady=(4, 16), padx=(0, 20))

        ttk.Label(corpo, text="Valor efetivo (R$)", style="Campo.TLabel").grid(
            row=0, column=1, sticky="w")
        self.cp_valor = CampoValor(corpo, width=16)
        self.cp_valor.set_valor(self.encargos["valor_atualizado"])
        self.cp_valor.grid(row=1, column=1, sticky="w", pady=(4, 16))

        ttk.Label(corpo, text="De qual conta saiu o dinheiro?" if pagar
                              else "Em qual conta o dinheiro entrou?",
                  style="Campo.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text="Conta corrente, carteira, poupança ou cartão.",
                  style="Dica.TLabel").grid(row=3, column=0, columnspan=2, sticky="w")
        self.sel_caixa = SeletorConta(corpo, tipos=("ATIVO", "PASSIVO"), width=56)
        self.sel_caixa.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 12))
        if self.titulo["conta_pagamento_id"]:
            # A conta escolhida no cadastro já vem preenchida.
            self.sel_caixa.set_conta_id(self.titulo["conta_pagamento_id"])
        else:
            for conta in services.listar_contas(apenas_ativas=True, apenas_analiticas=True):
                if conta["codigo"].startswith("1.1.02"):
                    self.sel_caixa.set_conta_id(conta["id"])
                    break

        # --- pagamento parcial ------------------------------------------
        self.quadro_parcial = ttk.Frame(corpo, style="Superficie.TFrame", padding=12)
        self.quadro_parcial.configure(relief="solid", borderwidth=1)
        self.quadro_parcial.grid(row=5, column=0, columnspan=2, sticky="we", pady=(0, 12))
        self.lbl_parcial = ttk.Label(self.quadro_parcial, style="CampoSuperficie.TLabel",
                                     wraplength=520, justify="left")
        self.lbl_parcial.pack(anchor="w")
        self.var_resto = tk.StringVar(value="aberto")
        ttk.Radiobutton(self.quadro_parcial, variable=self.var_resto, value="aberto",
                        style="Superficie.TRadiobutton", command=self._ajustar_parcial,
                        text="Ainda devo o resto: criar uma conta com o que faltou").pack(
            anchor="w", pady=(8, 0))
        ttk.Radiobutton(self.quadro_parcial, variable=self.var_resto, value="quitado",
                        style="Superficie.TRadiobutton", command=self._ajustar_parcial,
                        text="Foi desconto ou acordo: considerar a conta quitada").pack(
            anchor="w")
        self.linha_venc = ttk.Frame(self.quadro_parcial, style="Superficie.TFrame")
        ttk.Label(self.linha_venc, text="O que faltou vence em",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.dt_saldo = CampoData(self.linha_venc, self.titulo["vencimento"])
        self.dt_saldo.pack(side="left", padx=8)
        self.quadro_parcial.grid_remove()

        # Conferência do valor: o que foi combinado nem sempre é o que caiu na
        # conta (salário com hora extra, desconto, reajuste). A diferença tem de
        # saltar aos olhos antes de confirmar.
        self.lbl_conferencia = ttk.Label(corpo, style="Secao.TLabel", wraplength=560,
                                         justify="left")
        self.lbl_conferencia.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(corpo, text="Ao confirmar, este valor entra automaticamente na lista de"
                              " Entradas e Saídas.", style="Dica.TLabel").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(0, 16))

        self._parcial_visivel: bool | None = None
        self.cp_valor.ao_mudar(self._ao_mudar_valor)

        botoes = ttk.Frame(corpo)
        botoes.grid(row=8, column=0, columnspan=2, sticky="e")
        ttk.Button(botoes, text="Confirmar", style="Sucesso.TButton",
                   command=self.confirmar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        centralizar(self, 660, 460)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())
        self._ao_mudar_valor()   # já abre avisando se o valor sugerido é parcial

    # ------------------------------------------------------------------ #
    def _devido(self) -> float:
        """Quanto falta pagar hoje, já com multa e juros se houver atraso."""
        return services.encargos_do_titulo(self.titulo,
                                           ate=self.dt_data.get_iso())["valor_atualizado"]

    def _ao_mudar_valor(self) -> None:
        self._conferir_parcial()
        self._conferir_valor()

    def _conferir_valor(self) -> None:
        """Compara o valor digitado com o previsto e avisa a diferença."""
        recebe = self.titulo["tipo"] == "RECEBER"
        try:
            informado = self.cp_valor.get_valor()
            previsto = self._devido()
        except services.RegraNegocioError:
            self.lbl_conferencia.configure(text="")
            return
        diferenca = round(informado - previsto, 2)
        if abs(diferenca) < 0.005:
            self.lbl_conferencia.configure(
                text=f"Confere com o previsto: {services.moeda(previsto)}.",
                foreground=CORES["texto_suave"])
        elif diferenca > 0:
            self.lbl_conferencia.configure(
                text=(f"{services.moeda(diferenca)} A MAIS que o previsto"
                      f" ({services.moeda(previsto)})."
                      + ("  Entrou mais do que o combinado?" if recebe
                         else "  Pagou mais do que devia?")),
                foreground=CORES["sucesso"] if recebe else CORES["alerta"])
        else:
            self.lbl_conferencia.configure(
                text=(f"{services.moeda(abs(diferenca))} A MENOS que o previsto"
                      f" ({services.moeda(previsto)})."
                      + ("  Recebeu menos do que o combinado?" if recebe else "")),
                foreground=CORES["alerta"] if recebe else CORES["texto"])

    def _conferir_parcial(self) -> None:
        """Mostra as opções de saldo quando o valor digitado é menor que o devido."""
        try:
            pago = self.cp_valor.get_valor()
            devido = self._devido()
        except services.RegraNegocioError:
            pago, devido = 0.0, 0.0
        falta = round(devido - pago, 2)
        mostrar = pago > 0.005 and falta > 0.005
        if mostrar:
            self.lbl_parcial.configure(
                text=f"Você está pagando {services.moeda(pago)} de"
                     f" {services.moeda(devido)} — faltam {services.moeda(falta)}.")
        # A janela só é redimensionada quando o quadro aparece ou some — nunca
        # a cada tecla, o que travava a digitação.
        if mostrar == self._parcial_visivel:
            return
        self._parcial_visivel = mostrar
        if mostrar:
            self.quadro_parcial.grid()
            self._ajustar_parcial()
        else:
            self.quadro_parcial.grid_remove()
            self._ajustar_altura()

    def _ajustar_parcial(self) -> None:
        if self.var_resto.get() == "aberto":
            self.linha_venc.pack(anchor="w", pady=(8, 0))
        else:
            self.linha_venc.pack_forget()
        self._ajustar_altura()

    def _ajustar_altura(self) -> None:
        """A janela cresce quando as opções de saldo aparecem, para não cortar
        os botões de confirmar e cancelar."""
        self.update_idletasks()
        altura = max(self.winfo_reqheight(), 400)
        limite = self.winfo_screenheight() - 80
        largura = max(self.winfo_width(), self.winfo_reqwidth())
        self.geometry(f"{largura}x{min(altura, limite)}")

    def _confirmar_valor(self, pago: float, data: str, caixa_id: int) -> bool:
        """Pergunta se o valor é esse mesmo — sempre, antes de registrar."""
        recebe = self.titulo["tipo"] == "RECEBER"
        previsto = self._devido()
        diferenca = round(pago - previsto, 2)
        conta = services.obter_conta(caixa_id)

        linhas = [f"{self.titulo['descricao']}",
                  "",
                  f"Previsto:   {services.moeda(previsto)}",
                  f"{'Recebido' if recebe else 'Pago'}:   {services.moeda(pago)}"]
        if abs(diferenca) >= 0.005:
            lado = "a mais" if diferenca > 0 else "a menos"
            linhas.append(f"Diferença:  {services.moeda(abs(diferenca))} {lado}")
        linhas += ["",
                   f"{'Entra em' if recebe else 'Sai de'}: {conta['nome'] if conta else '—'}",
                   f"Data: {services.para_br(data)}",
                   "",
                   "Foi esse valor mesmo?"]
        return messagebox.askyesno("Confirme o valor", "\n".join(linhas), parent=self)

    def _oferecer_novo_valor_fixo(self, pago: float) -> None:
        """Conta fixa que mudou de valor: pergunta se vale para os próximos meses."""
        if not self.titulo["recorrencia_id"]:
            return
        if abs(round(pago - float(self.titulo["valor"]), 2)) < 0.005:
            return
        competencia = self.titulo["competencia"] or self.titulo["vencimento"][:7]
        recebe = self.titulo["tipo"] == "RECEBER"
        if not messagebox.askyesno(
                "Vale para os próximos meses?",
                f"'{self.titulo['descricao']}' é uma conta fixa de"
                f" {services.moeda(self.titulo['valor'])} e desta vez"
                f" {'entrou' if recebe else 'saiu'} {services.moeda(pago)}.\n\n"
                "Os próximos meses passam a usar o valor novo?\n\n"
                "(Responda não se foi coisa de um mês só.)", parent=self.master):
            return
        try:
            atingidos = services.aplicar_reajuste(self.titulo["recorrencia_id"],
                                                  competencia, pago)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self.master)
            return
        messagebox.showinfo(
            "Valor atualizado",
            f"{atingidos} mês(es) em aberto passaram a usar {services.moeda(pago)}."
            " Os meses já pagos não mudaram.", parent=self.master)

    def confirmar(self) -> None:
        try:
            caixa_id = self.sel_caixa.get_conta_id()
            if caixa_id is None:
                raise services.RegraNegocioError("Escolha a conta usada no pagamento.")
            pago = self.cp_valor.get_valor()
            data = self.dt_data.get_iso()
            if not self._confirmar_valor(pago, data, caixa_id):
                return                      # volta para o formulário, nada é registrado
            falta = round(self._devido() - pago, 2)
            parcial = falta > 0.005 and self.var_resto.get() == "aberto"
            services.baixar_titulo(
                self.titulo_id, data, pago, caixa_id,
                saldo_em_aberto=parcial,
                vencimento_do_saldo=self.dt_saldo.get_iso() if parcial else None)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível concluir", str(erro), parent=self)
            return
        self.ao_salvar()
        if parcial:
            messagebox.showinfo(
                "Pagamento parcial registrado",
                f"Foram pagos {services.moeda(pago)}.\n\n"
                f"O que faltou ({services.moeda(falta)}) virou uma nova conta a pagar,"
                f" com vencimento em {services.para_br(self.dt_saldo.get_iso())}.",
                parent=self.master)
        elif self.titulo["recorrencia_id"]:
            self._oferecer_novo_valor_fixo(pago)
        self.destroy()
