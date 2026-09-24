"""Previsão por conta, orçamento e painel."""
from __future__ import annotations

import pytest


def test_previsao_desconta_de_cada_conta_o_que_sai_dela(sistema, contas):
    hoje = sistema.hoje_iso()
    fim = sistema.ultimo_dia_mes()
    sistema.salvar_titulo(None, "PAGAR", "Internet", "", 150.0, fim,
                          contas["despesa"], None, conta_pagamento_id=contas["banco"])
    sistema.salvar_titulo(None, "PAGAR", "Streaming", "", 40.0, fim,
                          contas["despesa"], None, conta_pagamento_id=contas["outra"])

    previsao = sistema.previsao_por_conta(fim)
    por_conta = {c["nome"]: c for c in previsao["contas"]}

    assert por_conta["Banco Teste"]["previsto"] == 850.0
    assert por_conta["Carteira"]["previsto"] == 60.0
    assert previsao["previsto"] == 910.0
    assert hoje <= previsao["ate"]


def test_titulo_sem_conta_definida_fica_separado(sistema, contas):
    sistema.salvar_titulo(None, "PAGAR", "Sem conta", "", 80.0, sistema.ultimo_dia_mes(),
                          contas["despesa"], None)
    previsao = sistema.previsao_por_conta()

    assert previsao["sem_conta_pagar"] == 80.0
    assert previsao["previsto"] == 1100.0     # nada foi descontado das contas


def test_o_que_sai_do_cartao_nao_reduz_o_dinheiro(sistema, contas):
    sistema.salvar_titulo(None, "PAGAR", "Assinatura", "", 90.0, sistema.ultimo_dia_mes(),
                          contas["despesa"], None, conta_pagamento_id=contas["cartao"])
    previsao = sistema.previsao_por_conta()
    assert previsao["previsto"] == 1100.0
    assert previsao["sem_conta_pagar"] == 0.0


def test_conta_que_fica_negativa_e_sinalizada(sistema, contas):
    sistema.salvar_titulo(None, "PAGAR", "Conta alta", "", 1500.0, sistema.ultimo_dia_mes(),
                          contas["despesa"], None, conta_pagamento_id=contas["banco"])
    previsao = sistema.previsao_por_conta()
    assert [c["nome"] for c in previsao["contas_negativas"]] == ["Banco Teste"]


def test_orcamento_compara_teto_com_gasto(sistema, contas):
    sistema.definir_orcamento(contas["despesa"], 500.0)
    sistema.salvar_lancamento(
        None, sistema.primeiro_dia_mes(), "Mercado",
        [sistema.Partida(contas["despesa"], "D", 200.0),
         sistema.Partida(contas["banco"], "C", 200.0)])

    linha = next(l for l in sistema.orcamento_do_mes() if l["conta_id"] == contas["despesa"])
    assert linha["teto"] == 500.0
    assert linha["gasto"] == 200.0
    assert linha["restante"] == 300.0
    assert linha["percentual"] == 40.0
    assert not linha["estourou"]


def test_orcamento_marca_estouro(sistema, contas):
    sistema.definir_orcamento(contas["despesa"], 100.0)
    sistema.salvar_lancamento(
        None, sistema.primeiro_dia_mes(), "Mercado",
        [sistema.Partida(contas["despesa"], "D", 180.0),
         sistema.Partida(contas["banco"], "C", 180.0)])

    resumo = sistema.resumo_orcamento()
    assert len(resumo["estouradas"]) == 1
    assert resumo["gasto"] == 180.0
    assert resumo["restante"] == -80.0


def test_teto_do_mes_vence_o_teto_padrao(sistema, contas):
    sistema.definir_orcamento(contas["despesa"], 300.0)                      # padrão
    sistema.definir_orcamento(contas["despesa"], 900.0, sistema.mes_atual())  # só deste mês

    valor, do_mes = sistema.teto_da_categoria(contas["despesa"], sistema.mes_atual())
    assert (valor, do_mes) == (900.0, True)
    outro_mes = sistema.teto_da_categoria(contas["despesa"], "2030-01")
    assert outro_mes == (300.0, False)


def test_painel_separa_dinheiro_investimento_e_divida(sistema, contas):
    sistema.criar_carteira("CDB", "Investimento", "Banco", 400.0, "2026-01-02",
                           conta_origem_id=contas["banco"])
    sistema.salvar_lancamento(
        None, "2026-02-01", "Compra no cartão",
        [sistema.Partida(contas["despesa"], "D", 250.0),
         sistema.Partida(contas["cartao"], "C", 250.0)])

    resumo = sistema.resumo_dashboard()
    assert resumo["investido"] == 400.0
    assert resumo["disponivel"] == 700.0        # 600 no banco + 100 na carteira
    assert resumo["divida_cartoes"] == 250.0
    grupos = {c["nome"]: c["grupo"] for c in resumo["contas"]}
    assert grupos["CDB"] == "investimento"
    assert grupos["Banco Teste"] == "disponivel"


def test_conta_fora_do_disponivel_vai_para_outros(sistema, contas):
    sistema.definir_conta_dinheiro(contas["outra"], False)
    totais = sistema.total_disponivel()
    assert totais["tem"] == 1000.0
    assert totais["outros"] == 100.0
