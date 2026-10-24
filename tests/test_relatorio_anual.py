"""Ano a ano: a visão que diz se a vida financeira melhorou ou piorou.

Os relatórios iam só até o mês; o ano, que é onde a direção aparece, não existia
em nenhuma tela.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def historia(sistema, contas):
    """Dois anos fechados: 2024 sobrando, 2025 faltando."""
    def ganhou(data_iso: str, valor: float) -> None:
        sistema.salvar_lancamento(
            None, data_iso, "Salário",
            [sistema.Partida(contas["banco"], "D", valor),
             sistema.Partida(contas["receita"], "C", valor)])

    def gastou(data_iso: str, valor: float) -> None:
        sistema.salvar_lancamento(
            None, data_iso, "Mercado",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])

    ganhou("2024-06-05", 3000.0)
    gastou("2024-06-20", 1000.0)
    ganhou("2025-03-05", 4000.0)
    gastou("2025-03-20", 5000.0)
    return {"ganhou": ganhou, "gastou": gastou}


def por_ano(sistema) -> dict[str, dict]:
    return {linha["ano"]: linha for linha in sistema.resumo_anual()}


def test_sem_registros_nao_ha_anos(sistema):
    assert sistema.resumo_anual() == []


def test_um_ano_por_linha_sem_buracos(sistema, historia):
    anos = [linha["ano"] for linha in sistema.resumo_anual()]

    assert anos[0] == "2024"
    assert "2025" in anos
    # O ano corrente aparece mesmo sem nada lançado nele.
    assert anos[-1] == str(sistema.date.today().year)


def test_entrou_saiu_e_resultado_de_cada_ano(sistema, historia):
    anos = por_ano(sistema)

    assert anos["2024"]["receita"] == 3000.0
    assert anos["2024"]["despesa"] == 1000.0
    assert anos["2024"]["resultado"] == 2000.0
    assert anos["2025"]["resultado"] == -1000.0


def test_resultado_acumulado_atravessa_os_anos(sistema, historia):
    anos = por_ano(sistema)

    assert anos["2024"]["acumulado"] == 2000.0
    assert anos["2025"]["acumulado"] == 1000.0


def test_dinheiro_em_conta_no_fim_de_cada_ano(sistema, contas, historia):
    """O saldo inicial do banco é de 2026, então 2024 fecha só com o movimento."""
    anos = por_ano(sistema)

    assert anos["2024"]["saldo_contas"] == 2000.0
    assert anos["2025"]["saldo_contas"] == 1000.0


def test_media_por_mes_usa_os_meses_que_o_ano_teve(sistema, historia):
    """2024 começa em junho: a média não pode ser dividida por doze."""
    anos = por_ano(sistema)

    assert anos["2024"]["meses"] == 7          # junho a dezembro
    assert anos["2025"]["meses"] == 12
    assert anos["2024"]["media_receita"] == round(3000.0 / 7, 2)


def test_percentual_que_sobrou(sistema, historia):
    anos = por_ano(sistema)

    assert anos["2024"]["sobra_pct"] == pytest.approx(66.7, abs=0.1)
    assert anos["2025"]["sobra_pct"] == pytest.approx(-25.0, abs=0.1)


def test_ano_sem_receita_nao_divide_por_zero(sistema, contas, historia):
    anos = por_ano(sistema)
    corrente = anos[str(sistema.date.today().year)]

    assert corrente["receita"] == 0.0
    assert corrente["sobra_pct"] == 0.0


def test_ano_corrente_vem_marcado_como_parcial(sistema, historia):
    anos = sistema.resumo_anual()
    corrente = str(sistema.date.today().year)

    assert anos[-1]["ano"] == corrente
    assert anos[-1]["parcial"] is True
    assert anos[0]["parcial"] is False


def test_o_total_anual_bate_com_a_soma_dos_meses(sistema, historia):
    """Mesma informação em duas telas: elas não podem divergir."""
    meses = sistema.resumo_mensal(sistema.meses_do_historico())
    de_2025 = [m for m in meses if m["mes"].startswith("2025")]
    anual = por_ano(sistema)["2025"]

    assert round(sum(m["receita"] for m in de_2025), 2) == anual["receita"]
    assert round(sum(m["despesa"] for m in de_2025), 2) == anual["despesa"]
