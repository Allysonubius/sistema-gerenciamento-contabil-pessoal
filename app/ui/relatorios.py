"""Relatórios explicados em linguagem simples, com menu lateral de escolha."""
from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app import services
from app.config import EXPORT_DIR, ensure_dirs
from app.ui.theme import CORES, FONTE
from app.ui.widgets import (AutoConsulta, BarraFiltro, Cabecalho, ListaLateral, SeletorConta,
                            Tabela)

# (nome no menu, explicação curta no menu, explicação longa no topo do relatório)
RELATORIOS: list[tuple[str, str, str]] = [
    ("Mês a mês",
     "Quanto entrou e sobrou em cada mês",
     "Um mês por linha, desde o seu primeiro registro. Mostra o que entrou, o que saiu,"
     " quanto sobrou e quanto havia em conta no fim de cada mês."),
    ("Categorias mês a mês",
     "O que subiu ao longo do tempo",
     "Cada categoria em uma linha e cada mês em uma coluna, com total, média e a variação"
     " do último mês. É aqui que se enxerga o que ficou mais caro."),
    ("Resumo por conta",
     "Movimento de cada conta no período",
     "Quanto entrou e quanto saiu em cada conta e categoria dentro do período escolhido,"
     " com o saldo no começo e no fim."),
    ("Extrato de uma conta",
     "Todos os movimentos de uma conta",
     "Os movimentos de uma conta específica, em ordem de data, com o saldo recalculado"
     " a cada linha."),
    ("Ganhos e gastos",
     "O resultado do período",
     "O que você ganhou, o que gastou e quanto sobrou no período escolhido, com o peso de"
     " cada item sobre o total que entrou."),
    ("Meu patrimônio",
     "O que você tem e o que deve",
     "A fotografia de hoje: tudo o que você tem, tudo o que deve e a diferença entre os"
     " dois — o que é realmente seu."),
    ("Histórico completo",
     "A lista de todos os registros",
     "Todos os registros do período, um por um, com data, descrição e as contas"
     " envolvidas em cada um."),
    ("Previsão de saldo",
     "Como fica o seu dinheiro daqui pra frente",
     "Projeção do dinheiro disponível somando o saldo de hoje com as contas a pagar e a"
     " receber já agendadas. Mostra em que dia o saldo fica mais baixo."),
]

# Estes percorrem todo o histórico (ou o futuro) e não usam o seletor de período.
RELATORIOS_MENSAIS = (0, 1, 7)


class Relatorios(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._indice_atual = 0

        self.cabecalho = Cabecalho(
            self, "Relatórios",
            "Escolha um relatório na lista ao lado. Clique em um título de coluna para"
            " reordenar os resultados.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Atualizar", self.gerar, "Primario.TButton")
        self.cabecalho.botao("Salvar em arquivo", self.exportar)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)

        self.lista = ListaLateral(corpo, [(n, d) for n, d, _ in RELATORIOS], self._trocar)
        self.lista.grid(row=0, column=0, sticky="ns")

        direita = ttk.Frame(corpo)
        direita.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        direita.columnconfigure(0, weight=1)
        direita.rowconfigure(2, weight=1)

        # Título e explicação do relatório escolhido
        titulo = ttk.Frame(direita, style="Superficie.TFrame", padding=(16, 14))
        titulo.configure(relief="solid", borderwidth=1)
        titulo.grid(row=0, column=0, sticky="ew")
        self.lbl_titulo = ttk.Label(titulo, style="SecaoSuperficie.TLabel")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_explica = ttk.Label(titulo, style="DicaSuperficie.TLabel",
                                     wraplength=900, justify="left")
        self.lbl_explica.pack(anchor="w", pady=(4, 0))

        # Filtros
        self.barra = ttk.Frame(direita, style="Superficie.TFrame", padding=14)
        self.barra.configure(relief="solid", borderwidth=1)
        self.barra.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.filtro = BarraFiltro(self.barra, self.gerar, fundo="Superficie.TFrame")
        self.filtro.pack(side="left")
        self.lbl_sem_filtro = ttk.Label(
            self.barra, text="Este relatório mostra todo o seu histórico, do primeiro registro"
                             " até hoje.", style="DicaSuperficie.TLabel")

        # Conteúdo — um quadro por relatório, empilhados
        self.area = ttk.Frame(direita)
        self.area.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.quadros = [
            self._montar_mes_a_mes(),
            self._montar_categorias_mensais(),
            self._montar_balancete(),
            self._montar_razao(),
            self._montar_dre(),
            self._montar_balanco(),
            self._montar_diario(),
            self._montar_previsao(),
        ]
        self.lista.selecionar(0)

    # ------------------------------------------------------------------ #
    def _quadro(self) -> ttk.Frame:
        return ttk.Frame(self.area, style="Superficie.TFrame", padding=16)

    def _montar_mes_a_mes(self) -> ttk.Frame:
        aba = self._quadro()
        topo = ttk.Frame(aba, style="Superficie.TFrame")
        topo.pack(fill="x", pady=(0, 10))
        self.lbl_mes_a_mes = ttk.Label(topo, style="DicaSuperficie.TLabel")
        self.lbl_mes_a_mes.pack(side="left")

        self.tab_mensal = Tabela(aba, [
            ("mes", "Mês", 140, "w"),
            ("entrou", "Entrou", 118, "e"),
            ("saiu", "Saiu", 118, "e"),
            ("sobrou", "Sobrou no mês", 130, "e"),
            ("acumulado", "Acumulado", 130, "e"),
            ("saldo", "Em conta no fim", 150, "e"),
        ], largura_livre=True, altura=8)
        self.tab_mensal.definir_texto_vazio(
            "Ainda não há registros. Assim que você lançar o primeiro, os meses aparecem aqui.")
        self.tab_mensal.pack(fill="both", expand=True)
        self.lbl_media_mensal = ttk.Label(aba, style="SecaoSuperficie.TLabel")
        self.lbl_media_mensal.pack(anchor="e", pady=(10, 0))
        return aba

    def _montar_categorias_mensais(self) -> ttk.Frame:
        aba = self._quadro()
        topo = ttk.Frame(aba, style="Superficie.TFrame")
        topo.pack(fill="x", pady=(0, 10))
        ttk.Label(topo, text="Mostrar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_matriz_tipo = ttk.Combobox(topo, state="readonly", width=12,
                                           values=["Gastos", "Ganhos"])
        self.cb_matriz_tipo.set("Gastos")
        self.cb_matriz_tipo.pack(side="left", padx=8)
        self.cb_matriz_tipo.bind("<<ComboboxSelected>>", lambda _e: self.gerar())

        ttk.Label(topo, text="dos últimos", style="CampoSuperficie.TLabel").pack(
            side="left", padx=(12, 0))
        self.cb_matriz_meses = ttk.Combobox(topo, state="readonly", width=15,
                                            values=["6 meses", "12 meses", "24 meses",
                                                    "Desde o começo"])
        self.cb_matriz_meses.set("12 meses")
        self.cb_matriz_meses.pack(side="left", padx=8)
        self.cb_matriz_meses.bind("<<ComboboxSelected>>", lambda _e: self.gerar())
        self.lbl_matriz = ttk.Label(topo, style="DicaSuperficie.TLabel")
        self.lbl_matriz.pack(side="right")

        # A matriz tem uma coluna por mês, então é reconstruída a cada geração.
        self.area_matriz = ttk.Frame(aba, style="Superficie.TFrame")
        self.area_matriz.pack(fill="both", expand=True)
        self.tab_matriz: Tabela | None = None
        return aba

    def _montar_balancete(self) -> ttk.Frame:
        aba = self._quadro()
        topo = ttk.Frame(aba, style="Superficie.TFrame")
        topo.pack(fill="x", pady=(0, 10))
        self.var_zerados = tk.BooleanVar(value=True)
        ttk.Checkbutton(topo, text="Esconder o que não teve movimento",
                        variable=self.var_zerados, command=self.gerar,
                        style="Superficie.TCheckbutton").pack(side="left")
        self.lbl_balancete = ttk.Label(topo, style="DicaSuperficie.TLabel")
        self.lbl_balancete.pack(side="right")

        self.tab_balancete = Tabela(aba, [
            ("nome", "Conta ou categoria", 250, "w"),
            ("codigo", "Código", 75, "w"),
            ("anterior", "Saldo anterior", 110, "e"),
            ("debito", "Entrou", 120, "e"),
            ("credito", "Saiu", 105, "e"),
            ("saldo", "Saldo no fim", 120, "e"),
        ], largura_livre=True, altura=8)
        self.tab_balancete.definir_texto_vazio("Sem movimentos no período escolhido.")
        self.tab_balancete.pack(fill="both", expand=True)
        return aba

    def _montar_razao(self) -> ttk.Frame:
        aba = self._quadro()
        topo = ttk.Frame(aba, style="Superficie.TFrame")
        topo.pack(fill="x", pady=(0, 10))
        ttk.Label(topo, text="Qual conta você quer ver?",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.sel_razao = SeletorConta(topo, width=44)
        self.sel_razao.pack(side="left", padx=10)
        self.sel_razao.bind("<<ComboboxSelected>>", lambda _e: self.gerar(), add="+")
        self._auto_razao = AutoConsulta(self, self.gerar, atraso=450)
        self.sel_razao.bind("<KeyRelease>", self._auto_razao.agendar, add="+")

        self.tab_razao = Tabela(aba, [
            ("data", "Data", 85, "center"),
            ("historico", "Descrição", 200, "w"),
            ("contra", "Outra conta envolvida", 175, "w"),
            ("debito", "Entrou", 100, "e"),
            ("credito", "Saiu", 100, "e"),
            ("saldo", "Saldo", 115, "e"),
        ], largura_livre=True, altura=8)
        self.tab_razao.definir_texto_vazio("Escolha uma conta acima para ver o extrato.")
        self.tab_razao.pack(fill="both", expand=True)
        self.lbl_razao = ttk.Label(aba, style="SecaoSuperficie.TLabel")
        self.lbl_razao.pack(anchor="e", pady=(10, 0))
        return aba

    def _montar_dre(self) -> ttk.Frame:
        aba = self._quadro()
        self.tab_dre = Tabela(aba, [
            ("grupo", "Tipo", 110, "w"),
            ("conta", "Descrição", 380, "w"),
            ("valor", "Valor", 150, "e"),
            ("perc", "Do que entrou", 120, "e"),
        ], largura_livre=True, altura=8)
        self.tab_dre.definir_texto_vazio("Nenhum ganho ou gasto no período.")
        self.tab_dre.pack(fill="both", expand=True)
        self.lbl_dre = ttk.Label(aba, style="SecaoSuperficie.TLabel")
        self.lbl_dre.pack(anchor="e", pady=(10, 0))
        return aba

    def _montar_balanco(self) -> ttk.Frame:
        aba = self._quadro()
        self.tab_balanco = Tabela(aba, [
            ("grupo", "Grupo", 190, "w"),
            ("conta", "Descrição", 400, "w"),
            ("valor", "Valor", 160, "e"),
        ], largura_livre=True, altura=8)
        self.tab_balanco.definir_texto_vazio(
            "Cadastre suas contas em 'Minhas Contas' para ver seu patrimônio.")
        self.tab_balanco.pack(fill="both", expand=True)
        self.lbl_balanco = ttk.Label(aba, style="SecaoSuperficie.TLabel")
        self.lbl_balanco.pack(anchor="e", pady=(10, 0))
        return aba

    def _montar_diario(self) -> ttk.Frame:
        aba = self._quadro()
        quadro = ttk.Frame(aba, style="Superficie.TFrame")
        quadro.pack(fill="both", expand=True)
        self.txt_diario = tk.Text(quadro, wrap="none", font=("Consolas", 10),
                                  bg=CORES["superficie"], fg=CORES["texto"], relief="solid",
                                  borderwidth=1, padx=10, pady=8)
        vsb = ttk.Scrollbar(quadro, orient="vertical", command=self.txt_diario.yview)
        self.txt_diario.configure(yscrollcommand=vsb.set)
        self.txt_diario.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return aba

    def _montar_previsao(self) -> ttk.Frame:
        aba = self._quadro()
        topo = ttk.Frame(aba, style="Superficie.TFrame")
        topo.pack(fill="x", pady=(0, 10))
        ttk.Label(topo, text="Olhar até:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_previsao = ttk.Combobox(topo, state="readonly", width=14,
                                        values=["30 dias", "60 dias", "90 dias", "6 meses"])
        self.cb_previsao.set("90 dias")
        self.cb_previsao.pack(side="left", padx=8)
        self.cb_previsao.bind("<<ComboboxSelected>>", lambda _e: self.gerar())
        self.lbl_previsao = ttk.Label(topo, style="SecaoSuperficie.TLabel")
        self.lbl_previsao.pack(side="right")

        ttk.Label(aba, text="Dia a dia — só os dias em que algo acontece",
                  style="DicaSuperficie.TLabel").pack(anchor="w", pady=(0, 6))
        self.tab_previsao = Tabela(aba, [
            ("data", "Data", 100, "center"),
            ("evento", "O que acontece", 340, "w"),
            ("valor", "Valor", 130, "e"),
            ("saldo", "Saldo depois", 140, "e"),
        ], largura_livre=True, altura=6)
        self.tab_previsao.definir_texto_vazio("Nada agendado para os próximos dias.")
        self.tab_previsao.pack(fill="both", expand=True)

        ttk.Label(aba, text="Resumo por mês", style="DicaSuperficie.TLabel").pack(
            anchor="w", pady=(12, 6))
        self.tab_previsao_mes = Tabela(aba, [
            ("mes", "Mês", 180, "w"),
            ("pagar", "Vou pagar", 140, "e"),
            ("receber", "Vou receber", 140, "e"),
            ("saldo", "Saldo no fim do mês", 180, "e"),
        ], largura_livre=True, altura=6)
        self.tab_previsao_mes.definir_texto_vazio("Sem contas agendadas.")
        self.tab_previsao_mes.pack(fill="x")
        return aba

    def _gerar_previsao(self, _desde: str, _ate: str) -> None:
        dias = {"30 dias": 30, "60 dias": 60, "90 dias": 90, "6 meses": 180}[
            self.cb_previsao.get()]
        previsao = services.previsao_saldo(dias)

        self.tab_previsao.limpar()
        for linha in previsao["linhas"]:
            if not linha["eventos"]:
                self.tab_previsao.inserir(
                    (services.para_br(linha["data"]), "— saldo de hoje —", "",
                     services.moeda(linha["saldo"])), tags=("sintetica",))
                continue
            for evento in linha["eventos"]:
                self.tab_previsao.inserir(
                    (services.para_br(linha["data"]), evento["descricao"],
                     ("+ " if evento["valor"] > 0 else "- ")
                     + services.moeda(abs(evento["valor"])),
                     services.moeda(linha["saldo"])),
                    tags=("positivo",) if evento["valor"] > 0 else ("negativo",))
        self.tab_previsao.finalizar()

        self.tab_previsao_mes.limpar()
        for item in services.previsao_mensal(6):
            self.tab_previsao_mes.inserir(
                (item["nome"].capitalize(), services.moeda(item["pagar"]),
                 services.moeda(item["receber"]), services.moeda(item["saldo_projetado"])),
                tags=("negativo",) if item["saldo_projetado"] < 0 else ())
        self.tab_previsao_mes.finalizar()

        if previsao["negativa"]:
            texto = (f"Atenção: o saldo fica negativo em"
                     f" {services.para_br(previsao['menor_data'])}"
                     f" ({services.moeda(previsao['menor_saldo'])})")
            cor = CORES["perigo"]
        else:
            texto = (f"Menor saldo previsto: {services.moeda(previsao['menor_saldo'])}"
                     f" em {services.para_br(previsao['menor_data'])}")
            cor = CORES["sucesso"]
        self.lbl_previsao.configure(text=texto, foreground=cor)

    # ------------------------------------------------------------------ #
    def _trocar(self, indice: int) -> None:
        """Troca o relatório exibido."""
        for quadro in getattr(self, "quadros", []):
            quadro.pack_forget()
        self._indice_atual = indice
        nome, _, explicacao = RELATORIOS[indice]
        self.lbl_titulo.configure(text=nome)
        self.lbl_explica.configure(text=explicacao)
        if getattr(self, "quadros", None):
            self.quadros[indice].pack(fill="both", expand=True)
        self.gerar()

    def selecionar(self, indice: int) -> None:
        """Usado por outras telas para abrir um relatório específico."""
        self.lista.selecionar(indice)

    def recarregar(self) -> None:
        self.sel_razao.recarregar()
        self.gerar()

    def gerar(self) -> None:
        if not getattr(self, "quadros", None):
            return
        try:
            desde, ate = self.filtro.periodo()
        except services.RegraNegocioError:
            return  # data incompleta enquanto o usuário digita

        indice = self._indice_atual
        if indice in RELATORIOS_MENSAIS:
            self.filtro.pack_forget()
            self.lbl_sem_filtro.configure(
                text="Este relatório olha para frente: usa o que já está agendado."
                if indice == 7 else
                "Este relatório mostra todo o seu histórico, do primeiro registro até hoje.")
            self.lbl_sem_filtro.pack(side="left")
        else:
            self.lbl_sem_filtro.pack_forget()
            self.filtro.pack(side="left")

        [self._gerar_mes_a_mes, self._gerar_categorias_mensais, self._gerar_balancete,
         self._gerar_razao, self._gerar_dre, self._gerar_balanco,
         self._gerar_diario, self._gerar_previsao][indice](desde, ate)

    # ------------------------------------------------------------------ #
    def _gerar_mes_a_mes(self, _desde: str, _ate: str) -> None:
        self.tab_mensal.limpar()
        linhas = services.resumo_mensal(services.meses_do_historico())
        for linha in linhas:
            self.tab_mensal.inserir(
                (linha["nome"].capitalize(), services.moeda(linha["receita"]),
                 services.moeda(linha["despesa"]), services.moeda(linha["sobrou"]),
                 services.moeda(linha["acumulado"]), services.moeda(linha["saldo_contas"])),
                iid=linha["mes"], tags=() if linha["sobrou"] >= 0 else ("negativo",))
        self.tab_mensal.finalizar()

        if not linhas:
            self.lbl_mes_a_mes.configure(text="")
            self.lbl_media_mensal.configure(text="")
            return
        meses = len(linhas)
        media_entrou = sum(l["receita"] for l in linhas) / meses
        media_saiu = sum(l["despesa"] for l in linhas) / meses
        media_sobrou = sum(l["sobrou"] for l in linhas) / meses
        self.lbl_mes_a_mes.configure(text=f"{meses} mês(es) desde {linhas[0]['nome']}")
        self.lbl_media_mensal.configure(
            text=f"Média por mês — entrou {services.moeda(media_entrou)}   |   "
                 f"saiu {services.moeda(media_saiu)}   |   "
                 f"sobrou {services.moeda(media_sobrou)}",
            foreground=CORES["sucesso"] if media_sobrou >= 0 else CORES["perigo"])

    def _gerar_categorias_mensais(self, _desde: str, _ate: str) -> None:
        limites = {"6 meses": 6, "12 meses": 12, "24 meses": 24, "Desde o começo": None}
        meses = services.meses_do_historico(limites[self.cb_matriz_meses.get()])
        tipo = "DESPESA" if self.cb_matriz_tipo.get() == "Gastos" else "RECEITA"
        linhas = services.matriz_categorias(meses, tipo)

        if self.tab_matriz is not None:
            self.tab_matriz.destroy()
        colunas = [("categoria", "Categoria", 175, "w")]
        colunas += [(f"m{m}", f"{m[5:7]}/{m[2:4]}", 80, "e") for m in meses]
        colunas += [("total", "Total", 100, "e"), ("media", "Média/mês", 95, "e"),
                    ("var", "Último mês", 100, "e")]
        self.tab_matriz = Tabela(self.area_matriz, colunas, altura=10, largura_livre=True)
        self.tab_matriz.definir_texto_vazio("Nenhum movimento no período.")
        self.tab_matriz.pack(fill="both", expand=True)

        totais = {m: 0.0 for m in meses}
        for linha in linhas:
            for mes in meses:
                totais[mes] += linha["meses"][mes]
            variacao = linha["variacao"]
            sinal = "+" if variacao > 0 else ""
            self.tab_matriz.inserir(
                [linha["nome"]]
                + [services.moeda(linha["meses"][m]) if abs(linha["meses"][m]) > 0.005 else "—"
                   for m in meses]
                + [services.moeda(linha["total"]), services.moeda(linha["media"]),
                   f"{sinal}{services.moeda(variacao)}" if abs(variacao) > 0.005 else "="],
                tags=("negativo",) if variacao > 0.005 and tipo == "DESPESA" else ())
        if linhas:
            total_geral = sum(totais.values())
            self.tab_matriz.inserir(
                ["TOTAL"] + [services.moeda(totais[m]) for m in meses]
                + [services.moeda(total_geral),
                   services.moeda(total_geral / len(meses) if meses else 0), ""],
                tags=("sintetica",))
        self.tab_matriz.finalizar()
        self.lbl_matriz.configure(
            text=f"{len(linhas)} categoria(s) em {len(meses)} mês(es)"
                 if meses else "Sem registros ainda.")

    def _gerar_balancete(self, desde: str, ate: str) -> None:
        self.tab_balancete.limpar()
        linhas = services.balancete(desde, ate, self.var_zerados.get())
        total_debito = total_credito = 0.0
        for linha in linhas:
            if not linha["sintetica"]:
                total_debito += linha["debito"]
                total_credito += linha["credito"]
            self.tab_balancete.inserir(
                (linha["nome"], linha["codigo"], services.moeda(linha["anterior"]),
                 services.moeda(linha["debito"]) if linha["debito"] else "",
                 services.moeda(linha["credito"]) if linha["credito"] else "",
                 services.moeda(linha["saldo"])),
                tags=("sintetica",) if linha["sintetica"] else ())
        self.tab_balancete.finalizar()
        diferenca = round(total_debito - total_credito, 2)
        self.lbl_balancete.configure(
            text=f"Movimento do período: {services.moeda(total_debito)}"
                 + ("   (contas conferidas ✓)" if abs(diferenca) < 0.005
                    else f"   atenção: diferença de {services.moeda(diferenca)}"),
            foreground=CORES["texto_suave"] if abs(diferenca) < 0.005 else CORES["perigo"])

    def _gerar_razao(self, desde: str, ate: str) -> None:
        self.tab_razao.limpar()
        try:
            conta_id = self.sel_razao.get_conta_id()
        except services.RegraNegocioError:
            conta_id = None
        if conta_id is None:
            self.tab_razao.finalizar()
            self.lbl_razao.configure(text="Nenhuma conta escolhida.")
            return
        anterior, linhas = services.razao(conta_id, desde, ate)
        self.tab_razao.inserir(("", "Saldo antes do período", "", "", "",
                                services.moeda(anterior)), tags=("sintetica",))
        for linha in linhas:
            self.tab_razao.inserir(
                (services.para_br(linha["data"]), linha["historico"], linha["contrapartida"],
                 services.moeda(linha["debito"]) if linha["debito"] else "",
                 services.moeda(linha["credito"]) if linha["credito"] else "",
                 services.moeda(linha["saldo"])))
        self.tab_razao.finalizar()
        final = linhas[-1]["saldo"] if linhas else anterior
        self.lbl_razao.configure(
            text=f"{len(linhas)} movimento(s) — saldo no fim: {services.moeda(final)}",
            foreground=CORES["sucesso"] if final >= 0 else CORES["perigo"])

    def _gerar_dre(self, desde: str, ate: str) -> None:
        self.tab_dre.limpar()
        dados = services.dre(desde, ate)
        base = dados["total_receitas"] or 1.0
        for item in dados["receitas"]:
            self.tab_dre.inserir(("Entrou", item["nome"], services.moeda(item["valor"]),
                                  f"{item['valor'] / base * 100:.0f}%"), tags=("positivo",))
        self.tab_dre.inserir(("", "TOTAL QUE ENTROU", services.moeda(dados["total_receitas"]),
                              "100%"), tags=("sintetica",))
        for item in dados["despesas"]:
            self.tab_dre.inserir(("Saiu", item["nome"], services.moeda(-item["valor"]),
                                  f"{item['valor'] / base * 100:.0f}%"), tags=("negativo",))
        self.tab_dre.inserir(("", "TOTAL QUE SAIU", services.moeda(-dados["total_despesas"]),
                              f"{dados['total_despesas'] / base * 100:.0f}%"), tags=("sintetica",))
        self.tab_dre.inserir(("", "SOBROU NO PERÍODO", services.moeda(dados["resultado"]),
                              f"{dados['resultado'] / base * 100:.0f}%"), tags=("sintetica",))
        self.tab_dre.finalizar()
        sobrou = dados["resultado"]
        self.lbl_dre.configure(
            text=(f"Você guardou {services.moeda(sobrou)} no período." if sobrou >= 0
                  else f"Você gastou {services.moeda(-sobrou)} a mais do que recebeu."),
            foreground=CORES["sucesso"] if sobrou >= 0 else CORES["perigo"])

    def _gerar_balanco(self, _desde: str, ate: str) -> None:
        self.tab_balanco.limpar()
        dados = services.balanco(ate)
        rotulos = {"ativo": "O que você tem", "passivo": "O que você deve",
                   "patrimonio": "Seu patrimônio"}
        for chave, rotulo in rotulos.items():
            for item in dados[chave]:
                self.tab_balanco.inserir(
                    (rotulo, item["nome"], services.moeda(item["valor"])),
                    tags=("sintetica",) if item["sintetica"] else ())
        self.tab_balanco.inserir(("Seu patrimônio", "Resultado acumulado dos períodos",
                                  services.moeda(dados["resultado_exercicio"])))
        self.tab_balanco.inserir(("", "TOTAL DO QUE VOCÊ TEM",
                                  services.moeda(dados["total_ativo"])), tags=("sintetica",))
        self.tab_balanco.inserir(("", "TOTAL DO QUE VOCÊ DEVE",
                                  services.moeda(dados["total_passivo"])), tags=("sintetica",))
        self.tab_balanco.inserir(("", "SOBRA (o que é realmente seu)",
                                  services.moeda(dados["total_pl"])), tags=("sintetica",))
        self.tab_balanco.finalizar()
        equilibrado = abs(dados["diferenca"]) < 0.005
        self.lbl_balanco.configure(
            text=("Contas conferidas ✓" if equilibrado else
                  f"Atenção: diferença de {services.moeda(dados['diferenca'])}."
                  " Confira os saldos das suas contas."),
            foreground=CORES["sucesso"] if equilibrado else CORES["perigo"])

    def _gerar_diario(self, desde: str, ate: str) -> None:
        self.txt_diario.configure(state="normal")
        self.txt_diario.delete("1.0", "end")
        linhas = [f"HISTÓRICO COMPLETO — de {services.para_br(desde)} a {services.para_br(ate)}",
                  "=" * 92, ""]
        for lanc in services.livro_diario(desde, ate):
            linhas.append(f"Registro nº {lanc['id']:<6} Data: {services.para_br(lanc['data'])}"
                          f"   Valor: {services.moeda(lanc['valor'])}")
            linhas.append(f"Descrição: {lanc['historico']}")
            for partida in lanc["partidas"]:
                sinal = "Aplicado em" if partida["tipo"] == "D" else "Veio de   "
                linhas.append(f"   {sinal}  {partida['nome']:<48}"
                              f"{services.moeda(partida['valor']):>14}")
            linhas.append("-" * 92)
        if len(linhas) == 3:
            linhas.append("Nenhum registro no período escolhido.")
        self.txt_diario.insert("1.0", "\n".join(linhas))
        self.txt_diario.configure(state="disabled")

    # ------------------------------------------------------------------ #
    def exportar(self) -> None:
        ensure_dirs()
        indice = self._indice_atual
        nomes = ["mes_a_mes", "categorias_mes_a_mes", "resumo_por_conta", "extrato",
                 "ganhos_e_gastos", "meu_patrimonio", "historico", "previsao_saldo"]
        nome = nomes[indice]

        if indice == 6:
            caminho = filedialog.asksaveasfilename(
                parent=self, initialdir=EXPORT_DIR, initialfile=f"{nome}.txt",
                defaultextension=".txt", filetypes=[("Arquivo de texto", "*.txt")])
            if not caminho:
                return
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write(self.txt_diario.get("1.0", "end"))
        else:
            tabelas = [self.tab_mensal, self.tab_matriz, self.tab_balancete, self.tab_razao,
                       self.tab_dre, self.tab_balanco, None, self.tab_previsao]
            tabela = tabelas[indice]
            if tabela is None:
                messagebox.showinfo("Exportar", "Gere o relatório antes de salvar.", parent=self)
                return
            caminho = filedialog.asksaveasfilename(
                parent=self, initialdir=EXPORT_DIR, initialfile=f"{nome}.csv",
                defaultextension=".csv", filetypes=[("Planilha (CSV)", "*.csv")])
            if not caminho:
                return
            with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow([c[1] for c in tabela.colunas])
                for item in tabela.tree.get_children():
                    escritor.writerow(tabela.tree.item(item, "values"))

        self.app.notificar("Relatório salvo em arquivo.")
        messagebox.showinfo("Pronto", f"Arquivo salvo em:\n{caminho}\n\n"
                                      "Ele pode ser aberto no Excel.", parent=self)

