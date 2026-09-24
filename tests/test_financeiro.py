"""Contas a pagar e receber, contas fixas e encargos por atraso."""
from __future__ import annotations

import pytest


def criar_titulo(sistema, contas, valor=200.0, vencimento="2026-03-10", tipo="PAGAR", **extra):
    return sistema.salvar_titulo(None, tipo, "Internet", "", valor, vencimento,
                                 contas["despesa"], None, **extra)


def test_titulo_pago_vira_lancamento_e_baixa_o_saldo(sistema, contas):
    titulo = criar_titulo(sistema, contas)
    sistema.baixar_titulo(titulo, "2026-03-10", 200.0, contas["banco"])

    assert sistema.saldo_conta(contas["banco"]) == 800.0
    assert sistema.obter_titulo(titulo)["status"] == "QUITADO"
    assert abs(sistema.balanco("2026-03-31")["diferenca"]) < 0.01


def test_estorno_devolve_o_titulo_para_aberto(sistema, contas):
    titulo = criar_titulo(sistema, contas)
    sistema.baixar_titulo(titulo, "2026-03-10", 200.0, contas["banco"])
    sistema.estornar_titulo(titulo)

    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"
    assert sistema.saldo_conta(contas["banco"]) == 1000.0


def test_titulo_quitado_nao_pode_ser_baixado_de_novo(sistema, contas):
    titulo = criar_titulo(sistema, contas)
    sistema.baixar_titulo(titulo, "2026-03-10", 200.0, contas["banco"])
    with pytest.raises(sistema.RegraNegocioError):
        sistema.baixar_titulo(titulo, "2026-03-11", 200.0, contas["banco"])


def test_conta_de_desconto_e_gravada_e_propagada(sistema, contas):
    titulo = criar_titulo(sistema, contas, conta_pagamento_id=contas["banco"])
    linha = next(t for t in sistema.listar_titulos() if t["id"] == titulo)
    assert linha["conta_pagamento_nome"] == "Banco Teste"


def test_conta_fixa_gera_os_proximos_meses(sistema, contas):
    recorrencia = sistema.salvar_recorrencia(
        None, "PAGAR", "Streaming", "", 39.9, 5, contas["despesa"], None,
        sistema.mes_atual(), conta_pagamento_id=contas["banco"])
    criados = sistema.gerar_titulos_recorrentes()

    assert criados >= 12
    titulos = [t for t in sistema.listar_titulos() if t["recorrencia_id"] == recorrencia]
    assert all(t["conta_pagamento_nome"] == "Banco Teste" for t in titulos)
    assert all(int(t["vencimento"][8:10]) == 5 for t in titulos)
    # Nunca gera para trás.
    assert min(t["competencia"] for t in titulos) >= sistema.mes_atual()


def test_gerar_recorrentes_duas_vezes_nao_duplica(sistema, contas):
    sistema.salvar_recorrencia(None, "PAGAR", "Aluguel", "", 900.0, 10,
                              contas["despesa"], None, "2026-01")
    primeiro = sistema.gerar_titulos_recorrentes()
    segundo = sistema.gerar_titulos_recorrentes()
    assert primeiro > 0
    assert segundo == 0, "a segunda execução não pode criar meses passados"


def test_conta_fixa_antiga_nao_ressuscita_meses_passados(sistema, contas):
    """Uma fixa que começou há um ano só deve gerar deste mês em diante."""
    sistema.salvar_recorrencia(None, "PAGAR", "Academia", "", 120.0, 8,
                              contas["despesa"], None, "2020-01")
    sistema.gerar_titulos_recorrentes()
    sistema.gerar_titulos_recorrentes()

    competencias = [t["competencia"] for t in sistema.listar_titulos()]
    assert min(competencias) >= sistema.mes_atual()


def test_reajuste_vale_do_mes_escolhido_em_diante(sistema, contas):
    recorrencia = sistema.salvar_recorrencia(None, "PAGAR", "Aluguel", "", 900.0, 10,
                                             contas["despesa"], None, sistema.mes_atual())
    sistema.gerar_titulos_recorrentes()
    competencias = sorted(t["competencia"] for t in sistema.listar_titulos()
                          if t["recorrencia_id"] == recorrencia)
    antes, base = competencias[2], competencias[3]
    sistema.aplicar_reajuste(recorrencia, base, 1000.0)

    titulos = {t["competencia"]: t for t in sistema.listar_titulos()
               if t["recorrencia_id"] == recorrencia}
    assert titulos[antes]["valor"] == 900.0
    assert titulos[base]["valor"] == 1000.0


def test_atraso_cobra_multa_e_juros_proporcionais(sistema, contas):
    titulo = criar_titulo(sistema, contas, valor=1000.0, vencimento="2026-01-01",
                          multa_pct=2.0, juros_mes_pct=3.0)
    encargos = sistema.encargos_do_titulo(sistema.obter_titulo(titulo), ate="2026-02-01")

    assert encargos["multa"] == pytest.approx(20.0)          # 2% de 1000
    assert encargos["juros"] == pytest.approx(31.0, abs=1.5)  # ~3% ao mês por 31 dias
    assert encargos["valor_atualizado"] > 1000.0


def test_titulo_em_dia_nao_tem_encargos(sistema, contas):
    titulo = criar_titulo(sistema, contas, vencimento="2026-12-31",
                          multa_pct=2.0, juros_mes_pct=3.0)
    encargos = sistema.encargos_do_titulo(sistema.obter_titulo(titulo), ate="2026-03-01")
    assert encargos["total"] == 0.0


def test_cancelar_titulo_o_tira_da_lista_de_abertos(sistema, contas):
    titulo = criar_titulo(sistema, contas)
    sistema.cancelar_titulo(titulo)
    abertos = [t["id"] for t in sistema.listar_titulos(status="ABERTO")]
    assert titulo not in abertos
