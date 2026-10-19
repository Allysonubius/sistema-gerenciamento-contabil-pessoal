"""Conta fixa pausada não pode continuar contando nos meses seguintes."""
from __future__ import annotations

import pytest


@pytest.fixture()
def salario(sistema, contas):
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "RECEBER", "CEBUDV", "Empresa antiga", 1200.0, f"{mes}-01",
        contas["receita"], conta_pagamento_id=contas["banco"])
    return recorrencia


def meses(sistema, recorrencia) -> list[str]:
    return sorted(t["competencia"] for t in sistema.listar_titulos()
                  if t["recorrencia_id"] == recorrencia)


def test_pausar_tira_os_meses_seguintes(sistema, salario):
    atual = sistema.mes_atual()
    assert len(meses(sistema, salario)) > 1

    removidos = sistema.pausar_recorrencia(salario)

    assert removidos > 0
    assert meses(sistema, salario) == [atual]      # só o mês atual continua


def test_pausada_nao_entra_mais_no_total_a_receber(sistema, salario):
    seguinte = sistema._mes_seguinte(sistema.mes_atual())
    a_receber = [t for t in sistema.listar_titulos(tipo="RECEBER", status="ABERTO",
                                                   desde=f"{seguinte}-01", ate=f"{seguinte}-28")]
    assert a_receber, "o mês seguinte existia antes de pausar"

    sistema.pausar_recorrencia(salario)

    assert sistema.listar_titulos(tipo="RECEBER", status="ABERTO",
                                  desde=f"{seguinte}-01", ate=f"{seguinte}-28") == []


def test_mes_ja_recebido_nunca_some(sistema, contas, salario):
    atual = sistema.mes_atual()
    titulo = next(t for t in sistema.listar_titulos(tipo="RECEBER")
                  if t["competencia"] == atual)
    sistema.baixar_titulo(titulo["id"], f"{atual}-10", 1500.0, contas["banco"])

    sistema.pausar_recorrencia(salario)

    recebido = sistema.obter_titulo(titulo["id"])
    assert recebido["status"] == "QUITADO"
    assert recebido["valor_liquidado"] == 1500.0


def test_pausada_nao_gera_novos_meses(sistema, salario):
    sistema.pausar_recorrencia(salario)
    sistema.gerar_titulos_recorrentes()

    assert meses(sistema, salario) == [sistema.mes_atual()]


def test_voltar_a_ativar_traz_os_meses_de_novo(sistema, salario):
    sistema.pausar_recorrencia(salario)
    assert len(meses(sistema, salario)) == 1

    sistema.reativar_recorrencia(salario)

    assert len(meses(sistema, salario)) > 1


def test_limpeza_alcanca_o_que_ja_estava_na_lista(sistema, salario):
    """Quem pausou antes desta regra tinha meses futuros parados na lista."""
    sistema.db.execute("UPDATE recorrencia SET ativo = 0 WHERE id = ?", (salario,))
    assert len(meses(sistema, salario)) > 1        # continuam lá

    removidos = sistema.limpar_futuros_de_inativas()

    assert removidos > 0
    assert meses(sistema, salario) == [sistema.mes_atual()]


def test_limpeza_nao_mexe_nas_ativas(sistema, contas, salario):
    mes = sistema.mes_atual()
    ativa, _ = sistema.criar_conta_fixa("PAGAR", "Internet", "", 119.9, f"{mes}-15",
                                        contas["despesa"])
    antes = len(meses(sistema, ativa))

    sistema.pausar_recorrencia(salario)
    sistema.limpar_futuros_de_inativas()

    assert len(meses(sistema, ativa)) == antes
