"""Fatura atual: recebe as compras até o fechamento; garantia cobre o não pago."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


def dias(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture()
def cartao(sistema, contas):
    """Cartão que fecha e vence no mesmo dia, daqui a 5 dias."""
    dia = (date.today() + timedelta(days=5)).day
    if dia > 28:                      # evita meses curtos deixarem o teste instável
        dia = 5
    sistema.configurar_cartao(contas["cartao"], dia_fechamento=dia, dia_vencimento=dia)
    sistema.definir_conta_da_fatura(contas["cartao"], contas["banco"])
    return contas["cartao"]


def fatura_atual(sistema, cartao):
    abertas = [f for f in sistema.listar_faturas(cartao) if f["status_titulo"] == "ABERTO"]
    return min(abertas, key=lambda f: f["competencia"]) if abertas else None


def test_fecha_e_vence_no_mesmo_dia(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    info = sistema.fatura_da_data(cartao, hoje)
    assert info["fechamento"] == info["vencimento"]
    assert info["fechamento"] >= hoje


def test_compra_a_vista_entra_na_fatura_atual_na_hora(sistema, contas, cartao):
    info = sistema.registrar_compra_cartao(cartao, contas["despesa"], 80.0,
                                           sistema.hoje_iso(), "Mercado")
    fatura = fatura_atual(sistema, cartao)
    assert fatura is not None
    assert fatura["competencia"] == info["competencia"]
    assert fatura["total"] == 80.0
    assert fatura["fechada"] == 0

    titulo = sistema.obter_titulo(fatura["titulo_id"])
    assert titulo["valor"] == 80.0
    assert titulo["conta_pagamento_id"] == contas["banco"]
    assert "Fatura atual" in titulo["observacao"]


def test_cada_compra_atualiza_o_valor_da_fatura(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 80.0, sistema.hoje_iso())
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 20.5, sistema.hoje_iso())
    fatura = fatura_atual(sistema, cartao)
    assert fatura["total"] == 100.5
    assert sistema.obter_titulo(fatura["titulo_id"])["valor"] == 100.5
    # continua sendo uma fatura só
    assert len([f for f in sistema.listar_faturas(cartao)
                if f["competencia"] == fatura["competencia"]]) == 1


def test_compra_parcelada_poe_so_a_parcela_na_fatura_atual(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 300.0, sistema.hoje_iso(),
                                    "TV", parcelas=3)
    assert fatura_atual(sistema, cartao)["total"] == 100.0
    assert sistema.saldo_conta(cartao) == 300.0


def test_compra_depois_do_fechamento_vai_para_a_proxima(sistema, contas, cartao):
    atual = sistema.fatura_da_data(cartao, sistema.hoje_iso())
    depois = (date.fromisoformat(atual["fechamento"]) + timedelta(days=1)).isoformat()
    proxima = sistema.fatura_da_data(cartao, depois)
    assert proxima["competencia"] > atual["competencia"]


def test_nenhum_valor_aparece_em_duas_faturas(sistema, contas, cartao):
    """Fatura fechada ainda não paga não pode ser somada de novo na seguinte."""
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, "2026-01-10")
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 30.0, sistema.hoje_iso())
    abertas = [sistema.obter_titulo(f["titulo_id"]) for f in sistema.listar_faturas(cartao)
               if f["status_titulo"] == "ABERTO"]
    assert round(sum(t["valor"] for t in abertas), 2) == sistema.saldo_conta(cartao) == 80.0


def test_compra_esquecida_atualiza_fatura_fechada_nao_paga(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, "2026-01-10")
    antiga = next(f for f in sistema.listar_faturas(cartao) if f["fechada"] == 1)

    sistema.registrar_compra_cartao(cartao, contas["despesa"], 25.0, "2026-01-11")

    atualizada = next(f for f in sistema.listar_faturas(cartao) if f["id"] == antiga["id"])
    assert atualizada["total"] == 75.0
    assert sistema.obter_titulo(atualizada["titulo_id"])["valor"] == 75.0


def test_fatura_paga_nao_muda_mais(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, "2026-01-10")
    antiga = next(f for f in sistema.listar_faturas(cartao) if f["fechada"] == 1)
    sistema.baixar_titulo(antiga["titulo_id"], antiga["vencimento"], 50.0, contas["banco"])

    sistema.registrar_compra_cartao(cartao, contas["despesa"], 25.0, "2026-01-11")

    paga = next(f for f in sistema.listar_faturas(cartao) if f["id"] == antiga["id"])
    assert paga["total"] == 50.0
    assert sistema.saldo_conta(cartao) == 25.0      # a compra não se perde


def test_mudar_o_ciclo_refaz_so_as_faturas_nao_pagas(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, "2026-01-10")
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 30.0, sistema.hoje_iso())
    paga = next(f for f in sistema.listar_faturas(cartao) if f["fechada"] == 1)
    sistema.baixar_titulo(paga["titulo_id"], paga["vencimento"], 50.0, contas["banco"])

    sistema.configurar_cartao(cartao, dia_fechamento=28, dia_vencimento=28)

    faturas = sistema.listar_faturas(cartao)
    assert any(f["id"] == paga["id"] and f["status_titulo"] == "QUITADO" for f in faturas)
    abertas = [f for f in faturas if f["status_titulo"] == "ABERTO"]
    assert all(f["fechamento"].endswith("-28") for f in abertas)
    assert round(sum(f["total"] for f in abertas), 2) == 30.0


# --- saldo em garantia ------------------------------------------------------ #
@pytest.fixture()
def garantido(sistema, contas, cartao):
    cdb = sistema.criar_carteira("CDB Garantia", "Investimento", "Banco", 500.0,
                                 "2026-01-02", conta_origem_id=contas["banco"])
    sistema.definir_garantia_cartao(cartao, cdb)
    return cdb


def test_fatura_vencida_nao_paga_e_descontada_da_garantia(sistema, contas, cartao, garantido):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 120.0, "2026-01-10")
    fatura = next(f for f in sistema.listar_faturas(cartao) if f["fechada"] == 1)

    descontos = sistema.descontar_faturas_da_garantia()

    assert len(descontos) == 1 and descontos[0]["valor"] == 120.0
    assert sistema.obter_titulo(fatura["titulo_id"])["status"] == "QUITADO"
    assert sistema.saldo_conta(garantido) == 380.0
    assert sistema.saldo_conta(cartao) == 0.0
    assert sistema.saldo_conta(contas["banco"]) == 500.0   # a conta corrente não foi usada
    assert sistema.limite_do_cartao(cartao)["limite"] == 380.0
    assert abs(sistema.balanco(sistema.hoje_iso())["diferenca"]) < 0.01


def test_fatura_paga_em_dia_nao_mexe_na_garantia(sistema, contas, cartao, garantido):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 120.0, "2026-01-10")
    fatura = next(f for f in sistema.listar_faturas(cartao) if f["fechada"] == 1)
    sistema.baixar_titulo(fatura["titulo_id"], fatura["vencimento"], 120.0, contas["banco"])

    assert sistema.descontar_faturas_da_garantia() == []
    assert sistema.saldo_conta(garantido) == 500.0


def test_fatura_atual_ainda_nao_vencida_nao_e_descontada(sistema, contas, cartao, garantido):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 90.0, sistema.hoje_iso())
    assert sistema.descontar_faturas_da_garantia() == []
    assert sistema.saldo_conta(garantido) == 500.0


def test_garantia_menor_que_a_fatura_desconta_o_que_tem(sistema, contas, cartao):
    cdb = sistema.criar_carteira("CDB pequeno", "Investimento", "Banco", 100.0,
                                 "2026-01-02", conta_origem_id=contas["banco"])
    sistema.definir_garantia_cartao(cartao, cdb)
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 150.0, "2026-01-10")

    descontos = sistema.descontar_faturas_da_garantia()

    assert descontos[0]["valor"] == 100.0 and descontos[0]["faltou"] == 50.0
    assert sistema.saldo_conta(cdb) == 0.0
    sobra = [t for t in sistema.listar_titulos(status="ABERTO") if "faltou" in t["descricao"]]
    assert len(sobra) == 1 and sobra[0]["valor"] == 50.0


def test_cartao_sem_garantia_nunca_desconta_sozinho(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 120.0, "2026-01-10")
    assert sistema.descontar_faturas_da_garantia() == []
