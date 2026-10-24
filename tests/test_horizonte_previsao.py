"""A previsão vai até o último compromisso, não até um prazo fixo.

Projetar 90 dias enquanto havia parcelas cadastradas para dois anos à frente
escondia justamente o que o usuário não tem na cabeça.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def conta_longa(sistema, contas):
    """Uma conta a pagar vencendo bem longe, e outra para o mês que vem."""
    hoje = sistema.date.today()
    longe = sistema.somar_meses(hoje, 20).replace(day=10).isoformat()
    perto = sistema.somar_meses(hoje, 1).replace(day=10).isoformat()
    sistema.salvar_titulo(None, "PAGAR", "Parcela distante", "Loja", 300.0, longe,
                          contas["despesa"], None)
    sistema.salvar_titulo(None, "PAGAR", "Parcela próxima", "Loja", 300.0, perto,
                          contas["despesa"], None)
    return {"longe": longe, "perto": perto}


def test_sem_compromisso_nao_ha_horizonte(sistema):
    assert sistema.ultimo_compromisso() is None
    assert sistema.meses_de_compromisso() == 6        # o mínimo
    assert sistema.dias_de_compromisso() == 90


def test_horizonte_acompanha_o_vencimento_mais_distante(sistema, conta_longa):
    assert sistema.ultimo_compromisso() == conta_longa["longe"]
    assert sistema.meses_de_compromisso() >= 20


def test_previsao_mensal_alcanca_o_ultimo_compromisso(sistema, conta_longa):
    meses = sistema.previsao_mensal()

    assert len(meses) >= 21
    assert meses[-1]["mes"] >= conta_longa["longe"][:7]


def test_a_parcela_distante_aparece_na_previsao(sistema, conta_longa):
    """Com seis meses fixos ela ficava fora da tabela."""
    meses = {m["mes"]: m for m in sistema.previsao_mensal()}

    assert meses[conta_longa["longe"][:7]]["pagar"] == 300.0


def test_horizonte_pedido_a_mao_continua_valendo(sistema, conta_longa):
    assert len(sistema.previsao_mensal(6)) == 6


def test_titulo_quitado_nao_estica_o_horizonte(sistema, contas):
    hoje = sistema.date.today()
    longe = sistema.somar_meses(hoje, 30).replace(day=10).isoformat()
    titulo_id = sistema.salvar_titulo(None, "RECEBER", "Promessa", "Alguém", 50.0, longe,
                                      contas["receita"], None)
    sistema.cancelar_titulo(titulo_id)

    assert sistema.ultimo_compromisso() is None


def test_resumo_do_horizonte_para_a_tela(sistema, conta_longa):
    resumo = sistema.horizonte_da_previsao()

    assert resumo["ate"] == conta_longa["longe"]
    assert resumo["titulos"] == 2
    assert resumo["total"] == 600.0
    assert resumo["meses"] >= 20
    assert resumo["dias"] > 90


def test_horizonte_tem_teto(sistema, contas):
    """Uma data absurdamente distante não gera uma tabela infinita."""
    sistema.salvar_titulo(None, "PAGAR", "Daqui a muito tempo", "Loja", 10.0,
                          sistema.limite_de_data(), contas["despesa"], None)

    assert sistema.meses_de_compromisso() <= 120
    assert sistema.dias_de_compromisso() <= 3660
