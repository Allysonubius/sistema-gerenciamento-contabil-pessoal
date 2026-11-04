"""Aplicação desativada não some do mundo: ela sai do dia a dia e volta quando
o dono quiser.

Desativar sem caminho de volta seria apagar com outro nome. Estes testes
guardam as duas metades do gesto — a saída e o retorno — e a separação entre o
que está em uso e o que já foi encerrado.
"""
from __future__ import annotations

import importlib

import pytest


class _Perguntas:
    """Substitui as caixas de diálogo: o teste responde no lugar do usuário."""

    def __init__(self, escolha=None):
        self.avisos: list[tuple] = []
        self.opcoes: list[list] = []
        self._resposta = escolha

    def avisar(self, _master, titulo, texto, destaque=""):
        self.avisos.append((titulo, texto))

    def escolher(self, _master, _titulo, _pergunta, opcoes, detalhe=""):
        self.opcoes.append([o[2] for o in opcoes])
        return self._resposta


@pytest.fixture()
def investimentos(sistema, raiz_tk, monkeypatch):
    modulo = importlib.reload(importlib.import_module("app.ui.investimentos"))

    def abrir(resposta=None):
        falsas = _Perguntas(resposta)
        monkeypatch.setattr(modulo, "perguntas", falsas)
        janela = modulo.JanelaInvestimentos(raiz_tk, lambda: None)
        janela.grab_release()
        return janela, falsas

    yield abrir
    for filho in raiz_tk.winfo_children():
        filho.destroy()


def _aplicacao(sistema, nome: str = "Reserva", saldo: float = 0.0):
    conta = sistema.criar_carteira(nome, "Investimento")
    sistema.marcar_como_investimento(conta)
    if saldo:
        sistema.registrar_saldo_inicial(conta, saldo, sistema.hoje_iso())
    return conta


def _nomes(janela) -> list[str]:
    return [janela.tabela.tree.item(i, "values")[0]
            for i in janela.tabela.tree.get_children()]


# --------------------------------------------------------------------------- #
# A regra, antes da tela
# --------------------------------------------------------------------------- #
def test_a_lista_padrao_so_traz_as_ativas(sistema, contas):
    viva = _aplicacao(sistema, "Viva", 300.0)
    morta = _aplicacao(sistema, "Encerrada", 100.0)
    sistema.definir_conta_ativa(morta, False)

    ids = [i["id"] for i in sistema.listar_investimentos()]
    assert viva in ids
    assert morta not in ids


def test_as_inativas_aparecem_quando_pedidas(sistema, contas):
    morta = _aplicacao(sistema, "Encerrada", 100.0)
    sistema.definir_conta_ativa(morta, False)

    por_id = {i["id"]: i for i in sistema.listar_investimentos(incluir_inativas=True)}
    assert morta in por_id
    assert por_id[morta]["ativa"] is False
    assert por_id[morta]["saldo"] == 100.0, "o saldo continua lá"


def test_desativar_nao_derruba_o_total_investido_para_sempre(sistema, contas):
    conta = _aplicacao(sistema, "Reserva", 400.0)
    assert sistema.resumo_investimentos()["total"] == 400.0

    sistema.definir_conta_ativa(conta, False)
    assert sistema.resumo_investimentos()["total"] == 0.0

    sistema.definir_conta_ativa(conta, True)
    assert sistema.resumo_investimentos()["total"] == 400.0, "reativar devolve tudo"


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
def test_a_tela_separa_ativas_de_inativas(sistema, contas, investimentos):
    _aplicacao(sistema, "Viva", 300.0)
    morta = _aplicacao(sistema, "Encerrada", 100.0)
    sistema.definir_conta_ativa(morta, False)

    janela, _falsas = investimentos()
    try:
        assert _nomes(janela) == ["Viva"], "por padrão, só o que está em uso"

        janela.var_mostrar.set("inativas")
        janela.recarregar()
        assert _nomes(janela) == ["Encerrada"]

        janela.var_mostrar.set("todas")
        janela.recarregar()
        assert _nomes(janela) == ["Viva", "Encerrada"], "as ativas primeiro"
        assert "1 ativa(s)" in janela.lbl_quantas.cget("text")
    finally:
        janela.destroy()


def test_a_coluna_situacao_diz_qual_e_qual(sistema, contas, investimentos):
    morta = _aplicacao(sistema, "Encerrada", 100.0)
    sistema.definir_conta_ativa(morta, False)

    janela, _falsas = investimentos()
    try:
        janela.var_mostrar.set("todas")
        janela.recarregar()
        linha = janela.tabela.tree.item(str(morta), "values")
        assert linha[-1] == "Inativa"
        assert "inativa" in janela.tabela.tree.item(str(morta), "tags")
    finally:
        janela.destroy()


def test_o_botao_desativa_a_aplicacao_escolhida(sistema, contas, investimentos):
    conta = _aplicacao(sistema, "Reserva", 500.0)
    janela, _falsas = investimentos(resposta="sim")
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.alternar_ativa()

        guardada = sistema.obter_conta(conta)
        assert guardada["ativo"] == 0
        assert sistema.saldo_conta(conta) == 500.0, "desativar não apaga saldo"
    finally:
        janela.destroy()


def test_desativar_pede_confirmacao_e_a_recusa_vale(sistema, contas, investimentos):
    conta = _aplicacao(sistema, "Reserva", 500.0)
    janela, falsas = investimentos(resposta="nada")
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.alternar_ativa()

        assert falsas.opcoes, "precisa perguntar antes de desativar"
        assert falsas.opcoes[0][0] == "nada", "a opção que não muda nada vem primeiro"
        assert sistema.obter_conta(conta)["ativo"] == 1
    finally:
        janela.destroy()


def test_reativar_nao_pergunta_nada_e_traz_de_volta(sistema, contas, investimentos):
    """Voltar ao normal não precisa de aviso: nada se perde ao reativar."""
    conta = _aplicacao(sistema, "Reserva", 500.0)
    sistema.definir_conta_ativa(conta, False)

    janela, falsas = investimentos()
    try:
        janela.var_mostrar.set("inativas")
        janela.recarregar()
        janela.tabela.tree.selection_set(str(conta))
        janela._ajustar_botao_ativa()
        assert janela.btn_ativa.cget("text") == "Reativar"

        janela.alternar_ativa()
        assert falsas.opcoes == [], "reativar não precisa de confirmação"
        assert sistema.obter_conta(conta)["ativo"] == 1
        assert janela.var_mostrar.get() == "ativas", "mostra onde a linha foi parar"
        assert "Reserva" in _nomes(janela)
    finally:
        janela.destroy()


def test_o_botao_muda_de_nome_conforme_a_linha(sistema, contas, investimentos):
    viva = _aplicacao(sistema, "Viva", 300.0)
    morta = _aplicacao(sistema, "Encerrada", 100.0)
    sistema.definir_conta_ativa(morta, False)

    janela, _falsas = investimentos()
    try:
        janela.var_mostrar.set("todas")
        janela.recarregar()
        janela.tabela.tree.selection_set(str(viva))
        janela._ajustar_botao_ativa()
        assert janela.btn_ativa.cget("text") == "Desativar"

        janela.tabela.tree.selection_set(str(morta))
        janela._ajustar_botao_ativa()
        assert janela.btn_ativa.cget("text") == "Reativar"
    finally:
        janela.destroy()
