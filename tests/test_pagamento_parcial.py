"""Pagar menos do que se deve: o que faltou vira uma nova conta."""
from __future__ import annotations

import pytest


@pytest.fixture()
def titulo(sistema, contas):
    return sistema.salvar_titulo(None, "PAGAR", "Fatura", "", 500.0, "2026-03-10",
                                 contas["despesa"], None,
                                 conta_pagamento_id=contas["banco"])


def test_paga_metade_e_o_resto_vira_nova_conta(sistema, contas, titulo):
    sistema.baixar_titulo(titulo, "2026-03-10", 200.0, contas["banco"],
                          saldo_em_aberto=True, vencimento_do_saldo="2026-04-10")

    original = sistema.obter_titulo(titulo)
    assert original["status"] == "QUITADO"
    assert original["valor_liquidado"] == 200.0

    saldo = [t for t in sistema.listar_titulos(status="ABERTO") if t["id"] != titulo]
    assert len(saldo) == 1
    assert saldo[0]["valor"] == 300.0
    assert saldo[0]["vencimento"] == "2026-04-10"
    assert "faltou" in saldo[0]["descricao"]
    assert saldo[0]["conta_pagamento_nome"] == "Banco Teste"


def test_saiu_do_caixa_so_o_que_foi_pago(sistema, contas, titulo):
    sistema.baixar_titulo(titulo, "2026-03-10", 200.0, contas["banco"], saldo_em_aberto=True)
    assert sistema.saldo_conta(contas["banco"]) == 800.0
    assert abs(sistema.balanco("2026-03-31")["diferenca"]) < 0.01


def test_desconto_encerra_a_conta_sem_saldo(sistema, contas, titulo):
    sistema.baixar_titulo(titulo, "2026-03-10", 450.0, contas["banco"])
    assert sistema.obter_titulo(titulo)["status"] == "QUITADO"
    assert [t for t in sistema.listar_titulos(status="ABERTO") if t["id"] != titulo] == []


def test_saldo_herda_categoria_e_encargos(sistema, contas):
    titulo = sistema.salvar_titulo(None, "PAGAR", "Empréstimo", "Banco X", 1000.0,
                                   "2026-03-10", contas["despesa"], None,
                                   multa_pct=2.0, juros_mes_pct=1.0)
    sistema.baixar_titulo(titulo, "2026-03-10", 400.0, contas["banco"], saldo_em_aberto=True)

    saldo = next(t for t in sistema.listar_titulos(status="ABERTO"))
    assert saldo["conta_id"] == contas["despesa"]
    assert saldo["multa_pct"] == 2.0
    assert saldo["juros_mes_pct"] == 1.0
    assert saldo["pessoa"] == "Banco X"
    assert str(titulo) in saldo["observacao"]


def test_pagar_o_valor_cheio_marcando_parcial_e_recusado(sistema, contas, titulo):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.baixar_titulo(titulo, "2026-03-10", 500.0, contas["banco"],
                              saldo_em_aberto=True)


def test_conta_atrasada_considera_encargos_no_saldo(sistema, contas):
    titulo = sistema.salvar_titulo(None, "PAGAR", "Conta velha", "", 1000.0, "2026-01-01",
                                   contas["despesa"], None, multa_pct=10.0, juros_mes_pct=0.0)
    # Em 01/02 deve 1000 + 100 de multa: pagando 600, ficam 500 em aberto.
    sistema.baixar_titulo(titulo, "2026-02-01", 600.0, contas["banco"], saldo_em_aberto=True)

    saldo = next(t for t in sistema.listar_titulos(status="ABERTO"))
    assert saldo["valor"] == pytest.approx(500.0, abs=0.01)


def test_pode_pagar_o_saldo_depois(sistema, contas, titulo):
    sistema.baixar_titulo(titulo, "2026-03-10", 200.0, contas["banco"], saldo_em_aberto=True)
    saldo = next(t for t in sistema.listar_titulos(status="ABERTO"))
    sistema.baixar_titulo(saldo["id"], "2026-04-10", 300.0, contas["banco"])

    assert sistema.listar_titulos(status="ABERTO") == []
    assert sistema.saldo_conta(contas["banco"]) == 500.0
    assert abs(sistema.balanco("2026-04-30")["diferenca"]) < 0.01
