"""As telas novas abrem, mostram e reagem — sem depender do olho de ninguém.

Um erro de digitação em `relatorios.py` ou `configuracoes.py` só aparecia ao
clicar na tela; estes testes montam cada uma delas de verdade.
"""
from __future__ import annotations

import importlib

import pytest


class AppFalso:
    """O mínimo que as telas esperam do objeto da aplicação."""

    def __init__(self):
        self.avisos: list[str] = []

    def notificar(self, texto: str) -> None:
        self.avisos.append(texto)

    def atualizar_dependentes(self) -> None:
        pass

    def aplicar_preferencias(self) -> None:
        pass

    def abrir_relatorio(self, indice: int) -> None:
        pass


@pytest.fixture()
def limpar_tela(raiz_tk):
    yield
    for filho in raiz_tk.winfo_children():
        filho.destroy()


@pytest.fixture()
def movimento(sistema, contas):
    return sistema.salvar_lancamento(
        None, "2026-05-10", "Farmácia",
        [sistema.Partida(contas["despesa"], "D", 45.0),
         sistema.Partida(contas["banco"], "C", 45.0)])


# --------------------------------------------------------------------------- #
# Relatórios
# --------------------------------------------------------------------------- #
@pytest.fixture()
def relatorios(sistema, contas, movimento, raiz_tk, limpar_tela):
    modulo = importlib.import_module("app.ui.relatorios")
    importlib.reload(modulo)
    tela = modulo.Relatorios(raiz_tk, AppFalso())
    return tela, modulo


def test_o_ano_a_ano_esta_no_menu_logo_depois_do_mes_a_mes(relatorios):
    _tela, modulo = relatorios
    assert modulo.RELATORIOS[1][0] == "Ano a ano"


def test_cada_relatorio_tem_o_seu_quadro(relatorios):
    tela, modulo = relatorios
    assert len(tela.quadros) == len(modulo.RELATORIOS)


def test_todos_os_relatorios_geram_sem_erro(relatorios):
    """Percorre o menu inteiro: é o que pega índice trocado de lugar."""
    tela, modulo = relatorios
    for indice in range(len(modulo.RELATORIOS)):
        tela.lista.selecionar(indice)
        tela.update_idletasks()
        assert tela._indice_atual == indice


def test_o_ano_a_ano_preenche_a_tabela(relatorios):
    tela, _modulo = relatorios
    tela.lista.selecionar(1)

    linhas = tela.tab_anual.tree.get_children()
    assert linhas
    assert any("2026" in str(iid) for iid in linhas)


def test_o_ano_a_ano_resume_a_direcao_em_uma_frase(relatorios):
    tela, _modulo = relatorios
    tela.lista.selecionar(1)

    assert "2026" in tela.lbl_direcao.cget("text")


def test_a_previsao_abre_no_horizonte_inteiro(relatorios):
    tela, modulo = relatorios
    assert tela.cb_previsao.get() == modulo.OPCAO_COMPROMISSO


def test_o_relatorio_anual_nao_usa_o_seletor_de_periodo(relatorios):
    _tela, modulo = relatorios
    assert 1 in modulo.RELATORIOS_MENSAIS


# --------------------------------------------------------------------------- #
# Ajustes: fechamento, trilha e categorias
# --------------------------------------------------------------------------- #
@pytest.fixture()
def ajustes(sistema, contas, movimento, raiz_tk, limpar_tela):
    modulo = importlib.import_module("app.ui.configuracoes")
    importlib.reload(modulo)
    tela = modulo.Configuracoes(raiz_tk, AppFalso())
    tela.recarregar()
    return tela, modulo


def test_ajustes_avisa_que_nada_esta_fechado(ajustes):
    tela, _modulo = ajustes
    assert "Nenhum mês fechado" in tela.lbl_fecho.cget("text")


def test_ajustes_oferece_os_meses_que_ja_terminaram(ajustes, sistema):
    tela, _modulo = ajustes
    assert tela._meses_fechaveis
    assert all(mes < sistema.mes_atual() for mes in tela._meses_fechaveis)


def test_depois_de_fechar_a_tela_mostra_o_mes(ajustes, sistema):
    tela, _modulo = ajustes
    sistema.fechar_competencia(tela._meses_fechaveis[0])
    tela.recarregar()

    assert "Fechado até" in tela.lbl_fecho.cget("text")


def test_ajustes_lista_as_categorias_sem_uso(ajustes):
    tela, _modulo = ajustes
    assert tela._sem_uso
    assert "nunca receberam" in tela.lbl_sem_uso.cget("text")


def test_depois_de_arquivar_a_tela_diz_que_esta_tudo_em_uso(ajustes, sistema):
    tela, _modulo = ajustes
    sistema.arquivar_contas_sem_uso()
    tela.recarregar()

    assert tela._sem_uso == []
    assert "em uso" in tela.lbl_sem_uso.cget("text")


def test_a_janela_da_trilha_abre_e_lista(ajustes, sistema, movimento):
    tela, modulo = ajustes
    janela = modulo.JanelaTrilha(tela)
    janela.grab_release()
    try:
        assert janela.tabela.tree.get_children()
        assert "evento(s)" in janela.lbl_resumo.cget("text")
    finally:
        janela.destroy()


def test_a_trilha_filtra_por_acao(ajustes, sistema, contas, movimento):
    sistema.excluir_lancamento(movimento)
    tela, modulo = ajustes
    janela = modulo.JanelaTrilha(tela)
    janela.grab_release()
    try:
        janela.cb_acao.set("Só o que foi apagado")
        janela.recarregar()
        assert len(janela.linhas) == 1
        assert janela.linhas[0]["acao"] == "EXCLUIDO"
    finally:
        janela.destroy()


# --------------------------------------------------------------------------- #
# Comprovantes
# --------------------------------------------------------------------------- #
def test_a_janela_de_comprovantes_abre_vazia(sistema, contas, movimento, raiz_tk,
                                             limpar_tela):
    modulo = importlib.import_module("app.ui.lancamentos")
    importlib.reload(modulo)
    janela = modulo.JanelaComprovantes(raiz_tk, movimento)
    janela.grab_release()
    try:
        assert janela.anexos == []
        assert janela.tabela.tree.get_children() == ()
    finally:
        janela.destroy()


def test_a_janela_de_comprovantes_mostra_o_que_foi_anexado(sistema, contas, movimento,
                                                           raiz_tk, tmp_path, limpar_tela):
    recibo = tmp_path / "nota.pdf"
    recibo.write_bytes(b"x" * 512)
    sistema.anexar_comprovante(movimento, recibo)

    modulo = importlib.import_module("app.ui.lancamentos")
    importlib.reload(modulo)
    janela = modulo.JanelaComprovantes(raiz_tk, movimento)
    janela.grab_release()
    try:
        assert len(janela.anexos) == 1
        assert janela.tabela.tree.set(
            janela.tabela.tree.get_children()[0], "nome") == "nota.pdf"
    finally:
        janela.destroy()


def test_a_lista_de_lancamentos_tem_a_coluna_de_comprovante(sistema, contas, movimento,
                                                            raiz_tk, limpar_tela):
    modulo = importlib.import_module("app.ui.lancamentos")
    importlib.reload(modulo)
    tela = modulo.Lancamentos(raiz_tk, AppFalso())
    tela.recarregar()

    assert "anexos" in [coluna[0] for coluna in tela.tabela.colunas]


def test_o_registro_de_titulo_nao_pede_mais_o_grupo(sistema, contas, raiz_tk, limpar_tela):
    """O campo saiu: eram três opções sem nenhum relatório atrás delas."""
    modulo = importlib.import_module("app.ui.financeiro")
    importlib.reload(modulo)
    dialogo = modulo.DialogoTitulo(raiz_tk, None, lambda: None)
    dialogo.grab_release()
    try:
        assert not hasattr(dialogo, "sel_centro")
    finally:
        dialogo.destroy()


# --------------------------------------------------------------------------- #
# Ver as categorias antes de arquivar
# --------------------------------------------------------------------------- #
def test_a_janela_das_categorias_lista_as_candidatas(ajustes):
    tela, modulo = ajustes
    janela = modulo.JanelaCategoriasSemUso(tela)
    janela.grab_release()
    try:
        assert janela.candidatas
        assert len(janela.tabela.tree.get_children()) == len(janela.candidatas)
    finally:
        janela.destroy()


def test_a_janela_mostra_a_prova_de_que_a_categoria_esta_vazia(ajustes):
    """É isso que autoriza arquivar sem pensar duas vezes."""
    tela, modulo = ajustes
    janela = modulo.JanelaCategoriasSemUso(tela)
    janela.grab_release()
    try:
        primeira = janela.tabela.tree.get_children()[0]
        assert janela.tabela.tree.set(primeira, "lancamentos") == "0"
        assert janela.tabela.tree.set(primeira, "ligacoes") == "nada"
        assert janela.tabela.tree.set(primeira, "grupo")
    finally:
        janela.destroy()


def test_a_janela_arquiva_so_as_escolhidas(ajustes, sistema, monkeypatch):
    tela, modulo = ajustes
    monkeypatch.setattr(modulo.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(modulo.messagebox, "showinfo", lambda *a, **k: None)
    janela = modulo.JanelaCategoriasSemUso(tela)
    janela.grab_release()
    try:
        antes = len(janela.candidatas)
        escolhida = janela.tabela.tree.get_children()[0]
        janela.tabela.tree.selection_set(escolhida)
        janela.arquivar_escolhidas()

        assert len(janela.candidatas) == antes - 1
        assert sistema.obter_conta(int(escolhida))["ativo"] == 0
    finally:
        janela.destroy()


def test_a_janela_avisa_quando_nada_foi_escolhido(ajustes, monkeypatch):
    tela, modulo = ajustes
    avisos = []
    monkeypatch.setattr(modulo.messagebox, "showinfo",
                        lambda *a, **k: avisos.append(a))
    janela = modulo.JanelaCategoriasSemUso(tela)
    janela.grab_release()
    try:
        janela.tabela.tree.selection_remove(*janela.tabela.tree.selection())
        janela.arquivar_escolhidas()
        assert avisos
    finally:
        janela.destroy()


def test_ajustes_tem_o_botao_de_ver_antes_de_arquivar(ajustes):
    tela, _modulo = ajustes
    assert tela.btn_ver_sem_uso.cget("text") == "Ver as categorias"
    assert "disabled" not in tela.btn_ver_sem_uso.state()
