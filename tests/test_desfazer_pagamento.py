"""Marcar como pago e voltar para não pago, sem deixar sobra nem dinheiro fora do lugar."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


def nova_conta(sistema, contas, valor=200.0, descricao="Internet"):
    return sistema.salvar_titulo(None, "PAGAR", descricao, "", valor, sistema.hoje_iso(),
                                 contas["despesa"], None, multa_pct=0.0, juros_mes_pct=0.0)


def test_pagar_e_desfazer_volta_tudo_como_estava(sistema, contas):
    titulo = nova_conta(sistema, contas)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 200.0, contas["banco"])
    assert sistema.saldo_conta(contas["banco"]) == 800.0

    sistema.estornar_titulo(titulo)

    t = sistema.obter_titulo(titulo)
    assert t["status"] == "ABERTO" and t["liquidado_em"] is None and t["lancamento_id"] is None
    assert sistema.saldo_conta(contas["banco"]) == 1000.0
    assert abs(sistema.balanco(sistema.hoje_iso())["diferenca"]) < 0.01


def test_pode_pagar_de_novo_depois_de_desfazer(sistema, contas):
    titulo = nova_conta(sistema, contas)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 200.0, contas["banco"])
    sistema.estornar_titulo(titulo)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 200.0, contas["outra"])
    assert sistema.saldo_conta(contas["banco"]) == 1000.0
    assert sistema.saldo_conta(contas["outra"]) == -100.0


def test_desfazer_conta_nao_paga_avisa(sistema, contas):
    titulo = nova_conta(sistema, contas)
    with pytest.raises(sistema.RegraNegocioError):
        sistema.estornar_titulo(titulo)


def test_desfazer_pagamento_parcial_remove_a_sobra(sistema, contas):
    titulo = nova_conta(sistema, contas)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 50.0, contas["banco"], saldo_em_aberto=True)
    assert len(sistema.listar_titulos(status="ABERTO")) == 1          # a sobra de 150

    resultado = sistema.estornar_titulo(titulo)

    assert resultado["sobras_removidas"] == 1
    abertas = sistema.listar_titulos(status="ABERTO")
    assert [t["id"] for t in abertas] == [titulo]                     # só a original, inteira
    assert abertas[0]["valor"] == 200.0
    assert sistema.saldo_conta(contas["banco"]) == 1000.0


def test_sobra_ja_paga_bloqueia_o_desfazer(sistema, contas):
    titulo = nova_conta(sistema, contas)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 50.0, contas["banco"], saldo_em_aberto=True)
    sobra = sistema.listar_titulos(status="ABERTO")[0]
    sistema.baixar_titulo(sobra["id"], sistema.hoje_iso(), 150.0, contas["banco"])

    with pytest.raises(sistema.RegraNegocioError):
        sistema.estornar_titulo(titulo)

    sistema.estornar_titulo(sobra["id"])          # desfazendo na ordem certa, funciona
    sistema.estornar_titulo(titulo)
    assert sistema.saldo_conta(contas["banco"]) == 1000.0


def test_sobra_de_outra_conta_nao_e_apagada(sistema, contas):
    """A conta nº 1 não pode achar a sobra da conta nº 12 (ou 10, 11...)."""
    ids = [nova_conta(sistema, contas, 100.0, f"Conta {n}") for n in range(12)]
    primeira, decima_segunda = ids[0], ids[11]
    assert str(decima_segunda).startswith(str(primeira))
    sistema.baixar_titulo(primeira, sistema.hoje_iso(), 100.0, contas["banco"])
    sistema.baixar_titulo(decima_segunda, sistema.hoje_iso(), 40.0, contas["banco"],
                          saldo_em_aberto=True)

    resultado = sistema.estornar_titulo(primeira)

    assert resultado["sobras_removidas"] == 0
    assert any("faltou" in t["descricao"] for t in sistema.listar_titulos(status="ABERTO"))


def test_desfazer_pagamento_feito_com_cartao_atualiza_a_fatura(sistema, contas):
    dia = (date.today() + timedelta(days=5)).day
    dia = 5 if dia > 28 else dia
    sistema.configurar_cartao(contas["cartao"], dia_fechamento=dia, dia_vencimento=dia)
    titulo = nova_conta(sistema, contas, 110.0, "Assinatura")
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 110.0, contas["cartao"])
    atual = [f for f in sistema.listar_faturas(contas["cartao"]) if f["status_titulo"] == "ABERTO"]
    assert atual and atual[0]["total"] == 110.0

    sistema.estornar_titulo(titulo)

    assert sistema.saldo_conta(contas["cartao"]) == 0.0
    assert [f for f in sistema.listar_faturas(contas["cartao"])
            if f["status_titulo"] == "ABERTO"] == []
