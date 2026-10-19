"""Trocar de emprego: editar a renda fixa e encerrar a antiga.

Regras cobertas aqui: o que já foi recebido não muda, o que vem pela frente
passa a valer com os dados novos, e encerrar só limpa os meses seguintes.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def salario(sistema, contas):
    """Salário já em andamento, como uma renda fixa comum."""
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "RECEBER", "CEBUDV", "Empresa antiga", 1200.0, f"{mes}-01",
        contas["receita"], conta_pagamento_id=contas["banco"])
    return recorrencia


def titulos(sistema, recorrencia):
    return sorted((t for t in sistema.listar_titulos(tipo="RECEBER")
                   if t["recorrencia_id"] == recorrencia),
                  key=lambda t: t["competencia"])


def test_renda_fixa_nasce_com_meses_a_frente(sistema, salario):
    meses = titulos(sistema, salario)
    assert len(meses) > 1
    assert all(t["valor"] == 1200.0 for t in meses)


def test_editar_vale_do_mes_escolhido_em_diante(sistema, contas, salario):
    mes = sistema.mes_atual()
    atingidos = sistema.aplicar_reajuste(salario, mes, 3200.0, "Salário Empresa Nova",
                                         "Nova Empresa", contas["receita"])

    meses = titulos(sistema, salario)
    assert atingidos == len(meses)
    assert all(t["valor"] == 3200.0 for t in meses)
    assert all(t["descricao"] == "Salário Empresa Nova" for t in meses)


def test_mes_ja_recebido_nao_muda(sistema, contas, salario):
    mes = sistema.mes_atual()
    primeiro = titulos(sistema, salario)[0]
    sistema.baixar_titulo(primeiro["id"], primeiro["vencimento"], 1200.0, contas["banco"])

    sistema.aplicar_reajuste(salario, mes, 3200.0, "Salário Empresa Nova")

    pago = sistema.obter_titulo(primeiro["id"])
    assert pago["valor"] == 1200.0
    assert pago["descricao"] == "CEBUDV"          # histórico intacto
    assert pago["status"] == "QUITADO"


def test_encerrar_no_ultimo_mes_que_entrou(sistema, salario):
    mes = sistema.mes_atual()
    antes = len(titulos(sistema, salario))

    removidos = sistema.encerrar_recorrencia(salario, ultimo_mes=mes)

    restantes = titulos(sistema, salario)
    assert [t["competencia"] for t in restantes] == [mes]
    assert removidos == antes - 1
    regra = sistema.db.query_one("SELECT ativo, fim FROM recorrencia WHERE id = ?", (salario,))
    assert regra["ativo"] == 0
    assert regra["fim"] == mes


def test_encerrada_nao_gera_novos_meses(sistema, salario):
    sistema.encerrar_recorrencia(salario, ultimo_mes=sistema.mes_atual())
    sistema.gerar_titulos_recorrentes()

    assert len(titulos(sistema, salario)) == 1


def test_salario_novo_convive_com_o_antigo(sistema, contas, salario):
    """O emprego novo é outra renda fixa; o antigo fica no histórico."""
    sistema.encerrar_recorrencia(salario, ultimo_mes=sistema.mes_atual())
    mes = sistema.mes_atual()
    novo, _ = sistema.criar_conta_fixa("RECEBER", "Salário Empresa Nova", "Nova Empresa",
                                       3200.0, f"{mes}-05", contas["receita"],
                                       conta_pagamento_id=contas["banco"])

    rendas = {r["descricao"]: r for r in sistema.listar_recorrencias()}
    assert rendas["CEBUDV"]["ativo"] == 0
    assert rendas["Salário Empresa Nova"]["ativo"] == 1
    assert len(titulos(sistema, novo)) > 1


def test_pausar_e_reativar_a_renda(sistema, salario):
    sistema.pausar_recorrencia(salario)
    assert sistema.db.query_one("SELECT ativo FROM recorrencia WHERE id = ?",
                                (salario,))["ativo"] == 0

    sistema.reativar_recorrencia(salario)
    assert sistema.db.query_one("SELECT ativo FROM recorrencia WHERE id = ?",
                                (salario,))["ativo"] == 1
