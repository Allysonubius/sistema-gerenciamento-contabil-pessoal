"""Duas arrumações que eliminam erro silencioso.

A primeira: um ano digitado errado (2062 em vez de 2026) entrava sem aviso e
estragava toda a previsão. A segunda: as categorias do plano padrão que nunca
foram usadas enchiam os seletores e convidavam a classificar errado.
"""
from __future__ import annotations

import pytest


# --------------------------------------------------------------------------- #
# Datas aceitas
# --------------------------------------------------------------------------- #
def gastar(sistema, contas, data_iso: str) -> int:
    return sistema.salvar_lancamento(
        None, data_iso, "Mercado",
        [sistema.Partida(contas["despesa"], "D", 10.0),
         sistema.Partida(contas["banco"], "C", 10.0)])


def test_data_de_hoje_passa(sistema, contas):
    assert gastar(sistema, contas, sistema.hoje_iso()) > 0


def test_ano_digitado_errado_e_barrado(sistema, contas):
    ano = sistema.date.today().year + 36
    with pytest.raises(sistema.RegraNegocioError) as erro:
        gastar(sistema, contas, f"{ano}-05-10")
    assert "futuro" in str(erro.value)


def test_data_muito_antiga_e_barrada(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        gastar(sistema, contas, "1899-01-01")
    assert "anterior" in str(erro.value)


def test_data_sem_sentido_e_barrada(sistema, contas):
    for texto in ("2026-13-01", "2026-02-30", "dez/2026", ""):
        with pytest.raises(sistema.RegraNegocioError):
            gastar(sistema, contas, texto)


def test_parcelamento_longo_continua_cabendo(sistema, contas):
    """Dez anos à frente é o limite: um financiamento longo passa."""
    daqui_a_nove_anos = f"{sistema.date.today().year + 9}-01-10"
    assert gastar(sistema, contas, daqui_a_nove_anos) > 0


def test_o_limite_e_o_fim_do_decimo_ano(sistema):
    assert sistema.limite_de_data() == f"{sistema.date.today().year + 10}-12-31"


# --------------------------------------------------------------------------- #
# Categorias que nunca foram usadas
# --------------------------------------------------------------------------- #
def test_o_plano_padrao_vem_com_categorias_sem_uso(sistema):
    sem_uso = sistema.contas_sem_uso()

    assert sem_uso
    assert all(c["codigo"] for c in sem_uso)


def test_categoria_usada_nao_entra_na_lista(sistema, contas):
    gastar(sistema, contas, "2026-05-10")
    codigos = {c["id"] for c in sistema.contas_sem_uso()}

    assert contas["despesa"] not in codigos


def test_carteira_recem_criada_nao_e_tratada_como_lixo(sistema):
    """Uma conta de dinheiro sem movimento ainda não é sobra do plano padrão."""
    nova = sistema.criar_carteira("Banco Novo", "Conta corrente")
    ids = {c["id"] for c in sistema.contas_sem_uso()}

    assert nova not in ids


def test_categoria_com_orcamento_nao_entra_na_lista(sistema):
    conta = sistema._conta_por_codigo("5.6.02")        # Viagens
    sistema.definir_orcamento(conta, 300.0)
    ids = {c["id"] for c in sistema.contas_sem_uso()}

    assert conta not in ids


def test_categoria_de_conta_fixa_nao_entra_na_lista(sistema):
    conta = sistema._conta_por_codigo("5.6.01")        # Assinaturas
    sistema.salvar_recorrencia(None, "PAGAR", "Streaming", "", 30.0, 10, conta, None,
                               sistema.mes_atual())
    ids = {c["id"] for c in sistema.contas_sem_uso()}

    assert conta not in ids


def test_arquivar_desativa_sem_apagar(sistema):
    antes = sistema.contas_sem_uso()
    total = sistema.arquivar_contas_sem_uso()

    assert total == len(antes)
    assert sistema.contas_sem_uso() == []
    # Nada foi apagado: as contas continuam lá, apenas inativas.
    for conta in antes:
        guardada = sistema.obter_conta(conta["id"])
        assert guardada is not None
        assert guardada["ativo"] == 0


def test_arquivadas_saem_dos_seletores(sistema):
    antes = {c["id"] for c in sistema.contas_sem_uso()}
    sistema.arquivar_contas_sem_uso()
    ativas = {c["id"] for c in sistema.listar_contas(apenas_ativas=True)}

    assert not (antes & ativas)


def test_arquivar_so_as_escolhidas(sistema):
    sem_uso = sistema.contas_sem_uso()
    escolhida = sem_uso[0]["id"]
    total = sistema.arquivar_contas_sem_uso([escolhida])

    assert total == 1
    assert sistema.obter_conta(escolhida)["ativo"] == 0
    assert len(sistema.contas_sem_uso()) == len(sem_uso) - 1


def test_arquivar_duas_vezes_nao_faz_nada(sistema):
    sistema.arquivar_contas_sem_uso()

    assert sistema.arquivar_contas_sem_uso() == 0
