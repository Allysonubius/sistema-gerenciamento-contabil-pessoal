"""Cartão de crédito: fatura, rotativo e limite garantido."""
from __future__ import annotations

import pytest


@pytest.fixture()
def cartao(sistema, contas):
    sistema.configurar_cartao(contas["cartao"], dia_fechamento=25, dia_vencimento=5,
                              juros_rotativo=10.0)
    return contas["cartao"]


def comprar(sistema, contas, valor, data):
    return sistema.salvar_lancamento(
        None, data, "Compra no cartão",
        [sistema.Partida(contas["despesa"], "D", valor),
         sistema.Partida(contas["cartao"], "C", valor)])


def test_compra_no_cartao_vira_divida_e_nao_tira_do_banco(sistema, contas, cartao):
    comprar(sistema, contas, 300.0, "2026-02-10")
    assert sistema.saldo_conta(cartao) == 300.0
    assert sistema.saldo_conta(contas["banco"]) == 1000.0
    assert sistema.total_disponivel()["deve"] == 300.0


def test_fatura_fecha_e_gera_conta_a_pagar(sistema, contas, cartao, fixar_hoje):
    fixar_hoje("2026-02-10")
    comprar(sistema, contas, 300.0, "2026-02-10")
    # A fatura já nasce com a compra (fatura atual) e fecha no dia 25.
    assert sistema.listar_faturas(cartao)[0]["fechada"] == 0
    sistema.fechar_faturas("2026-02-26")

    fatura = sistema.listar_faturas(cartao)[0]
    assert fatura["fechada"] == 1
    assert fatura["total"] == 300.0
    assert fatura["vencimento"] == "2026-03-05"

    titulo = sistema.obter_titulo(fatura["titulo_id"])
    assert titulo["status"] == "ABERTO"
    assert titulo["valor"] == 300.0


def test_compra_depois_do_fechamento_vai_para_a_proxima(sistema, contas, cartao, fixar_hoje):
    fixar_hoje("2026-02-10")
    comprar(sistema, contas, 100.0, "2026-02-10")   # entra na fatura de fevereiro
    comprar(sistema, contas, 70.0, "2026-02-27")    # já é da próxima
    sistema.fechar_faturas("2026-02-28")

    faturas = {f["competencia"]: f for f in sistema.listar_faturas(cartao)}
    assert faturas["2026-02"]["total"] == 100.0
    assert faturas["2026-02"]["fechada"] == 1
    # A de março já existe como fatura atual, só com a compra dela.
    assert faturas["2026-03"]["total"] == 70.0
    assert faturas["2026-03"]["fechada"] == 0


def test_limite_garantido_acompanha_a_aplicacao(sistema, contas, cartao):
    aplicacao = sistema.criar_carteira("CDB Garantia", "Investimento", "Banco", 500.0,
                                       "2026-01-05", conta_origem_id=contas["banco"])
    sistema.definir_garantia_cartao(cartao, aplicacao)

    assert sistema.limite_do_cartao(cartao)["limite"] == 500.0
    sistema.registrar_rendimento(aplicacao, 25.0, "2026-02-01")
    assert sistema.limite_do_cartao(cartao)["limite"] == 525.0

    comprar(sistema, contas, 200.0, "2026-02-10")
    limite = sistema.limite_do_cartao(cartao)
    assert limite["usado"] == 200.0
    assert limite["disponivel"] == 325.0


def test_investimento_em_garantia_nao_conta_como_dinheiro(sistema, contas):
    sistema.criar_carteira("CDB Garantia", "Investimento", "Banco", 500.0,
                           "2026-01-05", conta_origem_id=contas["banco"])
    totais = sistema.total_disponivel()
    assert totais["investido"] == 500.0
    assert totais["tem"] == 600.0            # 1000 - 500 do banco + 100 da carteira


def test_garantia_so_aceita_cartao_de_credito(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.definir_garantia_cartao(contas["banco"], contas["outra"])


def test_validade_invalida_e_recusada(sistema, contas, cartao):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.definir_dados_do_cartao(cartao, validade="13/2030")
    sistema.definir_dados_do_cartao(cartao, validade="07/2030")
    assert not sistema.cartao_vencido("07/2030", "2026-09-08")
    assert sistema.cartao_vencido("01/2020", "2026-09-08")


def test_pre_pago_desconta_na_hora(sistema, contas):
    pre = sistema.criar_carteira("Vale", "Cartão pré-pago (você carrega antes de usar)",
                                 "Alelo", 200.0, "2026-01-10")
    sistema.salvar_lancamento(
        None, "2026-02-02", "Almoço",
        [sistema.Partida(contas["despesa"], "D", 45.0),
         sistema.Partida(pre, "C", 45.0)])

    assert sistema.saldo_conta(pre) == 155.0
    cartoes = {c["nome"]: c for c in sistema.listar_cartoes()}
    assert cartoes["Vale"]["credito"] is False
    assert cartoes["Vale"]["saldo"] == 155.0


def test_fatura_nasce_sabendo_de_qual_conta_sai(sistema, contas, cartao):
    sistema.definir_conta_da_fatura(cartao, contas["banco"])
    comprar(sistema, contas, 300.0, "2026-02-10")
    sistema.fechar_faturas("2026-02-26")

    fatura = sistema.listar_faturas(cartao)[0]
    titulo = sistema.obter_titulo(fatura["titulo_id"])
    assert titulo["conta_pagamento_id"] == contas["banco"]


def test_definir_conta_da_fatura_alcanca_as_faturas_em_aberto(sistema, contas, cartao):
    comprar(sistema, contas, 300.0, "2026-02-10")
    sistema.fechar_faturas("2026-02-26")
    fatura = sistema.listar_faturas(cartao)[0]
    assert sistema.obter_titulo(fatura["titulo_id"])["conta_pagamento_id"] is None

    sistema.definir_conta_da_fatura(cartao, contas["banco"])
    assert sistema.obter_titulo(fatura["titulo_id"])["conta_pagamento_id"] == contas["banco"]


def test_fatura_do_cartao_entra_na_previsao_da_conta(sistema, contas, cartao):
    sistema.definir_conta_da_fatura(cartao, contas["banco"])
    comprar(sistema, contas, 300.0, "2026-02-10")
    sistema.fechar_faturas("2026-02-26")
    fatura = sistema.listar_faturas(cartao)[0]

    previsao = sistema.previsao_por_conta(fatura["vencimento"])
    banco = next(c for c in previsao["contas"] if c["id"] == contas["banco"])
    assert banco["a_pagar"] >= 300.0
    assert previsao["sem_conta_pagar"] == 0.0


def test_fatura_nao_pode_ser_paga_por_outro_cartao(sistema, contas, cartao):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.definir_conta_da_fatura(cartao, cartao)


def test_emprestimo_nao_aparece_como_cartao(sistema, contas):
    sistema.criar_divida("Empréstimo Banco", "Banco X", 5000.0, "2026-01-10")
    nomes = [c["nome"] for c in sistema.listar_cartoes()]
    assert "Empréstimo Banco" not in nomes
