"""Paleta de cores e estilos ttk — visual claro, arejado e de alto contraste."""
from __future__ import annotations

from tkinter import ttk

CORES = {
    # superfícies
    "fundo": "#f4f6fb",
    "superficie": "#ffffff",
    "superficie_suave": "#eef2fa",
    "borda": "#e2e8f4",
    "borda_forte": "#c9d4e8",
    # menu lateral
    "barra": "#0f172a",
    "barra_hover": "#1e293b",
    "barra_ativo": "#2563eb",
    "barra_texto": "#94a3b8",
    # texto
    "texto": "#0f172a",
    "texto_suave": "#64748b",
    "texto_claro": "#ffffff",
    # semântica
    "primaria": "#2563eb",
    "primaria_escura": "#1d4ed8",
    "primaria_suave": "#e0e9ff",
    "sucesso": "#059669",
    "sucesso_suave": "#d8f3e7",
    "perigo": "#dc2626",
    "perigo_suave": "#fde3e3",
    "alerta": "#d97706",
    "alerta_suave": "#fdeed4",
    "neutro_suave": "#eef2fa",
    "linha_alt": "#f8fafd",
}

FONTE = "Segoe UI"
FONTE_NUM = "Segoe UI Semibold"


def aplicar(root) -> ttk.Style:
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")
    except Exception:
        pass

    # Atenção: não usar root.option_add("*Font", ...) — a option database tem
    # precedência sobre os estilos ttk e achataria todos os títulos.
    root.configure(bg=CORES["fundo"])
    root.option_add("*TCombobox*Listbox.font", (FONTE, 10))
    root.option_add("*TCombobox*Listbox.selectBackground", CORES["primaria"])

    # --- base ------------------------------------------------------------
    estilo.configure(".", font=(FONTE, 10), background=CORES["fundo"],
                     foreground=CORES["texto"], borderwidth=0, focuscolor=CORES["primaria"])
    estilo.configure("TFrame", background=CORES["fundo"])
    estilo.configure("Superficie.TFrame", background=CORES["superficie"])
    estilo.configure("Suave.TFrame", background=CORES["superficie_suave"])
    estilo.configure("Barra.TFrame", background=CORES["barra"])
    estilo.configure("Topo.TFrame", background=CORES["superficie"])

    # --- rótulos ---------------------------------------------------------
    estilo.configure("TLabel", background=CORES["fundo"], foreground=CORES["texto"])
    estilo.configure("Superficie.TLabel", background=CORES["superficie"])
    estilo.configure("Titulo.TLabel", font=(FONTE, 20, "bold"), background=CORES["superficie"])
    estilo.configure("Subtitulo.TLabel", font=(FONTE, 10), foreground=CORES["texto_suave"],
                     background=CORES["fundo"])
    estilo.configure("SubtituloTopo.TLabel", font=(FONTE, 10), foreground=CORES["texto_suave"],
                     background=CORES["superficie"])
    estilo.configure("Secao.TLabel", font=(FONTE, 13, "bold"), background=CORES["fundo"])
    estilo.configure("SecaoSuperficie.TLabel", font=(FONTE, 13, "bold"),
                     background=CORES["superficie"])
    estilo.configure("Dica.TLabel", font=(FONTE, 9), foreground=CORES["texto_suave"],
                     background=CORES["fundo"])
    estilo.configure("DicaSuperficie.TLabel", font=(FONTE, 9), foreground=CORES["texto_suave"],
                     background=CORES["superficie"])
    estilo.configure("Campo.TLabel", font=(FONTE, 10, "bold"), background=CORES["fundo"])
    estilo.configure("CampoSuperficie.TLabel", font=(FONTE, 10, "bold"),
                     background=CORES["superficie"])
    estilo.configure("Total.TLabel", font=(FONTE, 12, "bold"), background=CORES["fundo"])

    # --- botões ----------------------------------------------------------
    estilo.configure("TButton", padding=(16, 9), font=(FONTE, 10), relief="flat",
                     background=CORES["superficie"], foreground=CORES["texto"],
                     bordercolor=CORES["borda_forte"], borderwidth=1)
    estilo.map("TButton",
               background=[("active", CORES["superficie_suave"]), ("disabled", CORES["fundo"])],
               foreground=[("disabled", CORES["texto_suave"])])

    estilo.configure("Primario.TButton", background=CORES["primaria"],
                     foreground=CORES["texto_claro"], borderwidth=0, font=(FONTE, 10, "bold"))
    estilo.map("Primario.TButton",
               background=[("active", CORES["primaria_escura"]), ("disabled", "#a9c0f0")])

    estilo.configure("Sucesso.TButton", background=CORES["sucesso"],
                     foreground=CORES["texto_claro"], borderwidth=0, font=(FONTE, 10, "bold"))
    estilo.map("Sucesso.TButton", background=[("active", "#047857")])

    estilo.configure("Perigo.TButton", background=CORES["superficie"],
                     foreground=CORES["perigo"], borderwidth=1, bordercolor=CORES["perigo"])
    estilo.map("Perigo.TButton", background=[("active", CORES["perigo_suave"])])

    estilo.configure("Link.TButton", background=CORES["superficie"], borderwidth=0,
                     foreground=CORES["primaria"], padding=(6, 4), font=(FONTE, 10, "underline"))
    estilo.map("Link.TButton", background=[("active", CORES["superficie"])])

    # menu lateral
    estilo.configure("Menu.TButton", anchor="w", padding=(18, 12), borderwidth=0,
                     background=CORES["barra"], foreground=CORES["barra_texto"],
                     font=(FONTE, 11))
    estilo.map("Menu.TButton",
               background=[("active", CORES["barra_hover"])],
               foreground=[("active", CORES["texto_claro"])])
    estilo.configure("MenuAtivo.TButton", anchor="w", padding=(18, 12), borderwidth=0,
                     background=CORES["barra_ativo"], foreground=CORES["texto_claro"],
                     font=(FONTE, 11, "bold"))
    estilo.map("MenuAtivo.TButton", background=[("active", CORES["barra_ativo"])])

    # --- campos ----------------------------------------------------------
    for nome in ("TEntry", "TSpinbox"):
        estilo.configure(nome, padding=7, relief="flat", borderwidth=1,
                         bordercolor=CORES["borda_forte"], fieldbackground=CORES["superficie"],
                         background=CORES["superficie"], insertcolor=CORES["texto"])
        estilo.map(nome, bordercolor=[("focus", CORES["primaria"])])

    estilo.configure("TCombobox", padding=6, relief="flat", borderwidth=1,
                     bordercolor=CORES["borda_forte"], fieldbackground=CORES["superficie"],
                     background=CORES["superficie"], arrowcolor=CORES["texto_suave"])
    estilo.map("TCombobox",
               bordercolor=[("focus", CORES["primaria"])],
               fieldbackground=[("readonly", CORES["superficie"])])

    estilo.configure("TCheckbutton", background=CORES["fundo"], padding=4)
    estilo.configure("Superficie.TCheckbutton", background=CORES["superficie"], padding=4)
    estilo.configure("TRadiobutton", background=CORES["fundo"], padding=4)
    estilo.configure("Superficie.TRadiobutton", background=CORES["superficie"], padding=4)
    estilo.configure("TLabelframe", background=CORES["superficie"], borderwidth=1,
                     bordercolor=CORES["borda"], padding=14, relief="solid")
    estilo.configure("TLabelframe.Label", background=CORES["superficie"],
                     font=(FONTE, 11, "bold"), foreground=CORES["texto"])

    # --- abas ------------------------------------------------------------
    estilo.configure("TNotebook", background=CORES["fundo"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    estilo.configure("TNotebook.Tab", padding=(20, 10), font=(FONTE, 10),
                     background=CORES["superficie_suave"], foreground=CORES["texto_suave"],
                     borderwidth=0)
    estilo.map("TNotebook.Tab",
               background=[("selected", CORES["superficie"])],
               foreground=[("selected", CORES["primaria"])],
               font=[("selected", (FONTE, 10, "bold"))])

    # --- tabelas ---------------------------------------------------------
    estilo.configure("Treeview", rowheight=34, font=(FONTE, 10), borderwidth=0,
                     fieldbackground=CORES["superficie"], background=CORES["superficie"])
    estilo.configure("Treeview.Heading", font=(FONTE, 9, "bold"), padding=(8, 9),
                     background=CORES["superficie_suave"], foreground=CORES["texto_suave"],
                     relief="flat", borderwidth=0)
    estilo.map("Treeview.Heading", background=[("active", CORES["borda"])])
    estilo.map("Treeview",
               background=[("selected", CORES["primaria_suave"])],
               foreground=[("selected", CORES["texto"])])

    estilo.configure("TScrollbar", background=CORES["superficie_suave"], borderwidth=0,
                     troughcolor=CORES["fundo"], arrowcolor=CORES["texto_suave"])
    estilo.configure("TSeparator", background=CORES["borda"])
    return estilo


def marcar_zebra(tree) -> None:
    """Marcações de linha usadas pelas tabelas."""
    tree.tag_configure("par", background=CORES["superficie"])
    tree.tag_configure("impar", background=CORES["linha_alt"])
    tree.tag_configure("negativo", foreground=CORES["perigo"])
    tree.tag_configure("positivo", foreground=CORES["sucesso"])
    tree.tag_configure("sintetica", font=(FONTE, 10, "bold"), background=CORES["superficie_suave"])
    tree.tag_configure("vencido", foreground=CORES["perigo"])
    tree.tag_configure("quitado", foreground=CORES["texto_suave"])
    tree.tag_configure("destaque", background=CORES["primaria_suave"])
