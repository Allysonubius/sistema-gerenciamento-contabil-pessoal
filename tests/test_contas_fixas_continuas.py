"""Conta fixa continua para a frente até ser desmarcada."""
from __future__ import annotations

from datetime import date


def meses_da(sistema, recorrencia_id):
    return sorted(t["competencia"] for t in sistema.listar_titulos()
                  if t["recorrencia_id"] == recorrencia_id)


def mais_meses(sistema, competencia: str, quantidade: int) -> str:
    base = date.fromisoformat(f"{competencia}-01")
    return sistema.somar_meses(base, quantidade).strftime("%Y-%m")


def criar(sistema, contas, vencimento=None, meses=0):
    vencimento = vencimento or sistema.hoje_iso()
    return sistema.criar_conta_fixa("PAGAR", "Internet", "", 139.9, vencimento,
                                    contas["despesa"], meses=meses,
                                    conta_pagamento_id=contas["banco"])


def test_sempre_ha_um_ano_lancado_a_frente(sistema, contas):
    recorrencia, lancados = criar(sistema, contas)
    meses = meses_da(sistema, recorrencia)
    assert lancados == len(meses)
    assert meses[0] == sistema.mes_atual()
    assert meses[-1] >= mais_meses(sistema, sistema.mes_atual(), 12)


def test_ver_um_mes_distante_lanca_os_meses_ate_la(sistema, contas):
    recorrencia, _ = criar(sistema, contas)
    daqui_3_anos = mais_meses(sistema, sistema.mes_atual(), 36)

    sistema.gerar_titulos_recorrentes(ate_competencia=f"{daqui_3_anos}-15")

    meses = meses_da(sistema, recorrencia)
    assert daqui_3_anos in meses
    # contínuo: nenhum buraco entre o primeiro e o último mês
    assert len(meses) == len(set(meses)) == 37


def test_futuro_tem_teto_de_seguranca(sistema, contas):
    recorrencia, _ = criar(sistema, contas)
    sistema.gerar_titulos_recorrentes(ate_competencia="2999-12-31")
    assert len(meses_da(sistema, recorrencia)) <= sistema.MESES_MAXIMO_A_FRENTE + 1


def test_sem_prazo_continua_quando_o_tempo_passa(sistema, contas):
    """Simula a passagem do tempo: a série segue de onde parou, sem duplicar."""
    recorrencia, _ = criar(sistema, contas)
    ultimo = meses_da(sistema, recorrencia)[-1]
    sistema.gerar_titulos_recorrentes(ate_competencia=mais_meses(sistema, ultimo, 6))
    meses = meses_da(sistema, recorrencia)
    assert meses[-1] == mais_meses(sistema, ultimo, 6)
    assert len(meses) == len(set(meses))


def test_com_prazo_para_no_ultimo_mes(sistema, contas):
    recorrencia, lancados = criar(sistema, contas, meses=3)
    sistema.gerar_titulos_recorrentes(ate_competencia=mais_meses(sistema, sistema.mes_atual(), 24))
    assert lancados == 3
    assert len(meses_da(sistema, recorrencia)) == 3


def test_primeiro_mes_passado_e_lancado_ao_criar(sistema, contas):
    passado = mais_meses(sistema, sistema.mes_atual(), -2)
    recorrencia, _ = criar(sistema, contas, vencimento=f"{passado}-10")
    meses = meses_da(sistema, recorrencia)
    assert meses[0] == passado
    assert sistema.mes_atual() in meses


def test_desmarcar_mantem_o_mes_e_remove_os_seguintes(sistema, contas):
    recorrencia, _ = criar(sistema, contas)
    meses = meses_da(sistema, recorrencia)
    ultimo_que_fica = meses[2]

    removidos = sistema.encerrar_recorrencia(recorrencia, ultimo_mes=ultimo_que_fica)

    assert removidos == len(meses) - 3
    assert meses_da(sistema, recorrencia) == meses[:3]
    # e não volta a gerar sozinha
    sistema.gerar_titulos_recorrentes(ate_competencia=mais_meses(sistema, sistema.mes_atual(), 24))
    assert meses_da(sistema, recorrencia) == meses[:3]


def test_desmarcar_nao_apaga_meses_pagos(sistema, contas):
    recorrencia, _ = criar(sistema, contas)
    titulos = sorted((t for t in sistema.listar_titulos() if t["recorrencia_id"] == recorrencia),
                     key=lambda t: t["competencia"])
    futuro_pago = titulos[5]
    sistema.baixar_titulo(futuro_pago["id"], sistema.hoje_iso(), 139.9, contas["banco"])

    sistema.encerrar_recorrencia(recorrencia, ultimo_mes=titulos[0]["competencia"])

    restantes = meses_da(sistema, recorrencia)
    assert futuro_pago["competencia"] in restantes


def test_marcar_conta_avulsa_como_fixa_sem_duplicar(sistema, contas):
    titulo = sistema.salvar_titulo(None, "PAGAR", "Academia", "", 99.0, sistema.hoje_iso(),
                                   contas["despesa"], None)
    criados = sistema.tornar_recorrente(titulo)

    recorrencia = sistema.obter_titulo(titulo)["recorrencia_id"]
    meses = meses_da(sistema, recorrencia)
    assert recorrencia is not None
    assert criados >= 12
    assert meses.count(sistema.mes_atual()) == 1          # a própria conta é o 1º mês
    assert len(meses) == criados + 1


def test_reativar_encerrada_volta_a_gerar(sistema, contas):
    recorrencia, _ = criar(sistema, contas)
    sistema.encerrar_recorrencia(recorrencia, ultimo_mes=sistema.mes_atual())
    assert meses_da(sistema, recorrencia) == [sistema.mes_atual()]

    criados = sistema.reativar_recorrencia(recorrencia)

    assert criados >= 12
    assert len(meses_da(sistema, recorrencia)) > 12


def test_pausar_mantem_o_mes_atual_e_tira_os_seguintes(sistema, contas):
    """Pausada não pode seguir contando nos meses à frente."""
    recorrencia, _ = criar(sistema, contas)
    assert len(meses_da(sistema, recorrencia)) > 1

    sistema.pausar_recorrencia(recorrencia)
    sistema.gerar_titulos_recorrentes(ate_competencia=mais_meses(sistema, sistema.mes_atual(), 30))

    assert meses_da(sistema, recorrencia) == [sistema.mes_atual()]
