"""Tela de Salários: fontes de renda, histórico e troca de emprego."""
from __future__ import annotations

import pytest


@pytest.fixture()
def emprego(sistema, contas):
    """Salário em andamento, com um mês já recebido a mais do que o previsto."""
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "RECEBER", "CEBUDV", "Empresa antiga", 1200.0, f"{mes}-01",
        contas["receita"], conta_pagamento_id=contas["banco"])
    titulo = next(t for t in sistema.listar_titulos(tipo="RECEBER", status="ABERTO")
                  if t["recorrencia_id"] == recorrencia)
    sistema.baixar_titulo(titulo["id"], f"{mes}-10", 1500.0, contas["banco"])
    return recorrencia


def test_lista_so_as_fontes_de_renda(sistema, contas, emprego):
    sistema.criar_conta_fixa("PAGAR", "Internet", "", 119.9,
                             f"{sistema.mes_atual()}-15", contas["despesa"])

    fontes = sistema.listar_rendas_fixas()
    assert [f["descricao"] for f in fontes] == ["CEBUDV"]


def test_mostra_quanto_ja_entrou_de_cada_fonte(sistema, emprego):
    fonte = sistema.listar_rendas_fixas()[0]
    assert fonte["recebido"] == 1500.0      # o que caiu, não o previsto
    assert fonte["vezes"] == 1
    assert fonte["a_receber"] > 0           # os meses à frente
    assert fonte["encerrada"] is False


def test_historico_guarda_previsto_e_recebido(sistema, emprego):
    historico = sistema.historico_da_renda(emprego)
    recebidos = [h for h in historico if h["status"] == "QUITADO"]

    assert len(recebidos) == 1
    assert recebidos[0]["valor"] == 1200.0          # previsto
    assert recebidos[0]["recebido"] == 1500.0       # entrou
    assert recebidos[0]["diferenca"] == 300.0       # a mais


def test_fonte_encerrada_continua_na_lista_com_a_historia(sistema, emprego):
    sistema.encerrar_recorrencia(emprego, ultimo_mes=sistema.mes_atual())

    fontes = {f["descricao"]: f for f in sistema.listar_rendas_fixas()}
    assert fontes["CEBUDV"]["encerrada"] is True
    assert fontes["CEBUDV"]["recebido"] == 1500.0
    assert len(sistema.historico_da_renda(emprego)) >= 1


def test_so_as_que_ainda_entram(sistema, emprego):
    sistema.encerrar_recorrencia(emprego, ultimo_mes=sistema.mes_atual())
    assert sistema.listar_rendas_fixas(incluir_encerradas=False) == []


def test_emprego_novo_convive_com_o_antigo(sistema, contas, emprego):
    mes = sistema.mes_atual()
    sistema.encerrar_recorrencia(emprego, ultimo_mes=mes)
    sistema.criar_conta_fixa("RECEBER", "Salário Empresa Nova", "Nova Empresa", 3200.0,
                             f"{mes}-05", contas["receita"],
                             conta_pagamento_id=contas["banco"])

    fontes = sistema.listar_rendas_fixas()
    # As que ainda entram vêm primeiro; a encerrada continua logo atrás.
    assert [f["descricao"] for f in fontes] == ["Salário Empresa Nova", "CEBUDV"]
    assert fontes[0]["encerrada"] is False
    assert fontes[1]["encerrada"] is True


def test_de_onde_veio_o_dinheiro_no_periodo(sistema, contas, emprego):
    mes = sistema.mes_atual()
    avulso = sistema.salvar_titulo(None, "RECEBER", "Freelance", "Cliente", 800.0,
                                   f"{mes}-12", contas["receita"], None)
    sistema.baixar_titulo(avulso, f"{mes}-12", 800.0, contas["banco"])

    fontes = sistema.total_recebido_por_fonte(sistema.primeiro_dia_mes(),
                                              sistema.ultimo_dia_mes())
    por_nome = {f["fonte"]: f["total"] for f in fontes}
    assert por_nome["CEBUDV"] == 1500.0
    assert por_nome["Freelance"] == 800.0
    assert fontes[0]["fonte"] == "CEBUDV"       # ordenado pelo maior


def test_periodo_sem_recebimento_vem_vazio(sistema, emprego):
    assert sistema.total_recebido_por_fonte("2020-01-01", "2020-12-31") == []
