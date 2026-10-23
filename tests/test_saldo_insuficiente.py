"""Trabalhar dentro do saldo: ninguém tira de uma conta mais do que há nela.

A trava vive no núcleo, em salvar_lancamento, para valer em todo caminho que
mexe em dinheiro: gasto manual, baixa de conta, pagamento de dívida, quitação,
transferência e compra no cartão.
"""
from __future__ import annotations

import pytest


def gastar(sistema, contas, valor, conta=None):
    return sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Compra",
        [sistema.Partida(contas["despesa"], "D", valor),
         sistema.Partida(conta or contas["banco"], "C", valor)])


# --- o caminho comum -------------------------------------------------------- #
def test_gasto_dentro_do_saldo_passa(sistema, contas):
    gastar(sistema, contas, 999.0)
    assert sistema.saldo_conta(contas["banco"]) == 1.0


def test_gasto_acima_do_saldo_e_recusado(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        gastar(sistema, contas, 1000.01)

    assert "Banco Teste tem" in str(erro.value)
    assert sistema.saldo_conta(contas["banco"]) == 1000.0     # nada foi gravado


def test_zerar_a_conta_e_permitido(sistema, contas):
    gastar(sistema, contas, 1000.0)
    assert sistema.saldo_conta(contas["banco"]) == 0.0


def test_a_mensagem_diz_quanto_falta(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        gastar(sistema, contas, 1500.0)
    texto = str(erro.value)
    assert "1.000,00" in texto and "1.500,00" in texto and "500,00" in texto


# --- todos os caminhos que tiram dinheiro ----------------------------------- #
def test_baixa_de_conta_a_pagar_respeita_o_saldo(sistema, contas):
    titulo = sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 1200.0,
                                   sistema.hoje_iso(), contas["despesa"], None)
    with pytest.raises(sistema.RegraNegocioError):
        sistema.baixar_titulo(titulo, sistema.hoje_iso(), 1200.0, contas["banco"])

    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"


def test_pagamento_de_divida_respeita_o_saldo(sistema, contas):
    divida = sistema.criar_divida("Financiamento", "Banco X", 5000.0, "2026-01-10")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.pagar_divida(divida, 1200.0, contas["banco"], sistema.hoje_iso())

    assert sistema.saldo_conta(divida) == 5000.0


def test_quitacao_respeita_o_saldo(sistema, contas):
    divida = sistema.criar_divida("Financiamento", "Banco X", 5000.0, "2026-01-10")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso())

    assert sistema.listar_dividas_quitadas() == []


def test_transferencia_respeita_o_saldo(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.salvar_lancamento(
            None, sistema.hoje_iso(), "Transferência",
            [sistema.Partida(contas["outra"], "D", 2000.0),
             sistema.Partida(contas["banco"], "C", 2000.0)])

    assert sistema.saldo_conta(contas["outra"]) == 100.0


def test_debito_automatico_nao_estoura_a_conta(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Aluguel", "", 3000.0, "2026-03-15",
                                   contas["despesa"], None,
                                   conta_pagamento_id=contas["banco"],
                                   pagamento_automatico=True)

    resultado = sistema.pagar_automaticos("2026-03-20")

    assert resultado["pagos"] == []
    assert [p["id"] for p in resultado["pendentes"]] == [titulo]
    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"


# --- o que não pode ser barrado --------------------------------------------- #
def test_compra_no_cartao_nao_depende_de_saldo(sistema, contas):
    """Cartão de crédito é dívida: ela cresce, não consome saldo."""
    sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Compra no cartão",
        [sistema.Partida(contas["despesa"], "D", 9000.0),
         sistema.Partida(contas["cartao"], "C", 9000.0)])

    assert sistema.saldo_conta(contas["cartao"]) == 9000.0


def test_saldo_inicial_nao_e_barrado(sistema, contas):
    """Informar quanto já existia numa conta não pode depender de saldo."""
    nova = sistema.criar_carteira("Nubank", "Conta corrente", "Nu", 0.0, "2026-01-01")
    sistema.ajustar_saldo(nova, 250.0, sistema.hoje_iso())
    assert sistema.saldo_conta(nova) == 250.0


def test_extrato_importado_nao_e_barrado(sistema, contas):
    """O extrato conta o que já aconteceu — inclusive um saldo que ficou negativo."""
    sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Tarifa do banco",
        [sistema.Partida(contas["despesa"], "D", 1500.0),
         sistema.Partida(contas["banco"], "C", 1500.0)],
        documento="IMPORTADO")

    assert sistema.saldo_conta(contas["banco"]) == -500.0


def test_da_para_desligar_a_trava(sistema, contas):
    sistema.db.set_config("bloquear_saldo_negativo", "0")
    gastar(sistema, contas, 1500.0)
    assert sistema.saldo_conta(contas["banco"]) == -500.0


# --- detalhes de data e de correção ----------------------------------------- #
def test_saldo_e_conferido_na_data_do_lancamento(sistema, contas):
    """Gasto de ontem olha o saldo de ontem, não o de hoje."""
    sistema.salvar_lancamento(
        None, "2026-02-01", "Salário",
        [sistema.Partida(contas["banco"], "D", 5000.0),
         sistema.Partida(contas["receita"], "C", 5000.0)])

    with pytest.raises(sistema.RegraNegocioError):
        sistema.salvar_lancamento(
            None, "2026-01-15", "Compra antes do salário",
            [sistema.Partida(contas["despesa"], "D", 3000.0),
             sistema.Partida(contas["banco"], "C", 3000.0)])


def test_corrigir_um_lancamento_nao_conta_ele_duas_vezes(sistema, contas):
    """Ao editar, o próprio valor antigo sai da conta antes da conferência."""
    lancamento = gastar(sistema, contas, 900.0)

    sistema.salvar_lancamento(
        lancamento, sistema.hoje_iso(), "Compra",
        [sistema.Partida(contas["despesa"], "D", 950.0),
         sistema.Partida(contas["banco"], "C", 950.0)])

    assert sistema.saldo_conta(contas["banco"]) == 50.0


def test_quitar_com_desconto_registra_o_que_foi_pago(sistema, contas):
    divida = sistema.criar_divida("Mensalidade", "Escola", 885.0, "2026-01-10")

    resultado = sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"],
                                      sistema.hoje_iso(), valor_pago=500.0, aceitar_desconto=True)

    assert resultado["pago"] == 500.0
    assert resultado["desconto"] == 385.0
    assert sistema.saldo_conta(divida) == 0.0
    assert sistema.saldo_conta(contas["banco"]) == 500.0
    historico = sistema.listar_dividas_quitadas()[0]
    assert "desconto" in historico["observacao"].lower()


def test_nao_da_para_pagar_mais_do_que_a_divida_na_quitacao(sistema, contas):
    divida = sistema.criar_divida("Mensalidade", "Escola", 300.0, "2026-01-10")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                              valor_pago=500.0, aceitar_desconto=True)
