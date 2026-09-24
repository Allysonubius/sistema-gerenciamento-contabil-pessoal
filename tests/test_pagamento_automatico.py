"""Débito automático: a conta marcada assim é descontada sozinha no vencimento."""
from __future__ import annotations

import pytest


def test_conta_automatica_e_descontada_no_vencimento(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Internet", "", 99.9, "2026-03-15",
                                   contas["despesa"], None,
                                   conta_pagamento_id=contas["banco"],
                                   pagamento_automatico=True)

    resultado = sistema.pagar_automaticos("2026-03-20")

    assert [p["id"] for p in resultado["pagos"]] == [titulo]
    assert sistema.obter_titulo(titulo)["status"] == "QUITADO"
    # O desconto sai na data do vencimento, como sairia no banco.
    assert sistema.obter_titulo(titulo)["liquidado_em"] == "2026-03-15"
    assert sistema.saldo_conta(contas["banco"]) == pytest.approx(900.1)


def test_conta_que_ainda_nao_venceu_nao_e_descontada(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-10")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Internet", "", 100.0, "2026-03-15",
                                   contas["despesa"], None,
                                   conta_pagamento_id=contas["banco"],
                                   pagamento_automatico=True)

    assert sistema.pagar_automaticos("2026-03-10")["pagos"] == []
    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"
    assert sistema.saldo_conta(contas["banco"]) == 1000.0


def test_conta_manual_nunca_e_paga_sozinha(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 50.0, "2026-03-15",
                                   contas["despesa"], None,
                                   conta_pagamento_id=contas["banco"])

    sistema.pagar_automaticos("2026-03-20")
    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"


def test_automatica_sem_conta_de_desconto_fica_pendente(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Sem conta", "", 30.0, "2026-03-15",
                                   contas["despesa"], None)
    # Marcar sem conta de desconto é recusado na hora.
    with pytest.raises(sistema.RegraNegocioError):
        sistema.definir_pagamento_automatico(titulo, True)

    # Mas uma conta que perdeu a carteira (apagada) precisa aparecer como pendente.
    sistema.db.execute("UPDATE titulo SET pagamento_automatico = 1 WHERE id = ?", (titulo,))
    resultado = sistema.pagar_automaticos("2026-03-20")
    assert resultado["pagos"] == []
    assert [p["id"] for p in resultado["pendentes"]] == [titulo]
    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"


def test_pagar_duas_vezes_nao_duplica_o_desconto(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    sistema.salvar_titulo(None, "PAGAR", "Internet", "", 100.0, "2026-03-15",
                          contas["despesa"], None, conta_pagamento_id=contas["banco"],
                          pagamento_automatico=True)

    sistema.pagar_automaticos("2026-03-20")
    sistema.pagar_automaticos("2026-03-21")
    assert sistema.saldo_conta(contas["banco"]) == 900.0


def test_desfazer_deixa_a_conta_em_aberto_de_novo(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Internet", "", 100.0, "2026-03-15",
                                   contas["despesa"], None,
                                   conta_pagamento_id=contas["banco"],
                                   pagamento_automatico=True)
    sistema.pagar_automaticos("2026-03-20")

    sistema.estornar_titulo(titulo)
    assert sistema.obter_titulo(titulo)["status"] == "ABERTO"
    assert sistema.saldo_conta(contas["banco"]) == 1000.0
    # Continua marcada como automática: quem desfez pode desligar a marca à parte.
    assert sistema.obter_titulo(titulo)["pagamento_automatico"] == 1


def test_conta_fixa_leva_a_marca_para_os_meses_seguintes(sistema, contas):
    rec, _ = sistema.criar_conta_fixa("PAGAR", "Streaming", "", 40.0,
                                      f"{sistema.mes_atual()}-10", contas["despesa"],
                                      conta_pagamento_id=contas["banco"],
                                      pagamento_automatico=True)

    titulos = [t for t in sistema.listar_titulos() if t["recorrencia_id"] == rec]
    assert len(titulos) > 1
    assert all(t["pagamento_automatico"] == 1 for t in titulos)

    # Desligar vale deste mês em diante.
    atingidos = sistema.aplicar_pagamento_automatico(rec, sistema.mes_atual(), False)
    assert atingidos == len(titulos)
    assert all(t["pagamento_automatico"] == 0 for t in sistema.listar_titulos()
               if t["recorrencia_id"] == rec)


def test_marcar_conta_fixa_propaga_so_do_mes_escolhido_em_diante(sistema, contas, fixar_hoje):
    rec, _ = sistema.criar_conta_fixa("PAGAR", "Academia", "", 80.0,
                                      f"{sistema.mes_atual()}-05", contas["despesa"],
                                      conta_pagamento_id=contas["banco"])
    titulos = sorted((t for t in sistema.listar_titulos() if t["recorrencia_id"] == rec),
                     key=lambda t: t["competencia"])
    segundo = titulos[1]

    sistema.definir_pagamento_automatico(segundo["id"], True, propagar_fixa=True)

    marcados = {t["competencia"]: t["pagamento_automatico"]
                for t in sistema.listar_titulos() if t["recorrencia_id"] == rec}
    assert marcados[titulos[0]["competencia"]] == 0
    assert marcados[segundo["competencia"]] == 1
    assert marcados[titulos[-1]["competencia"]] == 1


def test_titulo_ja_pago_nao_muda_a_forma_de_pagamento(sistema, contas, fixar_hoje):
    fixar_hoje("2026-03-20")
    titulo = sistema.salvar_titulo(None, "PAGAR", "Água", "", 70.0, "2026-03-15",
                                   contas["despesa"], None, conta_pagamento_id=contas["banco"])
    sistema.baixar_titulo(titulo, "2026-03-15", 70.0, contas["banco"])

    with pytest.raises(sistema.RegraNegocioError):
        sistema.definir_pagamento_automatico(titulo, True)


def test_lista_do_periodo_mostra_o_que_sai_sozinho(sistema, contas):
    sistema.salvar_titulo(None, "PAGAR", "Internet", "", 100.0, "2026-04-10",
                          contas["despesa"], None, conta_pagamento_id=contas["banco"],
                          pagamento_automatico=True)
    sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 60.0, "2026-04-12",
                          contas["despesa"], None, conta_pagamento_id=contas["banco"])

    automaticas = sistema.titulos_automaticos_do_periodo("2026-04-01", "2026-04-30")
    assert [t["descricao"] for t in automaticas] == ["Internet"]
