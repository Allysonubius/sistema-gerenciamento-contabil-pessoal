"""Corrigir quanto se deve não é ter ganho nem gasto nada.

Esses acertos iam para "Despesas Diversas" e "Reembolsos e Restituições" e se
misturavam ao que foi de fato gasto e recebido: uma dívida acertada em 3.863,71
entrava no mês como se fosse dinheiro que entrou.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def divida(sistema, contas):
    return sistema.criar_divida("Empréstimo", "Banco X", 5000.0, "2026-02-01")


def contas_do_lancamento(sistema, lancamento_id: int) -> set[str]:
    return {p["codigo"] for p in sistema.partidas_do_lancamento(lancamento_id)}


def test_aumentar_a_divida_nao_vira_despesa(sistema, divida):
    lancamento = sistema.alterar_valor_divida(divida, 6000.0, "2026-03-10")

    assert "3.1" in contas_do_lancamento(sistema, lancamento)
    assert "5.9.01" not in contas_do_lancamento(sistema, lancamento)
    assert sistema.dre("2026-03-01", "2026-03-31")["total_despesas"] == 0.0


def test_diminuir_a_divida_nao_vira_receita(sistema, divida):
    lancamento = sistema.alterar_valor_divida(divida, 1000.0, "2026-03-10")

    assert "3.1" in contas_do_lancamento(sistema, lancamento)
    assert "4.3.01" not in contas_do_lancamento(sistema, lancamento)
    assert sistema.dre("2026-03-01", "2026-03-31")["total_receitas"] == 0.0


def test_o_saldo_da_divida_fica_correto(sistema, divida):
    sistema.alterar_valor_divida(divida, 1136.29, "2026-03-10")

    assert sistema.saldo_conta(divida) == 1136.29


def test_o_acerto_nao_mexe_no_caixa(sistema, contas, divida):
    antes = sistema.total_disponivel()["tem"]
    sistema.alterar_valor_divida(divida, 1000.0, "2026-03-10")
    fluxo = sistema.fluxo_de_caixa("2026-03-01", "2026-03-31")

    assert sistema.total_disponivel()["tem"] == antes
    assert fluxo["entrou"] == 0.0
    assert fluxo["saiu"] == 0.0


def test_o_balanco_continua_fechando(sistema, divida):
    sistema.alterar_valor_divida(divida, 1000.0, "2026-03-10")

    assert abs(sistema.balanco("2026-03-31")["diferenca"]) < 0.01


def test_acertar_conta_de_banco_tambem_vai_para_o_patrimonio(sistema, contas):
    """Acertar um saldo nunca é ganho nem gasto, seja dívida ou conta."""
    lancamento = sistema.ajustar_saldo(contas["banco"], 1050.0, "2026-03-10")

    assert "3.1" in contas_do_lancamento(sistema, lancamento)
    assert "4.3.01" not in contas_do_lancamento(sistema, lancamento)
    assert sistema.dre("2026-03-01", "2026-03-31")["total_receitas"] == 0.0
    assert sistema.saldo_conta(contas["banco"]) == 1050.0


def test_acerto_de_conta_aparece_separado_no_fluxo(sistema, contas):
    """O dinheiro mudou na conta, mas não foi recebimento: o painel diz isso."""
    sistema.ajustar_saldo(contas["banco"], 1050.0, "2026-03-10")
    fluxo = sistema.fluxo_de_caixa("2026-03-01", "2026-03-31")

    assert fluxo["entradas"] == {"ajustes": 50.0}
    assert "em acertos" in sistema.detalhe_do_fluxo(fluxo["entradas"])


def test_migracao_corrige_os_acertos_de_conta_antigos(sistema, contas):
    from app import db

    antigo = sistema.salvar_lancamento(
        None, "2026-03-05", "Acerto de saldo — Banco Teste",
        [sistema.Partida(contas["banco"], "D", 40.0),
         sistema.Partida(sistema._conta_por_codigo("4.3.01"), "C", 40.0)])
    with db.transaction() as conexao:
        corrigidos = db._reclassificar_acertos_de_saldo(conexao)

    assert corrigidos == 1
    assert "3.1" in contas_do_lancamento(sistema, antigo)
    assert sistema.dre("2026-03-01", "2026-03-31")["total_receitas"] == 0.0


def test_a_migracao_de_contas_nao_toca_num_gasto_comum(sistema, contas):
    """'Despesas Diversas pagas pelo banco' tem a mesma forma: o texto separa."""
    from app import db

    gasto = sistema.salvar_lancamento(
        None, "2026-03-05", "Taxa do banco",
        [sistema.Partida(sistema._conta_por_codigo("5.9.01"), "D", 40.0),
         sistema.Partida(contas["banco"], "C", 40.0)])
    with db.transaction() as conexao:
        corrigidos = db._reclassificar_acertos_de_saldo(conexao)

    assert corrigidos == 0
    assert "5.9.01" in contas_do_lancamento(sistema, gasto)


def test_pagar_a_divida_continua_sendo_saida_de_caixa(sistema, contas, divida):
    """Pagar é outra coisa: o dinheiro sai de verdade."""
    sistema.pagar_divida(divida, 200.0, contas["banco"], "2026-03-12")
    fluxo = sistema.fluxo_de_caixa("2026-03-01", "2026-03-31")

    assert fluxo["saiu"] == 200.0
    assert fluxo["saidas"]["dividas"] == 200.0
    assert sistema.saldo_conta(divida) == 4800.0


def test_migracao_corrige_os_acertos_antigos(sistema, contas, divida):
    """Os lançamentos já gravados do jeito antigo são reclassificados."""
    from app import db

    # Reproduz o formato antigo: a dívida sobe contra Despesas Diversas.
    antigo = sistema.salvar_lancamento(
        None, "2026-03-05", "Acerto do saldo devedor",
        [sistema.Partida(sistema._conta_por_codigo("5.9.01"), "D", 563.66),
         sistema.Partida(divida, "C", 563.66)])
    assert "5.9.01" in contas_do_lancamento(sistema, antigo)

    with db.transaction() as conexao:
        corrigidos = db._reclassificar_acertos_de_divida(conexao)

    assert corrigidos == 1
    assert "3.1" in contas_do_lancamento(sistema, antigo)
    assert "5.9.01" not in contas_do_lancamento(sistema, antigo)
    assert abs(sistema.balanco("2026-03-31")["diferenca"]) < 0.01


def test_a_correcao_fica_registrada_na_trilha(sistema, divida):
    from app import db

    antigo = sistema.salvar_lancamento(
        None, "2026-03-05", "Acerto do saldo devedor",
        [sistema.Partida(sistema._conta_por_codigo("5.9.01"), "D", 100.0),
         sistema.Partida(divida, "C", 100.0)])
    with db.transaction() as conexao:
        db._reclassificar_acertos_de_divida(conexao)

    trilha = sistema.listar_alteracoes(lancamento_id=antigo)
    assert trilha[0]["acao"] == "ALTERADO"
    assert "patrimônio" in trilha[0]["motivo"]
    assert "5.9.01" in trilha[0]["partidas"]        # guarda como era antes


def test_a_migracao_nao_toca_num_gasto_comum(sistema, contas, divida):
    """Um gasto de verdade pago com a dívida tem categoria própria, não 5.9.01."""
    from app import db

    gasto = sistema.salvar_lancamento(
        None, "2026-03-05", "Compra fiada",
        [sistema.Partida(contas["despesa"], "D", 80.0),
         sistema.Partida(divida, "C", 80.0)])
    with db.transaction() as conexao:
        corrigidos = db._reclassificar_acertos_de_divida(conexao)

    assert corrigidos == 0
    assert "5.2.01" in contas_do_lancamento(sistema, gasto)
