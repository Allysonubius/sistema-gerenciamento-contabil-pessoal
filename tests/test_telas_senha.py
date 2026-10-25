"""As janelas da porta e a seção 'Este computador' em Ajustes."""
from __future__ import annotations

import importlib

import pytest

from app import seguranca


class AppFalso:
    def __init__(self):
        self.avisos: list[str] = []
        self.paginas: list[str] = []

    def notificar(self, texto: str) -> None:
        self.avisos.append(texto)

    def atualizar_dependentes(self) -> None:
        pass

    def aplicar_preferencias(self) -> None:
        pass

    def instalar_no_computador(self) -> None:
        pass

    def abrir_pagina_da_versao(self) -> None:
        self.paginas.append("abriu")

    def _anunciar_versao_nova(self) -> None:
        pass


@pytest.fixture()
def tela_limpa(sistema, raiz_tk):
    seguranca._limpar()
    yield
    for filho in raiz_tk.winfo_children():
        filho.destroy()


@pytest.fixture()
def senha_ui(sistema, tela_limpa):
    return importlib.reload(importlib.import_module("app.ui.senha"))


# --------------------------------------------------------------------------- #
# Criar a senha no primeiro uso
# --------------------------------------------------------------------------- #
def test_criar_senha_pela_janela(senha_ui, raiz_tk):
    dialogo = senha_ui.DialogoCriarSenha(raiz_tk)
    dialogo.grab_release()
    try:
        dialogo.var_nova.set("segredo123")
        dialogo.var_confirma.set("segredo123")
        dialogo.salvar()
        assert seguranca.conferir_senha("segredo123") is True
    finally:
        if dialogo.winfo_exists():
            dialogo.destroy()


def test_a_janela_recusa_senha_fraca_sem_fechar(senha_ui, raiz_tk):
    dialogo = senha_ui.DialogoCriarSenha(raiz_tk)
    dialogo.grab_release()
    try:
        dialogo.var_nova.set("abc")
        dialogo.var_confirma.set("abc")
        dialogo.salvar()

        assert dialogo.liberado is False
        assert "6 caracteres" in dialogo.lbl_erro.cget("text")
        assert seguranca.tem_senha() is False
    finally:
        dialogo.destroy()


def test_a_janela_diz_o_que_a_senha_nao_faz(senha_ui, raiz_tk):
    """O aviso honesto precisa estar onde a pessoa decide usar a tranca."""
    assert "não embaralha" in senha_ui.AVISO_HONESTO
    assert "cofre" in senha_ui.AVISO_HONESTO


def test_fechar_a_janela_nao_libera(senha_ui, raiz_tk):
    dialogo = senha_ui.DialogoCriarSenha(raiz_tk)
    dialogo.grab_release()
    dialogo.desistir()

    assert dialogo.liberado is False


# --------------------------------------------------------------------------- #
# Entrar
# --------------------------------------------------------------------------- #
def test_entrar_com_a_senha_certa(senha_ui, raiz_tk):
    seguranca.definir_senha("segredo123", "segredo123")
    dialogo = senha_ui.DialogoEntrar(raiz_tk)
    dialogo.grab_release()
    try:
        dialogo.var_senha.set("segredo123")
        dialogo.entrar()
        assert dialogo.liberado is True
    finally:
        if dialogo.winfo_exists():
            dialogo.destroy()


def test_senha_errada_avisa_e_limpa_o_campo(senha_ui, raiz_tk):
    seguranca.definir_senha("segredo123", "segredo123")
    dialogo = senha_ui.DialogoEntrar(raiz_tk)
    dialogo.grab_release()
    try:
        dialogo.var_senha.set("chute")
        dialogo.entrar()

        assert dialogo.liberado is False
        assert "incorreta" in dialogo.lbl_erro.cget("text")
        assert dialogo.var_senha.get() == ""
        assert dialogo.tentativas == 1
    finally:
        dialogo.destroy()


def test_a_janela_explica_quando_a_maquina_e_outra(senha_ui, raiz_tk, monkeypatch):
    # A janela usa o módulo que ela mesma importou — é nele que o disfarce
    # precisa entrar, não no que este arquivo importou lá em cima.
    seguranca.definir_senha("segredo123", "segredo123")
    monkeypatch.setattr(senha_ui.seguranca, "_id_da_maquina",
                        lambda: "outro-computador")
    dialogo = senha_ui.DialogoEntrar(raiz_tk)
    dialogo.grab_release()
    try:
        assert "outro computador" in dialogo.lbl_erro.cget("text")
    finally:
        dialogo.destroy()


def test_esquecer_a_senha_destrava(senha_ui, raiz_tk):
    seguranca.definir_senha("segredo123", "segredo123")
    dialogo = senha_ui.DialogoEntrar(raiz_tk)
    dialogo.grab_release()
    try:
        reset = senha_ui.DialogoEsqueci(dialogo, dialogo._apos_reset)
        reset.grab_release()
        reset.var_palavra.set(seguranca.PALAVRA_DE_RESET)
        reset.apagar()

        assert seguranca.tem_senha() is False
        assert dialogo.liberado is True
    finally:
        if dialogo.winfo_exists():
            dialogo.destroy()


def test_a_palavra_errada_nao_destrava(senha_ui, raiz_tk):
    seguranca.definir_senha("segredo123", "segredo123")
    dialogo = senha_ui.DialogoEntrar(raiz_tk)
    dialogo.grab_release()
    try:
        reset = senha_ui.DialogoEsqueci(dialogo, dialogo._apos_reset)
        reset.grab_release()
        reset.var_palavra.set("sim")
        reset.apagar()

        assert seguranca.tem_senha() is True
        assert reset.lbl_erro.cget("text")
        reset.destroy()
    finally:
        dialogo.destroy()


# --------------------------------------------------------------------------- #
# A seção em Ajustes
# --------------------------------------------------------------------------- #
@pytest.fixture()
def ajustes(sistema, tela_limpa, raiz_tk):
    modulo = importlib.reload(importlib.import_module("app.ui.configuracoes"))
    tela = modulo.Configuracoes(raiz_tk, AppFalso())
    tela.recarregar()
    return tela


def test_ajustes_avisa_que_nao_ha_senha(ajustes):
    assert "Qualquer pessoa" in ajustes.lbl_senha.cget("text")
    assert ajustes.btn_senha.cget("text") == "Criar uma senha"


def test_ajustes_mostra_a_senha_existente(ajustes, sistema):
    seguranca.definir_senha("segredo123", "segredo123")
    ajustes.recarregar()

    assert "pede uma senha" in ajustes.lbl_senha.cget("text")
    assert "tranca na porta" in ajustes.lbl_senha.cget("text")
    assert ajustes.btn_senha.cget("text") == "Trocar a senha"


def test_ajustes_diz_que_a_instalacao_nao_cabe_aqui(ajustes):
    """Rodando pelo código-fonte não há .exe para instalar."""
    assert "compilado" in ajustes.lbl_instalacao.cget("text")


def test_ajustes_mostra_a_versao_atual(ajustes, sistema):
    from app.config import APP_VERSION

    assert APP_VERSION in ajustes.lbl_versao.cget("text")


def test_ajustes_anuncia_versao_nova(ajustes, sistema, monkeypatch):
    from app import atualizacao

    monkeypatch.setattr(atualizacao, "consultar", lambda *a, **k: {
        "versao": "99.0.0", "pagina": "https://exemplo/99", "nome": "", "notas": "",
        "arquivo": "", "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)
    ajustes.recarregar()

    assert "99.0.0" in ajustes.lbl_versao.cget("text")


def test_nao_ha_como_desligar_o_aviso_de_versao(ajustes, sistema):
    """Atualizar deixou de ser opcional: desligar a conferência seria a recusa
    entrando por outra porta."""
    assert not hasattr(ajustes, "var_avisar_versao")
    assert "não é opcional" in ajustes.lbl_versao.master.winfo_children()[-1].winfo_children()[-1].cget("text")


# --------------------------------------------------------------------------- #
# A janela precisa aparecer
# --------------------------------------------------------------------------- #
def test_a_janela_aparece_com_a_principal_retraida(senha_ui, raiz_tk):
    """O caso que deixou o programa invisível segurando a trava de instância.

    A janela principal fica retraída até a senha conferir. Um Toplevel
    ``transient`` de uma janela retraída nasce retraído junto — e o programa
    ficava rodando sem nada na tela, sem abrir nem liberar o lugar.
    """
    raiz_tk.withdraw()
    dialogo = senha_ui.DialogoCriarSenha(raiz_tk)
    dialogo.grab_release()
    try:
        dialogo.update_idletasks()
        dialogo.update()
        assert bool(dialogo.winfo_ismapped()) is True
    finally:
        dialogo.destroy()


def test_a_janela_de_entrar_tambem_aparece(senha_ui, raiz_tk):
    seguranca.definir_senha("segredo123", "segredo123")
    raiz_tk.withdraw()
    dialogo = senha_ui.DialogoEntrar(raiz_tk)
    dialogo.grab_release()
    try:
        dialogo.update_idletasks()
        dialogo.update()
        assert bool(dialogo.winfo_ismapped()) is True
    finally:
        dialogo.destroy()


def test_chamar_a_atencao_nao_quebra_janela_fechada(senha_ui, raiz_tk):
    dialogo = senha_ui.DialogoCriarSenha(raiz_tk)
    dialogo.grab_release()
    dialogo.destroy()
    raiz_tk.update()            # deixa o after agendado disparar sem erro


def test_abrir_porta_atende_quem_clicou_de_novo(senha_ui, raiz_tk):
    """Clicar no ícone outra vez traz a janela da senha para a frente."""
    chamadas = []
    seguranca.definir_senha("segredo123", "segredo123")

    def responder(dialogo):
        chamadas.append(dialogo)
        dialogo.var_senha.set("segredo123")
        dialogo.entrar()

    raiz_tk.withdraw()
    monitorado = senha_ui.INTERVALO_SEGUNDA_ABERTURA_MS
    senha_ui.INTERVALO_SEGUNDA_ABERTURA_MS = 50
    try:
        assert senha_ui.abrir_porta(raiz_tk, responder) is True
        assert chamadas
    finally:
        senha_ui.INTERVALO_SEGUNDA_ABERTURA_MS = monitorado
        raiz_tk.deiconify()


# --------------------------------------------------------------------------- #
# Uma porta só
# --------------------------------------------------------------------------- #
def test_pedir_a_senha_de_novo_nao_abre_outra_janela(sistema, tela_limpa, raiz_tk):
    """Clicar no ícone outra vez empilhava diálogos, um por cima do outro."""
    import importlib

    from app.ui import main_window

    seguranca.definir_senha("segredo123", "segredo123")
    senha_ui = importlib.reload(importlib.import_module("app.ui.senha"))

    class JanelaFalsa:
        _abrir_a_porta = main_window.Aplicacao._abrir_a_porta
        _guardar_janela_senha = main_window.Aplicacao._guardar_janela_senha

        def __init__(self):
            self._pedindo_senha = True       # como se já estivesse pedindo
            self._porta_aberta = False
            self._janela_senha = senha_ui.DialogoEntrar(raiz_tk)
            self._janela_senha.grab_release()

    janela = JanelaFalsa()
    abertas_antes = len([f for f in raiz_tk.winfo_children()
                         if isinstance(f, senha_ui.DialogoEntrar)])
    try:
        assert janela._abrir_a_porta() is False
        abertas_depois = len([f for f in raiz_tk.winfo_children()
                              if isinstance(f, senha_ui.DialogoEntrar)])
        assert abertas_depois == abertas_antes == 1
    finally:
        janela._janela_senha.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_restaurar_com_a_senha_na_tela_so_traz_para_a_frente(sistema, tela_limpa,
                                                             raiz_tk):
    from app.ui import main_window

    chamadas = []

    class JanelaFalsa:
        restaurar_da_bandeja = main_window.Aplicacao.restaurar_da_bandeja
        _pedindo_senha = True
        _porta_aberta = False
        _janela_senha = None

        def _abrir_a_porta(self):
            chamadas.append("porta")
            return False

        def recarregar_tela_atual(self):
            chamadas.append("recarregou")

    JanelaFalsa().restaurar_da_bandeja()

    # Só trouxe a porta para a frente: não recarregou nada atrás dela.
    assert chamadas == ["porta"]
