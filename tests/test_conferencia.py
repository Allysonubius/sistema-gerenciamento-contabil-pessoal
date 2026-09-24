"""Conferência na mão: bater os movimentos com o extrato do banco.

Aqui a conferência automática fica desligada de propósito — este arquivo cobre
o modo manual, de quem prefere marcar cada linha. O modo automático (o padrão)
está em test_conferencia_automatica.py.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def movimentos(sistema, contas):
    sistema.db.set_config("conferencia_automatica", "0")
    ids = []
    for dia, valor in (("2026-02-03", 100.0), ("2026-02-10", 50.0), ("2026-03-01", 30.0)):
        ids.append(sistema.salvar_lancamento(
            None, dia, "Mercado",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)]))
    return ids


def test_movimento_nasce_pendente(sistema, movimentos):
    criados = [m for m in sistema.listar_movimentos() if m["id"] in movimentos]
    assert criados and all(not m["conferido"] for m in criados)


def test_marcar_e_desmarcar(sistema, movimentos):
    sistema.marcar_conferido(movimentos[0])
    conferidos = {m["id"]: m["conferido"] for m in sistema.listar_movimentos()}
    assert conferidos[movimentos[0]] is True
    assert conferidos[movimentos[1]] is False

    sistema.marcar_conferido(movimentos[0], False)
    assert not next(m for m in sistema.listar_movimentos()
                    if m["id"] == movimentos[0])["conferido"]


def test_filtro_mostra_so_os_pendentes(sistema, movimentos):
    antes = len(sistema.listar_movimentos(apenas_pendentes=True))
    sistema.marcar_conferido(movimentos[0])
    pendentes = sistema.listar_movimentos(apenas_pendentes=True)

    assert movimentos[0] not in [m["id"] for m in pendentes]
    assert len(pendentes) == antes - 1


def test_conferir_periodo_pega_so_o_periodo(sistema, movimentos):
    total = sistema.conferir_periodo("2026-02-01", "2026-02-28")
    assert total == 2

    por_id = {m["id"]: m["conferido"] for m in sistema.listar_movimentos()}
    assert por_id[movimentos[0]] and por_id[movimentos[1]]
    assert not por_id[movimentos[2]]


def test_resumo_conta_pendentes_e_valor(sistema, movimentos):
    sistema.marcar_conferido(movimentos[0])
    resumo = sistema.resumo_conferencia("2026-02-01", "2026-02-28")
    assert resumo["total"] == 2
    assert resumo["conferidos"] == 1
    assert resumo["pendentes"] == 1
    assert resumo["valor_pendente"] == 50.0
    assert resumo["percentual"] == 50.0


def test_resumo_filtra_por_conta(sistema, contas, movimentos):
    sistema.salvar_lancamento(
        None, "2026-02-15", "Compra em espécie",
        [sistema.Partida(contas["despesa"], "D", 20.0),
         sistema.Partida(contas["outra"], "C", 20.0)])
    assert sistema.resumo_conferencia("2026-02-01", "2026-02-28", contas["outra"])["total"] == 1
    assert sistema.resumo_conferencia("2026-02-01", "2026-02-28", contas["banco"])["total"] == 2


def test_marcar_movimento_inexistente_falha(sistema):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.marcar_conferido(9999)
