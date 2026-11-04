"""Conta a conta: o dinheiro pode existir e estar no lugar errado.

O total do rodapé responde "dá para pagar?". Esta visão responde a pergunta
seguinte, que é a que trava o pagamento na hora: *desta* conta, dá?
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def contas_a_pagar(sistema, contas):
    def criar(valor: float, conta_pagamento=..., tipo: str = "PAGAR"):
        destino = contas["banco"] if conta_pagamento is ... else conta_pagamento
        return sistema.salvar_titulo(
            None, tipo, "Conta", "", valor, sistema.hoje_iso(),
            contas["despesa"] if tipo == "PAGAR" else contas["receita"], None,
            conta_pagamento_id=destino)

    return criar, lambda: sistema.titulos_com_encargos(status="ABERTO")


def por_nome(resumo: dict) -> dict:
    return {c["nome"]: c for c in resumo["contas"]}


# --------------------------------------------------------------------------- #
# A soma conta a conta
# --------------------------------------------------------------------------- #
def test_cada_conta_mostra_o_que_tem_e_o_que_sai(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(300.0)
    resumo = sistema.contas_para_pagamento(linhas())
    banco = por_nome(resumo)["Banco Teste"]

    assert banco["saldo"] == 1000.0
    assert banco["sai"] == 300.0
    assert banco["fica"] == 700.0
    assert banco["cobre"] is True
    assert banco["quantas"] == 1


def test_diz_quanto_falta_na_conta_que_nao_cobre(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(500.0, conta_pagamento=contas["outra"])      # tem 100,00
    resumo = sistema.contas_para_pagamento(linhas())
    carteira = por_nome(resumo)["Carteira"]

    assert carteira["cobre"] is False
    assert carteira["falta"] == 400.0
    assert carteira["fica"] == -400.0
    assert resumo["faltando"] == [carteira]


def test_o_dinheiro_pode_estar_no_lugar_errado(sistema, contas, contas_a_pagar):
    """No total sobra; na conta que paga, falta."""
    criar, linhas = contas_a_pagar
    criar(500.0, conta_pagamento=contas["outra"])
    resumo = sistema.contas_para_pagamento(linhas())

    assert resumo["tem"] > resumo["sai"], "no total o dinheiro existe"
    assert resumo["faltando"], "mas não na conta de onde sai"
    assert "transferir antes de pagar" in sistema.recado_por_conta(resumo)


def test_o_que_vai_entrar_aparece_na_conta(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(200.0, tipo="RECEBER")
    banco = por_nome(sistema.contas_para_pagamento(linhas()))["Banco Teste"]

    assert banco["entra"] == 200.0
    assert banco["fica"] == 1000.0, "o que entra não muda o que já tem"
    assert banco["fica_com_entradas"] == 1200.0


def test_conta_do_cartao_fica_fora_das_contas_de_dinheiro(sistema, contas,
                                                          contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(200.0, conta_pagamento=contas["cartao"])
    resumo = sistema.contas_para_pagamento(linhas())

    assert resumo["no_cartao"] == 200.0
    assert resumo["sai"] == 0.0
    assert resumo["usadas"] == []


def test_conta_sem_conta_escolhida_aparece_separada(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(150.0, conta_pagamento=None)
    resumo = sistema.contas_para_pagamento(linhas())

    assert resumo["sem_conta"] == 150.0
    assert resumo["sai"] == 0.0


def test_contas_com_problema_aparecem_primeiro(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(100.0)                                        # banco: sobra
    criar(500.0, conta_pagamento=contas["outra"])       # carteira: falta
    resumo = sistema.contas_para_pagamento(linhas())

    assert resumo["contas"][0]["nome"] == "Carteira", "a pior vem primeiro"
    assert resumo["contas"][1]["nome"] == "Banco Teste"


def test_conta_sem_movimento_e_marcada_como_tal(sistema, contas, contas_a_pagar):
    _criar, linhas = contas_a_pagar
    banco = por_nome(sistema.contas_para_pagamento(linhas()))["Banco Teste"]

    assert banco["usada"] is False
    assert banco["sai"] == 0.0 and banco["fica"] == banco["saldo"]


def test_conta_que_nao_vale_como_dinheiro_fica_de_fora(sistema, contas,
                                                       contas_a_pagar):
    """Em Minhas Contas o usuário escolhe quais contas valem como saldo."""
    criar, linhas = contas_a_pagar
    criar(50.0, conta_pagamento=contas["outra"])
    sistema.definir_conta_dinheiro(contas["outra"], False)
    resumo = sistema.contas_para_pagamento(linhas())

    assert "Carteira" not in por_nome(resumo)
    assert resumo["sai"] == 0.0


def test_conta_ja_paga_nao_entra(sistema, contas, contas_a_pagar):
    criar, _linhas = contas_a_pagar
    titulo = criar(100.0)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 100.0, contas["banco"])
    resumo = sistema.contas_para_pagamento(sistema.titulos_com_encargos())

    assert resumo["sai"] == 0.0


def test_tudo_coberto_tem_recado_proprio(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(100.0)

    assert "têm saldo" in sistema.recado_por_conta(
        sistema.contas_para_pagamento(linhas()))


# --------------------------------------------------------------------------- #
# A janela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


def test_a_janela_lista_as_contas_com_movimento(sistema, contas, raiz_tk):
    sistema.salvar_titulo(None, "PAGAR", "Luz", "", 200.0, sistema.hoje_iso(),
                          contas["despesa"], None, conta_pagamento_id=contas["banco"])
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    linhas = sistema.titulos_com_encargos(status="ABERTO")
    janela = modulo.JanelaDinheiroPorConta(raiz_tk, linhas, "novembro")
    janela.grab_release()
    try:
        nomes = [janela.tabela.tree.item(i, "values")[0]
                 for i in janela.tabela.tree.get_children()]
        assert "Banco Teste" in nomes
        assert "Somando tudo" in janela.lbl_total.cget("text")
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_janela_esconde_contas_vazias_e_sem_movimento(sistema, contas, raiz_tk):
    sistema.criar_carteira("Conta Nova", "Conta corrente")       # zerada, sem uso
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    janela = modulo.JanelaDinheiroPorConta(raiz_tk, [], "")
    janela.grab_release()
    try:
        nomes = [janela.tabela.tree.item(i, "values")[0]
                 for i in janela.tabela.tree.get_children()]
        assert "Conta Nova" not in nomes

        janela.var_todas.set(True)
        janela.recarregar()
        nomes = [janela.tabela.tree.item(i, "values")[0]
                 for i in janela.tabela.tree.get_children()]
        assert "Conta Nova" in nomes
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_o_botao_esta_na_tela_de_contas_a_pagar(sistema, contas, raiz_tk):
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        assert hasattr(tela, "abrir_por_conta")
        assert isinstance(tela._linhas, list)
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


# --------------------------------------------------------------------------- #
# Encerrar uma aplicação
# --------------------------------------------------------------------------- #
class _Perguntas:
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


def _aplicacao(sistema, saldo: float = 0.0):
    conta = sistema.criar_carteira("Reserva", "Investimento")
    sistema.marcar_como_investimento(conta)
    if saldo:
        sistema.registrar_saldo_inicial(conta, saldo, sistema.hoje_iso())
    return conta


def test_aplicacao_com_saldo_nao_oferece_apagar(sistema, contas, investimentos):
    """Apagar levaria junto os aportes que explicam de onde veio o dinheiro."""
    conta = _aplicacao(sistema, 500.0)
    janela, falsas = investimentos(resposta="nada")
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.encerrar()

        assert falsas.opcoes, "precisa perguntar"
        assert "apagar" not in falsas.opcoes[0]
        assert falsas.opcoes[0][0] == "nada", "a opção que não muda nada vem primeiro"
    finally:
        janela.destroy()


def test_desativar_tira_da_lista_sem_apagar(sistema, contas, investimentos):
    conta = _aplicacao(sistema, 500.0)
    janela, _falsas = investimentos(resposta="desativar")
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.encerrar()

        guardada = sistema.obter_conta(conta)
        assert guardada is not None and guardada["ativo"] == 0
        assert sistema.saldo_conta(conta) == 500.0, "o saldo não se perde"
    finally:
        janela.destroy()


def test_desmarcar_deixa_a_conta_viva(sistema, contas, investimentos):
    conta = _aplicacao(sistema, 500.0)
    janela, _falsas = investimentos(resposta="desmarcar")
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.encerrar()

        guardada = sistema.obter_conta(conta)
        assert guardada["ativo"] == 1
        assert conta not in [i["id"] for i in sistema.listar_investimentos()]
    finally:
        janela.destroy()


def test_aplicacao_zerada_e_sem_uso_pode_ser_apagada(sistema, contas, investimentos):
    conta = _aplicacao(sistema)
    janela, falsas = investimentos(resposta="apagar")
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.encerrar()

        assert "apagar" in falsas.opcoes[0]
        assert sistema.obter_conta(conta) is None
    finally:
        janela.destroy()


def test_desistir_nao_muda_nada(sistema, contas, investimentos):
    conta = _aplicacao(sistema, 500.0)
    janela, _falsas = investimentos(resposta=None)
    try:
        janela.tabela.tree.selection_set(str(conta))
        janela.encerrar()

        assert sistema.obter_conta(conta)["ativo"] == 1
    finally:
        janela.destroy()


def test_desativar_e_reversivel(sistema, contas):
    conta = _aplicacao(sistema, 500.0)
    sistema.definir_conta_ativa(conta, False)
    assert sistema.obter_conta(conta)["ativo"] == 0

    sistema.definir_conta_ativa(conta, True)

    assert sistema.obter_conta(conta)["ativo"] == 1
    assert sistema.saldo_conta(conta) == 500.0


def test_aplicacao_criada_e_zerada_aparece_na_lista(sistema, contas):
    """Conta que existe e não se vê é conta que não dá para encerrar."""
    conta = _aplicacao(sistema)

    assert conta in [i["id"] for i in sistema.listar_investimentos()]


def test_conta_generica_do_plano_so_aparece_se_usada(sistema, contas):
    """Essas vieram da carga inicial, não de uma escolha de ninguém."""
    generica = sistema._conta_por_codigo("1.1.05")
    sistema.marcar_como_investimento(generica)

    assert generica not in [i["id"] for i in sistema.listar_investimentos()]

    sistema.registrar_saldo_inicial(generica, 10.0, sistema.hoje_iso())

    assert generica in [i["id"] for i in sistema.listar_investimentos()]
