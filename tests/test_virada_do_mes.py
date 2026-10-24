"""O programa fica dias na bandeja: quando o mês vira, a tela tem de virar junto.

O painel sempre se recalcula a partir de hoje, mas o filtro de período era
calculado uma vez só, quando a tela nascia. Quem atravessava a meia-noite do
dia 1º continuava vendo "Este mês" com o mês anterior dentro.
"""
from __future__ import annotations

import datetime as _dt
import importlib

import pytest

DATA_REAL = _dt.date


def viajar_para(monkeypatch, modulos, ano: int, mes: int, dia: int) -> None:
    """Finge que hoje é outro dia, para os módulos informados."""
    class Hoje(DATA_REAL):
        @classmethod
        def today(cls):
            return DATA_REAL(ano, mes, dia)

    for modulo in modulos:
        monkeypatch.setattr(modulo, "date", Hoje)


@pytest.fixture()
def widgets(sistema, raiz_tk):
    modulo = importlib.import_module("app.ui.widgets")
    importlib.reload(modulo)
    yield modulo
    for filho in raiz_tk.winfo_children():
        filho.destroy()


# --------------------------------------------------------------------------- #
# O filtro de período
# --------------------------------------------------------------------------- #
def test_o_filtro_acompanha_a_virada_do_mes(widgets, sistema, raiz_tk, monkeypatch):
    viajar_para(monkeypatch, (widgets, sistema), 2026, 10, 24)
    barra = widgets.BarraFiltro(raiz_tk, lambda: None)
    assert barra.periodo() == ("2026-10-01", "2026-10-31")

    viajar_para(monkeypatch, (widgets, sistema), 2026, 11, 3)
    assert barra.revalidar() is True
    assert barra.periodo() == ("2026-11-01", "2026-11-30")
    assert barra.cb_atalho.get() == "Este mês"


def test_revalidar_no_mesmo_mes_nao_mexe_em_nada(widgets, sistema, raiz_tk, monkeypatch):
    viajar_para(monkeypatch, (widgets, sistema), 2026, 10, 24)
    barra = widgets.BarraFiltro(raiz_tk, lambda: None)

    assert barra.revalidar() is False
    assert barra.periodo() == ("2026-10-01", "2026-10-31")


def test_periodo_escolhido_a_mao_e_respeitado(widgets, sistema, raiz_tk, monkeypatch):
    """A data que o usuário digitou é dele; a virada do dia não a toma de volta."""
    viajar_para(monkeypatch, (widgets, sistema), 2026, 10, 24)
    barra = widgets.BarraFiltro(raiz_tk, lambda: None)
    barra.cb_atalho.set("Escolher datas")
    barra.dt_inicio.set_iso("2026-03-01")
    barra.dt_fim.set_iso("2026-03-31")

    viajar_para(monkeypatch, (widgets, sistema), 2026, 11, 3)

    assert barra.revalidar() is False
    assert barra.periodo() == ("2026-03-01", "2026-03-31")


def test_navegar_com_as_setas_tambem_e_respeitado(widgets, sistema, raiz_tk, monkeypatch):
    """Quem foi olhar agosto continua em agosto depois da meia-noite."""
    viajar_para(monkeypatch, (widgets, sistema), 2026, 10, 24)
    barra = widgets.BarraFiltro(raiz_tk, lambda: None)
    barra.deslocar(-2)
    assert barra.periodo() == ("2026-08-01", "2026-08-31")

    viajar_para(monkeypatch, (widgets, sistema), 2026, 11, 3)

    assert barra.revalidar() is False
    assert barra.periodo() == ("2026-08-01", "2026-08-31")


def test_mes_passado_tambem_anda(widgets, sistema, raiz_tk, monkeypatch):
    viajar_para(monkeypatch, (widgets, sistema), 2026, 10, 24)
    barra = widgets.BarraFiltro(raiz_tk, lambda: None)
    barra.cb_atalho.set("Mês passado")
    barra._aplicar_atalho(avisar=False)
    assert barra.periodo() == ("2026-09-01", "2026-09-30")

    viajar_para(monkeypatch, (widgets, sistema), 2026, 11, 3)
    barra.revalidar()

    assert barra.periodo() == ("2026-10-01", "2026-10-31")


def test_a_virada_do_ano_tambem_funciona(widgets, sistema, raiz_tk, monkeypatch):
    viajar_para(monkeypatch, (widgets, sistema), 2026, 12, 28)
    barra = widgets.BarraFiltro(raiz_tk, lambda: None)
    assert barra.periodo() == ("2026-12-01", "2026-12-31")

    viajar_para(monkeypatch, (widgets, sistema), 2027, 1, 2)
    barra.revalidar()

    assert barra.periodo() == ("2027-01-01", "2027-01-31")


# --------------------------------------------------------------------------- #
# Os números do mês
# --------------------------------------------------------------------------- #
@pytest.fixture()
def movimento(sistema, contas):
    sistema.salvar_lancamento(
        None, "2026-10-10", "Salário",
        [sistema.Partida(contas["banco"], "D", 2000.0),
         sistema.Partida(contas["receita"], "C", 2000.0)])
    sistema.salvar_lancamento(
        None, "2026-10-12", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 700.0),
         sistema.Partida(contas["banco"], "C", 700.0)])


def test_o_painel_zera_os_numeros_no_mes_novo(sistema, contas, movimento, monkeypatch):
    viajar_para(monkeypatch, (sistema,), 2026, 10, 24)
    outubro = sistema.resumo_dashboard()
    assert outubro["entrou_mes"] == 2000.0
    assert outubro["sobrou_mes"] == 1300.0

    viajar_para(monkeypatch, (sistema,), 2026, 11, 3)
    novembro = sistema.resumo_dashboard()

    assert novembro["entrou_mes"] == 0.0
    assert novembro["saiu_mes"] == 0.0
    assert novembro["sobrou_mes"] == 0.0


def test_o_saldo_de_outubro_vira_o_saldo_inicial_de_novembro(sistema, contas, movimento,
                                                             monkeypatch):
    viajar_para(monkeypatch, (sistema,), 2026, 10, 24)
    fim_de_outubro = sistema.resumo_dashboard()["disponivel"]

    viajar_para(monkeypatch, (sistema,), 2026, 11, 3)
    novembro = sistema.resumo_dashboard()

    assert novembro["saldo_inicio_mes"] == fim_de_outubro
    assert novembro["disponivel"] == fim_de_outubro


def test_a_poupanca_recomeca_no_mes_novo(sistema, contas, movimento, monkeypatch):
    viajar_para(monkeypatch, (sistema,), 2026, 11, 3)
    meta = sistema.meta_de_poupanca()

    assert meta["competencia"] == "2026-11"
    assert meta["recebido"] == 0.0
    assert meta["situacao"] == "sem_renda"
    # O que já estava guardado não some com a virada.
    assert meta["total_guardado"] == sistema.total_guardado()


def test_outubro_continua_inteiro_depois_da_virada(sistema, contas, movimento, monkeypatch):
    """Passar de mês não mexe no que já aconteceu."""
    viajar_para(monkeypatch, (sistema,), 2026, 11, 3)

    assert sistema.fluxo_de_caixa("2026-10-01", "2026-10-31")["sobrou"] == 1300.0
    assert sistema.meta_de_poupanca("2026-10")["recebido"] == 2000.0
