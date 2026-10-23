"""Ao escolher a conta no registro, a janela mostra o saldo dela.

O objetivo é ver, antes de salvar, de qual conta o dinheiro sai e como ela fica.
"""
from __future__ import annotations

import importlib
import tkinter as tk

import pytest



@pytest.fixture()
def janela(sistema, contas, raiz_tk):
    """Diálogo de registro aberto sobre um banco de teste."""
    lancamentos = importlib.import_module("app.ui.lancamentos")
    importlib.reload(lancamentos)
    dialogo = lancamentos.DialogoMovimento(raiz_tk, None, lambda: None)
    dialogo.grab_release()
    yield dialogo, sistema, contas
    dialogo.destroy()
    for filho in raiz_tk.winfo_children():
        filho.destroy()


def texto_de(dialogo, seletor) -> str:
    for alvo, rotulo, _sinal in dialogo._saldos:
        if alvo is seletor:
            return rotulo.cget("text")
    raise AssertionError("seletor sem rótulo de saldo")


def test_sem_conta_escolhida_nao_mostra_nada(janela):
    dialogo, _sistema, _contas = janela
    assert texto_de(dialogo, dialogo.sel_gasto_conta) == ""


def test_mostra_o_saldo_de_hoje(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_gasto_conta.set_conta_id(contas["banco"])
    dialogo._atualizar_saldos()

    assert texto_de(dialogo, dialogo.sel_gasto_conta) == "tem 1.000,00"


def test_gasto_mostra_como_a_conta_fica(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_gasto_conta.set_conta_id(contas["banco"])
    dialogo.cp_valor.set_valor(250.0)
    dialogo._atualizar_saldos()

    assert texto_de(dialogo, dialogo.sel_gasto_conta) == "tem 1.000,00  →  fica 750,00"


def test_avisa_quando_a_conta_fica_negativa(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_gasto_conta.set_conta_id(contas["banco"])
    dialogo.cp_valor.set_valor(1500.0)
    dialogo._atualizar_saldos()

    texto = texto_de(dialogo, dialogo.sel_gasto_conta)
    assert "fica -500,00" in texto
    assert "fica negativa" in texto


def test_recebimento_soma_na_conta(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_rec_conta.set_conta_id(contas["banco"])
    dialogo.cp_valor.set_valor(300.0)
    dialogo._atualizar_saldos()

    assert texto_de(dialogo, dialogo.sel_rec_conta) == "tem 1.000,00  →  fica 1.300,00"


def test_cartao_de_credito_aumenta_a_divida(janela):
    dialogo, sistema, contas = janela
    sistema.salvar_lancamento(
        None, "2026-02-01", "Compra",
        [sistema.Partida(contas["despesa"], "D", 200.0),
         sistema.Partida(contas["cartao"], "C", 200.0)])
    dialogo.sel_gasto_conta.set_conta_id(contas["cartao"])
    dialogo.cp_valor.set_valor(100.0)
    dialogo._atualizar_saldos()

    # No cartão o saldo é dívida: gastar faz subir, não descer.
    assert texto_de(dialogo, dialogo.sel_gasto_conta) == "deve 200,00  →  fica 300,00"


def test_transferencia_mostra_os_dois_lados(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_tr_origem.set_conta_id(contas["banco"])
    dialogo.sel_tr_destino.set_conta_id(contas["outra"])
    dialogo.cp_valor.set_valor(100.0)
    dialogo._atualizar_saldos()

    assert texto_de(dialogo, dialogo.sel_tr_origem) == "tem 1.000,00  →  fica 900,00"
    assert texto_de(dialogo, dialogo.sel_tr_destino) == "tem 100,00  →  fica 200,00"


def test_saldo_inicial_so_mostra_o_de_hoje(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_saldo_conta.set_conta_id(contas["banco"])
    dialogo.cp_valor.set_valor(999.0)
    dialogo._atualizar_saldos()

    assert texto_de(dialogo, dialogo.sel_saldo_conta) == "tem 1.000,00"


def test_valor_invalido_nao_quebra_a_janela(janela):
    dialogo, sistema, contas = janela
    dialogo.sel_gasto_conta.set_conta_id(contas["banco"])
    dialogo.cp_valor.var.set("abc")
    dialogo._atualizar_saldos()

    assert texto_de(dialogo, dialogo.sel_gasto_conta) == "tem 1.000,00"
