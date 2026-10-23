"""Ajustes do sistema, cópias de segurança e informações do arquivo de dados."""
from __future__ import annotations

import csv
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app import db, inicializacao, services
from app.config import APP_VERSION, BACKUP_DIR, DB_PATH, EXPORT_DIR, ensure_dirs
from app.ui.theme import CORES
from app.ui.widgets import Cabecalho, Tabela


class Configuracoes(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.cabecalho = Cabecalho(
            self, "Ajustes",
            "Preferências do programa e cópias de segurança dos seus dados.")
        self.cabecalho.pack(fill="x")
        self.cabecalho.botao("Salvar cópia agora", self.gerar_backup, "Primario.TButton")
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(24, 18))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(1, weight=1)

        # --- preferências ------------------------------------------------
        prefs = ttk.Labelframe(corpo, text=" Como o programa se comporta ")
        prefs.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        linha = ttk.Frame(prefs, style="Superficie.TFrame")
        linha.pack(fill="x", pady=(0, 10))
        ttk.Label(linha, text="Nome que aparece no sistema:",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.var_empresa = tk.StringVar(value=db.get_config("empresa"))
        ttk.Entry(linha, textvariable=self.var_empresa, width=28).pack(side="left", padx=10)

        # O texto é quebrado à mão: ttk.Checkbutton não tem wraplength, e uma
        # linha única de ~500px passaria a ditar a largura mínima da tela.
        self.var_min_bandeja = tk.BooleanVar(value=db.get_config("minimizar_bandeja") == "1")
        ttk.Checkbutton(prefs, style="Superficie.TCheckbutton", variable=self.var_min_bandeja,
                        text="Ao minimizar, deixar o programa perto do relógio\n"
                             "(em vez da barra de tarefas)").pack(anchor="w")
        self.var_fechar_bandeja = tk.BooleanVar(value=db.get_config("fechar_para_bandeja") == "1")
        ttk.Checkbutton(prefs, style="Superficie.TCheckbutton", variable=self.var_fechar_bandeja,
                        text="Ao fechar a janela, manter o programa aberto\n"
                             "perto do relógio").pack(anchor="w")
        # Abrir com o Windows não é preferência do banco: mora no registro do
        # usuário, por isso é lido de lá e gravado na hora em que muda.
        estado_inicio = inicializacao.situacao()
        self.var_com_windows = tk.BooleanVar(value=estado_inicio["ativo"])
        self.var_inicio_bandeja = tk.BooleanVar(value=estado_inicio["minimizado"])
        if inicializacao.disponivel():
            ttk.Checkbutton(prefs, style="Superficie.TCheckbutton",
                            variable=self.var_com_windows, command=self._aplicar_inicio,
                            text="Abrir o programa junto com o Windows").pack(anchor="w")
            self.chk_inicio_bandeja = ttk.Checkbutton(
                prefs, style="Superficie.TCheckbutton", variable=self.var_inicio_bandeja,
                command=self._aplicar_inicio,
                text="        ao abrir com o Windows, começar perto do relógio")
            self.chk_inicio_bandeja.pack(anchor="w")
            self._ajustar_inicio_bandeja()

        self.var_trava_saldo = tk.BooleanVar(
            value=db.get_config("bloquear_saldo_negativo", "1") == "1")
        ttk.Checkbutton(prefs, style="Superficie.TCheckbutton", variable=self.var_trava_saldo,
                        text="Não deixar tirar de uma conta mais do que há nela\n"
                             "(trabalhar sempre dentro do saldo)").pack(anchor="w")
        self.var_conferencia = tk.BooleanVar(
            value=db.get_config("conferencia_automatica", "1") == "1")
        ttk.Checkbutton(prefs, style="Superficie.TCheckbutton", variable=self.var_conferencia,
                        text="Conferir os registros sozinho\n"
                             "(sem precisar marcar um a um)").pack(anchor="w")
        self.var_backup_sair = tk.BooleanVar(value=db.get_config("backup_ao_sair") == "1")
        ttk.Checkbutton(prefs, style="Superficie.TCheckbutton", variable=self.var_backup_sair,
                        text="Salvar cópia de segurança sozinho\n"
                             "(ao abrir, durante o uso e ao fechar)").pack(anchor="w")

        ttk.Label(prefs, text="No máximo uma cópia por dia, e só quando algum dado mudou."
                              " O sistema verifica sozinho ao abrir, a cada 30 minutos de uso"
                              " e ao fechar. O histórico é enxugado automaticamente: últimos"
                              " 7 dias, uma por semana no último mês e uma por mês no último"
                              " semestre.",
                  style="DicaSuperficie.TLabel", wraplength=430,
                  justify="left").pack(anchor="w", pady=(8, 0))

        ttk.Separator(prefs).pack(fill="x", pady=12)
        ttk.Label(prefs, text="Contas atrasadas", style="SecaoSuperficie.TLabel").pack(anchor="w")
        self.var_encargos = tk.BooleanVar(value=db.get_config("encargos_automaticos") == "1")
        ttk.Checkbutton(prefs, style="Superficie.TCheckbutton", variable=self.var_encargos,
                        text="Lançar multa e juros das contas atrasadas todo mês").pack(anchor="w")

        linha_encargos = ttk.Frame(prefs, style="Superficie.TFrame")
        linha_encargos.pack(fill="x", pady=(8, 0))
        ttk.Label(linha_encargos, text="Multa padrão", style="CampoSuperficie.TLabel").pack(
            side="left")
        self.var_multa = tk.StringVar(value=db.get_config("multa_padrao", "0"))
        ttk.Spinbox(linha_encargos, from_=0, to=100, increment=0.5, width=6,
                    textvariable=self.var_multa).pack(side="left", padx=6)
        ttk.Label(linha_encargos, text="%   ·   juros padrão",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.var_juros = tk.StringVar(value=db.get_config("juros_padrao", "0"))
        ttk.Spinbox(linha_encargos, from_=0, to=100, increment=0.5, width=6,
                    textvariable=self.var_juros).pack(side="left", padx=6)
        ttk.Label(linha_encargos, text="% ao mês", style="CampoSuperficie.TLabel").pack(side="left")
        ttk.Label(prefs, text="Valores sugeridos ao cadastrar uma nova conta a pagar. Cada conta"
                              " pode ter os seus próprios.", style="DicaSuperficie.TLabel",
                  wraplength=430, justify="left").pack(anchor="w", pady=(6, 0))

        ttk.Button(prefs, text="Salvar preferências", style="Primario.TButton",
                   command=self.salvar_prefs).pack(anchor="e", pady=(14, 0))

        # --- informações -------------------------------------------------
        info = ttk.Labelframe(corpo, text=" Seus dados ")
        info.grid(row=0, column=1, sticky="nsew")
        self.lbl_info = ttk.Label(info, style="DicaSuperficie.TLabel", justify="left")
        self.lbl_info.pack(anchor="w")

        acoes_info = ttk.Frame(info, style="Superficie.TFrame")
        acoes_info.pack(fill="x", pady=(14, 0))
        ttk.Button(acoes_info, text="Abrir a pasta dos dados",
                   command=self.abrir_pasta).pack(side="left")
        ttk.Button(acoes_info, text="Exportar tudo para planilha",
                   command=self.exportar_lancamentos).pack(side="left", padx=8)
        ttk.Button(acoes_info, text="Conferir os dados", command=self.verificar).pack(side="left")

        ttk.Label(info, text="Seus registros ficam somente neste computador. Nada é enviado para"
                            " a internet.", style="DicaSuperficie.TLabel",
                  wraplength=420, justify="left").pack(anchor="w", pady=(14, 0))

        # --- cópias de segurança -----------------------------------------
        backup = ttk.Labelframe(corpo, text=" Cópias de segurança ")
        backup.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(16, 0))

        acoes = ttk.Frame(backup, style="Superficie.TFrame")
        acoes.pack(fill="x")
        ttk.Button(acoes, text="Salvar cópia agora", style="Primario.TButton",
                   command=self.gerar_backup).pack(side="left")
        ttk.Button(acoes, text="Salvar cópia em outro lugar...",
                   command=self.salvar_como).pack(side="left", padx=8)
        ttk.Button(acoes, text="Voltar para a cópia selecionada",
                   command=self.restaurar).pack(side="left")
        ttk.Button(acoes, text="Voltar para um arquivo...",
                   command=self.restaurar_arquivo).pack(side="left", padx=8)

        ttk.Label(backup, text="Voltar para uma cópia substitui os dados atuais pelos daquela"
                               " data. Antes disso, o sistema guarda automaticamente uma cópia"
                               " do estado de agora.", style="DicaSuperficie.TLabel",
                  wraplength=620, justify="left").pack(anchor="w", pady=(10, 8))

        # --- cópia fora do computador ------------------------------------
        nuvem = ttk.Frame(backup, style="Superficie.TFrame")
        nuvem.pack(fill="x", pady=(4, 10))
        ttk.Label(nuvem, text="Cópia fora deste computador",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        ttk.Label(nuvem, text="As cópias acima ficam neste PC: se o disco falhar, elas se perdem"
                              " junto. Aponte uma pasta do OneDrive, Google Drive ou um pen drive"
                              " e o sistema deixa lá uma segunda via de cada cópia diária.",
                  style="DicaSuperficie.TLabel", wraplength=620,
                  justify="left").pack(anchor="w", pady=(2, 8))

        linha_nuvem = ttk.Frame(nuvem, style="Superficie.TFrame")
        linha_nuvem.pack(fill="x")
        self.var_nuvem = tk.StringVar(value=db.get_config("pasta_backup_nuvem"))
        ttk.Entry(linha_nuvem, textvariable=self.var_nuvem, width=52).pack(side="left")
        ttk.Button(linha_nuvem, text="Escolher pasta...",
                   command=self.escolher_pasta_nuvem).pack(side="left", padx=8)
        ttk.Button(linha_nuvem, text="Copiar agora",
                   command=self.copiar_para_nuvem).pack(side="left")
        ttk.Button(linha_nuvem, text="Não usar",
                   command=self.desligar_nuvem).pack(side="left", padx=8)
        self.lbl_nuvem = ttk.Label(nuvem, style="DicaSuperficie.TLabel", wraplength=620,
                                   justify="left")
        self.lbl_nuvem.pack(anchor="w", pady=(8, 0))

        self.tab_backups = Tabela(backup, [
            ("arquivo", "Arquivo", 340, "w"),
            ("data", "Salva em", 180, "center"),
            ("tamanho", "Tamanho", 120, "e"),
        ], largura_livre=True, altura=7)
        self.tab_backups.definir_texto_vazio("Nenhuma cópia de segurança ainda.")
        self.tab_backups.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    def recarregar(self) -> None:
        ensure_dirs()
        self.tab_backups.limpar()
        arquivos = sorted(BACKUP_DIR.glob("contabil_*.db"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        for arquivo in arquivos:
            dados = arquivo.stat()
            self.tab_backups.inserir(
                (arquivo.name,
                 datetime.fromtimestamp(dados.st_mtime).strftime("%d/%m/%Y às %H:%M"),
                 f"{dados.st_size / 1024:.0f} KB"),
                iid=arquivo.name)
        self.tab_backups.finalizar()

        tamanho = DB_PATH.stat().st_size / 1024 if DB_PATH.exists() else 0
        registros = db.query_one("SELECT COUNT(*) AS c FROM lancamento")["c"]
        titulos = db.query_one("SELECT COUNT(*) AS c FROM titulo")["c"]
        self.lbl_info.configure(
            text=f"Registros de entrada e saída: {registros}\n"
                 f"Contas a pagar e receber: {titulos}\n"
                 f"Cópias de segurança guardadas: {len(arquivos)}\n\n"
                 f"Arquivo de dados ({tamanho:.0f} KB):\n{DB_PATH}\n\n"
                 f"Versão do programa: {APP_VERSION}")
        self._atualizar_nuvem()

    def _atualizar_nuvem(self) -> None:
        """Mostra a situação da cópia externa e sugere pastas encontradas."""
        pasta = db.pasta_backup_nuvem()
        if pasta is None:
            sugestoes = db.pastas_de_nuvem_detectadas()
            if sugestoes:
                nomes = ", ".join(p.name for p in sugestoes[:3])
                texto = (f"Nenhuma pasta escolhida — hoje só existe cópia neste PC."
                         f" Encontrei aqui: {nomes}. Clique em 'Escolher pasta...'.")
            else:
                texto = ("Nenhuma pasta escolhida — hoje só existe cópia neste PC."
                         " Serve qualquer pasta sincronizada ou um pen drive.")
            self.lbl_nuvem.configure(text=texto, foreground=CORES["alerta"])
            return

        ultima = db.get_config("ultimo_backup_nuvem", "")
        if ultima:
            quando = datetime.fromisoformat(ultima).strftime("%d/%m/%Y às %H:%M")
            detalhe = f"Última cópia enviada em {quando}."
        else:
            detalhe = "Ainda não foi copiado nada para lá."
        existe = pasta.is_dir()
        copias = len(list(pasta.glob("contabil_*.db"))) if existe else 0
        self.lbl_nuvem.configure(
            text=(f"Copiando para: {pasta}\n{detalhe}"
                  + (f" {copias} cópia(s) lá." if existe else
                     "  A pasta não está acessível agora.")),
            foreground=CORES["sucesso"] if existe else CORES["perigo"])

    def escolher_pasta_nuvem(self) -> None:
        sugestao = db.pastas_de_nuvem_detectadas()
        inicial = str(sugestao[0]) if sugestao else str(Path.home())
        escolhida = filedialog.askdirectory(
            parent=self, initialdir=inicial,
            title="Onde guardar a segunda via das cópias de segurança?")
        if not escolhida:
            return
        destino = Path(escolhida)
        if DB_PATH.parent == destino:
            messagebox.showwarning(
                "Escolha outra pasta",
                "Essa é a própria pasta dos dados. A ideia é guardar a cópia em outro"
                " lugar — de preferência sincronizado com a nuvem.", parent=self)
            return
        db.definir_pasta_backup_nuvem(destino)
        self.var_nuvem.set(str(destino))
        self.copiar_para_nuvem()

    def copiar_para_nuvem(self) -> None:
        texto = self.var_nuvem.get().strip()
        if not texto:
            messagebox.showinfo("Cópia externa", "Escolha antes a pasta de destino.",
                                parent=self)
            return
        db.definir_pasta_backup_nuvem(texto)
        origem = db.backup_automatico()
        if origem is None:
            arquivos = sorted(BACKUP_DIR.glob("contabil_*.db"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
            origem = arquivos[0] if arquivos else db.fazer_backup()
        destino = db.copiar_para_nuvem(origem)
        self.recarregar()
        if destino is None:
            messagebox.showwarning(
                "Não deu para copiar",
                f"A pasta '{texto}' não pôde ser usada. Verifique se ela existe e se você"
                " tem permissão para gravar nela.", parent=self)
            return
        self.app.notificar("Cópia de segurança enviada para a pasta externa.")
        messagebox.showinfo("Pronto", f"Cópia guardada em:\n{destino}", parent=self)

    def desligar_nuvem(self) -> None:
        db.definir_pasta_backup_nuvem(None)
        self.var_nuvem.set("")
        self.recarregar()
        self.app.notificar("Cópia externa desligada.")

    # ------------------------------------------------------------------ #
    def _ajustar_inicio_bandeja(self) -> None:
        """A opção de começar minimizado só faz sentido se ele abrir sozinho."""
        self.chk_inicio_bandeja.configure(
            state="normal" if self.var_com_windows.get() else "disabled")

    def _aplicar_inicio(self) -> None:
        """Grava a escolha no Windows na hora: não depende de 'Salvar preferências'."""
        ligar = self.var_com_windows.get()
        try:
            inicializacao.definir(ligar, self.var_inicio_bandeja.get())
        except OSError as erro:
            self.var_com_windows.set(not ligar)
            messagebox.showwarning(
                "Abrir com o Windows",
                f"Não foi possível alterar esta opção:\n\n{erro}", parent=self)
            return
        self._ajustar_inicio_bandeja()
        if ligar:
            destino = ("perto do relógio" if self.var_inicio_bandeja.get()
                       else "com a janela aberta")
            self.app.notificar(f"O programa passa a abrir junto com o Windows, {destino}.")
        else:
            self.app.notificar("O programa não abre mais junto com o Windows.")

    def salvar_prefs(self) -> None:
        db.set_config("empresa", self.var_empresa.get().strip())
        db.set_config("minimizar_bandeja", "1" if self.var_min_bandeja.get() else "0")
        db.set_config("fechar_para_bandeja", "1" if self.var_fechar_bandeja.get() else "0")
        db.set_config("backup_ao_sair", "1" if self.var_backup_sair.get() else "0")
        db.set_config("conferencia_automatica", "1" if self.var_conferencia.get() else "0")
        db.set_config("bloquear_saldo_negativo", "1" if self.var_trava_saldo.get() else "0")
        if self.var_conferencia.get():
            services.conferir_automatico()
        db.set_config("encargos_automaticos", "1" if self.var_encargos.get() else "0")
        db.set_config("multa_padrao", self.var_multa.get().replace(",", "."))
        db.set_config("juros_padrao", self.var_juros.get().replace(",", "."))
        self.app.aplicar_preferencias()
        self.app.notificar("Preferências salvas.")
        messagebox.showinfo("Pronto", "Suas preferências foram salvas.", parent=self)

    def gerar_backup(self) -> None:
        caminho = db.backup_automatico()
        self.recarregar()
        if caminho is None:
            messagebox.showinfo("Cópias de segurança",
                                "Nada mudou desde a última cópia de hoje — não foi preciso"
                                " criar outra.", parent=self)
            return
        self.app.notificar("Cópia de segurança salva.")
        messagebox.showinfo("Pronto", f"Cópia salva em:\n{caminho}", parent=self)

    def salvar_como(self) -> None:
        caminho = filedialog.asksaveasfilename(
            parent=self, initialdir=str(BACKUP_DIR), initialfile="minhas_contas_copia.db",
            defaultextension=".db", filetypes=[("Arquivo de dados", "*.db")])
        if not caminho:
            return
        db.fazer_backup(Path(caminho))
        messagebox.showinfo("Pronto", f"Cópia salva em:\n{caminho}", parent=self)

    def restaurar(self) -> None:
        item = self.tab_backups.selecionado()
        if not item:
            messagebox.showinfo("Cópias", "Escolha antes uma cópia da lista.", parent=self)
            return
        self._restaurar(BACKUP_DIR / item)

    def restaurar_arquivo(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self, initialdir=str(BACKUP_DIR), filetypes=[("Arquivo de dados", "*.db")])
        if caminho:
            self._restaurar(Path(caminho))

    def _restaurar(self, origem: Path) -> None:
        if not messagebox.askyesno(
                "Voltar para uma cópia",
                f"Os dados de agora serão substituídos pelos do arquivo:\n{origem.name}\n\n"
                "Uma cópia do estado atual será guardada antes, por segurança.\n\nContinuar?",
                parent=self):
            return
        db.fazer_backup()
        try:
            db.restaurar_backup(origem)
        except Exception as erro:  # pragma: no cover - falha de disco
            messagebox.showerror("Não foi possível", f"Erro ao restaurar:\n{erro}", parent=self)
            return
        self.recarregar()
        self.app.recarregar_tudo()
        messagebox.showinfo("Pronto", "Os dados daquela cópia foram restaurados.", parent=self)

    def abrir_pasta(self) -> None:
        import os
        ensure_dirs()
        os.startfile(str(DB_PATH.parent))  # noqa: S606 - abre o Explorador do Windows

    def verificar(self) -> None:
        # Índice quebrado tem conserto: reconstruir antes de dar o diagnóstico.
        reparado = db.reparar_indices()
        resultado = db.query_one("PRAGMA integrity_check")
        estado = resultado[0] if resultado else "desconhecido"
        db.compactar()
        balanco = services.balanco(services.hoje_iso())
        equilibrio = ("Tudo confere." if abs(balanco["diferenca"]) < 0.005
                      else f"Há uma diferença de {services.moeda(balanco['diferenca'])} entre o"
                           " que você tem e o que está registrado. Confira os saldos iniciais.")
        self.recarregar()
        reparo = ("\n\nUm índice estava fora de sincronia e foi reconstruído —"
                  " nenhum registro se perdeu." if reparado else "")
        messagebox.showinfo(
            "Conferência",
            f"Arquivo de dados: {'sem problemas' if estado == 'ok' else estado}"
            f"{reparo}\n\n{equilibrio}", parent=self)

    def exportar_lancamentos(self) -> None:
        ensure_dirs()
        caminho = filedialog.asksaveasfilename(
            parent=self, initialdir=str(EXPORT_DIR), initialfile="minhas_contas.csv",
            defaultextension=".csv", filetypes=[("Planilha (CSV)", "*.csv")])
        if not caminho:
            return
        with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(["Data", "O que foi", "Descrição", "Categoria", "Conta usada",
                               "Valor", "Grupo"])
            for mov in services.listar_movimentos("1900-01-01", "2999-12-31", limite=100000):
                escritor.writerow([
                    services.para_br(mov["data"]), mov["rotulo"], mov["descricao"],
                    mov["categoria"], mov["conta"],
                    f"{mov['valor']:.2f}".replace(".", ","), mov["centro_custo"]])
        messagebox.showinfo("Pronto", f"Arquivo salvo em:\n{caminho}\n\n"
                                      "Ele pode ser aberto no Excel.", parent=self)
