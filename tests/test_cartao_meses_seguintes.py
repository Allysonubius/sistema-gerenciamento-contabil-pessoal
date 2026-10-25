"""Regras do cartão para os meses seguintes.

O que já passou (fatura fechada, mês pago) nunca muda; o que ainda vem pode ser
recalculado.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def cartao(sistema, contas):
    sistema.configurar_cartao(contas["cartao"], dia_fechamento=25, dia_vencimento=5,
                              juros_rotativo=10.0)
    sistema.definir_conta_da_fatura(contas["cartao"], contas["banco"])
    return contas["cartao"]


# --- 1. mudar o valor vale para a frente ----------------------------------- #
def test_reajuste_de_fixa_do_cartao_so_muda_o_que_vem(sistema, contas, cartao):
    recorrencia = sistema.salvar_recorrencia(
        None, "PAGAR", "Assinatura", "", 110.0, 3, contas["despesa"], None,
        sistema.mes_atual(), conta_pagamento_id=cartao)
    sistema.gerar_titulos_recorrentes()

    meses = sorted(t["competencia"] for t in sistema.listar_titulos()
                   if t["recorrencia_id"] == recorrencia)
    primeiro, quarto = meses[0], meses[3]

    # O primeiro mês é pago: vira história.
    titulo = next(t for t in sistema.listar_titulos()
                  if t["recorrencia_id"] == recorrencia and t["competencia"] == primeiro)
    sistema.baixar_titulo(titulo["id"], titulo["vencimento"], 110.0, cartao)

    sistema.aplicar_reajuste(recorrencia, quarto, 130.0)

    valores = {t["competencia"]: t["valor"] for t in sistema.listar_titulos()
               if t["recorrencia_id"] == recorrencia}
    assert valores[primeiro] == 110.0          # já pago: intocado
    assert valores[meses[2]] == 110.0          # antes do mês escolhido
    assert valores[quarto] == 130.0            # daqui em diante, o valor novo
    assert valores[meses[-1]] == 130.0


def test_fatura_fechada_nao_muda_quando_o_valor_futuro_muda(sistema, contas, cartao, fixar_hoje):
    fixar_hoje("2026-02-10")
    sistema.salvar_lancamento(
        None, "2026-02-10", "Assinatura",
        [sistema.Partida(contas["despesa"], "D", 110.0),
         sistema.Partida(cartao, "C", 110.0)])
    sistema.fechar_faturas("2026-02-26")
    fatura = sistema.listar_faturas(cartao)[0]

    sistema.salvar_lancamento(
        None, "2026-03-10", "Assinatura",
        [sistema.Partida(contas["despesa"], "D", 130.0),
         sistema.Partida(cartao, "C", 130.0)])

    assert sistema.listar_faturas(cartao)[0]["total"] == fatura["total"] == 110.0


# --- 2. compra parcelada ---------------------------------------------------- #
def test_parcelas_caem_uma_por_mes(sistema, contas, cartao, fixar_hoje):
    fixar_hoje("2026-02-05")
    sistema.criar_compra_parcelada("Notebook", cartao, contas["despesa"], 3000.0, 10,
                                   "2026-02", "2026-02-05")
    compra = sistema.listar_compras_parceladas()[0]
    assert compra["parcelas"] == 10
    assert compra["valor_parcela"] == 300.0
    assert sistema.saldo_conta(cartao) == 3000.0


def test_alterar_valor_recalcula_so_as_parcelas_que_faltam(sistema, contas, cartao, fixar_hoje):
    fixar_hoje("2026-02-05")
    # Sem rotativo aqui: o teste é sobre as parcelas, não sobre juros.
    sistema.configurar_cartao(cartao, dia_fechamento=25, dia_vencimento=5, juros_rotativo=0.0)
    compra = sistema.criar_compra_parcelada("Notebook", cartao, contas["despesa"], 1000.0, 10,
                                            "2026-02", "2026-02-05")
    sistema.fechar_faturas("2026-03-26")     # fecha fevereiro e março: 2 parcelas

    recalculadas = sistema.ajustar_compra_parcelada(compra, 1200.0)
    assert recalculadas == 8

    lancamentos = sistema.db.query(
        "SELECT data, valor FROM lancamento WHERE compra_id = ? ORDER BY data", (compra,))
    ja_faturadas = [l["valor"] for l in lancamentos[:2]]
    futuras = [l["valor"] for l in lancamentos[2:]]

    assert ja_faturadas == [100.0, 100.0], "parcelas já faturadas não podem mudar"
    assert sum(futuras) == pytest.approx(1000.0)   # 1200 - 200 já cobrados
    assert sistema.saldo_conta(cartao) == pytest.approx(1200.0)


def test_nao_da_para_reduzir_abaixo_do_que_ja_foi_faturado(sistema, contas, cartao):
    compra = sistema.criar_compra_parcelada("Notebook", cartao, contas["despesa"], 1000.0, 10,
                                            "2026-02", "2026-02-05")
    sistema.fechar_faturas("2026-03-26")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.ajustar_compra_parcelada(compra, 150.0)


# --- 3. o que não foi pago rola para a fatura seguinte ---------------------- #
def test_saldo_nao_pago_entra_na_proxima_fatura_com_juros(sistema, contas, cartao):
    sistema.salvar_lancamento(
        None, "2026-02-10", "Compra",
        [sistema.Partida(contas["despesa"], "D", 1000.0),
         sistema.Partida(cartao, "C", 1000.0)])
    sistema.fechar_faturas("2026-02-26")

    primeira = sistema.listar_faturas(cartao)[0]
    # Paga só uma parte da fatura.
    sistema.baixar_titulo(primeira["titulo_id"], "2026-03-05", 400.0, contas["banco"])
    sistema.fechar_faturas("2026-03-26")

    faturas = {f["competencia"]: f for f in sistema.listar_faturas(cartao)}
    segunda = faturas["2026-03"]
    assert segunda["saldo_anterior"] == 1000.0
    assert segunda["pagamentos"] == 400.0
    assert segunda["encargos"] == pytest.approx(60.0)     # 10% sobre os 600 que sobraram
    assert segunda["total"] == pytest.approx(660.0)


# --- 4. previsão das próximas faturas -------------------------------------- #
def test_previsao_mostra_o_que_ja_esta_agendado(sistema, contas, cartao):
    sistema.criar_compra_parcelada("Notebook", cartao, contas["despesa"], 1200.0, 6,
                                   sistema.mes_atual(), sistema.hoje_iso())
    previsao = sistema.previsao_faturas(cartao, meses=4)

    # Pode vir uma a menos: o ciclo que já fechou não é "próxima fatura".
    # Fixar o número exato fazia o teste quebrar sozinho no dia do fechamento.
    assert 3 <= len(previsao) <= 4
    assert all(p["fechamento"] > sistema._ultimo_fechamento(cartao) for p in previsao)
    assert all(p["vencimento"] > p["fechamento"] for p in previsao)
    assert sum(p["parcelas"] for p in previsao) > 0
    assert previsao[0]["previsto"] >= previsao[0]["parcelas"]


def test_previsao_inclui_contas_fixas_pagas_no_cartao(sistema, contas, cartao):
    sistema.salvar_recorrencia(None, "PAGAR", "Assinatura", "", 110.0, 3,
                               contas["despesa"], None, sistema.mes_atual(),
                               conta_pagamento_id=cartao)
    sistema.gerar_titulos_recorrentes()

    previsao = sistema.previsao_faturas(cartao, meses=3)
    assert sum(p["contas_fixas"] for p in previsao) >= 110.0
