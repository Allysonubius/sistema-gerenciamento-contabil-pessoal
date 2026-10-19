"""Conta a pagar em parcelas: início, quantidade e divisão do total."""
from __future__ import annotations

import pytest


def parcelas_de(sistema, recorrencia) -> list[tuple]:
    return sorted((t["competencia"], t["descricao"], t["valor"])
                  for t in sistema.listar_titulos() if t["recorrencia_id"] == recorrencia)


def test_parcelas_sao_numeradas(sistema, contas):
    mes = sistema.mes_atual()
    recorrencia, criados = sistema.criar_conta_fixa(
        "PAGAR", "Notebook", "Loja", 300.0, f"{mes}-10", contas["despesa"], meses=5)

    lancadas = parcelas_de(sistema, recorrencia)
    assert criados == 5
    assert [p[1] for p in lancadas] == [f"Notebook ({i}/5)" for i in range(1, 6)]


def test_comeca_no_mes_do_vencimento_informado(sistema, contas):
    mes = sistema.mes_atual()
    seguinte = sistema._mes_seguinte(mes)
    recorrencia, _ = sistema.criar_conta_fixa(
        "PAGAR", "Curso", "Escola", 200.0, f"{seguinte}-15", contas["despesa"], meses=3)

    lancadas = parcelas_de(sistema, recorrencia)
    assert lancadas[0][0] == seguinte
    assert len(lancadas) == 3


def test_uma_parcela_so_nao_numera(sistema, contas):
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "PAGAR", "Taxa", "", 90.0, f"{mes}-10", contas["despesa"], meses=1)

    assert parcelas_de(sistema, recorrencia)[0][1] == "Taxa"


def test_conta_fixa_sem_prazo_nao_numera(sistema, contas):
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "PAGAR", "Internet", "", 119.9, f"{mes}-10", contas["despesa"], meses=0)

    assert all(p[1] == "Internet" for p in parcelas_de(sistema, recorrencia))


def test_parcelamento_para_no_fim(sistema, contas):
    """Parcelado não é conta fixa: depois da última, não nasce mais nenhuma."""
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "PAGAR", "Notebook", "", 300.0, f"{mes}-10", contas["despesa"], meses=4)

    sistema.gerar_titulos_recorrentes()

    assert len(parcelas_de(sistema, recorrencia)) == 4


def test_total_dividido_fecha_a_soma(sistema, contas):
    """1.000 em 3x: 333,33 cada e o centavo que sobra vai na primeira."""
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "PAGAR", "Conserto", "", 333.33, f"{mes}-10", contas["despesa"], meses=3)
    sistema.ajustar_valor_do_mes(recorrencia, mes, 333.34)

    lancadas = parcelas_de(sistema, recorrencia)
    assert lancadas[0][2] == 333.34
    assert round(sum(p[2] for p in lancadas), 2) == 1000.0


def test_parcelas_entram_nas_contas_a_pagar_do_mes(sistema, contas):
    mes = sistema.mes_atual()
    sistema.criar_conta_fixa("PAGAR", "Notebook", "", 300.0, f"{mes}-10",
                             contas["despesa"], meses=6)

    deste_mes = sistema.listar_titulos(tipo="PAGAR", status="ABERTO",
                                       desde=f"{mes}-01", ate=f"{mes}-28")
    assert [t["descricao"] for t in deste_mes] == ["Notebook (1/6)"]


def test_pagar_uma_parcela_nao_mexe_nas_outras(sistema, contas):
    mes = sistema.mes_atual()
    recorrencia, _ = sistema.criar_conta_fixa(
        "PAGAR", "Notebook", "", 300.0, f"{mes}-10", contas["despesa"], meses=3,
        conta_pagamento_id=contas["banco"])
    primeira = next(t for t in sistema.listar_titulos() if t["competencia"] == mes)

    sistema.baixar_titulo(primeira["id"], f"{mes}-10", 300.0, contas["banco"])

    lancadas = parcelas_de(sistema, recorrencia)
    assert len(lancadas) == 3
    assert sistema.obter_titulo(primeira["id"])["status"] == "QUITADO"
    assert all(p[2] == 300.0 for p in lancadas)
