"""Ajustes do sistema, cópias de segurança e informações do arquivo de dados."""
from __future__ import annotations

import csv
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app import atualizacao, db, inicializacao, instalacao, seguranca, services
from app.config import APP_VERSION, BACKUP_DIR, DB_PATH, EXPORT_DIR, ensure_dirs
from app.ui.theme import CORES
from app.ui.widgets import Cabecalho, Tabela, centralizar


class Configuracoes(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._meses_fechaveis: list[str] = []
        self._sem_uso: list[dict] = []

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

        # --- fechamento de competência e auditoria ------------------------
        auditoria = ttk.Labelframe(corpo, text=" Fechamento de competência e auditoria ")
        auditoria.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(16, 0))

        ttk.Label(auditoria,
                  text="Fechar um mês é dizer que ele já virou relatório: nada mais entra,"
                       " sai ou muda de valor dentro dele. É o que garante que o balanço de"
                       " um mês passado continue o mesmo se você olhar de novo daqui a um ano."
                       " Reabrir é possível a qualquer momento.",
                  style="DicaSuperficie.TLabel", wraplength=880,
                  justify="left").pack(anchor="w", pady=(0, 10))

        linha_fecho = ttk.Frame(auditoria, style="Superficie.TFrame")
        linha_fecho.pack(fill="x")
        self.lbl_fecho = ttk.Label(linha_fecho, style="SecaoSuperficie.TLabel")
        self.lbl_fecho.pack(side="left")

        acoes_fecho = ttk.Frame(auditoria, style="Superficie.TFrame")
        acoes_fecho.pack(fill="x", pady=(10, 0))
        ttk.Label(acoes_fecho, text="Fechar até o mês:",
                  style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_fecho = ttk.Combobox(acoes_fecho, state="readonly", width=22)
        self.cb_fecho.pack(side="left", padx=8)
        self.btn_fechar = ttk.Button(acoes_fecho, text="Fechar competência",
                                     style="Primario.TButton", command=self.fechar_competencia)
        self.btn_fechar.pack(side="left")
        self.btn_reabrir = ttk.Button(acoes_fecho, text="Reabrir o último mês fechado",
                                      command=self.reabrir_competencia)
        self.btn_reabrir.pack(side="left", padx=8)
        ttk.Button(acoes_fecho, text="Ver trilha de alterações",
                   command=self.abrir_trilha).pack(side="left")
        self.var_lembrar_fecho = tk.BooleanVar(value=services.lembrete_ligado())
        ttk.Checkbutton(acoes_fecho, style="Superficie.TCheckbutton",
                        variable=self.var_lembrar_fecho,
                        command=self.alternar_lembrete,
                        text="Lembrar no mês seguinte").pack(side="left", padx=16)

        ttk.Separator(auditoria).pack(fill="x", pady=12)
        ttk.Label(auditoria, text="Categorias que nunca foram usadas",
                  style="SecaoSuperficie.TLabel").pack(anchor="w")
        self.lbl_sem_uso = ttk.Label(auditoria, style="DicaSuperficie.TLabel", wraplength=880,
                                     justify="left")
        self.lbl_sem_uso.pack(anchor="w", pady=(2, 8))
        acoes_sem_uso = ttk.Frame(auditoria, style="Superficie.TFrame")
        acoes_sem_uso.pack(fill="x")
        self.btn_ver_sem_uso = ttk.Button(acoes_sem_uso, text="Ver as categorias",
                                          style="Primario.TButton",
                                          command=self.ver_sem_uso)
        self.btn_ver_sem_uso.pack(side="left")
        self.btn_arquivar = ttk.Button(acoes_sem_uso,
                                       text="Arquivar todas de uma vez",
                                       command=self.arquivar_sem_uso)
        self.btn_arquivar.pack(side="left", padx=8)

        # --- senha, instalação e versão -----------------------------------
        sistema = ttk.Labelframe(corpo, text=" Este computador ")
        sistema.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(16, 0))

        ttk.Label(sistema, text="Senha de abertura", style="SecaoSuperficie.TLabel").pack(
            anchor="w")
        self.lbl_senha = ttk.Label(sistema, style="DicaSuperficie.TLabel", wraplength=880,
                                   justify="left")
        self.lbl_senha.pack(anchor="w", pady=(2, 8))
        acoes_senha = ttk.Frame(sistema, style="Superficie.TFrame")
        acoes_senha.pack(fill="x")
        self.btn_senha = ttk.Button(acoes_senha, text="Trocar a senha",
                                    command=self.trocar_senha)
        self.btn_senha.pack(side="left")
        self.btn_tirar_senha = ttk.Button(acoes_senha, text="Tirar a senha",
                                          command=self.tirar_senha)
        self.btn_tirar_senha.pack(side="left", padx=8)

        ttk.Separator(sistema).pack(fill="x", pady=12)
        ttk.Label(sistema, text="Instalação", style="SecaoSuperficie.TLabel").pack(anchor="w")
        self.lbl_instalacao = ttk.Label(sistema, style="DicaSuperficie.TLabel",
                                        wraplength=880, justify="left")
        self.lbl_instalacao.pack(anchor="w", pady=(2, 8))
        self.btn_instalar = ttk.Button(sistema, text="Instalar neste computador",
                                       command=self.instalar)
        self.btn_instalar.pack(anchor="w")

        ttk.Separator(sistema).pack(fill="x", pady=12)
        ttk.Label(sistema, text="Versão", style="SecaoSuperficie.TLabel").pack(anchor="w")
        self.lbl_versao = ttk.Label(sistema, style="DicaSuperficie.TLabel", wraplength=880,
                                    justify="left")
        self.lbl_versao.pack(anchor="w", pady=(2, 8))
        acoes_versao = ttk.Frame(sistema, style="Superficie.TFrame")
        acoes_versao.pack(fill="x")
        ttk.Button(acoes_versao, text="Procurar atualizações agora",
                   command=self.procurar_atualizacao).pack(side="left")
        self.btn_baixar = ttk.Button(acoes_versao, text="Ver o que mudou e atualizar",
                                     command=self.abrir_versao_nova)
        self.btn_baixar.pack(side="left", padx=8)
        self.var_avisar_versao = tk.BooleanVar(value=atualizacao.verificacao_ligada())
        ttk.Checkbutton(acoes_versao, style="Superficie.TCheckbutton",
                        variable=self.var_avisar_versao, command=self.alternar_aviso_versao,
                        text="Conferir sozinho uma vez por dia").pack(side="left", padx=16)

    # ------------------------------------------------------------------ #
    def _atualizar_sistema(self) -> None:
        """Senha, instalação e versão: o estado de cada uma, em uma frase."""
        if seguranca.tem_senha():
            quando = seguranca.criada_em()[:10]
            self.lbl_senha.configure(
                text="O programa pede uma senha para abrir"
                     + (f" (definida em {services.para_br(quando)})" if quando else "")
                     + ". Ela vale só neste computador e não embaralha o arquivo dos"
                       " dados — é uma tranca na porta, não um cofre.",
                foreground=CORES["sucesso"])
            self.btn_senha.configure(text="Trocar a senha")
            self.btn_tirar_senha.state(["!disabled"])
        else:
            self.lbl_senha.configure(
                text="Qualquer pessoa que abra este programa vê os seus números.",
                foreground=CORES["alerta"])
            self.btn_senha.configure(text="Criar uma senha")
            self.btn_tirar_senha.state(["disabled"])

        estado = instalacao.situacao()
        if not estado["disponivel"]:
            texto, cor, pode = ("A instalação só existe no programa compilado para"
                                " Windows.", CORES["texto_suave"], False)
        elif estado["portatil"]:
            texto, cor, pode = ("Modo portátil: o programa e os dados andam juntos na"
                                " mesma pasta, e nada deve ser instalado.",
                                CORES["texto_suave"], False)
        elif estado["aqui"]:
            texto, cor, pode = (f"Instalado em {estado['caminho_instalado']}.",
                                CORES["sucesso"], False)
        else:
            texto, cor, pode = (
                f"Rodando direto de {estado['caminho_atual']}. Instalar cria o atalho no"
                " menu Iniciar, põe o programa na lista de aplicativos do Windows e"
                " dispensa guardar o arquivo baixado. Não precisa de administrador, e os"
                " seus dados não mudam de lugar.", CORES["alerta"], True)
        self.lbl_instalacao.configure(text=texto, foreground=cor)
        self.btn_instalar.state(["!disabled"] if pode else ["disabled"])

        self._mostrar_versao(atualizacao.estado_guardado())

    def _mostrar_versao(self, estado: dict) -> None:
        quando = estado["consultada_em"][:10]
        visto = f"  Conferido em {services.para_br(quando)}." if quando else ""
        if estado.get("falhou"):
            self.lbl_versao.configure(
                text=f"Você está na versão {estado['atual']}. "
                     + (estado.get("motivo") or "Não consegui falar com o GitHub agora."),
                foreground=CORES["alerta"])
        elif estado["ha_novidade"]:
            self.lbl_versao.configure(
                text=f"Saiu a versão {estado['disponivel']} — você está na"
                     f" {estado['atual']}.{visto}", foreground=CORES["alerta"])
        else:
            self.lbl_versao.configure(
                text=f"Você está na versão mais recente ({estado['atual']}).{visto}",
                foreground=CORES["sucesso"])
        # O botão fica sempre de pé: mesmo sem novidade, serve para relembrar o
        # que mudou na versão que está rodando.
        self.btn_baixar.configure(
            text="Ver o que mudou e atualizar" if estado["ha_novidade"]
            else "Ver o que mudou nesta versão")

    def trocar_senha(self) -> None:
        from app.ui.senha import DialogoCriarSenha

        dialogo = DialogoCriarSenha(self, trocando=seguranca.tem_senha())
        self.wait_window(dialogo)
        if dialogo.liberado:
            self.recarregar()
            self.app.notificar("Senha salva.")

    def tirar_senha(self) -> None:
        from tkinter import simpledialog

        if not messagebox.askyesno(
                "Tirar a senha",
                "Sem senha, qualquer pessoa que abra o programa neste computador vê os"
                " seus números.\n\nTirar mesmo assim?", parent=self):
            return
        atual = simpledialog.askstring("Confirmar", "Digite a senha de hoje:",
                                       show="•", parent=self)
        if atual is None:
            return
        try:
            seguranca.remover_senha(atual)
        except ValueError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.recarregar()
        self.app.notificar("Senha removida.")

    def instalar(self) -> None:
        self.app.instalar_no_computador()
        self.recarregar()

    def mostrar_fechamento_pendente(self) -> None:
        from app.ui.avisos import DialogoFechamento

        DialogoFechamento(self, self._apos_fechamento)

    def _apos_fechamento(self, recado: str) -> None:
        self.app.notificar(recado)
        self.recarregar()

    def alternar_aviso_versao(self) -> None:
        atualizacao.definir_verificacao(bool(self.var_avisar_versao.get()))
        self.app.notificar("Aviso de versão nova "
                           + ("ligado." if self.var_avisar_versao.get() else "desligado."))

    def procurar_atualizacao(self) -> None:
        estado = atualizacao.verificar(forcar=True)
        atualizacao.limpar_ignorada()
        self._mostrar_versao(estado)
        if estado.get("falhou"):
            messagebox.showwarning(
                "Não deu para conferir",
                (estado.get("motivo")
                 or "Não consegui falar com o GitHub agora.")
                + "\n\nO detalhe também fica registrado no arquivo de log, em Ajustes"
                  " → Abrir a pasta dos dados.", parent=self)
        elif estado["ha_novidade"]:
            self.app._anunciar_versao_nova()
            messagebox.showinfo(
                "Versão nova",
                f"Saiu a versão {estado['disponivel']}. Você está na {estado['atual']}.\n\n"
                "Clique em 'Ver o que mudou e atualizar'.", parent=self)
        else:
            messagebox.showinfo(
                "Tudo em dia", f"Você já está na versão mais recente"
                               f" ({estado['atual']}).", parent=self)

    def abrir_versao_nova(self) -> None:
        self.app.abrir_versao_nova()
        self.recarregar()

    # ------------------------------------------------------------------ #
    def _atualizar_auditoria(self) -> None:
        """Situação do fechamento e das categorias sem uso."""
        resumo = services.resumo_fechamento()
        if resumo["fechado_ate"]:
            self.lbl_fecho.configure(
                text=f"Fechado até {resumo['nome_fechado']}"
                     f" — {resumo['lancamentos_travados']} registro(s) travado(s).",
                foreground=CORES["sucesso"])
            self.btn_reabrir.state(["!disabled"])
        else:
            self.lbl_fecho.configure(
                text="Nenhum mês fechado: qualquer registro antigo ainda pode ser alterado.",
                foreground=CORES["alerta"])
            self.btn_reabrir.state(["disabled"])

        # Só meses que já terminaram podem ser fechados, um a um, na ordem.
        opcoes, atual = [], resumo["proximo"]
        while atual and atual <= resumo["ultimo_fechavel"]:
            opcoes.append(atual)
            atual = services._mes_seguinte(atual)
        self._meses_fechaveis = opcoes
        self.cb_fecho.configure(values=[services.mes_nome(m).capitalize() for m in opcoes])
        if opcoes:
            self.cb_fecho.current(0)
            self.cb_fecho.state(["!disabled"])
            self.btn_fechar.state(["!disabled"])
        else:
            self.cb_fecho.set("")
            self.cb_fecho.state(["disabled"])
            self.btn_fechar.state(["disabled"])

        self.var_lembrar_fecho.set(services.lembrete_ligado())

        sem_uso = services.contas_sem_uso()
        self._sem_uso = sem_uso
        if sem_uso:
            exemplos = ", ".join(c["nome"] for c in sem_uso[:4])
            self.lbl_sem_uso.configure(
                text=f"{len(sem_uso)} categoria(s) vieram do plano padrão e nunca receberam"
                     f" nenhum lançamento: {exemplos}"
                     f"{' e outras' if len(sem_uso) > 4 else ''}."
                     " Arquivar tira as duas coisas do caminho: a lista comprida nos seletores"
                     " e o risco de classificar um gasto na categoria errada."
                     " Nada é apagado — elas voltam em Categorias quando você quiser.",
                foreground=CORES["alerta"])
            self.btn_arquivar.state(["!disabled"])
            self.btn_ver_sem_uso.state(["!disabled"])
        else:
            self.lbl_sem_uso.configure(
                text="Todas as suas categorias estão em uso. Nada a arrumar aqui.",
                foreground=CORES["sucesso"])
            self.btn_arquivar.state(["disabled"])
            self.btn_ver_sem_uso.state(["disabled"])

    def fechar_competencia(self) -> None:
        indice = self.cb_fecho.current()
        if indice < 0 or indice >= len(self._meses_fechaveis):
            return
        competencia = self._meses_fechaveis[indice]
        quantos = db.query_one(
            "SELECT COUNT(*) AS n FROM lancamento WHERE substr(data,1,7) <= ?",
            (competencia,))["n"]
        if not messagebox.askyesno(
                "Fechar competência",
                f"Fechar tudo até {services.mes_nome(competencia)}?\n\n"
                f"{quantos} registro(s) passam a não aceitar alteração nem exclusão."
                " As contas a pagar dos meses seguintes continuam normais.\n\n"
                "Dá para reabrir depois, aqui mesmo.", parent=self):
            return
        try:
            services.fechar_competencia(competencia)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.recarregar()
        self.app.notificar(f"Competência fechada até {services.mes_nome(competencia)}.")

    def reabrir_competencia(self) -> None:
        fechado = services.competencia_fechada()
        if not fechado:
            return
        anterior = services._mes_anterior(fechado)
        primeiro = services.primeiro_mes_registrado() or ""
        destino = "" if (not primeiro or anterior < primeiro) else anterior
        texto = (f"deixar fechado até {services.mes_nome(destino)}" if destino
                 else "destravar todo o histórico")
        if not messagebox.askyesno(
                "Reabrir competência",
                f"Reabrir {services.mes_nome(fechado)} e {texto}?\n\n"
                "Os registros daquele mês voltam a aceitar correção — e um relatório já"
                " entregue daquele período pode deixar de bater.", parent=self):
            return
        try:
            services.reabrir_competencia(destino)
        except services.RegraNegocioError as erro:
            messagebox.showwarning("Não foi possível", str(erro), parent=self)
            return
        self.recarregar()
        self.app.notificar(f"{services.mes_nome(fechado).capitalize()} reaberto.")

    def alternar_lembrete(self) -> None:
        services.definir_lembrete(bool(self.var_lembrar_fecho.get()))
        self.app.notificar(
            "Aviso de fechamento ligado." if self.var_lembrar_fecho.get()
            else "Não aviso mais sobre fechamento.")
        self.recarregar()

    def abrir_trilha(self) -> None:
        JanelaTrilha(self)

    def ver_sem_uso(self) -> None:
        janela = JanelaCategoriasSemUso(self, self._apos_arquivar)
        self.wait_window(janela)
        self.recarregar()

    def _apos_arquivar(self) -> None:
        self.app.atualizar_dependentes()

    def arquivar_sem_uso(self) -> None:
        if not self._sem_uso:
            return
        nomes = "\n".join(f"  · {c['codigo']}  {c['nome']}" for c in self._sem_uso[:15])
        resto = (f"\n  ... e mais {len(self._sem_uso) - 15}"
                 if len(self._sem_uso) > 15 else "")
        if not messagebox.askyesno(
                "Arquivar categorias",
                f"Arquivar {len(self._sem_uso)} categoria(s) sem nenhum uso?\n\n"
                f"{nomes}{resto}\n\n"
                "Elas saem dos seletores mas não são apagadas: para usar qualquer uma de"
                " novo, basta reativá-la na tela Categorias.", parent=self):
            return
        total = services.arquivar_contas_sem_uso()
        self.recarregar()
        self.app.atualizar_dependentes()
        self.app.notificar(f"{total} categoria(s) arquivada(s).")
        messagebox.showinfo("Pronto", f"{total} categoria(s) arquivada(s).", parent=self)

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
        self._atualizar_auditoria()
        self._atualizar_sistema()

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


# --------------------------------------------------------------------------- #
class JanelaTrilha(tk.Toplevel):
    """Tudo o que foi corrigido ou apagado, com o estado anterior de cada um.

    Cada linha guarda como o registro era ANTES daquela mudança. Somado ao que
    está hoje em Entradas e Saídas, isso reconstrói a história inteira.
    """

    FILTROS = {"Tudo": "", "Só o que foi corrigido": "ALTERADO",
               "Só o que foi apagado": "EXCLUIDO", "Só criações": "CRIADO"}

    def __init__(self, master):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.title("Trilha de alterações")
        self.configure(padx=0, pady=0)

        cabecalho = Cabecalho(
            self, "Trilha de alterações",
            "Cada linha mostra como o registro estava antes da mudança. Nada aqui pode ser"
            " editado — é justamente o ponto.")
        cabecalho.pack(fill="x")
        cabecalho.botao("Salvar em arquivo", self.exportar)
        cabecalho.botao("Fechar", self.destroy)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(20, 16))
        corpo.pack(fill="both", expand=True)

        filtros = ttk.Frame(corpo, style="Superficie.TFrame", padding=12)
        filtros.configure(relief="solid", borderwidth=1)
        filtros.pack(fill="x")
        ttk.Label(filtros, text="Mostrar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.cb_acao = ttk.Combobox(filtros, state="readonly", width=24,
                                    values=list(self.FILTROS))
        self.cb_acao.set("Tudo")
        self.cb_acao.pack(side="left", padx=(8, 20))
        self.cb_acao.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        ttk.Label(filtros, text="Procurar:", style="CampoSuperficie.TLabel").pack(side="left")
        self.var_texto = tk.StringVar()
        entrada = ttk.Entry(filtros, textvariable=self.var_texto, width=30)
        entrada.pack(side="left", padx=8)
        entrada.bind("<Return>", lambda _e: self.recarregar())
        ttk.Button(filtros, text="Procurar", command=self.recarregar).pack(side="left")
        ttk.Button(filtros, text="Limpar", command=self.limpar).pack(side="left", padx=8)
        self.lbl_resumo = ttk.Label(filtros, style="DicaSuperficie.TLabel")
        self.lbl_resumo.pack(side="right")

        self.tabela = Tabela(corpo, [
            ("quando", "Quando mudou", 150, "center"),
            ("acao", "O que houve", 100, "center"),
            ("data", "Data do registro", 110, "center"),
            ("descricao", "Como estava", 260, "w"),
            ("valor", "Valor de então", 120, "e"),
            ("motivo", "Por quê", 190, "w"),
            ("situacao", "Hoje", 90, "center"),
        ], largura_livre=True, altura=16)
        self.tabela.definir_texto_vazio(
            "Nada foi corrigido nem apagado desde que a trilha passou a existir.")
        self.tabela.pack(fill="both", expand=True, pady=(12, 0))

        self.lbl_partidas = ttk.Label(corpo, style="DicaSuperficie.TLabel", wraplength=900,
                                      justify="left")
        self.lbl_partidas.pack(anchor="w", pady=(10, 0))
        self.tabela.tree.bind("<<TreeviewSelect>>", lambda _e: self._mostrar_partidas())

        self.recarregar()
        centralizar(self, 1060, 640)
        self.grab_set()

    # ------------------------------------------------------------------ #
    def limpar(self) -> None:
        self.var_texto.set("")
        self.cb_acao.set("Tudo")
        self.recarregar()

    def recarregar(self) -> None:
        self.linhas = services.listar_alteracoes(
            texto=self.var_texto.get().strip(),
            acao=self.FILTROS.get(self.cb_acao.get(), ""))
        self.tabela.limpar()
        for linha in self.linhas:
            quando = linha["quando"].replace("T", " às ")[:16]
            self.tabela.inserir(
                (quando, linha["rotulo"], services.para_br(linha["data"]),
                 linha["historico"], services.moeda(linha["valor"]),
                 linha["motivo"] or "—",
                 "existe" if linha["ainda_existe"] else "apagado"),
                iid=str(linha["id"]),
                tags=("negativo",) if linha["acao"] == "EXCLUIDO" else ())
        self.tabela.finalizar()

        resumo = services.resumo_alteracoes()
        self.lbl_resumo.configure(
            text=f"{len(self.linhas)} de {resumo['total']} evento(s)   ·   "
                 f"{resumo['alterados']} correção(ões), {resumo['excluidos']} exclusão(ões)")
        self.lbl_partidas.configure(
            text="Escolha uma linha para ver as contas que o registro usava naquele momento.")

    def _mostrar_partidas(self) -> None:
        item = self.tabela.selecionado()
        if not item:
            return
        escolhida = next((l for l in self.linhas if str(l["id"]) == item), None)
        if escolhida is None:
            return
        documento = f"   ·   documento {escolhida['documento']}" if escolhida["documento"] else ""
        self.lbl_partidas.configure(
            text=f"Registro #{escolhida['lancamento_id']}{documento}\n"
                 f"{escolhida['partidas'] or 'sem partidas registradas'}")

    def exportar(self) -> None:
        ensure_dirs()
        caminho = filedialog.asksaveasfilename(
            parent=self, initialdir=EXPORT_DIR, initialfile="trilha_de_alteracoes.csv",
            defaultextension=".csv", filetypes=[("Planilha (CSV)", "*.csv")])
        if not caminho:
            return
        with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(["Quando mudou", "O que houve", "Registro", "Data do registro",
                               "Como estava", "Valor de então", "Contas", "Por quê",
                               "Hoje"])
            for linha in self.linhas:
                escritor.writerow([
                    linha["quando"].replace("T", " "), linha["rotulo"],
                    linha["lancamento_id"], services.para_br(linha["data"]),
                    linha["historico"], f"{linha['valor']:.2f}".replace(".", ","),
                    linha["partidas"], linha["motivo"],
                    "existe" if linha["ainda_existe"] else "apagado"])
        messagebox.showinfo("Pronto", f"Arquivo salvo em:\n{caminho}", parent=self)


# --------------------------------------------------------------------------- #
class JanelaCategoriasSemUso(tk.Toplevel):
    """Ver o que há dentro de cada categoria antes de decidir arquivá-la.

    Arquivar é uma decisão pequena, mas é uma decisão. A pessoa merece ver a
    prova — lançamentos, contas, tetos, metas, tudo em zero — em vez de confiar
    na palavra do programa de que aquilo "nunca foi usado".
    """

    def __init__(self, master, ao_mudar=None):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.title("Categorias que nunca foram usadas")
        self.ao_mudar = ao_mudar

        cabecalho = Cabecalho(
            self, "Categorias que nunca foram usadas",
            "Vieram do plano de contas padrão. Confira o que há em cada uma e escolha o"
            " que tirar do caminho.")
        cabecalho.pack(fill="x")
        cabecalho.botao("Arquivar as escolhidas", self.arquivar_escolhidas,
                        "Primario.TButton")
        cabecalho.botao("Arquivar todas", self.arquivar_todas)
        cabecalho.botao("Fechar", self.destroy)
        ttk.Separator(self).pack(fill="x")

        corpo = ttk.Frame(self, padding=(20, 16))
        corpo.pack(fill="both", expand=True)

        self.tabela = Tabela(corpo, [
            ("codigo", "Código", 90, "w"),
            ("nome", "Categoria", 240, "w"),
            ("grupo", "Dentro de", 180, "w"),
            ("tipo", "Tipo", 110, "w"),
            ("lancamentos", "Lançamentos", 100, "center"),
            ("ligacoes", "Ligada a", 160, "w"),
        ], largura_livre=True, altura=12, selecao_multipla=True)
        self.tabela.definir_texto_vazio(
            "Todas as suas categorias estão em uso. Nada a arrumar aqui.")
        self.tabela.pack(fill="both", expand=True)

        ttk.Label(corpo,
                  text="Escolha uma ou mais linhas (segure Ctrl ou Shift) e clique em"
                       " 'Arquivar as escolhidas'. Arquivar não apaga nada: a categoria"
                       " some dos seletores e volta quando você quiser, na tela"
                       " Categorias.",
                  style="Dica.TLabel", wraplength=880,
                  justify="left").pack(anchor="w", pady=(12, 0))
        self.lbl_resumo = ttk.Label(corpo, style="Secao.TLabel")
        self.lbl_resumo.pack(anchor="w", pady=(8, 0))

        self.recarregar()
        centralizar(self, 980, 560)
        self.grab_set()

    # ------------------------------------------------------------------ #
    def recarregar(self) -> None:
        self.candidatas = services.detalhe_das_contas_sem_uso()
        self.tabela.limpar()
        for linha in self.candidatas:
            self.tabela.inserir(
                (linha["codigo"], linha["nome"], linha["grupo"] or "—", linha["rotulo"],
                 str(linha["lancamentos"]), self._ligacoes(linha)),
                iid=str(linha["id"]),
                tags=() if linha["vazia"] else ("negativo",))
        self.tabela.finalizar()
        self.lbl_resumo.configure(
            text=f"{len(self.candidatas)} categoria(s) sem nenhum uso."
            if self.candidatas else "Nenhuma categoria sobrando.")

    @staticmethod
    def _ligacoes(linha: dict) -> str:
        """O que existe amarrado nesta categoria, dito por extenso."""
        partes = [(linha["titulos"], "conta(s) a pagar"),
                  (linha["contas_fixas"], "conta(s) fixa(s)"),
                  (linha["orcamentos"], "teto(s)"),
                  (linha["metas"], "meta(s)"),
                  (linha["compras"], "compra(s) parcelada(s)"),
                  (linha["filhas"], "subcategoria(s)"),
                  (linha["regras"], "regra(s) de importação")]
        texto = ", ".join(f"{n} {nome}" for n, nome in partes if n)
        return texto or "nada"

    def _escolhidas(self) -> list[dict]:
        ids = {int(item) for item in self.tabela.tree.selection()}
        return [c for c in self.candidatas if c["id"] in ids]

    def arquivar_escolhidas(self) -> None:
        escolhidas = self._escolhidas()
        if not escolhidas:
            messagebox.showinfo(
                "Arquivar", "Escolha antes uma ou mais categorias na lista.", parent=self)
            return
        self._arquivar(escolhidas)

    def arquivar_todas(self) -> None:
        if not self.candidatas:
            return
        self._arquivar(self.candidatas)

    def _arquivar(self, alvos: list[dict]) -> None:
        nomes = "\n".join(f"  · {c['codigo']}  {c['nome']}" for c in alvos[:15])
        resto = f"\n  ... e mais {len(alvos) - 15}" if len(alvos) > 15 else ""
        if not messagebox.askyesno(
                "Arquivar categorias",
                f"Arquivar {len(alvos)} categoria(s)?\n\n{nomes}{resto}\n\n"
                "Elas saem dos seletores mas não são apagadas: para usar qualquer uma"
                " de novo, basta reativá-la na tela Categorias.", parent=self):
            return
        total = services.arquivar_contas_sem_uso([c["id"] for c in alvos])
        self.recarregar()
        if self.ao_mudar:
            self.ao_mudar()
        messagebox.showinfo("Pronto", f"{total} categoria(s) arquivada(s).", parent=self)
