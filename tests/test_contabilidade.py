"""O que nunca pode quebrar: partidas dobradas, saldos e balanço."""
from __future__ import annotations

import pytest


def test_banco_novo_nasce_com_o_plano_de_contas(sistema):
    contas = sistema.listar_contas(apenas_ativas=True, apenas_analiticas=False)
    assert len(contas) > 30
    codigos = {c["codigo"] for c in contas}
    for esperado in ("1", "2", "3", "4", "5", "1.1.02", "5.2.01"):
        assert esperado in codigos


def test_lancamento_precisa_estar_equilibrado(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.salvar_lancamento(
            None, "2026-02-01", "Desequilibrado",
            [sistema.Partida(contas["despesa"], "D", 100.0),
             sistema.Partida(contas["banco"], "C", 90.0)])


def test_saldo_inicial_e_gasto_alteram_o_saldo(sistema, contas):
    assert sistema.saldo_conta(contas["banco"]) == 1000.0
    sistema.salvar_lancamento(
        None, "2026-02-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 250.0),
         sistema.Partida(contas["banco"], "C", 250.0)])
    assert sistema.saldo_conta(contas["banco"]) == 750.0


def test_balanco_fecha_depois_de_varios_movimentos(sistema, contas):
    sistema.salvar_lancamento(
        None, "2026-02-05", "Salário",
        [sistema.Partida(contas["banco"], "D", 3000.0),
         sistema.Partida(contas["receita"], "C", 3000.0)])
    sistema.salvar_lancamento(
        None, "2026-02-06", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 420.5),
         sistema.Partida(contas["banco"], "C", 420.5)])
    sistema.transferir(contas["banco"], contas["outra"], 100.0, "2026-02-07", "Saque")

    balanco = sistema.balanco("2026-02-28")
    assert abs(balanco["diferenca"]) < 0.01


def test_transferencia_nao_muda_o_total(sistema, contas):
    antes = sistema.total_disponivel()["tem"]
    sistema.transferir(contas["banco"], contas["outra"], 300.0, "2026-02-08", "Troco")
    assert sistema.total_disponivel()["tem"] == pytest.approx(antes)
    assert sistema.saldo_conta(contas["banco"]) == 700.0
    assert sistema.saldo_conta(contas["outra"]) == 400.0


def test_saldo_respeita_a_data_de_corte(sistema, contas):
    sistema.salvar_lancamento(
        None, "2026-03-15", "Gasto futuro",
        [sistema.Partida(contas["despesa"], "D", 100.0),
         sistema.Partida(contas["banco"], "C", 100.0)])
    assert sistema.saldo_conta(contas["banco"], ate="2026-03-14") == 1000.0
    assert sistema.saldo_conta(contas["banco"], ate="2026-03-31") == 900.0


def test_categoria_nao_pode_ficar_no_grupo_errado(sistema):
    """Uma despesa em 3.x era contada como patrimônio e quebrava o balanço."""
    with pytest.raises(sistema.RegraNegocioError):
        sistema.salvar_conta(None, "3.03", "Seguros", "DESPESA", "D", True, True)

    nova = sistema.salvar_conta(None, "5.9.05", "Seguros", "DESPESA", "D", True, True)
    conta = sistema.obter_conta(nova)
    assert sistema.obter_conta(conta["pai_id"])["tipo"] == "DESPESA"


def test_excluir_conta_com_lancamento_e_recusado(sistema, contas):
    sistema.salvar_lancamento(
        None, "2026-02-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 10.0),
         sistema.Partida(contas["banco"], "C", 10.0)])
    with pytest.raises(sistema.RegraNegocioError):
        sistema.excluir_conta(contas["despesa"])
