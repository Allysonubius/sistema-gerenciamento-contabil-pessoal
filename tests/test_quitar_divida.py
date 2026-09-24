"""Dívida: alterar o valor é uma coisa, quitar é outra."""
from __future__ import annotations

import pytest


@pytest.fixture()
def divida(sistema, contas):
    return sistema.criar_divida("Financiamento", "Banco X", 1000.0, "2026-01-10")


def saldo(sistema, conta_id):
    return sistema.saldo_conta(conta_id)


# --- alterar o valor: não é pagamento -------------------------------------- #
def test_alterar_valor_nao_tira_dinheiro_da_conta(sistema, contas, divida):
    sistema.alterar_valor_divida(divida, 1200.0, "2026-02-01")

    assert saldo(sistema, divida) == 1200.0
    assert saldo(sistema, contas["banco"]) == 1000.0     # intacto
    assert sistema.listar_dividas_quitadas() == []


def test_alterar_valor_para_menos_tambem_vale(sistema, divida):
    sistema.alterar_valor_divida(divida, 700.0, "2026-02-01")
    assert saldo(sistema, divida) == 700.0


def test_nao_da_para_zerar_alterando_o_valor(sistema, divida):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.alterar_valor_divida(divida, 0.0, "2026-02-01")
    assert "Quitar dívida" in str(erro.value)
    assert saldo(sistema, divida) == 1000.0


def test_valor_negativo_e_recusado(sistema, divida):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.alterar_valor_divida(divida, -50.0)


# --- quitar: encerra e entra no histórico ---------------------------------- #
def test_quitar_pagando_zera_a_divida_e_desconta(sistema, contas, divida):
    resultado = sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], "2026-03-01")

    assert resultado["valor"] == 1000.0
    assert saldo(sistema, divida) == 0.0
    assert saldo(sistema, contas["banco"]) == 0.0        # 1000 - 1000
    assert divida not in [d["conta_id"] for d in sistema.listar_dividas()]


def test_quitacao_entra_no_historico(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], "2026-03-01",
                          observacao="Último boleto")

    historico = sistema.listar_dividas_quitadas()
    assert len(historico) == 1
    item = historico[0]
    assert item["nome"] == "Financiamento"
    assert item["credor"] == "Banco X"
    assert item["valor"] == 1000.0
    assert item["data"] == "2026-03-01"
    assert item["forma_texto"] == "Paguei o que faltava"
    assert item["conta_dinheiro_nome"] == "Banco Teste"
    assert item["observacao"] == "Último boleto"


def test_divida_perdoada_nao_tira_dinheiro(sistema, contas, divida):
    sistema.quitar_divida(divida, "PERDAO", data_iso="2026-03-01")

    assert saldo(sistema, divida) == 0.0
    assert saldo(sistema, contas["banco"]) == 1000.0
    assert sistema.listar_dividas_quitadas()[0]["forma_texto"] == "Perdoada / baixada sem pagar"


def test_quitar_pagando_exige_a_conta_do_dinheiro(sistema, divida):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.quitar_divida(divida, "PAGAMENTO", None, "2026-03-01")
    assert saldo(sistema, divida) == 1000.0


def test_divida_ja_zerada_nao_quita_de_novo(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], "2026-03-01")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], "2026-03-02")


def test_quitar_depois_de_alterar_o_valor_usa_o_valor_novo(sistema, contas, divida):
    sistema.alterar_valor_divida(divida, 600.0, "2026-02-01")
    resultado = sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], "2026-03-01")

    assert resultado["valor"] == 600.0
    assert saldo(sistema, contas["banco"]) == 400.0


def test_forma_invalida_e_recusada(sistema, contas, divida):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.quitar_divida(divida, "SEI_LA", contas["banco"])


# --- desfazer --------------------------------------------------------------- #
def test_reabrir_devolve_a_divida_e_o_dinheiro(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], "2026-03-01")
    quitacao = sistema.listar_dividas_quitadas()[0]

    sistema.desfazer_quitacao(quitacao["id"])

    assert saldo(sistema, divida) == 1000.0
    assert saldo(sistema, contas["banco"]) == 1000.0
    assert sistema.listar_dividas_quitadas() == []
    assert divida in [d["conta_id"] for d in sistema.listar_dividas()]


# --- pagar uma parte -------------------------------------------------------- #
def test_pagar_parte_abate_o_saldo(sistema, contas, divida):
    sistema.pagar_divida(divida, 300.0, contas["banco"], "2026-02-05")

    assert saldo(sistema, divida) == 700.0
    assert saldo(sistema, contas["banco"]) == 700.0
    assert divida in [d["conta_id"] for d in sistema.listar_dividas()]   # continua aberta


def test_varias_partes_vao_abatendo(sistema, contas, divida):
    for valor in (200.0, 150.0, 50.0):
        sistema.pagar_divida(divida, valor, contas["banco"], "2026-02-05")
    assert saldo(sistema, divida) == 600.0


def test_parte_com_juros_abate_so_o_principal(sistema, contas, divida):
    sistema.pagar_divida(divida, 300.0, contas["banco"], "2026-02-05", juros=50.0)

    assert saldo(sistema, divida) == 750.0                # abateu 250
    assert saldo(sistema, contas["banco"]) == 700.0       # saíram os 300


def test_nao_da_para_pagar_mais_do_que_deve(sistema, contas, divida):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.pagar_divida(divida, 1500.0, contas["banco"], "2026-02-05")
    assert "Quitar dívida" in str(erro.value)
    assert saldo(sistema, divida) == 1000.0


def test_extrato_separa_pagamento_de_correcao(sistema, contas, divida):
    sistema.pagar_divida(divida, 300.0, contas["banco"], "2026-02-05")
    sistema.alterar_valor_divida(divida, 500.0, "2026-02-10")

    extrato = sistema.extrato_da_divida(divida)
    tipos = [m["tipo"] for m in extrato]
    assert tipos == ["Correção do valor", "Pagamento", "Dívida registrada"]
    assert extrato[0]["saldo_depois"] == 500.0            # o saldo bate com a dívida
    assert extrato[1]["conta_dinheiro"] == "Banco Teste"
    assert extrato[2]["aumentou"] is True


# --- "já pago": só o que saiu de conta ------------------------------------- #
def item(sistema, conta_id):
    return next(d for d in sistema.listar_dividas(incluir_quitadas=True)
                if d["conta_id"] == conta_id)


def test_divida_recem_criada_nao_tem_nada_pago(sistema, divida):
    assert item(sistema, divida)["pago"] == 0.0


def test_alterar_valor_nao_conta_como_pago(sistema, divida):
    sistema.alterar_valor_divida(divida, 400.0, "2026-02-01")   # caiu 600
    assert item(sistema, divida)["pago"] == 0.0


def test_pagamento_de_verdade_conta(sistema, contas, divida):
    sistema.pagar_divida(divida, 300.0, contas["banco"], "2026-02-05")
    assert item(sistema, divida)["pago"] == 300.0


def test_divida_perdoada_nao_conta_como_paga(sistema, contas, divida):
    sistema.pagar_divida(divida, 200.0, contas["banco"], "2026-02-05")
    sistema.quitar_divida(divida, "PERDAO", data_iso="2026-03-01")
    assert item(sistema, divida)["pago"] == 200.0    # só o que saiu mesmo


def test_provisao_de_encargos_nao_aparece_como_divida(sistema, contas, fixar_hoje):
    """A conta interna 2.1.02 guarda multa e juros provisionados — não é dívida."""
    fixar_hoje("2026-04-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Conta atrasada", "", 100.0, "2026-03-10",
                                   contas["despesa"], None, multa_pct=2.0, juros_mes_pct=1.0)
    sistema.lancar_encargos_do_mes("2026-04-20")
    assert sistema.obter_titulo(titulo)["encargos_lancados"] > 0   # provisão existe

    nomes = [d["nome"] for d in sistema.listar_dividas(incluir_quitadas=True)]
    assert "Contas a Pagar" not in nomes


def test_procurar_no_historico(sistema, contas):
    primeira = sistema.criar_divida("Carro", "Banco X", 500.0, "2026-01-10")
    segunda = sistema.criar_divida("Notebook", "Loja Y", 300.0, "2026-01-10")
    sistema.quitar_divida(primeira, "PAGAMENTO", contas["banco"], "2026-03-01")
    sistema.quitar_divida(segunda, "PAGAMENTO", contas["banco"], "2026-03-02")

    assert [d["nome"] for d in sistema.listar_dividas_quitadas()] == ["Notebook", "Carro"]
    assert [d["nome"] for d in sistema.listar_dividas_quitadas("carro")] == ["Carro"]
    assert [d["nome"] for d in sistema.listar_dividas_quitadas("loja")] == ["Notebook"]
