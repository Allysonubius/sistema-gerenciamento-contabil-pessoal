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

    # --- partes reais, emprestadas da Aplicação ----------------------- #
    _vigiar_virada_do_dia = main_window.Aplicacao._vigiar_virada_do_dia

    # --- dublês --------------------------------------------------------- #
    def recarregar_tela_atual(self):
        self.recarregou += 1

    def _rotinas_de_abertura(self):
        self.rotinas += 1

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
    assert janela._dia_em_tela == date.today()


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
