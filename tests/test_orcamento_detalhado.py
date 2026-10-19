"""Orçamento: comprometido, projeção honesta e histórico da categoria."""
from __future__ import annotations

import pytest


@pytest.fixture()
def mes(sistema):
    return sistema.mes_atual()


def gastar(sistema, contas, valor, dia, categoria=None):
    return sistema.salvar_lancamento(
        None, f"{sistema.mes_atual()}-{dia:02d}", "Compra",
        [sistema.Partida(categoria or contas["despesa"], "D", valor),
         sistema.Partida(contas["banco"], "C", valor)])


# --- o que já tem dono ------------------------------------------------------ #
def test_conta_em_aberto_entra_como_comprometido(sistema, contas, mes):
    sistema.definir_orcamento(contas["despesa"], 1000.0)
    gastar(sistema, contas, 200.0, 3)
    sistema.salvar_titulo(None, "PAGAR", "Boleto do mês", "", 300.0, f"{mes}-28",
                          contas["despesa"], None)

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    assert linha["gasto"] == 200.0
    assert linha["comprometido"] == 300.0
    assert linha["restante"] == 800.0        # só o que saiu
    assert linha["livre"] == 500.0           # descontando o que já tem dono


def test_conta_paga_nao_conta_duas_vezes(sistema, contas, mes):
    sistema.definir_orcamento(contas["despesa"], 1000.0)
    titulo = sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 300.0, f"{mes}-10",
                                   contas["despesa"], None)
    sistema.baixar_titulo(titulo, f"{mes}-10", 300.0, contas["banco"])

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    assert linha["gasto"] == 300.0
    assert linha["comprometido"] == 0.0      # já virou gasto
    assert linha["livre"] == 700.0


def test_categoria_so_com_conta_a_pagar_aparece(sistema, contas, mes):
    """Mesmo sem nada gasto ainda, o que está contratado precisa ser visto."""
    sistema.salvar_titulo(None, "PAGAR", "Seguro", "", 150.0, f"{mes}-25",
                          contas["despesa"], None)

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    assert linha["gasto"] == 0.0
    assert linha["comprometido"] == 150.0


# --- projeção --------------------------------------------------------------- #
def test_projecao_soma_gasto_comprometido_e_estimativa(sistema, contas, mes, fixar_hoje):
    fixar_hoje(f"{mes}-10")
    sistema.definir_orcamento(contas["despesa"], 1000.0)
    gastar(sistema, contas, 200.0, 5)
    sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 300.0, f"{mes}-28",
                          contas["despesa"], None)

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    # 200 já gastos + 300 contratados + o ritmo do dia a dia até o fim do mês.
    assert linha["projecao"] > 500.0
    assert linha["projecao"] >= linha["gasto"] + linha["comprometido"]


def test_mes_fechado_nao_projeta_nada_a_mais(sistema, contas):
    """Mês passado não tem futuro: a projeção é o que aconteceu."""
    anterior = sistema._mes_anterior(sistema.mes_atual())
    sistema.salvar_lancamento(
        None, f"{anterior}-10", "Compra",
        [sistema.Partida(contas["despesa"], "D", 400.0),
         sistema.Partida(contas["banco"], "C", 400.0)])

    linha = next(l for l in sistema.orcamento_do_mes(anterior)
                 if l["conta_id"] == contas["despesa"])
    assert linha["projecao"] == 400.0


def test_gasto_grande_no_dia_2_nao_vira_projecao_absurda(sistema, contas, mes, fixar_hoje):
    """A extrapolação linear dizia que um gasto no dia 2 viraria 15x no mês."""
    fixar_hoje(f"{mes}-02")
    gastar(sistema, contas, 500.0, 2)

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    assert linha["projecao"] < 500.0 * 5


def test_risco_considera_o_que_ja_tem_dono(sistema, contas, mes, fixar_hoje):
    fixar_hoje(f"{mes}-10")
    sistema.definir_orcamento(contas["despesa"], 500.0)
    gastar(sistema, contas, 100.0, 3)
    sistema.salvar_titulo(None, "PAGAR", "Boleto grande", "", 450.0, f"{mes}-28",
                          contas["despesa"], None)

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    assert linha["estourou"] is False        # ainda não saiu do bolso
    assert linha["risco"] is True            # mas vai estourar


# --- histórico e sugestão --------------------------------------------------- #
def meses_anteriores(sistema, quantos: int) -> list[str]:
    """Os meses fechados mais recentes, do mais antigo para o mais novo."""
    competencia = sistema.mes_atual()
    meses = []
    for _ in range(quantos):
        competencia = sistema._mes_anterior(competencia)
        meses.append(competencia)
    return list(reversed(meses))


def test_sugestao_usa_o_mes_passado(sistema, contas):
    """O retrato mais próximo da vida de agora é o mês que acabou."""
    valores = [200.0, 210.0, 2000.0, 190.0]
    for competencia, valor in zip(meses_anteriores(sistema, 4), valores):
        sistema.salvar_lancamento(
            None, f"{competencia}-10", "Compra",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])

    assert sistema.sugerir_orcamento(contas["despesa"]) == 190.0      # o último mês


def test_com_janela_maior_a_mediana_segura_o_mes_atipico(sistema, contas):
    """Quem pedir mais meses não pode ser traído pela média."""
    valores = [200.0, 210.0, 2000.0, 190.0]
    for competencia, valor in zip(meses_anteriores(sistema, 4), valores):
        sistema.salvar_lancamento(
            None, f"{competencia}-10", "Compra",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])

    mediana = sistema.sugerir_orcamento(contas["despesa"], meses=4)
    media = sistema.sugerir_orcamento(contas["despesa"], meses=4, metodo="media")
    assert mediana == 205.0
    assert media > 600.0


def test_mostra_o_gasto_do_mes_passado_e_se_estourou(sistema, contas):
    sistema.definir_orcamento(contas["despesa"], 100.0)
    for competencia, valor in zip(meses_anteriores(sistema, 3), (300.0, 50.0, 400.0)):
        sistema.salvar_lancamento(
            None, f"{competencia}-10", "Compra",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])

    linha = next(l for l in sistema.orcamento_do_mes()
                 if l["conta_id"] == contas["despesa"])
    assert linha["mediana_historica"] == 400.0      # o mês passado
    assert linha["estouros_anteriores"] == 1        # e ele estourou o teto


def test_sem_historico_nao_inventa_teto(sistema, contas):
    assert sistema.sugerir_orcamento(contas["despesa"]) == 0.0


# --- resumo contra a renda -------------------------------------------------- #
def test_resumo_compara_o_planejado_com_a_renda(sistema, contas, mes):
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 3000.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 3000.0, contas["banco"])
    sistema.salvar_titulo(None, "RECEBER", "Freela", "", 1000.0, f"{mes}-20",
                          contas["receita"], None)
    sistema.definir_orcamento(contas["despesa"], 1000.0)

    resumo = sistema.resumo_orcamento()
    assert resumo["renda"]["recebido"] == 3000.0
    assert resumo["renda"]["a_receber"] == 1000.0
    assert resumo["renda"]["total"] == 4000.0
    assert resumo["percentual_da_renda"] == 25.0


def test_sobra_prevista_desconta_a_projecao(sistema, contas, mes, fixar_hoje):
    fixar_hoje(f"{mes}-15")
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 2000.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 2000.0, contas["banco"])
    gastar(sistema, contas, 600.0, 10)

    resumo = sistema.resumo_orcamento()
    assert resumo["sobra_prevista"] == round(2000.0 - resumo["projecao"], 2)
    assert resumo["sobra_prevista"] < 1400.0     # conta o que ainda vai gastar


def test_mes_futuro_so_conta_o_que_ja_esta_agendado(sistema, contas, mes):
    """Mês que não começou não tem ritmo — projetar o gasto típico era ficção."""
    for competencia in meses_anteriores(sistema, 4):      # histórico gordo
        sistema.salvar_lancamento(
            None, f"{competencia}-10", "Compra",
            [sistema.Partida(contas["despesa"], "D", 3000.0),
             sistema.Partida(contas["banco"], "C", 3000.0)])
    seguinte = sistema._mes_seguinte(mes)
    sistema.salvar_titulo(None, "PAGAR", "Aluguel", "", 400.0, f"{seguinte}-10",
                          contas["despesa"], None)

    resumo = sistema.resumo_orcamento(seguinte)
    assert resumo["comprometido"] == 400.0
    assert resumo["projecao"] == 400.0        # nada de extrapolar os 3.000


def test_projecao_nao_cresce_de_mes_em_mes(sistema, contas, mes):
    for competencia in meses_anteriores(sistema, 4):
        sistema.salvar_lancamento(
            None, f"{competencia}-10", "Compra",
            [sistema.Partida(contas["despesa"], "D", 2000.0),
             sistema.Partida(contas["banco"], "C", 2000.0)])

    seguinte = sistema._mes_seguinte(mes)
    depois = sistema._mes_seguinte(seguinte)
    assert sistema.resumo_orcamento(seguinte)["projecao"] == 0.0
    assert sistema.resumo_orcamento(depois)["projecao"] == 0.0


def test_limite_para_fechar_no_azul(sistema, contas, mes, fixar_hoje):
    fixar_hoje(f"{mes}-15")
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 2000.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 2000.0, contas["banco"])
    gastar(sistema, contas, 500.0, 10)
    sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 300.0, f"{mes}-28",
                          contas["despesa"], None)

    resumo = sistema.resumo_orcamento()
    # 2000 que entram - 500 gastos - 300 com dono.
    assert resumo["limite_ate_o_fim"] == 1200.0


def test_limite_zera_quando_a_renda_acabou(sistema, contas, mes, fixar_hoje):
    fixar_hoje(f"{mes}-15")
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 500.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 500.0, contas["banco"])
    gastar(sistema, contas, 900.0, 10)

    assert sistema.resumo_orcamento()["limite_ate_o_fim"] == 0.0


# --- plano enxuto ----------------------------------------------------------- #
@pytest.fixture()
def historico_variado(sistema, contas):
    """Três meses na categoria: 400, 150 e 300 — no mês passado gastou 300."""
    for competencia, valor in zip(meses_anteriores(sistema, 3), (400.0, 150.0, 300.0)):
        sistema.salvar_lancamento(
            None, f"{competencia}-10", "Compra",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])
    return contas["despesa"]


def test_plano_parte_do_mes_passado(sistema, contas, mes, historico_variado):
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 3000.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 3000.0, contas["banco"])

    plano = sistema.plano_sugerido()
    linha = next(l for l in plano["categorias"] if l["conta_id"] == historico_variado)
    assert linha["minimo"] == 300.0           # o mês que acabou, não meio ano atrás
    assert linha["sugerido"] == 300.0
    assert plano["aperta"] is False


def test_plano_mostra_a_fatia_da_renda(sistema, contas, mes, historico_variado):
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 1500.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 1500.0, contas["banco"])

    plano = sistema.plano_sugerido()
    linha = next(l for l in plano["categorias"] if l["conta_id"] == historico_variado)
    assert linha["percentual_renda"] == 20.0  # 300 de 1.500
    assert plano["percentual_da_renda"] == 20.0
    assert plano["sobra"] == 1200.0


def test_conta_fixa_do_mes_e_piso_do_plano(sistema, contas, mes, historico_variado):
    """O que já está contratado não se corta: ele é o piso da categoria."""
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 3000.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 3000.0, contas["banco"])
    sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 500.0, f"{mes}-20",
                          contas["despesa"], None)

    linha = next(l for l in sistema.plano_sugerido()["categorias"]
                 if l["conta_id"] == historico_variado)
    assert linha["fixo"] == 500.0
    assert linha["sugerido"] >= 500.0         # nunca abaixo do contratado


def test_quando_nem_o_minimo_cabe_o_plano_corta_proporcional(sistema, contas, mes,
                                                             historico_variado):
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 100.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 100.0, contas["banco"])

    plano = sistema.plano_sugerido()
    assert plano["aperta"] is True
    assert plano["fator"] < 1.0
    assert plano["total_sugerido"] <= 100.0


def test_aplicar_plano_grava_os_tetos(sistema, contas, mes, historico_variado):
    salario = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 3000.0, f"{mes}-05",
                                    contas["receita"], None)
    sistema.baixar_titulo(salario, f"{mes}-05", 3000.0, contas["banco"])

    quantas = sistema.aplicar_plano_sugerido()

    assert quantas >= 1
    teto, _ = sistema.teto_da_categoria(historico_variado, mes)
    assert teto == 300.0


def test_plano_do_mes_seguinte_olha_o_mes_atual(sistema, contas, mes, historico_variado):
    """Para planejar novembro, o espelho é outubro — não o semestre inteiro."""
    gastar(sistema, contas, 250.0, 8)         # o gasto deste mês
    seguinte = sistema._mes_seguinte(mes)
    sistema.salvar_titulo(None, "RECEBER", "Salário", "", 5000.0, f"{seguinte}-05",
                          contas["receita"], None)

    plano = sistema.plano_sugerido(seguinte)
    linha = next(l for l in plano["categorias"] if l["conta_id"] == historico_variado)
    assert plano["renda"] == 5000.0
    assert linha["sugerido"] == 250.0
    assert plano["aperta"] is False


def test_categorias_sem_teto_relevantes_sao_apontadas(sistema, contas, mes):
    gastar(sistema, contas, 250.0, 4)

    resumo = sistema.resumo_orcamento()
    nomes = [l["conta_id"] for l in resumo["sem_teto_relevantes"]]
    assert contas["despesa"] in nomes
