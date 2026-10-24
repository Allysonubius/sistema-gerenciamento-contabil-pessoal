"""Mês fechado é mês que já virou relatório: ninguém mexe mais nele.

Sem isto, um lançamento de 2024 podia ser alterado hoje e o balanço daquele
período deixava de bater com o que já tinha sido exportado.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def gasto(sistema, contas):
    """Um gasto em janeiro de 2026, para ter o que travar."""
    def criar(data_iso: str = "2026-01-10", valor: float = 100.0) -> int:
        return sistema.salvar_lancamento(
            None, data_iso, "Compra de janeiro",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])
    return criar


def test_nada_fechado_por_padrao(sistema):
    assert sistema.competencia_fechada() == ""
    assert sistema.periodo_fechado("2024-01-01") is False


def test_fecha_e_informa_quantos_registros_travaram(sistema, contas, gasto):
    """Conta o que ficou travado — e deixa de fora o mês seguinte."""
    antes = len(sistema.listar_lancamentos(ate="2026-01-31"))
    gasto("2026-01-10")
    gasto("2026-02-10")
    resumo = sistema.fechar_competencia("2026-01")

    assert sistema.competencia_fechada() == "2026-01"
    assert resumo["lancamentos_travados"] == antes + 1


def test_mes_fechado_nao_aceita_registro_novo(sistema, gasto):
    sistema.fechar_competencia("2026-01")

    with pytest.raises(sistema.RegraNegocioError) as erro:
        gasto("2026-01-20")
    assert "fechado" in str(erro.value)


def test_mes_fechado_nao_aceita_correcao(sistema, gasto):
    lancamento_id = gasto("2026-01-10")
    sistema.fechar_competencia("2026-01")

    with pytest.raises(sistema.RegraNegocioError):
        sistema.salvar_lancamento(
            lancamento_id, "2026-01-10", "Outro valor",
            [sistema.Partida(sistema._conta_por_codigo("5.2.01"), "D", 50.0),
             sistema.Partida(sistema._conta_por_codigo("1.1.01"), "C", 50.0)])


def test_mes_fechado_nao_aceita_exclusao(sistema, gasto):
    lancamento_id = gasto("2026-01-10")
    sistema.fechar_competencia("2026-01")

    with pytest.raises(sistema.RegraNegocioError):
        sistema.excluir_lancamento(lancamento_id)


def test_nao_da_para_tirar_um_registro_de_dentro_do_mes_fechado(sistema, contas, gasto):
    """Mudar a data para fora do mês fechado é mexer naquele mês."""
    lancamento_id = gasto("2026-01-10")
    sistema.fechar_competencia("2026-01")

    with pytest.raises(sistema.RegraNegocioError):
        sistema.salvar_lancamento(
            lancamento_id, "2026-03-10", "Compra de janeiro",
            [sistema.Partida(contas["despesa"], "D", 100.0),
             sistema.Partida(contas["banco"], "C", 100.0)])


def test_nem_para_jogar_um_registro_novo_para_dentro(sistema, gasto):
    sistema.fechar_competencia("2026-01")

    with pytest.raises(sistema.RegraNegocioError):
        gasto("2026-01-31")


def test_mes_aberto_segue_funcionando(sistema, gasto):
    sistema.fechar_competencia("2026-01")
    lancamento_id = gasto("2026-02-10")

    assert lancamento_id > 0
    sistema.excluir_lancamento(lancamento_id)


def test_mes_corrente_nao_pode_ser_fechado(sistema):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.fechar_competencia(sistema.mes_atual())
    assert "ainda não terminou" in str(erro.value)


def test_competencia_invalida_e_recusada(sistema):
    for texto in ("", "2026", "2026-13", "janeiro", "26-01"):
        with pytest.raises(sistema.RegraNegocioError):
            sistema.fechar_competencia(texto)


def test_nao_fecha_duas_vezes_o_mesmo_mes(sistema):
    sistema.fechar_competencia("2026-01")
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.fechar_competencia("2026-01")
    assert "já está fechada" in str(erro.value)


def test_reabrir_devolve_o_mes(sistema, gasto):
    lancamento_id = gasto("2026-01-10")
    sistema.fechar_competencia("2026-01")
    sistema.reabrir_competencia("")

    assert sistema.competencia_fechada() == ""
    sistema.excluir_lancamento(lancamento_id)      # volta a aceitar


def test_reabrir_so_anda_para_tras(sistema):
    sistema.fechar_competencia("2026-01")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.reabrir_competencia("2026-02")


def test_reabrir_sem_nada_fechado_avisa(sistema):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.reabrir_competencia("")


def test_resumo_aponta_o_proximo_mes_a_fechar(sistema, gasto):
    gasto("2026-01-10")
    resumo = sistema.resumo_fechamento()
    assert resumo["proximo"] == "2026-01"

    sistema.fechar_competencia("2026-01")
    assert sistema.resumo_fechamento()["proximo"] == "2026-02"


def test_pagar_conta_dentro_do_mes_fechado_e_barrado(sistema, contas):
    titulo_id = sistema.salvar_titulo(
        None, "PAGAR", "Luz de janeiro", "Companhia", 200.0, "2026-01-15",
        contas["despesa"], None)
    sistema.fechar_competencia("2026-01")

    with pytest.raises(sistema.RegraNegocioError):
        sistema.baixar_titulo(titulo_id, "2026-01-20", 200.0, contas["banco"])
