"""Corrigir e remover compras lançadas no cartão."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


@pytest.fixture()
def cartao(sistema, contas):
    dia = (date.today() + timedelta(days=5)).day
    if dia > 28:
        dia = 5
    sistema.configurar_cartao(contas["cartao"], dia_fechamento=dia, dia_vencimento=dia)
    sistema.definir_conta_da_fatura(contas["cartao"], contas["banco"])
    return contas["cartao"]


def fatura_de(sistema, cartao, data):
    info = sistema.fatura_da_data(cartao, data)
    return next(f for f in sistema.listar_faturas(cartao) if f["competencia"] == info["competencia"])


def compra_listada(sistema, cartao, descricao):
    return next(c for c in sistema.listar_compras_cartao(cartao) if c["descricao"].startswith(descricao))


def test_compras_aparecem_com_a_fatura_de_cada_uma(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 80.0, hoje, "Mercado")
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 300.0, hoje, "TV", parcelas=3)

    compras = sistema.listar_compras_cartao(cartao)
    mercado = compra_listada(sistema, cartao, "Mercado")
    assert mercado["valor"] == 80.0 and mercado["parcela"] == "" and mercado["editavel"]
    assert len([c for c in compras if c["compra_id"]]) == 3
    assert {c["parcela"] for c in compras if c["compra_id"]} == {"1/3", "2/3", "3/3"}

    atual = sistema.fatura_da_data(cartao, hoje)["competencia"]
    so_atual = sistema.listar_compras_cartao(cartao, atual)
    assert {c["descricao"] for c in so_atual} == {"Mercado", "TV (1/3)"}


def test_corrigir_valor_atualiza_a_fatura(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 80.0, hoje, "Mercado")
    compra = compra_listada(sistema, cartao, "Mercado")

    sistema.editar_compra_cartao(compra["id"], contas["despesa"], 95.5, hoje, "Mercado certo")

    assert fatura_de(sistema, cartao, hoje)["total"] == 95.5
    assert sistema.saldo_conta(cartao) == 95.5
    assert compra_listada(sistema, cartao, "Mercado certo")["valor"] == 95.5


def test_corrigir_data_muda_a_compra_de_fatura(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, hoje, "Livro")
    compra = compra_listada(sistema, cartao, "Livro")
    fechamento = sistema.fatura_da_data(cartao, hoje)["fechamento"]
    depois = (date.fromisoformat(fechamento) + timedelta(days=1)).isoformat()

    sistema.editar_compra_cartao(compra["id"], contas["despesa"], 50.0, depois, "Livro")

    # Saiu da fatura atual...
    atual = sistema.fatura_da_data(cartao, hoje)["competencia"]
    assert [f for f in sistema.listar_faturas(cartao)
            if f["competencia"] == atual and f["status_titulo"] == "ABERTO"] == []
    # ...e passou a pertencer à seguinte, que nasce quando o ciclo dela começar.
    nova = sistema.fatura_da_data(cartao, depois)["competencia"]
    assert nova > atual
    assert compra_listada(sistema, cartao, "Livro")["competencia"] == nova
    assert sistema.saldo_conta(cartao) == 50.0
    assert any(p["mes"] == nova and p["outras_compras"] == 50.0
               for p in sistema.previsao_faturas(cartao, meses=3))


def test_corrigir_categoria(sistema, contas, cartao):
    outra = sistema._conta_por_codigo("5.6.01")
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 30.0, sistema.hoje_iso(), "Filme")
    compra = compra_listada(sistema, cartao, "Filme")
    sistema.editar_compra_cartao(compra["id"], outra, 30.0, compra["data"], "Filme")
    assert compra_listada(sistema, cartao, "Filme")["categoria_id"] == outra


def test_remover_compra_a_vista(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 80.0, hoje, "Errada")
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 20.0, hoje, "Certa")

    sistema.remover_compra_cartao(compra_listada(sistema, cartao, "Errada")["id"])

    assert [c["descricao"] for c in sistema.listar_compras_cartao(cartao)] == ["Certa"]
    assert fatura_de(sistema, cartao, hoje)["total"] == 20.0


def test_remover_a_unica_compra_some_com_a_fatura_em_aberto(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 80.0, hoje, "Errada")
    sistema.remover_compra_cartao(compra_listada(sistema, cartao, "Errada")["id"])
    assert sistema.saldo_conta(cartao) == 0.0
    assert [f for f in sistema.listar_faturas(cartao) if f["status_titulo"] == "ABERTO"] == []
    assert abs(sistema.balanco(hoje)["diferenca"]) < 0.01


def test_compra_em_fatura_paga_nao_pode_mudar(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, "2026-01-10", "Antiga")
    fatura = fatura_de(sistema, cartao, "2026-01-10")
    sistema.baixar_titulo(fatura["titulo_id"], fatura["vencimento"], 50.0, contas["banco"])
    compra = compra_listada(sistema, cartao, "Antiga")

    assert compra["paga"] and not compra["editavel"]
    with pytest.raises(sistema.RegraNegocioError):
        sistema.editar_compra_cartao(compra["id"], contas["despesa"], 10.0, compra["data"], "x")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.remover_compra_cartao(compra["id"])


def test_nao_da_para_mover_compra_para_fatura_paga(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 50.0, "2026-01-10", "Antiga")
    fatura = fatura_de(sistema, cartao, "2026-01-10")
    sistema.baixar_titulo(fatura["titulo_id"], fatura["vencimento"], 50.0, contas["banco"])
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 30.0, sistema.hoje_iso(), "Nova")

    nova = compra_listada(sistema, cartao, "Nova")
    with pytest.raises(sistema.RegraNegocioError):
        sistema.editar_compra_cartao(nova["id"], contas["despesa"], 30.0, "2026-01-10", "Nova")


def test_corrigir_compra_parcelada(sistema, contas, cartao):
    outra = sistema._conta_por_codigo("5.6.01")
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 300.0, sistema.hoje_iso(),
                                    "TV", parcelas=3)
    compra_id = compra_listada(sistema, cartao, "TV")["compra_id"]

    sistema.editar_compra_parcelada(compra_id, "Televisão", outra, 600.0)

    parcelas = [c for c in sistema.listar_compras_cartao(cartao) if c["compra_id"] == compra_id]
    assert {c["descricao"] for c in parcelas} == {"Televisão (1/3)", "Televisão (2/3)",
                                                  "Televisão (3/3)"}
    assert all(c["categoria_id"] == outra for c in parcelas)
    assert round(sum(c["valor"] for c in parcelas), 2) == 600.0


def test_remover_compra_parcelada_inteira(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 300.0, sistema.hoje_iso(),
                                    "TV", parcelas=3)
    parcela = compra_listada(sistema, cartao, "TV")

    resultado = sistema.remover_compra_cartao(parcela["id"])

    assert resultado == {"removidas": 3, "mantidas": 0}
    assert sistema.listar_compras_cartao(cartao) == []
    assert sistema.listar_compras_parceladas(False) == []
    assert sistema.saldo_conta(cartao) == 0.0


def test_parcela_em_fatura_paga_e_mantida_ao_remover(sistema, contas, cartao):
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 300.0, "2026-01-10",
                                    "Geladeira", parcelas=3)
    primeira = fatura_de(sistema, cartao, "2026-01-10")
    sistema.baixar_titulo(primeira["titulo_id"], primeira["vencimento"],
                          sistema.obter_titulo(primeira["titulo_id"])["valor"], contas["banco"])

    parcela = compra_listada(sistema, cartao, "Geladeira")
    resultado = sistema.remover_compra_cartao(parcela["id"])

    assert resultado["mantidas"] == 1
    restantes = sistema.listar_compras_cartao(cartao)
    assert len(restantes) == 1 and restantes[0]["paga"]


def test_conta_paga_com_cartao_aparece_mas_se_corrige_em_contas_a_pagar(sistema, contas, cartao):
    hoje = sistema.hoje_iso()
    titulo = sistema.salvar_titulo(None, "PAGAR", "Assinatura", "", 110.0, hoje,
                                   contas["despesa"], None, multa_pct=0.0, juros_mes_pct=0.0)
    sistema.baixar_titulo(titulo, hoje, 110.0, cartao)
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 4.08, hoje, "taxa")

    compras = sistema.listar_compras_cartao(cartao)
    via_contas = next(c for c in compras if c["origem"] == "BAIXA")
    taxa = next(c for c in compras if c["descricao"] == "taxa")

    assert round(sum(c["valor"] for c in compras), 2) == sistema.saldo_conta(cartao) == 114.08
    assert not via_contas["editavel"] and "Contas a Pagar" in via_contas["motivo"]
    assert taxa["editavel"]
    with pytest.raises(sistema.RegraNegocioError):
        sistema.remover_compra_cartao(via_contas["id"])


def test_nova_compra_do_cartao_so_se_corrige_na_tela_do_cartao(sistema, contas, cartao):
    """Regra do sistema: um registro é corrigido/apagado onde foi criado."""
    sistema.registrar_compra_cartao(cartao, contas["despesa"], 40.0, sistema.hoje_iso(), "Café")
    movimento = next(m for m in sistema.listar_movimentos() if m["descricao"] == "Café")
    assert movimento["editavel"] is False
    with pytest.raises(sistema.RegraNegocioError):
        sistema.excluir_lancamento(movimento["id"])
