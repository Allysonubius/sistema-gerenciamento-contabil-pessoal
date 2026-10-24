"""O sistema precisa alcançar o primeiro registro, não só o ano corrente."""
from __future__ import annotations

import pytest


@pytest.fixture()
def historico_longo(sistema, contas):
    """Lançamentos espalhados por três anos, incluindo um bem antigo."""
    datas = ["2023-05-10", "2024-01-15", "2024-10-03", "2025-07-20", "2026-03-01"]
    for data in datas:
        sistema.salvar_lancamento(
            None, data, f"Compra de {data}",
            [sistema.Partida(contas["despesa"], "D", 100.0),
             sistema.Partida(contas["banco"], "C", 100.0)],
            documento="IMPORTADO")      # retrato do passado, sem trava de saldo
    return datas


def test_primeiro_mes_registrado_e_o_mais_antigo(sistema, historico_longo):
    assert sistema.primeiro_mes_registrado() == "2023-05"


def test_meses_do_historico_cobrem_tudo_sem_buraco(sistema, historico_longo):
    meses = sistema.meses_do_historico()
    assert meses[0] == "2023-05"
    assert meses[-1] == sistema.mes_atual()
    assert "2023-12" in meses and "2024-06" in meses      # meses sem registro entram


def test_livro_diario_alcanca_o_primeiro_registro(sistema, historico_longo):
    diario = sistema.livro_diario("1900-01-01", "2999-12-31")
    datas = [l["data"] for l in diario]
    assert datas[0] == "2023-05-10"
    assert len(diario) >= len(historico_longo)


def test_dre_de_todo_o_periodo_soma_os_anos_antigos(sistema, historico_longo):
    resultado = sistema.dre("1900-01-01", "2999-12-31")
    assert resultado["total_despesas"] == 500.0          # os cinco lançamentos

    so_este_ano = sistema.dre("2026-01-01", "2026-12-31")
    assert so_este_ano["total_despesas"] == 100.0        # só o de 2026


def test_listar_lancamentos_sem_limite_traz_tudo(sistema, contas):
    for i in range(1200):
        sistema.salvar_lancamento(
            None, "2024-02-10", f"Registro {i}",
            [sistema.Partida(contas["despesa"], "D", 1.0),
             sistema.Partida(contas["banco"], "C", 1.0)],
            documento="IMPORTADO")

    todos = sistema.listar_lancamentos("1900-01-01", "2999-12-31")
    assert len(todos) >= 1200        # antes parava nos mil mais recentes


def test_limite_continua_disponivel_para_quem_precisa(sistema, historico_longo):
    assert len(sistema.listar_lancamentos("1900-01-01", "2999-12-31", limite=2)) == 2


def test_movimentos_tambem_vem_completos(sistema, historico_longo):
    movimentos = sistema.listar_movimentos("1900-01-01", "2999-12-31")
    assert len(movimentos) >= len(historico_longo)
    assert movimentos[-1]["data"] == "2023-05-10"        # o mais antigo está lá
