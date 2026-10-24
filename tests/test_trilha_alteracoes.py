"""Toda mudança em um lançamento deixa rastro do estado anterior.

Antes disto, "esse valor mudou depois que eu lancei?" não tinha resposta: o
registro era alterado por cima e a exclusão não deixava nada atrás.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def lancamento(sistema, contas):
    return sistema.salvar_lancamento(
        None, "2026-03-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 80.0),
         sistema.Partida(contas["banco"], "C", 80.0)])


def eventos(sistema, lancamento_id: int) -> list[dict]:
    return sistema.listar_alteracoes(lancamento_id=lancamento_id)


def test_criar_registra_a_criacao(sistema, lancamento):
    trilha = eventos(sistema, lancamento)

    assert len(trilha) == 1
    assert trilha[0]["acao"] == "CRIADO"
    assert trilha[0]["historico"] == "Mercado"
    assert trilha[0]["valor"] == 80.0
    assert trilha[0]["ainda_existe"] is True


def test_corrigir_guarda_o_valor_de_antes(sistema, contas, lancamento):
    sistema.salvar_lancamento(
        lancamento, "2026-03-10", "Mercado (corrigido)",
        [sistema.Partida(contas["despesa"], "D", 95.0),
         sistema.Partida(contas["banco"], "C", 95.0)])
    trilha = eventos(sistema, lancamento)

    assert [e["acao"] for e in trilha] == ["ALTERADO", "CRIADO"]
    # A linha de ALTERADO fotografa o estado ANTERIOR à correção.
    assert trilha[0]["valor"] == 80.0
    assert trilha[0]["historico"] == "Mercado"


def test_apagar_guarda_o_que_havia_ali(sistema, lancamento):
    sistema.excluir_lancamento(lancamento)
    trilha = eventos(sistema, lancamento)

    assert trilha[0]["acao"] == "EXCLUIDO"
    assert trilha[0]["valor"] == 80.0
    assert trilha[0]["ainda_existe"] is False


def test_a_trilha_sobrevive_ao_registro(sistema, lancamento):
    """A linha da trilha não é apagada em cascata com o lançamento."""
    sistema.excluir_lancamento(lancamento)

    assert sistema.listar_alteracoes(lancamento_id=lancamento)
    assert sistema.obter_conta(1) is not None   # o banco segue íntegro


def test_as_contas_usadas_ficam_na_trilha(sistema, lancamento):
    sistema.excluir_lancamento(lancamento)
    partidas = eventos(sistema, lancamento)[0]["partidas"]

    assert "D " in partidas and "C " in partidas
    assert "80,00" in partidas


def test_carimbo_de_alteracao_no_registro(sistema, contas, lancamento):
    antes = sistema.listar_movimentos("2026-03-01", "2026-03-31")[0]
    assert antes["alterado_em"] == ""

    sistema.salvar_lancamento(
        lancamento, "2026-03-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 81.0),
         sistema.Partida(contas["banco"], "C", 81.0)])
    depois = sistema.listar_movimentos("2026-03-01", "2026-03-31")[0]

    assert depois["alterado_em"] != ""


def test_filtro_por_acao(sistema, contas, lancamento):
    sistema.salvar_lancamento(
        lancamento, "2026-03-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 90.0),
         sistema.Partida(contas["banco"], "C", 90.0)])

    assert len(sistema.listar_alteracoes(acao="ALTERADO")) == 1
    assert sistema.listar_alteracoes(acao="EXCLUIDO") == []


def test_filtro_por_texto(sistema, lancamento):
    assert sistema.listar_alteracoes(texto="Mercado")
    assert sistema.listar_alteracoes(texto="Farmácia") == []


def test_resumo_conta_correcoes_e_exclusoes(sistema, contas, lancamento):
    sistema.salvar_lancamento(
        lancamento, "2026-03-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 90.0),
         sistema.Partida(contas["banco"], "C", 90.0)])
    sistema.excluir_lancamento(lancamento)
    resumo = sistema.resumo_alteracoes()

    assert resumo["alterados"] == 1
    assert resumo["excluidos"] == 1
    # O resumo é do banco inteiro; deste lançamento são três eventos.
    assert len(eventos(sistema, lancamento)) == 3
    assert resumo["total"] >= 3
    assert resumo["ultima"]


def test_desfazer_pagamento_tambem_deixa_rastro(sistema, contas):
    titulo_id = sistema.salvar_titulo(
        None, "PAGAR", "Internet", "Provedor", 120.0, "2026-03-05",
        contas["despesa"], None)
    sistema.baixar_titulo(titulo_id, "2026-03-05", 120.0, contas["banco"])
    sistema.estornar_titulo(titulo_id)

    apagados = sistema.listar_alteracoes(acao="EXCLUIDO")
    assert apagados
    assert apagados[0]["motivo"] == "pagamento desfeito"


def test_registro_de_origem_fica_no_motivo(sistema, lancamento):
    assert eventos(sistema, lancamento)[0]["motivo"] == "origem manual"
