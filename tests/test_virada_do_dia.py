"""O painel não pode mostrar números de ontem.

O programa costuma ficar dias aberto na bandeja: quando o dia (ou o mês) vira,
as contas da tela precisam ser refeitas sozinhas.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.ui import main_window


class JanelaFalsa:
    """Só o suficiente da Aplicação para exercitar a vigia da virada do dia."""

    def __init__(self):
        self._encerrando = False
        self._dia_em_tela = date.today()
        self.recarregou = 0
        self.rotinas = 0
        self.agendado = None
        self._telas = {}
        self.conferiu_fechamento = 0
        self.conferiu_versao = 0

    # --- partes reais, emprestadas da Aplicação ----------------------- #
    _vigiar_virada_do_dia = main_window.Aplicacao._vigiar_virada_do_dia
    _reacertar_periodos = main_window.Aplicacao._reacertar_periodos

    # --- dublês --------------------------------------------------------- #
    def recarregar_tela_atual(self):
        self.recarregou += 1

    def _rotinas_de_abertura(self):
        self.rotinas += 1

    def conferir_fechamento(self):
        self.conferiu_fechamento += 1

    def _vigiar_versao_nova(self):
        self.conferiu_versao += 1

    def after(self, _ms, funcao):
        self.agendado = funcao


def test_mesmo_dia_nao_refaz_nada():
    janela = JanelaFalsa()
    janela._vigiar_virada_do_dia()

    assert janela.recarregou == 0
    assert janela.rotinas == 0
    assert janela.agendado is not None       # continua vigiando


def test_dia_virou_refaz_as_contas_da_tela():
    janela = JanelaFalsa()
    janela._dia_em_tela = date.today() - timedelta(days=1)

    janela._vigiar_virada_do_dia()

    assert janela.recarregou == 1
    assert janela.rotinas == 1               # contas fixas, faturas, automáticos
    assert janela.conferiu_fechamento == 1   # e o mês anterior pode ter fechado
    assert janela.conferiu_versao == 1       # dias na bandeja sem conferir é não conferir
    assert janela._dia_em_tela == date.today()


def test_o_filtro_de_periodo_e_reacertado(sistema, raiz_tk):
    """Toda tela já montada volta para o mês de hoje, não só a que está à vista."""
    import importlib

    widgets = importlib.reload(importlib.import_module("app.ui.widgets"))

    class TelaFalsa:
        def __init__(self, filtro):
            self.filtro = filtro

    barra = widgets.BarraFiltro(raiz_tk, lambda: None)
    barra.dt_inicio.set_iso("2020-01-01")
    barra.dt_fim.set_iso("2020-01-31")

    janela = JanelaFalsa()
    janela._telas = {"Entradas e Saídas": TelaFalsa(barra), "Início": object()}
    janela._dia_em_tela = date.today() - timedelta(days=1)
    try:
        janela._vigiar_virada_do_dia()
        assert barra.periodo()[0].startswith(date.today().strftime("%Y-%m"))
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_vira_so_uma_vez_por_dia():
    janela = JanelaFalsa()
    janela._dia_em_tela = date.today() - timedelta(days=30)

    janela._vigiar_virada_do_dia()
    janela._vigiar_virada_do_dia()

    assert janela.recarregou == 1


def test_falha_nas_rotinas_nao_derruba_a_janela():
    janela = JanelaFalsa()
    janela._dia_em_tela = date.today() - timedelta(days=1)
    janela._rotinas_de_abertura = lambda: (_ for _ in ()).throw(RuntimeError("falhou"))

    janela._vigiar_virada_do_dia()           # não levanta

    assert janela.recarregou == 1
    assert janela.agendado is not None


def test_encerrando_para_de_vigiar():
    janela = JanelaFalsa()
    janela._encerrando = True
    janela._dia_em_tela = date.today() - timedelta(days=1)

    janela._vigiar_virada_do_dia()

    assert janela.recarregou == 0
    assert janela.agendado is None


@pytest.mark.parametrize("intervalo", [main_window.INTERVALO_VIRADA_DIA_MS])
def test_intervalo_razoavel(intervalo):
    assert 60_000 <= intervalo <= 30 * 60_000
