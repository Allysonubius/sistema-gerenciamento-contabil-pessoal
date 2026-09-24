"""Conta não paga no mês anterior continua aparecendo nos meses seguintes."""
from __future__ import annotations

from datetime import date


def meses(sistema, deslocamento: int) -> tuple[str, str]:
    base = sistema.somar_meses(date.today().replace(day=1), deslocamento)
    return sistema.primeiro_dia_mes(base), sistema.ultimo_dia_mes(base)


def conta(sistema, contas, descricao, vencimento, valor=100.0):
    return sistema.salvar_titulo(None, "PAGAR", descricao, "", valor, vencimento,
                                 contas["despesa"], None, multa_pct=2.0, juros_mes_pct=1.0)


def descricoes(lista):
    return [t["descricao"] for t in lista]


def test_conta_do_mes_passado_nao_paga_entra_no_mes_atual(sistema, contas):
    inicio_passado, _ = meses(sistema, -1)
    conta(sistema, contas, "Luz de agosto", inicio_passado)
    inicio, fim = meses(sistema, 0)

    sem = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim)
    com = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim, trazer_atrasadas=True)

    assert "Luz de agosto" not in descricoes(sem)
    assert "Luz de agosto" in descricoes(com)


def test_pendencia_acumula_varios_meses(sistema, contas):
    for n, nome in ((-3, "Junho"), (-2, "Julho"), (-1, "Agosto")):
        conta(sistema, contas, nome, meses(sistema, n)[0], valor=50.0)
    inicio, fim = meses(sistema, 0)
    lista = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim, trazer_atrasadas=True)
    assert descricoes(lista)[:3] == ["Junho", "Julho", "Agosto"]    # mais antigas primeiro
    assert sum(t["valor"] for t in lista) == 150.0


def test_conta_paga_nao_e_carregada(sistema, contas):
    passado = meses(sistema, -1)[0]
    titulo = conta(sistema, contas, "Paga", passado)
    sistema.baixar_titulo(titulo, passado, 100.0, contas["banco"])
    inicio, fim = meses(sistema, 0)
    lista = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim, trazer_atrasadas=True)
    assert "Paga" not in descricoes(lista)


def test_continua_nos_meses_futuros_ate_ser_paga(sistema, contas):
    conta(sistema, contas, "Esquecida", meses(sistema, -1)[0])
    inicio, fim = meses(sistema, 2)
    lista = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim, trazer_atrasadas=True)
    assert "Esquecida" in descricoes(lista)


def test_nao_duplica_quando_ja_esta_no_periodo(sistema, contas):
    conta(sistema, contas, "Atrasada", meses(sistema, -1)[0])
    inicio, _ = meses(sistema, -1)
    _, fim = meses(sistema, 0)
    lista = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim, trazer_atrasadas=True)
    assert descricoes(lista).count("Atrasada") == 1


def test_outros_filtros_valem_para_as_pendencias(sistema, contas):
    conta(sistema, contas, "Luz", meses(sistema, -1)[0])
    conta(sistema, contas, "Internet", meses(sistema, -1)[0])
    inicio, fim = meses(sistema, 0)
    lista = sistema.listar_titulos(status="ABERTO", desde=inicio, ate=fim, texto="luz",
                                   trazer_atrasadas=True)
    assert descricoes(lista) == ["Luz"]


def test_pendencia_carregada_tem_multa_e_juros_calculados(sistema, contas):
    conta(sistema, contas, "Aluguel", meses(sistema, -2)[0], valor=1000.0)
    inicio, fim = meses(sistema, 0)
    item = next(t for t in sistema.titulos_com_encargos(status="ABERTO", desde=inicio, ate=fim,
                                                        trazer_atrasadas=True)
                if t["descricao"] == "Aluguel")
    assert item["encargos"]["multa"] == 20.0
    assert item["valor_atualizado"] > 1020.0
