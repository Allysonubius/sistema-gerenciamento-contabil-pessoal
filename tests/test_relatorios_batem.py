"""Os relatórios contam a mesma história que o resto da ferramenta.

Cada teste aqui nasceu de uma divergência achada ao conferir os relatórios
contra os saldos: números certos cada um no seu canto, mas que não batiam
entre si — e dois números para a mesma pergunta valem menos do que nenhum.
"""
from __future__ import annotations

import importlib
from datetime import date, timedelta

import pytest


def lancar(sistema, data_iso, debito, credito, valor, historico="Movimento"):
    return sistema.salvar_lancamento(
        None, data_iso, historico,
        [sistema.Partida(debito, "D", valor), sistema.Partida(credito, "C", valor)])


def hoje(sistema) -> date:
    return date.fromisoformat(sistema.hoje_iso())


@pytest.fixture()
def aplicacao(sistema, contas):
    """Parte do dinheiro do banco vira aplicação: muda de bolso, não some."""
    conta = sistema.criar_carteira("Reserva", "Investimento")
    sistema.marcar_como_investimento(conta)
    lancar(sistema, sistema.hoje_iso(), conta, contas["banco"], 300.0, "Aporte")
    return conta


# --------------------------------------------------------------------------- #
# Mês a mês e ano a ano: "dinheiro" é o mesmo Dinheiro das outras telas
# --------------------------------------------------------------------------- #
def test_o_dinheiro_do_mes_a_mes_e_o_mesmo_do_resto(sistema, contas, aplicacao):
    ultimo = sistema.resumo_mensal(sistema.meses_do_historico())[-1]
    totais = sistema.total_disponivel()

    assert ultimo["saldo_contas"] == totais["tem"]
    assert ultimo["saldo_guardado"] == round(totais["investido"] + totais["outros"], 2)


def test_aplicar_nao_infla_o_dinheiro_em_conta(sistema, contas, aplicacao):
    """Era o defeito: o relatório somava a aplicação e chamava tudo de 'em conta'."""
    ultimo = sistema.resumo_mensal(sistema.meses_do_historico())[-1]

    assert ultimo["saldo_guardado"] == 300.0
    assert ultimo["saldo_contas"] == sistema.total_disponivel()["tem"]
    assert ultimo["saldo_contas"] < ultimo["saldo_contas"] + ultimo["saldo_guardado"]


def test_o_ano_a_ano_fecha_com_o_mes_a_mes(sistema, contas, aplicacao):
    mes = sistema.resumo_mensal(sistema.meses_do_historico())[-1]
    ano = next(a for a in sistema.resumo_anual() if a["ano"] == mes["mes"][:4])

    assert ano["saldo_contas"] == mes["saldo_contas"]
    assert ano["saldo_guardado"] == mes["saldo_guardado"]


def test_conta_desativada_nao_reescreve_o_passado(sistema, contas):
    """O dinheiro que ela teve existiu; desativá-la não o apaga dos meses antigos."""
    antiga = sistema.criar_carteira("Banco Antigo", "Conta corrente", "", 500.0,
                                    "2026-01-01")
    lancar(sistema, "2026-02-10", contas["banco"], antiga, 500.0, "Fechei a conta")
    antes = {l["mes"]: l["saldo_contas"]
             for l in sistema.resumo_mensal(sistema.meses_do_historico())}

    sistema.definir_conta_ativa(antiga, False)
    depois = {l["mes"]: l["saldo_contas"]
              for l in sistema.resumo_mensal(sistema.meses_do_historico())}

    assert depois == antes


def test_dinheiro_mais_guardado_fecha_com_o_patrimonio(sistema, contas, aplicacao):
    """O total do que se tem, no relatório de patrimônio, é a soma das duas colunas."""
    ultimo = sistema.resumo_mensal(sistema.meses_do_historico())[-1]
    balanco = sistema.balanco(sistema.ultimo_dia_mes())

    assert round(ultimo["saldo_contas"] + ultimo["saldo_guardado"], 2) == balanco["total_ativo"]
    assert balanco["diferenca"] == 0.0


# --------------------------------------------------------------------------- #
# Categorias mês a mês: a média de cada linha soma com a do total
# --------------------------------------------------------------------------- #
def test_a_soma_das_medias_e_a_media_do_total(sistema, contas, fixar_hoje):
    fixar_hoje("2026-06-15")
    outra = sistema._conta_por_codigo("5.2.02")
    lancar(sistema, "2026-04-10", contas["despesa"], contas["banco"], 300.0)
    lancar(sistema, "2026-05-10", contas["despesa"], contas["banco"], 300.0)
    lancar(sistema, "2026-06-10", outra, contas["banco"], 90.0)       # só um mês

    meses = ["2026-04", "2026-05", "2026-06"]
    linhas = sistema.matriz_categorias(meses, "DESPESA")
    total = sum(l["total"] for l in linhas)

    assert round(sum(l["media"] for l in linhas), 2) == round(total / len(meses), 2)
    esporadica = next(l for l in linhas if l["total"] == 90.0)
    assert esporadica["media"] == 30.0, "um gasto em três meses é 30 por mês, não 90"


def test_a_matriz_fecha_com_ganhos_e_gastos(sistema, contas):
    lancar(sistema, "2026-03-10", contas["despesa"], contas["banco"], 120.0)
    lancar(sistema, "2026-04-10", contas["despesa"], contas["banco"], 80.0)

    meses = ["2026-03", "2026-04"]
    matriz = sum(l["total"] for l in sistema.matriz_categorias(meses, "DESPESA"))
    assert round(matriz, 2) == sistema.dre("2026-03-01", "2026-04-30")["total_despesas"]


# --------------------------------------------------------------------------- #
# Previsão: conta atrasada e conta de hoje também saem do bolso
# --------------------------------------------------------------------------- #
def test_conta_atrasada_entra_na_previsao(sistema, contas):
    """Quem já está devendo é quem mais precisa do fundo do poço verdadeiro."""
    ontem = (hoje(sistema) - timedelta(days=5)).isoformat()
    sistema.salvar_titulo(None, "PAGAR", "Mensalidade", "", 200.0, ontem,
                          contas["despesa"], None, multa_pct=0, juros_mes_pct=0)

    previsao = sistema.previsao_saldo(30)
    assert previsao["final"] == round(previsao["hoje"] - 200.0, 2)
    descricoes = [e["descricao"] for l in previsao["linhas"] for e in l["eventos"]]
    assert any("atrasada desde" in d for d in descricoes)


def test_conta_que_vence_hoje_entra_na_previsao(sistema, contas):
    sistema.salvar_titulo(None, "PAGAR", "Boleto de hoje", "", 150.0, sistema.hoje_iso(),
                          contas["despesa"], None)

    previsao = sistema.previsao_saldo(30)
    assert previsao["final"] == round(previsao["hoje"] - 150.0, 2)


def test_a_previsao_comeca_do_dinheiro_de_hoje(sistema, contas, aplicacao):
    previsao = sistema.previsao_saldo(30)

    assert previsao["hoje"] == sistema.total_disponivel()["tem"]
    assert previsao["linhas"][0]["eventos"] == []
    assert previsao["linhas"][0]["saldo"] == previsao["hoje"]


def test_previsao_dia_a_dia_e_mensal_chegam_ao_mesmo_saldo(sistema, contas):
    """As duas tabelas ficam lado a lado: não podem discordar."""
    base = hoje(sistema)
    atrasada = (base - timedelta(days=10)).isoformat()
    sistema.salvar_titulo(None, "PAGAR", "Atrasada", "", 100.0, atrasada,
                          contas["despesa"], None, multa_pct=2, juros_mes_pct=1)
    sistema.salvar_titulo(None, "PAGAR", "De hoje", "", 50.0, base.isoformat(),
                          contas["despesa"], None)
    sistema.salvar_titulo(None, "RECEBER", "Vai entrar", "", 400.0,
                          (base + timedelta(days=3)).isoformat(), contas["receita"], None)

    fim_do_mes = date.fromisoformat(sistema.ultimo_dia_mes(base))
    dias = (fim_do_mes - base).days
    diaria = sistema.previsao_saldo(dias)
    mensal = sistema.previsao_mensal(1)[0]

    em_aberto_no_mes = [
        t for t in sistema.titulos_com_encargos(status="ABERTO")
        if t["vencimento"] <= fim_do_mes.isoformat()]
    assert len(em_aberto_no_mes) >= 2
    assert mensal["saldo_projetado"] == diaria["final"]


def test_o_menor_saldo_considera_o_que_ja_venceu(sistema, contas):
    ontem = (hoje(sistema) - timedelta(days=1)).isoformat()
    sistema.salvar_titulo(None, "PAGAR", "Grande e atrasada", "", 5000.0, ontem,
                          contas["despesa"], None, multa_pct=0, juros_mes_pct=0)

    previsao = sistema.previsao_saldo(30)
    assert previsao["negativa"] is True
    assert previsao["menor_data"] == sistema.hoje_iso()


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


@pytest.fixture()
def tela(sistema, contas, raiz_tk):
    modulo = importlib.reload(importlib.import_module("app.ui.relatorios"))
    relatorios = modulo.Relatorios(raiz_tk, AppFalso())
    yield relatorios
    for filho in raiz_tk.winfo_children():
        filho.destroy()


def test_ganhos_e_gastos_sem_receita_nao_inventa_porcentagem(sistema, contas, tela):
    """Dividir por um transformava um gasto de 900 em '90000%'."""
    lancar(sistema, sistema.hoje_iso(), contas["despesa"], contas["banco"], 900.0)
    tela._gerar_dre(sistema.primeiro_dia_mes(), sistema.ultimo_dia_mes())

    pesos = [tela.tab_dre.tree.item(i, "values")[3]
             for i in tela.tab_dre.tree.get_children()]
    assert all(p == "—" for p in pesos), pesos


def test_ganhos_e_gastos_com_receita_mede_o_peso(sistema, contas, tela):
    lancar(sistema, sistema.hoje_iso(), contas["banco"], contas["receita"], 1000.0)
    lancar(sistema, sistema.hoje_iso(), contas["despesa"], contas["banco"], 250.0)
    tela._gerar_dre(sistema.primeiro_dia_mes(), sistema.ultimo_dia_mes())

    linhas = [tela.tab_dre.tree.item(i, "values") for i in tela.tab_dre.tree.get_children()]
    saiu = next(l for l in linhas if l[1] == "TOTAL QUE SAIU")
    assert saiu[3] == "25%"


def test_o_mes_a_mes_mostra_dinheiro_e_guardado_separados(sistema, contas, aplicacao, tela):
    tela._gerar_mes_a_mes("", "")
    colunas = [c[0] for c in tela.tab_mensal.colunas]
    ultima = tela.tab_mensal.tree.get_children()[-1]
    valores = dict(zip(colunas, tela.tab_mensal.tree.item(ultima, "values")))

    assert valores["saldo"] == sistema.moeda(sistema.total_disponivel()["tem"])
    assert valores["guardado"] == "300,00"


def test_todos_os_relatorios_abrem_sem_erro(sistema, contas, aplicacao, tela):
    for indice in range(9):
        tela._trocar(indice)
