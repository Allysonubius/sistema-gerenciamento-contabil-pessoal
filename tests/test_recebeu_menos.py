"""Receber menos num mês não é o salário novo.

É desconto, falta, adiantamento. O programa perguntava do mesmo jeito, com a
caixa do Windows e "Sim" já escolhido — e um Enter distraído rebaixava o ano
inteiro de uma vez.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def salario(sistema, contas):
    """Um salário de 5.000 com os meses à frente já gerados."""
    rec = sistema.salvar_recorrencia(
        None, "RECEBER", "Foursys", "Foursys", 5000.0, 1, contas["receita"], None,
        sistema.mes_atual())
    sistema.gerar_titulos_recorrentes()
    titulos = sorted((t for t in sistema.listar_titulos(tipo="RECEBER")
                      if t["recorrencia_id"] == rec),
                     key=lambda t: t["competencia"])
    return rec, titulos


def abertos(sistema, rec) -> list[float]:
    return [float(t["valor"]) for t in sistema.listar_titulos(tipo="RECEBER",
                                                              status="ABERTO")
            if t["recorrencia_id"] == rec]


class _Perguntas:
    """Troca as caixas de verdade por um registro do que seria perguntado."""

    def __init__(self, escolha=None):
        self.avisos: list[tuple] = []
        self.escolhas: list[tuple] = []
        self._resposta = escolha

    def avisar(self, _master, titulo, texto, destaque=""):
        self.avisos.append((titulo, texto, destaque))

    def escolher(self, _master, titulo, pergunta, opcoes, detalhe=""):
        self.escolhas.append((titulo, pergunta, [o[2] for o in opcoes]))
        return self._resposta


@pytest.fixture()
def tela(sistema, contas, raiz_tk, monkeypatch):
    """A janela de baixa, com as caixas substituídas."""
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))

    def montar(titulo_id, resposta=None):
        falsas = _Perguntas(resposta)
        monkeypatch.setattr(modulo, "perguntas", falsas)
        dialogo = modulo.DialogoBaixa(raiz_tk, titulo_id, lambda: None)
        dialogo.grab_release()
        return dialogo, falsas

    yield montar
    for filho in raiz_tk.winfo_children():
        filho.destroy()


# --------------------------------------------------------------------------- #
# Recebeu menos
# --------------------------------------------------------------------------- #
def test_receber_menos_nao_mexe_nos_proximos_meses(sistema, salario, tela):
    """O caso que rebaixou um ano inteiro de salário."""
    rec, titulos = salario
    dialogo, falsas = tela(titulos[0]["id"])
    try:
        dialogo._oferecer_novo_valor_fixo(2009.32)

        assert falsas.escolhas == [], "não pode nem perguntar"
        assert abertos(sistema, rec) == [5000.0] * len(abertos(sistema, rec))
    finally:
        dialogo.destroy()


def test_receber_menos_avisa_que_ficou_so_no_mes(sistema, salario, tela):
    rec, titulos = salario
    dialogo, falsas = tela(titulos[0]["id"])
    try:
        dialogo._oferecer_novo_valor_fixo(2009.32)

        titulo, texto, destaque = falsas.avisos[0]
        assert titulo == "Registrado só neste mês"
        assert "2.990,68 a menos" in destaque
        assert "5.000,00" in texto
        assert "Salários e Rendas" in texto
    finally:
        dialogo.destroy()


def test_pagar_menos_tambem_fica_so_no_mes(sistema, contas, raiz_tk, monkeypatch):
    """Vale para conta a pagar igual: pagar menos não é a conta nova."""
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    rec = sistema.salvar_recorrencia(None, "PAGAR", "Internet", "", 139.9, 10,
                                     contas["despesa"], None, sistema.mes_atual())
    sistema.gerar_titulos_recorrentes()
    titulo = sorted((t for t in sistema.listar_titulos(tipo="PAGAR")
                     if t["recorrencia_id"] == rec),
                    key=lambda t: t["competencia"])[0]
    falsas = _Perguntas()
    monkeypatch.setattr(modulo, "perguntas", falsas)
    dialogo = modulo.DialogoBaixa(raiz_tk, titulo["id"], lambda: None)
    dialogo.grab_release()
    try:
        dialogo._oferecer_novo_valor_fixo(100.0)

        assert falsas.escolhas == []
        assert "Corrigir" in falsas.avisos[0][1]
    finally:
        dialogo.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


# --------------------------------------------------------------------------- #
# Recebeu mais
# --------------------------------------------------------------------------- #
def test_receber_mais_pergunta_com_a_opcao_segura_primeiro(sistema, salario, tela):
    rec, titulos = salario
    dialogo, falsas = tela(titulos[0]["id"], resposta="mes")
    try:
        dialogo._oferecer_novo_valor_fixo(6000.0)

        assert falsas.escolhas, "aumento merece a pergunta"
        _titulo, _pergunta, valores = falsas.escolhas[0]
        assert valores[0] == "mes", "a opção que não estraga nada vem primeiro"
        assert abertos(sistema, rec) == [5000.0] * len(abertos(sistema, rec))
    finally:
        dialogo.destroy()


def test_escolher_para_sempre_reajusta(sistema, salario, tela):
    rec, titulos = salario
    dialogo, falsas = tela(titulos[0]["id"], resposta="sempre")
    try:
        dialogo._oferecer_novo_valor_fixo(6000.0)

        assert abertos(sistema, rec) == [6000.0] * len(abertos(sistema, rec))
        assert falsas.avisos[-1][0] == "Valor atualizado"
    finally:
        dialogo.destroy()


def test_desistir_da_pergunta_nao_muda_nada(sistema, salario, tela):
    rec, titulos = salario
    dialogo, falsas = tela(titulos[0]["id"], resposta=None)
    try:
        dialogo._oferecer_novo_valor_fixo(6000.0)

        assert abertos(sistema, rec) == [5000.0] * len(abertos(sistema, rec))
    finally:
        dialogo.destroy()


def test_valor_igual_nao_pergunta_nada(sistema, salario, tela):
    _rec, titulos = salario
    dialogo, falsas = tela(titulos[0]["id"])
    try:
        dialogo._oferecer_novo_valor_fixo(5000.0)

        assert falsas.escolhas == [] and falsas.avisos == []
    finally:
        dialogo.destroy()


def test_conta_avulsa_nao_pergunta_nada(sistema, contas, raiz_tk, monkeypatch):
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    titulo = sistema.salvar_titulo(None, "PAGAR", "Avulsa", "", 100.0,
                                   sistema.hoje_iso(), contas["despesa"], None)
    falsas = _Perguntas()
    monkeypatch.setattr(modulo, "perguntas", falsas)
    dialogo = modulo.DialogoBaixa(raiz_tk, titulo, lambda: None)
    dialogo.grab_release()
    try:
        dialogo._oferecer_novo_valor_fixo(80.0)

        assert falsas.escolhas == [] and falsas.avisos == []
    finally:
        dialogo.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


# --------------------------------------------------------------------------- #
# As caixas da ferramenta
# --------------------------------------------------------------------------- #
@pytest.fixture()
def caixas(sistema, raiz_tk, monkeypatch):
    modulo = importlib.reload(importlib.import_module("app.ui.perguntas"))
    # Sem esperar o usuário: a janela é montada e devolvida na hora.
    monkeypatch.setattr(modulo._Caixa, "apresentar", lambda self, foco=None: None)
    yield modulo
    for filho in raiz_tk.winfo_children():
        filho.destroy()


def test_a_escolha_nasce_na_opcao_segura(caixas, raiz_tk):
    """Enter distraído não pode mudar o ano inteiro."""
    caixa = caixas.CaixaDeEscolha(raiz_tk, "T", "Pergunta?",
                                  [("Só neste mês", "", "mes"),
                                   ("Para sempre", "", "sempre")])
    try:
        assert caixa.var.get() == "mes"
        caixa._confirmar()
        assert caixa.resposta == "mes"
    finally:
        if caixa.winfo_exists():
            caixa.destroy()


def test_fechar_a_escolha_sem_confirmar_devolve_nada(caixas, raiz_tk):
    caixa = caixas.CaixaDeEscolha(raiz_tk, "T", "Pergunta?",
                                  [("A", "", "a"), ("B", "", "b")])
    caixa.destroy()

    assert caixa.resposta is None


def test_o_aviso_mostra_destaque_e_texto(caixas, raiz_tk):
    caixa = caixas.CaixaDeAviso(raiz_tk, "T", "o texto", destaque="o destaque")
    try:
        textos = [f.cget("text") for f in caixa.corpo.winfo_children()
                  if hasattr(f, "cget") and "text" in f.keys()]
        assert "o destaque" in textos and "o texto" in textos
    finally:
        caixa.destroy()
