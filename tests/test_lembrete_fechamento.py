"""O programa lembra, no mês seguinte, que o anterior ficou por fechar.

O fechamento só vale se acontecer. Deixar para quando lembrar é o mesmo que não
ter — então quem lembra é o programa, e volta a lembrar até o mês ser fechado.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def com_historico(sistema, contas):
    """Um lançamento no mês passado, para haver o que fechar."""
    anterior = sistema._mes_anterior(sistema.mes_atual())
    sistema.salvar_lancamento(
        None, f"{anterior}-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 100.0),
         sistema.Partida(contas["banco"], "C", 100.0)])
    return anterior


# --------------------------------------------------------------------------- #
# Quais meses estão esperando
# --------------------------------------------------------------------------- #
def test_sem_registro_nao_ha_o_que_fechar(sistema):
    assert sistema.meses_a_fechar() == []
    assert sistema.lembrete_de_fechamento()["pendente"] is False


def test_o_mes_passado_aparece_para_fechar(sistema, com_historico):
    meses = sistema.meses_a_fechar()

    assert com_historico in meses
    assert sistema.mes_atual() not in meses, "o mês corrente ainda não terminou"


def test_o_lembrete_diz_qual_mes_e_quantos_registros(sistema, com_historico):
    lembrete = sistema.lembrete_de_fechamento()

    assert lembrete["pendente"] is True
    assert lembrete["primeiro"] == sistema.meses_a_fechar()[0]
    assert lembrete["lancamentos"] > 0
    assert lembrete["nome"]


def test_depois_de_fechar_o_lembrete_anda(sistema, com_historico):
    primeiro = sistema.meses_a_fechar()[0]
    sistema.fechar_competencia(primeiro)
    lembrete = sistema.lembrete_de_fechamento()

    assert primeiro not in sistema.meses_a_fechar()
    if lembrete["pendente"]:
        assert lembrete["primeiro"] > primeiro


def test_fechando_tudo_o_lembrete_cala(sistema, com_historico):
    for mes in list(sistema.meses_a_fechar()):
        sistema.fechar_competencia(mes)

    assert sistema.lembrete_de_fechamento()["pendente"] is False
    assert sistema.deve_lembrar_fechamento() is False


# --------------------------------------------------------------------------- #
# Quando avisar
# --------------------------------------------------------------------------- #
def test_avisa_por_padrao(sistema, com_historico):
    assert sistema.lembrete_ligado() is True
    assert sistema.deve_lembrar_fechamento() is True


def test_desligar_o_lembrete(sistema, com_historico):
    sistema.definir_lembrete(False)

    assert sistema.deve_lembrar_fechamento() is False
    # O mês continua lá esperando — o que mudou foi só o aviso.
    assert sistema.lembrete_de_fechamento()["pendente"] is True


def test_religar_o_lembrete_limpa_o_adiamento(sistema, com_historico):
    sistema.adiar_lembrete(30)
    assert sistema.deve_lembrar_fechamento() is False

    sistema.definir_lembrete(True)

    assert sistema.deve_lembrar_fechamento() is True


def test_adiar_cala_o_aviso_por_alguns_dias(sistema, com_historico):
    volta = sistema.adiar_lembrete(7)

    assert sistema.deve_lembrar_fechamento() is False
    assert volta > sistema.hoje_iso()


def test_passado_o_prazo_o_aviso_volta(sistema, com_historico):
    from app import db

    sistema.adiar_lembrete(7)
    db.set_config("fechamento_adiado_ate", "2000-01-01")   # como se já tivesse passado

    assert sistema.deve_lembrar_fechamento() is True


# --------------------------------------------------------------------------- #
# A faixa na tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


def test_a_faixa_nasce_escondida_e_aparece_com_recado(sistema, raiz_tk):
    import importlib

    widgets = importlib.reload(importlib.import_module("app.ui.widgets"))
    faixa = widgets.FaixaAviso(raiz_tk)
    try:
        assert faixa.visivel is False

        faixa.mostrar("outubro já terminou")
        assert faixa.visivel is True
        assert "outubro" in faixa.lbl.cget("text")

        faixa.esconder()
        assert faixa.visivel is False
    finally:
        faixa.destroy()


def test_mostrar_duas_vezes_nao_empilha(sistema, raiz_tk):
    import importlib

    widgets = importlib.reload(importlib.import_module("app.ui.widgets"))
    faixa = widgets.FaixaAviso(raiz_tk)
    try:
        faixa.mostrar("primeiro")
        faixa.mostrar("segundo")

        assert faixa.visivel is True
        assert faixa.lbl.cget("text") == "segundo"
    finally:
        faixa.destroy()


def test_as_acoes_sao_trocaveis(sistema, raiz_tk):
    import importlib

    widgets = importlib.reload(importlib.import_module("app.ui.widgets"))
    faixa = widgets.FaixaAviso(raiz_tk)
    cliques = []
    try:
        faixa.acoes([("Fechar agora", lambda: cliques.append("fechar"))])
        assert len(faixa._botoes) == 1

        faixa.acoes([("A", lambda: None), ("B", lambda: None)])
        assert len(faixa._botoes) == 2

        faixa._botoes[0].invoke()
    finally:
        faixa.destroy()
