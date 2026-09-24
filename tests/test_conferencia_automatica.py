"""Conferência automática: o sistema confere sozinho, sem clique."""
from __future__ import annotations

import pytest


def gasto(sistema, contas, valor=50.0, data="2026-03-10"):
    return sistema.salvar_lancamento(
        None, data, "Mercado",
        [sistema.Partida(contas["despesa"], "D", valor),
         sistema.Partida(contas["banco"], "C", valor)])


def conferido(sistema, lancamento_id) -> int:
    return sistema.db.query_one("SELECT conferido FROM lancamento WHERE id = ?",
                                (lancamento_id,))["conferido"]


def test_registro_novo_ja_nasce_conferido(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    assert conferido(sistema, gasto(sistema, contas)) == 1


def test_registro_com_data_futura_espera_o_dia(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    futuro = gasto(sistema, contas, data="2026-04-10")
    assert conferido(sistema, futuro) == 0

    # Quando o dia chega, a rotina confere sem ninguém clicar.
    assert sistema.conferir_automatico("2026-04-10") == 1
    assert conferido(sistema, futuro) == 1


def test_pagamento_de_conta_tambem_ja_vem_conferido(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Luz", "", 80.0, "2026-03-15",
                                   contas["despesa"], None, conta_pagamento_id=contas["banco"])
    lancamento = sistema.baixar_titulo(titulo, "2026-03-15", 80.0, contas["banco"])
    assert conferido(sistema, lancamento) == 1


def test_o_que_ficou_para_tras_e_conferido_ao_abrir(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    antigo = gasto(sistema, contas, data="2026-03-01")
    sistema.marcar_conferido(antigo, False)         # como se viesse de antes

    assert sistema.conferir_automatico("2026-03-20") == 1
    assert conferido(sistema, antigo) == 1
    assert sistema.resumo_conferencia("2026-01-01", "2026-12-31")["pendentes"] == 0


def test_desligado_nada_e_conferido_sozinho(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    sistema.db.set_config("conferencia_automatica", "0")

    novo = gasto(sistema, contas)
    assert conferido(sistema, novo) == 0
    assert sistema.conferir_automatico("2026-03-20") == 0
    assert conferido(sistema, novo) == 0


def test_desmarcar_na_mao_continua_valendo(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    lancamento = gasto(sistema, contas)
    sistema.marcar_conferido(lancamento, False)
    assert conferido(sistema, lancamento) == 0

    # A rotina automática confere de novo na próxima abertura — é o combinado
    # de quem deixa a opção ligada.
    sistema.conferir_automatico("2026-03-20")
    assert conferido(sistema, lancamento) == 1


def test_rodar_duas_vezes_nao_faz_nada_a_mais(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    gasto(sistema, contas)
    sistema.conferir_automatico("2026-03-20")
    assert sistema.conferir_automatico("2026-03-20") == 0


def test_ligada_por_padrao(sistema):
    assert sistema.conferencia_automatica() is True
