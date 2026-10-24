"""Tela inicial: os números mais importantes, em linguagem do dia a dia."""
from __future__ import annotations

from datetime import date
from tkinter import ttk

from app import services
from app.ui.theme import CORES
from app.ui.widgets import Cabecalho, Cartao, GraficoBarras, Paginacao, Tabela


class Dashboard(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Início",
            "Um resumo rápido da sua situação financeira. Os valores abaixo são atualizados"
            " sozinhos a cada registro.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Registrar entrada ou saída", self._novo_lancamento, "Primario.TButton")
        self.cabecalho.botao("Atualizar", self.recarregar)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 20))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)

        # --- cartões -----------------------------------------------------
        grade = ttk.Frame(corpo)
        grade.grid(row=0, column=0, sticky="ew")
        for coluna in range(4):
            grade.columnconfigure(coluna, weight=1, uniform="cartoes")

        self.cartoes: dict[str, Cartao] = {}
        definicoes = [
            ("disponivel", "Dinheiro que você tem hoje"),
            ("investido", "Aplicado em investimentos"),
            ("dividas", "Total que você deve"),
            ("patrimonio_liquido", "Seu patrimônio"),
            ("entrou_mes", "Entrou este mês"),
            ("saiu_mes", "Saiu este mês"),
            ("sobrou_mes", "Sobrou este mês"),
            ("previsto", "Previsão para o fim do mês"),
            ("a_pagar_30", "Contas a pagar neste mês"),
            ("a_receber_30", "Você tem a receber neste mês"),
            ("orcamento", "Orçamento do mês"),
            ("poupanca", "Poupança deste mês"),
        ]
        for indice, (chave, rotulo) in enumerate(definicoes):
            cartao = Cartao(grade, rotulo)
            cartao.grid(row=indice // 4, column=indice % 4, sticky="ew", padx=6, pady=6)
            self.cartoes[chave] = cartao

        # --- saldo de cada conta e dívidas -------------------------------
        detalhe = ttk.Frame(corpo)
        detalhe.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        detalhe.columnconfigure(0, weight=3)
        detalhe.columnconfigure(1, weight=2)
        detalhe.rowconfigure(0, weight=1)

        quadro_contas = ttk.Frame(detalhe, style="Superficie.TFrame", padding=16)
        quadro_contas.configure(relief="solid", borderwidth=1)
        quadro_contas.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        linha_contas = ttk.Frame(quadro_contas, style="Superficie.TFrame")
        linha_contas.pack(fill="x")
        textos_contas = ttk.Frame(linha_contas, style="Superficie.TFrame")
        textos_contas.pack(side="left")
        ttk.Label(textos_contas, text="Quanto tem em cada conta",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        ttk.Label(textos_contas, text="O previsto desconta de cada conta só o que sai dela."
                                      " Investimento aparece separado.",
                  style="DicaSuperficie.TLabel", wraplength=330,
                  justify="left").pack(anchor="w", pady=(2, 8))
        ttk.Button(linha_contas, text="Ver contas",
                   command=self._abrir_carteiras).pack(side="right")
        self.tab_contas = Tabela(quadro_contas, [
            ("nome", "Conta", 130, "w"),
            ("situacao", "Serve para", 120, "w"),
            ("saldo", "Saldo hoje", 95, "e"),
            ("sai", "Ainda sai", 95, "e"),
            ("previsto", "Sobra no fim do mês", 130, "e"),
        ], largura_livre=True, altura=5)
        self.tab_contas.definir_texto_vazio("Nenhuma conta cadastrada ainda.")
        self.tab_contas.pack(fill="both", expand=True)
        self.pag_contas = Paginacao(quadro_contas, self._desenhar_contas,
                                    nome_itens="contas")
        self.pag_contas.pack(fill="x", pady=(8, 0))

        quadro_dividas = ttk.Frame(detalhe, style="Superficie.TFrame", padding=16)
        quadro_dividas.configure(relief="solid", borderwidth=1)
        quadro_dividas.grid(row=0, column=1, sticky="nsew")
        linha_div = ttk.Frame(quadro_dividas, style="Superficie.TFrame")
        linha_div.pack(fill="x")
        textos_div = ttk.Frame(linha_div, style="Superficie.TFrame")
        textos_div.pack(side="left")
        ttk.Label(textos_div, text="O que você ainda deve",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        ttk.Label(textos_div, text="Cartões, empréstimos e financiamentos em aberto.",
                  style="DicaSuperficie.TLabel", wraplength=250,
                  justify="left").pack(anchor="w", pady=(2, 8))
        ttk.Button(linha_div, text="Ver dívidas", command=self._abrir_dividas).pack(side="right")
        self.tab_dividas = Tabela(quadro_dividas, [
            ("nome", "Dívida", 140, "w"),
            ("parcelas", "Parcelas", 75, "center"),
            ("saldo", "Falta pagar", 100, "e"),
        ], largura_livre=True, altura=5)
        self.tab_dividas.definir_texto_vazio("Você não tem dívidas registradas. Ótimo!")
        self.tab_dividas.pack(fill="both", expand=True)
        self.pag_dividas = Paginacao(quadro_dividas, self._desenhar_dividas,
                                     nome_itens="dívidas")
        self.pag_dividas.pack(fill="x", pady=(8, 0))

        # --- gráfico e categorias ---------------------------------------
        meio = ttk.Frame(corpo)
        meio.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        meio.columnconfigure(0, weight=3)
        meio.columnconfigure(1, weight=2)
        meio.rowconfigure(0, weight=1)

        quadro_grafico = ttk.Frame(meio, style="Superficie.TFrame", padding=16)
        quadro_grafico.configure(relief="solid", borderwidth=1)
        quadro_grafico.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(quadro_grafico, text="O que entrou e o que saiu, mês a mês",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        ttk.Label(quadro_grafico, text="Barras verdes são recebimentos; vermelhas são gastos.",
                  style="DicaSuperficie.TLabel").pack(anchor="w", pady=(2, 8))
        self.grafico = GraficoBarras(quadro_grafico, altura=140)
        self.grafico.pack(fill="both", expand=True)

        quadro_cat = ttk.Frame(meio, style="Superficie.TFrame", padding=16)
        quadro_cat.configure(relief="solid", borderwidth=1)
        quadro_cat.grid(row=0, column=1, sticky="nsew")
        ttk.Label(quadro_cat, text="Onde seu dinheiro foi este mês",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        ttk.Label(quadro_cat, text="Seus maiores gastos, do maior para o menor.",
                  style="DicaSuperficie.TLabel").pack(anchor="w", pady=(2, 8))
        self.tab_categorias = Tabela(quadro_cat, [
            ("categoria", "Tipo de gasto", 150, "w"),
            ("valor", "Valor", 100, "e"),
            ("perc", "Do total", 70, "e"),
        ], largura_livre=True, altura=5)
        self.tab_categorias.definir_texto_vazio("Nenhum gasto registrado neste mês.")
        self.tab_categorias.pack(fill="both", expand=True)
        self.pag_categorias = Paginacao(quadro_cat, self._desenhar_categorias,
                                        nome_itens="categorias")
        self.pag_categorias.pack(fill="x", pady=(8, 0))

        # --- vencimentos -------------------------------------------------
        quadro_venc = ttk.Frame(corpo, style="Superficie.TFrame", padding=16)
        quadro_venc.configure(relief="solid", borderwidth=1)
        quadro_venc.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        linha = ttk.Frame(quadro_venc, style="Superficie.TFrame")
        linha.pack(fill="x")
        textos = ttk.Frame(linha, style="Superficie.TFrame")
        textos.pack(side="left")
        ttk.Label(textos, text="Contas que vencem nos próximos 30 dias",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        ttk.Label(textos, text="Em vermelho, o que já passou da data.",
                  style="DicaSuperficie.TLabel").pack(anchor="w", pady=(2, 8))
        ttk.Button(linha, text="Ver todas", command=self._abrir_contas).pack(side="right")

        self.tab_vencimentos = Tabela(quadro_venc, [
            ("venc", "Vence em", 95, "center"),
            ("tipo", "O que é", 110, "center"),
            ("descricao", "Descrição", 240, "w"),
            ("conta", "Sai / entra na conta", 160, "w"),
            ("valor", "Valor", 105, "e"),
            ("situacao", "Situação", 120, "center"),
        ], largura_livre=True, altura=5)
        self.tab_vencimentos.definir_texto_vazio("Nenhuma conta a vencer nos próximos 30 dias.")
        self.tab_vencimentos.pack(fill="both", expand=True)
        self.pag_vencimentos = Paginacao(quadro_venc, self._desenhar_vencimentos,
                                         nome_itens="contas")
        self.pag_vencimentos.pack(fill="x", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def _novo_lancamento(self) -> None:
        self.app._atalho_novo_lancamento()

    def _abrir_contas(self) -> None:
        from app.ui.main_window import CONTAS
        self.app.ir_para(CONTAS)

    def _abrir_carteiras(self) -> None:
        from app.ui.main_window import CARTEIRAS
        self.app.ir_para(CARTEIRAS)

    def _abrir_dividas(self) -> None:
        from app.ui.main_window import DIVIDAS
        self.app.ir_para(DIVIDAS)

    def recarregar(self) -> None:
        resumo = services.resumo_dashboard()

        def cor(valor: float) -> str:
            return CORES["sucesso"] if valor >= 0 else CORES["perigo"]

        contas = resumo["contas"]
        quantas = sum(1 for c in contas if c["grupo"] == "disponivel")
        outros = resumo["outros_saldos"]
        self.cartoes["disponivel"].atualizar(
            services.moeda(resumo["disponivel"]), CORES["texto"],
            f"só contas de dinheiro ({quantas})"
            + (f" · outros saldos {services.moeda(outros)}" if outros > 0.005 else ""),
            CORES["primaria"])

        investido = resumo["investido"]
        inv = resumo["investimentos"]
        self.cartoes["investido"].atualizar(
            services.moeda(investido),
            CORES["texto"] if investido > 0.005 else CORES["texto_suave"],
            (f"rendeu {services.moeda(inv['rendimento'])} · {inv['rentabilidade']:.2f}%"
             if investido > 0.005 else "não entra no dinheiro disponível"),
            CORES["primaria"])

        total_dividas = resumo["total_dividas"]
        self.cartoes["dividas"].atualizar(
            services.moeda(total_dividas),
            CORES["perigo"] if total_dividas > 0.005 else CORES["sucesso"],
            (f"cartões: {services.moeda(resumo['divida_cartoes'])}" if total_dividas > 0.005
             else "você não deve nada"),
            CORES["perigo"] if total_dividas > 0.005 else CORES["sucesso"])

        previsao = resumo["previsao"]
        previsto = previsao["previsto"]
        negativas = previsao["contas_negativas"]
        indefinido = previsao["sem_conta_pagar"]
        if negativas:
            nota = "falta em: " + ", ".join(c["nome"] for c in negativas[:2])
        elif indefinido > 0.005:
            nota = f"fora {services.moeda(indefinido)} sem conta definida"
        else:
            nota = "cada conta pagando o que sai dela"
        self.cartoes["previsto"].atualizar(
            services.moeda(previsto),
            CORES["perigo"] if negativas else cor(previsto), nota,
            CORES["perigo"] if negativas else CORES["primaria"])

        # Os três cartões do mês falam de dinheiro, não de competência: o que
        # entrou nas contas, o que saiu delas e a diferença. Assim o número
        # fecha com o saldo — antes dizia que havia sobrado 459,48 num mês que
        # terminou com 8,99 na conta.
        fluxo = resumo["fluxo"]
        sobrou = fluxo["sobrou"]
        self.cartoes["sobrou_mes"].atualizar(
            services.moeda(sobrou), cor(sobrou),
            f"você tinha {services.moeda(fluxo['saldo_inicial'])}"
            f" e tem {services.moeda(fluxo['saldo_final'])} hoje")

        def comparacao(variacao: float | None, para_gasto: bool) -> str:
            if variacao is None:
                return "sem comparação com o mês passado"
            if abs(variacao) < 0.5:
                return "igual ao mês passado"
            palavra = "a mais" if variacao > 0 else "a menos"
            return f"{abs(variacao):.0f}% {palavra} que no mês passado"

        # Quando tudo foi recebimento e gasto comum, o mais útil é comparar com
        # o mês passado. Quando parte do dinheiro saiu para pagar dívida ou
        # virar aplicação, o útil é dizer isso: é o que explica a diferença
        # entre o que se gastou e o que sobrou.
        def nota(parcelas: dict, comum: str, variacao: float | None,
                 para_gasto: bool) -> str:
            if set(parcelas) - {comum}:
                return services.detalhe_do_fluxo(parcelas)
            return comparacao(variacao, para_gasto)

        self.cartoes["entrou_mes"].atualizar(
            services.moeda(fluxo["entrou"]), CORES["sucesso"],
            nota(fluxo["entradas"], "recebimentos", resumo["var_receitas"], False))
        self.cartoes["saiu_mes"].atualizar(
            services.moeda(fluxo["saiu"]), CORES["perigo"],
            nota(fluxo["saidas"], "gastos", resumo["var_despesas"], True))

        vencidos_p = resumo["vencidos_pagar"]
        self.cartoes["a_pagar_30"].atualizar(
            services.moeda(resumo["a_pagar_30"]),
            CORES["alerta"] if vencidos_p else CORES["texto"],
            f"já venceram: {services.moeda(vencidos_p)}" if vencidos_p else "nada atrasado",
            CORES["alerta"] if vencidos_p else CORES["primaria"])

        self.cartoes["a_receber_30"].atualizar(
            services.moeda(resumo["a_receber_30"]), CORES["sucesso"],
            f"atrasados: {services.moeda(resumo['vencidos_receber'])}"
            if resumo["vencidos_receber"] else "nada atrasado")

        self.cartoes["patrimonio_liquido"].atualizar(
            services.moeda(resumo["patrimonio_liquido"]), cor(resumo["patrimonio_liquido"]),
            f"tem {services.moeda(resumo['total_ativo'])}"
            f" · deve {services.moeda(resumo['total_passivo'])}")

        previsto = resumo["orcamento_previsto"]
        if previsto > 0.005:
            percentual = resumo["orcamento_percentual"]
            cor_orcamento = (CORES["sucesso"] if percentual < 80
                             else CORES["alerta"] if percentual <= 100 else CORES["perigo"])
            nota = f"de {services.moeda(previsto)} planejados"
            if resumo["categorias_estouradas"]:
                nota += f" · {resumo['categorias_estouradas']} estourada(s)"
            self.cartoes["orcamento"].atualizar(
                f"{percentual:.0f}%", cor_orcamento, nota, cor_orcamento)
        else:
            self.cartoes["orcamento"].atualizar(
                "—", CORES["texto_suave"],
                "defina seus tetos na tela Orçamento", CORES["texto_suave"])

        # Guardar não é o que sobra depois de gastar: é uma fatia do que entrou.
        # O cartão compara as duas coisas antes de o mês acabar.
        poupanca = resumo["poupanca"]
        if poupanca["situacao"] == "sem_renda":
            self.cartoes["poupanca"].atualizar(
                "—", CORES["texto_suave"],
                "a meta aparece quando o dinheiro entrar", CORES["texto_suave"])
        else:
            cores_poupanca = {"em_dia": CORES["sucesso"], "parcial": CORES["alerta"],
                              "nada": CORES["perigo"]}
            tom = cores_poupanca[poupanca["situacao"]]
            if poupanca["situacao"] == "em_dia":
                nota = (f"{poupanca['do_que_entrou']:.0f}% do que entrou"
                        f"  ·  meta {poupanca['percentual_meta']:.0f}%")
            else:
                nota = (f"faltam {services.moeda(poupanca['falta'])} para"
                        f" os {poupanca['percentual_meta']:.0f}% do que entrou")
            self.cartoes["poupanca"].atualizar(
                services.moeda(poupanca["guardado"]), tom, nota, tom)

        # As tabelas abaixo são paginadas: cada Paginacao guarda a lista inteira
        # e chama o método de desenho só com os itens da página escolhida.
        self.pag_contas.definir(contas)
        self.pag_dividas.definir(resumo["dividas"])

        self.grafico.definir_dados(services.fluxo_mensal(12))

        categorias = services.despesas_por_categoria(
            services.primeiro_dia_mes(), services.ultimo_dia_mes())
        self._total_categorias = sum(c["total"] for c in categorias) or 1.0
        self.pag_categorias.definir(categorias)

        self.pag_vencimentos.definir(services.proximos_vencimentos(limite=60))

    # ------------------------------------------------------------------ #
    def _desenhar_contas(self, contas: list) -> None:
        rotulos = {"disponivel": "Dia a dia",
                   "investimento": "Aplicado",
                   "outro": "Saldo preso",
                   "divida": "Dívida"}
        self.tab_contas.limpar()
        for conta in contas:
            saldo = conta["saldo"]
            if conta["grupo"] == "divida":
                texto = f"deve {services.moeda(saldo)}"
                tags = ("negativo",)
            else:
                texto = services.moeda(saldo)
                tags = ("negativo",) if saldo < -0.005 else ()
            previsto = conta.get("previsto")
            if previsto is not None and previsto < -0.005:
                tags = ("negativo",)
            self.tab_contas.inserir(
                (conta["nome"], rotulos[conta["grupo"]], texto,
                 services.moeda(conta["a_pagar"]) if conta.get("a_pagar") else "—",
                 services.moeda(previsto) if previsto is not None else "—"),
                iid=conta["id"], tags=tags)
        self.tab_contas.finalizar()

    def _desenhar_dividas(self, dividas: list) -> None:
        self.tab_dividas.limpar()
        for divida in dividas:
            parcelas = (f"{divida['pagas']}/{divida['parcelas']}" if divida["parcelas"]
                        else "—")
            self.tab_dividas.inserir(
                (divida["nome"], parcelas, services.moeda(divida["saldo"])),
                iid=divida["conta_id"], tags=("negativo",))
        self.tab_dividas.finalizar()

    def _desenhar_categorias(self, categorias: list) -> None:
        total = getattr(self, "_total_categorias", 1.0)
        self.tab_categorias.limpar()
        for item in categorias:
            self.tab_categorias.inserir(
                (item["nome"], services.moeda(item["total"]),
                 f"{item['total'] / total * 100:.0f}%"))
        self.tab_categorias.finalizar()

    def _desenhar_vencimentos(self, titulos: list) -> None:
        self.tab_vencimentos.limpar()
        hoje = date.today().isoformat()
        for titulo in titulos:
            vencido = titulo["vencimento"] < hoje
            dias = (date.fromisoformat(titulo["vencimento"]) - date.today()).days
            if vencido:
                situacao = f"Atrasada há {abs(dias)} dia(s)"
            elif dias == 0:
                situacao = "Vence hoje"
            else:
                situacao = f"Faltam {dias} dia(s)"
            self.tab_vencimentos.inserir(
                (services.para_br(titulo["vencimento"]),
                 "Você paga" if titulo["tipo"] == "PAGAR" else "Você recebe",
                 titulo["descricao"], titulo["conta_pagamento_nome"] or "— não definida —",
                 services.moeda(titulo["valor"]), situacao),
                iid=titulo["id"], tags=("vencido",) if vencido else ())
        self.tab_vencimentos.finalizar()
