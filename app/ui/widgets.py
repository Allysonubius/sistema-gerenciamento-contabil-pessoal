"""Componentes reutilizáveis da interface."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from typing import Callable, Iterable

from app import services
from app.ui.theme import CORES, FONTE


# --------------------------------------------------------------------------- #
# Campos de entrada
# --------------------------------------------------------------------------- #
MESES_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
            "agosto", "setembro", "outubro", "novembro", "dezembro")
DIAS_PT = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


class CampoData(ttk.Frame):
    """Data com calendário: clique no 📅 e escolha o dia.

    Continua aceitando digitação para quem prefere o teclado (+ e - mudam o dia,
    H volta para hoje). Aceita limites de início e fim: fora do intervalo, o
    campo avisa e não deixa passar.
    """

    def __init__(self, master, valor_inicial: str | None = None, **kwargs):
        largura = kwargs.pop("width", 12)
        super().__init__(master, **kwargs)
        self.var = tk.StringVar()
        self._minimo: str | None = None
        self._maximo: str | None = None
        self._par_fim: "CampoData | None" = None
        self._par_inicio: "CampoData | None" = None

        self.entrada = ttk.Entry(self, textvariable=self.var, width=largura, justify="center")
        self.entrada.pack(side="left")
        self.botao = ttk.Button(self, text="📅", width=3, takefocus=False,
                                command=self.abrir_calendario)
        self.botao.pack(side="left", padx=(2, 0))

        self.entrada.bind("<KeyRelease>", self._mascarar)
        self.entrada.bind("<FocusOut>", lambda _e: self._normalizar())
        self.entrada.bind("<Down>", lambda _e: self.abrir_calendario())
        if valor_inicial:
            self.set_iso(valor_inicial)

    # --- compatibilidade com quem trata o campo como um Entry ---------- #
    def configure(self, **kwargs):          # type: ignore[override]
        estado = kwargs.pop("state", None)
        if estado is not None:
            self.entrada.configure(state=estado)
            self.botao.configure(state="disabled" if estado in ("disabled", "readonly")
                                 else "normal")
        return super().configure(**kwargs) if kwargs else None

    config = configure

    def bind(self, sequencia=None, funcao=None, add=None):   # type: ignore[override]
        """Eventos de teclado interessam ao campo de texto, não ao quadro."""
        if sequencia and sequencia.startswith("<Key"):
            return self.entrada.bind(sequencia, funcao, add)
        return super().bind(sequencia, funcao, add)

    # --- limites (início x fim) ---------------------------------------- #
    _MANTER = object()

    def definir_limites(self, minimo=_MANTER, maximo=_MANTER) -> None:
        """Muda só o limite informado; o outro continua como estava."""
        if minimo is not CampoData._MANTER:
            self._minimo = minimo
        if maximo is not CampoData._MANTER:
            self._maximo = maximo

    def ligar_intervalo(self, fim: "CampoData") -> None:
        """Liga dois campos: este vira o início e o outro o fim do período."""
        self._par_fim = fim
        fim._par_inicio = self
        self._sincronizar_limites()
        fim._sincronizar_limites()

    def _sincronizar_limites(self) -> None:
        try:
            atual = self.get_iso()
        except services.RegraNegocioError:
            atual = None
        if self._par_fim is not None:
            self._par_fim.definir_limites(minimo=atual)
        if self._par_inicio is not None:
            self._par_inicio.definir_limites(maximo=atual)

    def _dentro_dos_limites(self, iso: str) -> str | None:
        """Devolve a mensagem do problema, ou None se a data está válida."""
        if self._minimo and iso < self._minimo:
            return f"A data não pode ser antes de {services.para_br(self._minimo)}."
        if self._maximo and iso > self._maximo:
            return f"A data não pode ser depois de {services.para_br(self._maximo)}."
        return None

    # --- digitação ----------------------------------------------------- #
    def _mascarar(self, evento) -> None:
        if evento.keysym in ("BackSpace", "Delete", "Left", "Right", "Tab"):
            return
        if evento.char in "+-":
            self._deslocar(1 if evento.char == "+" else -1)
            return
        if evento.char in ("h", "H"):
            self.set_iso(services.hoje_iso())
            return
        digitos = "".join(c for c in self.var.get() if c.isdigit())[:8]
        partes = [digitos[:2], digitos[2:4], digitos[4:8]]
        self.var.set("/".join(p for p in partes if p))
        self.entrada.icursor(tk.END)

    def _deslocar(self, dias: int) -> None:
        try:
            base = date.fromisoformat(self.get_iso())
        except services.RegraNegocioError:
            base = date.today()
        self.set_iso((base + timedelta(days=dias)).isoformat())

    def _normalizar(self) -> None:
        try:
            iso = self.get_iso()
        except services.RegraNegocioError:
            return
        problema = self._dentro_dos_limites(iso)
        if problema:
            messagebox.showwarning("Data fora do período", problema, parent=self.winfo_toplevel())
            iso = self._minimo if self._minimo and iso < self._minimo else self._maximo
        self.set_iso(iso)

    # --- calendário ----------------------------------------------------- #
    def abrir_calendario(self) -> None:
        if str(self.entrada.cget("state")) in ("disabled", "readonly"):
            return
        try:
            atual = date.fromisoformat(self.get_iso())
        except services.RegraNegocioError:
            atual = date.today()
        PopupCalendario(self, atual, self.set_iso, self._minimo, self._maximo)

    def get_iso(self) -> str:
        return services.para_iso(self.var.get())

    def set_iso(self, iso: str) -> None:
        self.var.set(services.para_br(iso))
        self._sincronizar_limites()

    def limpar(self) -> None:
        self.var.set("")

    def get(self) -> str:
        return self.var.get()


class PopupCalendario(tk.Toplevel):
    """Calendário de um mês, com navegação e limites de período."""

    def __init__(self, campo: CampoData, referencia: date, ao_escolher,
                 minimo: str | None = None, maximo: str | None = None):
        super().__init__(campo.winfo_toplevel())
        self.ao_escolher = ao_escolher
        self.selecionada = referencia
        self.mostrando = referencia.replace(day=1)
        self.minimo, self.maximo = minimo, maximo
        self.overrideredirect(True)          # sem barra de título: é um popup
        self.configure(bg=CORES["borda"])
        self.transient(campo.winfo_toplevel())

        corpo = tk.Frame(self, bg=CORES["superficie"], padx=10, pady=10)
        corpo.pack(padx=1, pady=1)

        topo = tk.Frame(corpo, bg=CORES["superficie"])
        topo.pack(fill="x", pady=(0, 8))
        ttk.Button(topo, text="◀", width=3, takefocus=False,
                   command=lambda: self._mudar_mes(-1)).pack(side="left")
        self.lbl_mes = tk.Label(topo, bg=CORES["superficie"], fg=CORES["texto"],
                                font=(FONTE, 11, "bold"), width=18)
        self.lbl_mes.pack(side="left", padx=4)
        ttk.Button(topo, text="▶", width=3, takefocus=False,
                   command=lambda: self._mudar_mes(1)).pack(side="left")

        self.grade = tk.Frame(corpo, bg=CORES["superficie"])
        self.grade.pack()

        rodape = tk.Frame(corpo, bg=CORES["superficie"])
        rodape.pack(fill="x", pady=(8, 0))
        ttk.Button(rodape, text="Hoje", takefocus=False,
                   command=lambda: self._escolher(date.today())).pack(side="left")
        ttk.Button(rodape, text="Fechar", takefocus=False,
                   command=self.destroy).pack(side="right")

        self._desenhar()
        self._posicionar(campo)
        # Sem janela visível, o grab falha silenciosamente e o popup some.
        self.update_idletasks()
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:          # pragma: no cover - janela fechada antes de aparecer
            pass
        self.lift()
        self.bind("<Escape>", lambda _e: self.destroy())
        # Clique fora fecha. (FocusOut não serve: o próprio grab já o dispara.)
        self.bind("<Button-1>", self._clique, add="+")

    def _clique(self, evento) -> None:
        fora = not (0 <= evento.x_root - self.winfo_rootx() <= self.winfo_width()
                    and 0 <= evento.y_root - self.winfo_rooty() <= self.winfo_height())
        if fora:
            self.destroy()

    def _posicionar(self, campo: CampoData) -> None:
        self.update_idletasks()
        x = campo.winfo_rootx()
        y = campo.winfo_rooty() + campo.winfo_height() + 2
        largura, altura = self.winfo_reqwidth(), self.winfo_reqheight()
        # Se não couber abaixo do campo, abre acima; nunca sai da tela.
        if y + altura > self.winfo_screenheight():
            y = max(0, campo.winfo_rooty() - altura - 2)
        x = max(0, min(x, self.winfo_screenwidth() - largura))
        self.geometry(f"+{x}+{y}")

    def _mudar_mes(self, passo: int) -> None:
        mes = self.mostrando.month + passo
        ano = self.mostrando.year + (mes - 1) // 12
        self.mostrando = date(ano, (mes - 1) % 12 + 1, 1)
        self._desenhar()

    def _permitida(self, dia: date) -> bool:
        iso = dia.isoformat()
        return not ((self.minimo and iso < self.minimo) or (self.maximo and iso > self.maximo))

    def _escolher(self, dia: date) -> None:
        if not self._permitida(dia):
            return
        self.ao_escolher(dia.isoformat())
        self.destroy()

    def _desenhar(self) -> None:
        for filho in self.grade.winfo_children():
            filho.destroy()
        self.lbl_mes.configure(
            text=f"{MESES_PT[self.mostrando.month - 1].capitalize()} {self.mostrando.year}")

        for coluna, nome in enumerate(DIAS_PT):
            tk.Label(self.grade, text=nome, bg=CORES["superficie"], fg=CORES["texto_suave"],
                     font=(FONTE, 9, "bold"), width=4).grid(row=0, column=coluna, pady=(0, 4))

        primeiro = self.mostrando
        deslocamento = primeiro.weekday()              # segunda = 0
        dias_no_mes = calendar.monthrange(primeiro.year, primeiro.month)[1]
        hoje = date.today()

        for numero in range(1, dias_no_mes + 1):
            dia = primeiro.replace(day=numero)
            linha, coluna = divmod(deslocamento + numero - 1, 7)
            permitida = self._permitida(dia)
            if dia == self.selecionada:
                fundo, frente = CORES["primaria"], "#ffffff"
            elif dia == hoje:
                fundo, frente = CORES["superficie_suave"], CORES["primaria"]
            else:
                fundo, frente = CORES["superficie"], (CORES["texto"] if permitida
                                                      else CORES["texto_suave"])
            botao = tk.Label(self.grade, text=str(numero), width=4, pady=3,
                             bg=fundo, fg=frente,
                             font=(FONTE, 10, "bold" if dia in (hoje, self.selecionada)
                                   else "normal"))
            botao.grid(row=linha + 1, column=coluna, padx=1, pady=1)
            if permitida:
                botao.bind("<Button-1>", lambda _e, d=dia: self._escolher(d))
                botao.bind("<Enter>", lambda _e, b=botao: b.configure(bg=CORES["superficie_suave"]))
                botao.bind("<Leave>", lambda _e, b=botao, f=fundo: b.configure(bg=f))


class CampoValor(ttk.Entry):
    """Dinheiro em reais, já formatado enquanto se digita: R$ 1.234,56.

    Digite apenas os números — os centavos vão se enchendo da direita para a
    esquerda, como em caixa eletrônico. Colar "1.234,56" ou "1234.56" também
    funciona.
    """

    PREFIXO = "R$ "
    MAXIMO_DIGITOS = 13          # até R$ 99.999.999.999,99
    TECLAS_LIVRES = {"Tab", "ISO_Left_Tab", "Return", "KP_Enter", "Escape", "Left", "Right",
                     "Home", "End", "Up", "Down", "Shift_L", "Shift_R", "Control_L",
                     "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Num_Lock"}
    CONTROL = 0x0004

    def __init__(self, master, **kwargs):
        self.var = tk.StringVar()
        super().__init__(master, textvariable=self.var, justify="right",
                         width=kwargs.pop("width", 14), font=(FONTE, 11), **kwargs)
        # A tecla é tratada ANTES de entrar no texto e depois descartada
        # ("break"): o campo nunca fica num estado intermediário que precise ser
        # interpretado. A versão anterior lia o texto já alterado e confundia
        # cada tecla com uma colagem — o valor travava em R$ 0,01.
        self.bind("<KeyPress>", self._tecla)
        self.bind("<<Paste>>", self._colar)
        self.bind("<FocusIn>", lambda _e: self.after_idle(self._selecionar_tudo))
        self.bind("<FocusOut>", lambda _e: self._formatar())

    # --- digitação ------------------------------------------------------- #
    def _editavel(self) -> bool:
        return str(self.cget("state")) not in ("disabled", "readonly")

    def _centavos(self) -> int:
        digitos = "".join(c for c in self.var.get() if c.isdigit())
        return int(digitos) if digitos else 0

    def _tecla(self, evento):
        if evento.keysym in self.TECLAS_LIVRES or evento.state & self.CONTROL:
            return None                      # navegação, Tab, Ctrl+C/V/A seguem normais
        if not self._editavel():
            return "break"

        substituir = self.selection_present()
        if evento.char and evento.char.isdigit():
            base = 0 if substituir else self._centavos()
            novo = base * 10 + int(evento.char)
            if len(str(novo)) <= self.MAXIMO_DIGITOS:
                self._mostrar(novo)
            return "break"

        if evento.keysym in ("BackSpace", "Delete"):
            novo = 0 if substituir else self._centavos() // 10
            if novo:
                self._mostrar(novo)
            else:
                self.limpar()
            return "break"

        return "break"                       # letras e símbolos não entram

    def _colar(self, _evento=None):
        if not self._editavel():
            return "break"
        try:
            self.set_valor(abs(services.para_float(self.clipboard_get())))
        except (tk.TclError, services.RegraNegocioError):
            pass
        return "break"

    def _selecionar_tudo(self) -> None:
        """Ao entrar no campo, o valor fica selecionado: digitar substitui."""
        if self.var.get() and self._editavel():
            self.select_range(0, tk.END)
            self.icursor(tk.END)

    def _mostrar(self, centavos: int) -> None:
        self.var.set(self.PREFIXO + self._formatar_centavos(centavos))
        self.selection_clear()
        self.icursor(tk.END)

    @staticmethod
    def _formatar_centavos(centavos: int) -> str:
        return f"{centavos / 100:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")

    def _formatar(self) -> None:
        if self.var.get().strip():
            try:
                self.set_valor(services.para_float(self.var.get()))
            except services.RegraNegocioError:
                self.limpar()

    def ao_mudar(self, funcao: Callable[[], None], atraso: int = 300) -> None:
        """Chama `funcao` quando o valor para de mudar por um instante.

        Use isto em vez de ligar em <KeyRelease>: recalcular (ou redimensionar
        a janela) a cada tecla deixava a digitação lenta.
        """
        pendente: list[str | None] = [None]

        def disparar() -> None:
            pendente[0] = None
            try:
                funcao()
            except tk.TclError:          # pragma: no cover - janela já fechada
                pass

        def agendar(*_args) -> None:
            if pendente[0] is not None:
                self.after_cancel(pendente[0])
            pendente[0] = self.after(atraso, disparar)

        self.var.trace_add("write", agendar)

    # --- leitura e escrita ---------------------------------------------- #
    def get_valor(self) -> float:
        return services.para_float(self.var.get())

    def set_valor(self, valor: float) -> None:
        sinal = "-" if valor < 0 else ""
        self.var.set(sinal + self.PREFIXO + self._formatar_centavos(round(abs(valor) * 100)))

    def limpar(self) -> None:
        self.var.set("")


class SeletorConta(ttk.Combobox):
    """Lista de contas/categorias com busca por código ou nome."""

    def __init__(self, master, apenas_analiticas: bool = True, permitir_vazio: bool = False,
                 tipos: tuple[str, ...] | None = None, rotulo_vazio: str | None = None,
                 **kwargs):
        self._apenas_analiticas = apenas_analiticas
        self._permitir_vazio = permitir_vazio or rotulo_vazio is not None
        self._tipos = tipos
        # Opção fixa no topo da lista para desfazer o filtro (ex.: "(todas)").
        self._rotulo_vazio = rotulo_vazio
        self._mapa: dict[str, int] = {}
        self._todos: list[str] = []
        super().__init__(master, state="normal", font=(FONTE, 10),
                         width=kwargs.pop("width", 46), **kwargs)
        self.recarregar()
        self.bind("<KeyRelease>", self._filtrar)

    def _com_vazio(self, itens: list[str]) -> list[str]:
        return [self._rotulo_vazio] + itens if self._rotulo_vazio else itens

    def recarregar(self) -> None:
        atual = self.get()
        contas = services.listar_contas(apenas_ativas=True, apenas_analiticas=self._apenas_analiticas)
        if self._tipos:
            contas = [c for c in contas if c["tipo"] in self._tipos]
        self._mapa = {f"{c['nome']}  ({c['codigo']})": c["id"] for c in contas}
        self._todos = list(self._mapa)
        self["values"] = self._com_vazio(self._todos)
        if atual in self._mapa:
            self.set(atual)
        elif self._rotulo_vazio and not atual:
            self.set(self._rotulo_vazio)

    def _filtrar(self, evento) -> None:
        if evento.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        termo = self.get().strip().lower()
        achados = [t for t in self._todos if termo in t.lower()] if termo else self._todos
        self["values"] = self._com_vazio(achados)

    def get_conta_id(self) -> int | None:
        texto = self.get().strip()
        if self._rotulo_vazio and texto == self._rotulo_vazio:
            return None
        conta_id = self._mapa.get(texto)
        if conta_id is None and texto and not self._permitir_vazio:
            iguais = [r for r in self._todos if r.lower().startswith(texto.lower())]
            if len(iguais) == 1:
                self.set(iguais[0])
                return self._mapa[iguais[0]]
            raise services.RegraNegocioError(
                f"Não encontrei a conta {texto!r}. Escolha uma opção da lista.")
        return conta_id

    def set_conta_id(self, conta_id: int | None) -> None:
        if conta_id is None:
            self.set(self._rotulo_vazio or "")
            return
        for rotulo, cid in self._mapa.items():
            if cid == conta_id:
                self.set(rotulo)
                return
        self.set("")


class SeletorCentro(ttk.Combobox):
    def __init__(self, master, **kwargs):
        self._mapa: dict[str, int] = {}
        super().__init__(master, state="readonly", width=kwargs.pop("width", 22), **kwargs)
        self.recarregar()

    def recarregar(self) -> None:
        centros = services.listar_centros(apenas_ativos=True)
        self._mapa = {c["nome"]: c["id"] for c in centros}
        self["values"] = ["(nenhum)"] + list(self._mapa)
        if not self.get():
            self.set("(nenhum)")

    def get_centro_id(self) -> int | None:
        return self._mapa.get(self.get())

    def set_centro_id(self, centro_id: int | None) -> None:
        for nome, cid in self._mapa.items():
            if cid == centro_id:
                self.set(nome)
                return
        self.set("(nenhum)")


# --------------------------------------------------------------------------- #
# Blocos visuais
# --------------------------------------------------------------------------- #
class Cabecalho(ttk.Frame):
    """Faixa branca no topo da tela: título grande, explicação e ações."""

    def __init__(self, master, titulo: str, explicacao: str = ""):
        super().__init__(master, style="Topo.TFrame", padding=(24, 18))
        textos = ttk.Frame(self, style="Topo.TFrame")
        textos.pack(side="left", fill="x", expand=True)
        ttk.Label(textos, text=titulo, style="Titulo.TLabel").pack(anchor="w")
        if explicacao:
            # A explicação quebra em mais linhas em telas estreitas em vez de
            # esticar o cabeçalho e, com ele, a largura mínima da tela toda.
            self._explicacao = ttk.Label(textos, text=explicacao, style="SubtituloTopo.TLabel",
                                         wraplength=self.LARGURA_EXPLICACAO[0], justify="left")
            self._explicacao.pack(anchor="w", pady=(4, 0))
            textos.bind("<Configure>", self._ajustar_quebra)

        self.acoes = ttk.Frame(self, style="Topo.TFrame")
        self.acoes.pack(side="right")

    LARGURA_EXPLICACAO = (280, 500)   # mínimo e máximo da linha de explicação

    def _ajustar_quebra(self, evento) -> None:
        # Teto proposital: sem ele, em telas largas a explicação vira uma linha
        # única de 900px e passa a ser ela a ditar a largura mínima da tela.
        menor, maior = self.LARGURA_EXPLICACAO
        self._explicacao.configure(wraplength=min(max(evento.width - 12, menor), maior))

    def botao(self, texto: str, comando, estilo: str = "TButton") -> ttk.Button:
        botao = ttk.Button(self.acoes, text=texto, command=comando, style=estilo)
        botao.pack(side="right", padx=(8, 0))
        return botao


class Cartao(tk.Canvas):
    """Indicador do painel: caixa arredondada com título, número grande e nota."""

    LARGURA, ALTURA = 250, 128
    LARGURA_MINIMA = 185

    def __init__(self, master, titulo: str, nota: str = ""):
        # Largura pequena de propósito: o cartão estica com a coluna do grid, e
        # um mínimo alto obrigaria a janela inteira a ficar larga.
        super().__init__(master, width=self.LARGURA_MINIMA, height=self.ALTURA,
                         bg=CORES["fundo"], highlightthickness=0)
        self._titulo = titulo
        self._valor = "—"
        self._nota = nota
        self._cor = CORES["texto"]
        self._faixa = CORES["primaria"]
        self.bind("<Configure>", lambda _e: self._desenhar())

    def atualizar(self, valor: str, cor: str | None = None, nota: str | None = None,
                  faixa: str | None = None) -> None:
        self._valor = valor
        self._cor = cor or CORES["texto"]
        if nota is not None:
            self._nota = nota
        self._faixa = faixa or self._cor
        self._desenhar()

    def _desenhar(self) -> None:
        self.delete("all")
        largura = max(self.winfo_width(), 10)
        altura = self.ALTURA
        _retangulo_arredondado(self, 2, 2, largura - 2, altura - 2, 14,
                               fill=CORES["superficie"], outline=CORES["borda"])
        self.create_rectangle(2, 2, 8, altura - 2, fill=self._faixa, outline="")
        util = largura - 34   # espaço entre o texto e a borda direita
        self.create_text(22, 24, text=self._titulo.upper(), anchor="w",
                         font=(FONTE, 9, "bold"), fill=CORES["texto_suave"],
                         width=util)
        self.create_text(22, 62, text=self._valor, anchor="w",
                         font=(FONTE, 22, "bold"), fill=self._cor)
        if self._nota:
            # A nota quebra em duas linhas em vez de sair cortada pela borda.
            self.create_text(22, 98, text=self._nota, anchor="w",
                             font=(FONTE, 9), fill=CORES["texto_suave"],
                             width=util)


def _retangulo_arredondado(canvas: tk.Canvas, x1, y1, x2, y2, raio, **kwargs):
    pontos = [
        x1 + raio, y1, x2 - raio, y1, x2, y1, x2, y1 + raio,
        x2, y2 - raio, x2, y2, x2 - raio, y2, x1 + raio, y2,
        x1, y2, x1, y2 - raio, x1, y1 + raio, x1, y1,
    ]
    return canvas.create_polygon(pontos, smooth=True, **kwargs)


class Painel(ttk.Frame):
    """Bloco branco com título opcional, usado para agrupar conteúdo."""

    def __init__(self, master, titulo: str = "", dica: str = "", padding: int = 16):
        super().__init__(master, style="Superficie.TFrame", padding=padding)
        self.configure(relief="solid", borderwidth=1)
        if titulo:
            ttk.Label(self, text=titulo, style="SecaoSuperficie.TLabel").pack(anchor="w")
        if dica:
            ttk.Label(self, text=dica, style="DicaSuperficie.TLabel",
                      wraplength=680, justify="left").pack(anchor="w", pady=(2, 8))
        elif titulo:
            ttk.Label(self, text="", style="Superficie.TLabel").pack(pady=2)


class ListaLateral(ttk.Frame):
    """Menu vertical de opções com título e uma linha de explicação.

    Usado no lugar de abas quando há muitas opções: nada é comprimido nem
    abreviado, e cada item diz para que serve.
    """

    def __init__(self, master, itens: list[tuple[str, str]],
                 on_selecionar: Callable[[int], None], largura: int = 226):
        super().__init__(master, style="Superficie.TFrame", padding=6)
        self.configure(relief="solid", borderwidth=1, width=largura)
        self.pack_propagate(False)
        self.on_selecionar = on_selecionar
        self._itens: list[dict] = []
        self._ativo = -1

        for indice, (titulo, descricao) in enumerate(itens):
            linha = tk.Frame(self, bg=CORES["superficie"], cursor="hand2")
            linha.pack(fill="x", pady=1)
            faixa = tk.Frame(linha, bg=CORES["superficie"], width=4)
            faixa.pack(side="left", fill="y")
            textos = tk.Frame(linha, bg=CORES["superficie"], padx=10, pady=8)
            textos.pack(side="left", fill="both", expand=True)
            lbl_titulo = tk.Label(textos, text=titulo, bg=CORES["superficie"],
                                  fg=CORES["texto"], font=(FONTE, 10, "bold"),
                                  anchor="w", justify="left")
            lbl_titulo.pack(fill="x")
            lbl_desc = tk.Label(textos, text=descricao, bg=CORES["superficie"],
                                fg=CORES["texto_suave"], font=(FONTE, 8),
                                anchor="w", justify="left", wraplength=largura - 40)
            lbl_desc.pack(fill="x")

            item = {"linha": linha, "faixa": faixa, "textos": textos,
                    "titulo": lbl_titulo, "desc": lbl_desc}
            self._itens.append(item)
            for widget in (linha, textos, lbl_titulo, lbl_desc):
                widget.bind("<Button-1>", lambda _e, i=indice: self.selecionar(i))
                widget.bind("<Enter>", lambda _e, i=indice: self._destacar(i, True))
                widget.bind("<Leave>", lambda _e, i=indice: self._destacar(i, False))

    def _pintar(self, indice: int, fundo: str, cor_faixa: str, cor_titulo: str) -> None:
        item = self._itens[indice]
        for chave in ("linha", "textos"):
            item[chave].configure(bg=fundo)
        item["faixa"].configure(bg=cor_faixa)
        item["titulo"].configure(bg=fundo, fg=cor_titulo)
        item["desc"].configure(bg=fundo)

    def _destacar(self, indice: int, entrando: bool) -> None:
        if indice == self._ativo:
            return
        fundo = CORES["superficie_suave"] if entrando else CORES["superficie"]
        self._pintar(indice, fundo, fundo, CORES["texto"])

    def selecionar(self, indice: int) -> None:
        if not 0 <= indice < len(self._itens):
            return
        if self._ativo >= 0:
            self._pintar(self._ativo, CORES["superficie"], CORES["superficie"], CORES["texto"])
        self._ativo = indice
        self._pintar(indice, CORES["primaria_suave"], CORES["primaria"], CORES["primaria_escura"])
        self.on_selecionar(indice)

    @property
    def ativo(self) -> int:
        return self._ativo


class Tabela(ttk.Frame):
    """Lista de dados com cabeçalho, rolagem e ordenação por clique."""

    ALTURA_LINHA = 34   # igual ao rowheight definido no tema

    def __init__(self, master, colunas: Iterable[tuple[str, str, int, str]],
                 on_duplo_clique: Callable[[str], None] | None = None, altura: int = 14,
                 largura_livre: bool = False):
        super().__init__(master, style="Superficie.TFrame", padding=1)
        self.configure(relief="solid", borderwidth=1)
        self.colunas = list(colunas)
        ids = [c[0] for c in self.colunas]
        self.tree = ttk.Treeview(self, columns=ids, show="headings", height=altura,
                                 selectmode="browse")
        for cid, titulo, largura, alinhamento in self.colunas:
            self.tree.heading(cid, text=titulo, command=lambda c=cid: self.ordenar(c))
            self.tree.column(cid, width=largura, anchor=alinhamento,
                             stretch=(alinhamento == "w"))
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self._hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self._vsb.set, xscrollcommand=self._hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self._altura = altura
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._ordem_reversa = False
        self._largura_minima = sum(c[2] for c in self.colunas)
        if largura_livre:
            # O quadro não cresce junto com as colunas: quem rola na horizontal
            # é a própria tabela, e a tela continua cabendo na janela. Sem isso,
            # uma tabela de 1.600px obriga a janela inteira a ter 1.600px.
            # Altura mínima curta de propósito: a tabela cresce com a janela,
            # mas em telas baixas ela encolhe em vez de empurrar os botões e os
            # totais para fora da área visível.
            minimo = min(altura, 4)
            self.configure(width=460, height=minimo * self.ALTURA_LINHA + 74)
            self.grid_propagate(False)
            self.pack_propagate(False)
        self.bind("<Configure>", lambda _e: self._ajustar_rolagem())

        from app.ui.theme import marcar_zebra
        marcar_zebra(self.tree)

        self._vazio = ttk.Label(self, text="", style="Superficie.TLabel",
                                foreground=CORES["texto_suave"], font=(FONTE, 11))
        self._texto_vazio = "Nenhum registro encontrado."

        if on_duplo_clique:
            self.tree.bind("<Double-1>", lambda _e: self._acionar(on_duplo_clique))
            self.tree.bind("<Return>", lambda _e: self._acionar(on_duplo_clique))

    def definir_texto_vazio(self, texto: str) -> None:
        self._texto_vazio = texto

    def _ajustar_rolagem(self) -> None:
        """Só mostra cada barra quando o conteúdo realmente não cabe."""
        if self.winfo_width() - 24 < self._largura_minima:
            self._hsb.grid(row=1, column=0, sticky="ew")
        else:
            self._hsb.grid_remove()

        visiveis = max(self.tree.cget("height"), 1)
        if len(self.tree.get_children()) > visiveis:
            self._vsb.grid(row=0, column=1, sticky="ns")
        else:
            self._vsb.grid_remove()

    def _acionar(self, callback: Callable[[str], None]) -> None:
        item = self.selecionado()
        if item:
            callback(item)

    def limpar(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def inserir(self, valores: Iterable, iid: str | int | None = None,
                tags: tuple[str, ...] = ()) -> str:
        indice = len(self.tree.get_children())
        zebra = "par" if indice % 2 == 0 else "impar"
        return self.tree.insert("", "end", iid=str(iid) if iid is not None else None,
                                values=tuple(valores), tags=tags + (zebra,))

    def finalizar(self) -> None:
        """Mostra o aviso de lista vazia quando não há linhas."""
        self._ajustar_rolagem()
        if self.tree.get_children():
            self._vazio.place_forget()
        else:
            self._vazio.configure(text=self._texto_vazio)
            self._vazio.place(relx=0.5, rely=0.5, anchor="center")

    def selecionado(self) -> str | None:
        selecao = self.tree.selection()
        return selecao[0] if selecao else None

    def ordenar(self, coluna: str) -> None:
        self._ordem_reversa = not self._ordem_reversa
        itens = [(self.tree.set(k, coluna), k) for k in self.tree.get_children("")]

        def chave(par):
            texto = par[0].replace(".", "").replace(",", ".").replace("R$", "").strip()
            try:
                return (0, float(texto))
            except ValueError:
                return (1, par[0].lower())

        itens.sort(key=chave, reverse=self._ordem_reversa)
        for indice, (_, k) in enumerate(itens):
            self.tree.move(k, "", indice)
            tags = [t for t in self.tree.item(k, "tags") if t not in ("par", "impar")]
            self.tree.item(k, tags=tags + ["par" if indice % 2 == 0 else "impar"])


class AreaRolavel(ttk.Frame):
    """Área com rolagem vertical: o conteúdo vai dentro de ``.interno``.

    Evita que painéis com muitos quadros fiquem espremidos (ou cortados)
    quando a janela é menor que o conteúdo.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                 background=CORES["fundo"])
        self._barra = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._barra_h = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._barra.set,
                               xscrollcommand=self._barra_h.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.interno = ttk.Frame(self._canvas)
        self._janela = self._canvas.create_window((0, 0), window=self.interno, anchor="nw")

        self.interno.bind("<Configure>", self._ao_mudar_conteudo)
        self._canvas.bind("<Configure>", self._ao_mudar_area)
        # A roda do mouse só é capturada enquanto o ponteiro está sobre esta
        # área. Um "bind_all" permanente fazia a roda girada dentro de uma
        # janela aberta por cima rolar a tela que ficou atrás.
        self.bind("<Enter>", self._assumir_roda)
        self.bind("<Leave>", self._liberar_roda)
        self.bind("<Destroy>", self._liberar_roda)

    def _ao_mudar_conteudo(self, _evento=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._ajustar_largura()
        self._atualizar_barra()

    def _ao_mudar_area(self, _evento=None) -> None:
        self._ajustar_largura()
        self._atualizar_barra()

    def _ajustar_largura(self) -> None:
        """O conteúdo ocupa a área visível, mas nunca fica menor que o mínimo de
        que precisa — nesse caso aparece a rolagem.

        Dar a altura da janela ao conteúdo (e não só a que ele pede) é o que
        faz as tabelas esticarem até o rodapé em telas grandes.
        """
        largura = max(self._canvas.winfo_width(), self.interno.winfo_reqwidth())
        altura = max(self._canvas.winfo_height(), self.interno.winfo_reqheight())
        self._canvas.itemconfigure(self._janela, width=largura, height=altura)

    def _atualizar_barra(self) -> None:
        if self.interno.winfo_reqheight() > self._canvas.winfo_height():
            self._barra.grid(row=0, column=1, sticky="ns")
        else:
            self._barra.grid_remove()
            self._canvas.yview_moveto(0)
        if self.interno.winfo_reqwidth() > self._canvas.winfo_width():
            self._barra_h.grid(row=1, column=0, sticky="ew")
        else:
            self._barra_h.grid_remove()
            self._canvas.xview_moveto(0)

    def _assumir_roda(self, _evento=None) -> None:
        self._canvas.bind_all("<MouseWheel>", self._rolar)

    def _liberar_roda(self, _evento=None) -> None:
        try:
            self._canvas.unbind_all("<MouseWheel>")
        except tk.TclError:      # pragma: no cover - janela já destruída
            pass

    def _rolar(self, evento) -> None:
        if not self.winfo_ismapped() or not self._barra.winfo_viewable():
            return
        # Com uma janela modal aberta, quem manda é ela: a tela de trás fica
        # parada mesmo se o ponteiro passar por cima dela.
        dono = self.grab_current()
        if dono is not None and dono.winfo_toplevel() is not self.winfo_toplevel():
            return
        sob = self.winfo_containing(evento.x_root, evento.y_root)
        while sob is not None:
            if sob is self:
                self._canvas.yview_scroll(-1 if evento.delta > 0 else 1, "units")
                return
            sob = getattr(sob, "master", None)


class Paginacao(ttk.Frame):
    """Divide uma lista longa em páginas, com setas e contagem.

    Quem usa entrega a lista completa em ``definir`` e recebe, no retorno de
    chamada, apenas os itens da página que deve ser desenhada.
    """

    OPCOES = (5, 10, 20, 50)

    def __init__(self, master, ao_mudar: Callable[[list], None], por_pagina: int = 5,
                 fundo: str = "Superficie.TFrame", nome_itens: str = "itens"):
        super().__init__(master, style=fundo)
        self._ao_mudar = ao_mudar
        self._itens: list = []
        self._pagina = 0
        self._por_pagina = por_pagina
        self._nome = nome_itens
        estilo_dica = ("DicaSuperficie.TLabel" if fundo == "Superficie.TFrame"
                       else "Dica.TLabel")

        self.btn_anterior = ttk.Button(self, text="◀", width=3, takefocus=False,
                                       command=lambda: self.ir(self._pagina - 1))
        self.btn_anterior.pack(side="left")
        self.lbl = ttk.Label(self, style=estilo_dica)
        self.lbl.pack(side="left", padx=8)
        self.btn_proximo = ttk.Button(self, text="▶", width=3, takefocus=False,
                                      command=lambda: self.ir(self._pagina + 1))
        self.btn_proximo.pack(side="left")

        self.cb_tamanho = ttk.Combobox(self, state="readonly", width=4,
                                       values=[str(o) for o in self.OPCOES])
        self.cb_tamanho.set(str(por_pagina))
        self.cb_tamanho.pack(side="right")
        self.cb_tamanho.bind("<<ComboboxSelected>>", lambda _e: self._mudar_tamanho())
        ttk.Label(self, text="por página", style=estilo_dica).pack(side="right", padx=6)

    # ------------------------------------------------------------------ #
    def definir(self, itens: list) -> None:
        """Guarda a lista completa e redesenha a página atual."""
        self._itens = list(itens)
        self._pagina = min(self._pagina, max(self.total_paginas() - 1, 0))
        self._desenhar()

    def total_paginas(self) -> int:
        return max(-(-len(self._itens) // self._por_pagina), 1)

    def ir(self, pagina: int) -> None:
        pagina = max(0, min(pagina, self.total_paginas() - 1))
        if pagina != self._pagina:
            self._pagina = pagina
            self._desenhar()

    def _mudar_tamanho(self) -> None:
        self._por_pagina = int(self.cb_tamanho.get())
        self._pagina = 0
        self._desenhar()

    def _desenhar(self) -> None:
        inicio = self._pagina * self._por_pagina
        fatia = self._itens[inicio:inicio + self._por_pagina]
        total, paginas = len(self._itens), self.total_paginas()
        if total == 0:
            self.lbl.configure(text=f"nenhum {self._nome[:-1]}"
                                    if self._nome.endswith("s") else f"nenhum {self._nome}")
        else:
            fim = min(inicio + self._por_pagina, total)
            self.lbl.configure(
                text=f"Página {self._pagina + 1} de {paginas}"
                     f"  ·  {inicio + 1}–{fim} de {total} {self._nome}")
        self.btn_anterior.state(["disabled"] if self._pagina == 0 else ["!disabled"])
        self.btn_proximo.state(["disabled"] if self._pagina >= paginas - 1 else ["!disabled"])
        self._ao_mudar(fatia)


class BarraFiltro(ttk.Frame):
    """Escolha de período em linguagem simples."""

    OPCOES = ["Este mês", "Mês passado", "Últimos 30 dias", "Últimos 3 meses",
              "Este ano", "Todo o histórico", "Escolher datas"]

    def __init__(self, master, on_aplicar: Callable[[], None], fundo: str = "TFrame",
                 inicial: str = "Este mês"):
        super().__init__(master, style=fundo)
        self.on_aplicar = on_aplicar
        estilo_label = "CampoSuperficie.TLabel" if fundo == "Superficie.TFrame" else "Campo.TLabel"

        ttk.Label(self, text="Mostrar:", style=estilo_label).pack(side="left")
        self.cb_atalho = ttk.Combobox(self, state="readonly", width=16, values=self.OPCOES)
        self.cb_atalho.set(inicial if inicial in self.OPCOES else "Este mês")
        self.cb_atalho.pack(side="left", padx=(8, 8))
        self.cb_atalho.bind("<<ComboboxSelected>>", lambda _e: self._aplicar_atalho())

        # Navegação mês a mês
        self.btn_anterior = ttk.Button(self, text="◀", width=3,
                                       command=lambda: self.deslocar(-1), takefocus=False)
        self.btn_anterior.pack(side="left")
        self.btn_proximo = ttk.Button(self, text="▶", width=3,
                                      command=lambda: self.deslocar(1), takefocus=False)
        self.btn_proximo.pack(side="left", padx=(4, 12))

        self.area_datas = ttk.Frame(self, style=fundo)
        ttk.Label(self.area_datas, text="de", style=estilo_label).pack(side="left")
        self.dt_inicio = CampoData(self.area_datas, services.primeiro_dia_mes())
        self.dt_inicio.pack(side="left", padx=6)
        ttk.Label(self.area_datas, text="até", style=estilo_label).pack(side="left")
        self.dt_fim = CampoData(self.area_datas, services.ultimo_dia_mes())
        self.dt_fim.pack(side="left", padx=6)
        # O fim nunca pode ser antes do início — e vice-versa.
        self.dt_inicio.ligar_intervalo(self.dt_fim)
        ttk.Button(self.area_datas, text="Aplicar", style="Primario.TButton",
                   command=self.on_aplicar).pack(side="left", padx=(4, 0))

        self.lbl_periodo = ttk.Label(
            self, style="DicaSuperficie.TLabel" if fundo == "Superficie.TFrame" else "Dica.TLabel")
        self.lbl_periodo.pack(side="left")
        # Sem isto, o atalho inicial aparecia escolhido mas as datas seguiam no mês.
        self._aplicar_atalho(avisar=False)
        self._atualizar_rotulo()

        # Datas digitadas também consultam sozinhas, sem precisar do botão.
        self._auto = AutoConsulta(self, self._ao_mudar_datas, atraso=500)
        self._auto.ligar_campos(self.dt_inicio, self.dt_fim)

    def _ao_mudar_datas(self) -> None:
        try:
            self.periodo()
        except services.RegraNegocioError:
            return  # data ainda incompleta: espera o usuário terminar de digitar
        self._atualizar_rotulo()
        self.on_aplicar()

    def _intervalo(self, opcao: str) -> tuple[str, str]:
        """As datas de cada atalho, sem mexer na tela."""
        hoje = date.today()
        if opcao == "Este mês":
            inicio, fim = services.primeiro_dia_mes(), services.ultimo_dia_mes()
        elif opcao == "Mês passado":
            anterior = hoje.replace(day=1) - timedelta(days=1)
            inicio, fim = services.primeiro_dia_mes(anterior), services.ultimo_dia_mes(anterior)
        elif opcao == "Últimos 30 dias":
            inicio, fim = (hoje - timedelta(days=30)).isoformat(), hoje.isoformat()
        elif opcao == "Últimos 3 meses":
            inicio, fim = (hoje - timedelta(days=90)).isoformat(), hoje.isoformat()
        elif opcao == "Este ano":
            inicio = hoje.replace(month=1, day=1).isoformat()
            fim = hoje.replace(month=12, day=31).isoformat()
        else:
            # Todo o histórico: começa no primeiro registro que existe de verdade.
            primeiro = services.primeiro_mes_registrado()
            inicio = f"{primeiro}-01" if primeiro else "1900-01-01"
            fim = max(hoje.isoformat(), services.ultimo_dia_mes())
        return inicio, fim

    def _aplicar_atalho(self, avisar: bool = True) -> None:
        opcao = self.cb_atalho.get()
        if opcao == "Escolher datas":
            self.lbl_periodo.pack_forget()
            self.area_datas.pack(side="left")
            return
        self.area_datas.pack_forget()
        inicio, fim = self._intervalo(opcao)
        self.dt_inicio.set_iso(inicio)
        self.dt_fim.set_iso(fim)
        self._atualizar_rotulo()
        self.lbl_periodo.pack(side="left")
        if avisar:
            self.on_aplicar()

    def revalidar(self) -> bool:
        """Reacerta as datas quando o dia vira com o programa aberto.

        O atalho é relativo a hoje, mas as datas foram calculadas uma vez só, na
        hora em que a tela nasceu. Quem deixa o sistema na bandeja atravessava a
        virada do mês vendo "Este mês" com o mês anterior dentro.

        Período escolhido à mão fica como está — ali a data é do usuário.
        """
        opcao = self.cb_atalho.get()
        if opcao == "Escolher datas":
            return False
        try:
            if self.periodo() == self._intervalo(opcao):
                return False
        except services.RegraNegocioError:
            pass
        self._aplicar_atalho(avisar=False)
        return True

    def deslocar(self, passos: int) -> None:
        """◀ ▶ andam de mês em mês quando o período é um mês inteiro.

        Em qualquer outro período, desliza a janela pelo mesmo número de dias.
        """
        try:
            inicio, fim = (date.fromisoformat(d) for d in self.periodo())
        except (services.RegraNegocioError, ValueError):
            return
        if self._e_mes_inteiro(inicio, fim):
            novo = services.somar_meses(inicio.replace(day=1), passos)
            inicio = novo.replace(day=1)
            fim = date.fromisoformat(services.ultimo_dia_mes(inicio))
        else:
            dias = (fim - inicio).days + 1
            inicio += timedelta(days=dias * passos)
            fim += timedelta(days=dias * passos)
        self.dt_inicio.set_iso(inicio.isoformat())
        self.dt_fim.set_iso(fim.isoformat())
        self.cb_atalho.set("Escolher datas")
        self.area_datas.pack_forget()
        self._atualizar_rotulo()
        self.lbl_periodo.pack(side="left")
        self.on_aplicar()

    @staticmethod
    def _e_mes_inteiro(inicio: date, fim: date) -> bool:
        return (inicio.day == 1 and inicio.year == fim.year and inicio.month == fim.month
                and fim.isoformat() == services.ultimo_dia_mes(inicio))

    def _atualizar_rotulo(self) -> None:
        try:
            inicio_iso, fim_iso = self.periodo()
            inicio, fim = date.fromisoformat(inicio_iso), date.fromisoformat(fim_iso)
        except (services.RegraNegocioError, ValueError):
            return
        if inicio_iso <= "1900-01-01":
            texto = "todo o histórico"
        elif self._e_mes_inteiro(inicio, fim):
            texto = services.mes_nome(inicio_iso[:7]).capitalize()
        else:
            texto = f"{services.para_br(inicio_iso)}  até  {services.para_br(fim_iso)}"
        self.lbl_periodo.configure(text=texto)

    def periodo(self) -> tuple[str, str]:
        return self.dt_inicio.get_iso(), self.dt_fim.get_iso()


class GraficoBarras(tk.Canvas):
    """Comparativo mensal de entradas e saídas, desenhado sem bibliotecas externas."""

    def __init__(self, master, altura: int = 210, **kwargs):
        super().__init__(master, height=altura, bg=CORES["superficie"], highlightthickness=0,
                         **kwargs)
        self._dados: list[dict] = []
        self.bind("<Configure>", lambda _e: self._desenhar())

    def definir_dados(self, dados: list[dict]) -> None:
        self._dados = dados
        self._desenhar()

    def _desenhar(self) -> None:
        self.delete("all")
        largura, altura = self.winfo_width(), self.winfo_height()
        if largura < 60 or altura < 60:
            return
        if not self._dados:
            self.create_text(largura / 2, altura / 2,
                             text="Ainda não há movimentos para mostrar aqui.",
                             fill=CORES["texto_suave"], font=(FONTE, 10))
            return

        margem, margem_inf, margem_sup = 16, 34, 34
        area = altura - margem_inf - margem_sup
        maximo = max(max(d["receita"], d["despesa"]) for d in self._dados) or 1.0
        passo = (largura - margem * 2) / len(self._dados)
        largura_barra = min(20, max(7, passo / 3.2))
        base = altura - margem_inf

        for fracao in (0.5, 1.0):
            y = base - area * fracao
            self.create_line(margem, y, largura - margem, y, fill=CORES["borda"], dash=(2, 4))
        self.create_line(margem, base, largura - margem, base, fill=CORES["borda_forte"])

        for indice, item in enumerate(self._dados):
            centro = margem + passo * indice + passo / 2
            for deslocamento, chave, cor in (
                (-largura_barra / 2 - 1.5, "receita", CORES["sucesso"]),
                (largura_barra / 2 + 1.5, "despesa", CORES["perigo"]),
            ):
                alto = max(2, area * (item[chave] / maximo))
                x = centro + deslocamento
                _retangulo_arredondado(self, x - largura_barra / 2, base - alto,
                                       x + largura_barra / 2, base, 3, fill=cor, outline="")
            self.create_text(centro, base + 14, text=f"{item['mes'][5:7]}/{item['mes'][2:4]}",
                             font=(FONTE, 8), fill=CORES["texto_suave"])

        self.create_oval(margem, 12, margem + 10, 22, fill=CORES["sucesso"], outline="")
        self.create_text(margem + 18, 17, text="Entrou", anchor="w", font=(FONTE, 9),
                         fill=CORES["texto_suave"])
        self.create_oval(margem + 76, 12, margem + 86, 22, fill=CORES["perigo"], outline="")
        self.create_text(margem + 94, 17, text="Saiu", anchor="w", font=(FONTE, 9),
                         fill=CORES["texto_suave"])


class AutoConsulta:
    """Refaz a consulta sozinho quando o usuário mexe em um filtro.

    Campos de digitação esperam um instante depois da última tecla, para não
    consultar a cada letra; listas e caixas de seleção disparam na hora.
    """

    def __init__(self, widget: tk.Misc, callback: Callable[[], None], atraso: int = 350):
        self._widget = widget
        self._callback = callback
        self._atraso = atraso
        self._pendente: str | None = None
        self._ligado = True

    def agendar(self, *_args) -> None:
        if not self._ligado:
            return
        if self._pendente is not None:
            try:
                self._widget.after_cancel(self._pendente)
            except Exception:
                pass
        self._pendente = self._widget.after(self._atraso, self._disparar)

    def imediato(self, *_args) -> None:
        if self._ligado:
            self._callback()

    def _disparar(self) -> None:
        self._pendente = None
        if self._ligado:
            self._callback()

    def pausar(self) -> None:
        """Evita consultas enquanto vários filtros são mudados de uma vez."""
        self._ligado = False

    def retomar(self, consultar: bool = True) -> None:
        self._ligado = True
        if consultar:
            self._callback()

    # --- ligações prontas -------------------------------------------- #
    def ligar_combos(self, *combos: ttk.Combobox) -> None:
        for combo in combos:
            combo.bind("<<ComboboxSelected>>", self.imediato, add="+")

    def ligar_textos(self, *variaveis: tk.Variable) -> None:
        for variavel in variaveis:
            variavel.trace_add("write", self.agendar)

    def ligar_campos(self, *campos: tk.Widget) -> None:
        """Para CampoData/CampoValor e Entry comuns."""
        for campo in campos:
            variavel = getattr(campo, "var", None)
            if variavel is not None:
                variavel.trace_add("write", self.agendar)
            else:
                campo.bind("<KeyRelease>", self.agendar, add="+")


def centralizar(janela: tk.Misc, largura: int, altura: int) -> None:
    """Centraliza a janela sobre a janela que a abriu, sem cortar o conteúdo.

    O tamanho informado é o mínimo desejado: se os campos precisarem de mais
    espaço (um campo novo, uma fonte maior), a janela cresce até o limite da
    tela em vez de esconder os botões. Nunca ultrapassa a área visível do
    monitor, e o canto superior esquerdo nunca sai da tela.
    """
    janela.update_idletasks()
    tela_largura, tela_altura = janela.winfo_screenwidth(), janela.winfo_screenheight()
    largura = min(max(largura, janela.winfo_reqwidth()), tela_largura - 40)
    altura = min(max(altura, janela.winfo_reqheight()), tela_altura - 80)

    # Referência: a janela que abriu esta (ou a tela toda, se não houver).
    dono = janela.master.winfo_toplevel() if janela.master is not None else None
    if dono is not None and dono.winfo_ismapped() and dono.winfo_width() > 1:
        base_x, base_y = dono.winfo_rootx(), dono.winfo_rooty()
        base_w, base_h = dono.winfo_width(), dono.winfo_height()
    else:
        base_x = base_y = 0
        base_w, base_h = tela_largura, tela_altura

    x = base_x + (base_w - largura) // 2
    y = base_y + (base_h - altura) // 3
    x = max(0, min(x, tela_largura - largura))
    y = max(0, min(y, tela_altura - altura))
    janela.geometry(f"{largura}x{altura}+{x}+{y}")


def rotulo_campo(master, texto: str, dica: str = "", fundo_branco: bool = False) -> ttk.Frame:
    """Rótulo em negrito com uma linha de explicação opcional."""
    estilo_frame = "Superficie.TFrame" if fundo_branco else "TFrame"
    quadro = ttk.Frame(master, style=estilo_frame)
    ttk.Label(quadro, text=texto,
              style="CampoSuperficie.TLabel" if fundo_branco else "Campo.TLabel").pack(anchor="w")
    if dica:
        ttk.Label(quadro, text=dica,
                  style="DicaSuperficie.TLabel" if fundo_branco else "Dica.TLabel").pack(anchor="w")
    return quadro
