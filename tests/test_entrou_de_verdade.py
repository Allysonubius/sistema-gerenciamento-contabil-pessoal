"""O que entrou é o que caiu na conta — e no mês em que a conta é do mês.

Duas coisas se escondiam. O salário de novembro pago no dia 31 de outubro
sumia de novembro, porque "Entrou" contava pela data do pagamento enquanto a
lista contava pelo vencimento. E a linha mostrava o valor combinado, não o que
caiu: receber 1.840 de um salário de 3.000 aparecia como 5.000.
"""
from __future__ import annotations

import importlib
from datetime import date

import pytest


class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass

    def ir_para(self, _destino) -> None:
        pass


@pytest.fixture()
def salario(sistema, contas):
    """Salário de 5.000 com vencimento no dia 1º deste mês."""
    mes = sistema.mes_atual()
    titulo = sistema.salvar_titulo(None, "RECEBER", "Empresa", "", 3000.0,
                                   f"{mes}-01", contas["receita"], None)
    return titulo, mes


def fim_do_mes(sistema, competencia: str) -> str:
    """O último dia que existe naquele mês — 31 não serve para todo mês."""
    return sistema.ultimo_dia_mes(date.fromisoformat(f"{competencia}-01"))


def primeiro_dia(sistema) -> str:
    return f"{sistema.mes_atual()}-01"


def ultimo_dia(sistema) -> str:
    return sistema.ultimo_dia_mes()


# --------------------------------------------------------------------------- #
# O mês em que o dinheiro conta
# --------------------------------------------------------------------------- #
def test_recebido_antes_do_vencimento_conta_no_mes_da_conta(sistema, contas, salario):
    """Pago em 31 de outubro, mas é o salário de novembro."""
    titulo, mes = salario
    anterior = sistema._mes_anterior(mes)
    sistema.baixar_titulo(titulo, fim_do_mes(sistema, anterior), 3000.0, contas["banco"])

    entrou = sistema.recebido_no_periodo(primeiro_dia(sistema), ultimo_dia(sistema))
    assert entrou["recebido"] == 3000.0
    assert entrou["quantas"] == 1


def test_o_mes_anterior_nao_fica_com_o_dinheiro_de_novembro(sistema, contas, salario):
    titulo, mes = salario
    anterior = sistema._mes_anterior(mes)
    sistema.baixar_titulo(titulo, fim_do_mes(sistema, anterior), 3000.0, contas["banco"])

    entrou = sistema.recebido_no_periodo(f"{anterior}-01", fim_do_mes(sistema, anterior))
    assert entrou["recebido"] == 0.0


def test_pelo_mes_de_referencia_tambem_conta(sistema, contas, salario):
    titulo, mes = salario
    sistema.baixar_titulo(titulo, f"{mes}-05", 3000.0, contas["banco"])

    entrou = sistema.recebido_no_periodo(primeiro_dia(sistema), ultimo_dia(sistema),
                                         criterio="competencia")
    assert entrou["recebido"] == 3000.0


# --------------------------------------------------------------------------- #
# O valor que realmente entrou
# --------------------------------------------------------------------------- #
def test_entrou_o_que_caiu_e_nao_o_combinado(sistema, contas, salario):
    titulo, mes = salario
    sistema.baixar_titulo(titulo, f"{mes}-02", 1840.55, contas["banco"])

    entrou = sistema.recebido_no_periodo(primeiro_dia(sistema), ultimo_dia(sistema))
    assert entrou["recebido"] == 1840.55
    assert entrou["combinado"] == 3000.0
    assert entrou["diferenca"] == -1159.45


def test_receber_a_mais_tambem_aparece(sistema, contas, salario):
    titulo, mes = salario
    sistema.baixar_titulo(titulo, f"{mes}-02", 3200.0, contas["banco"])

    entrou = sistema.recebido_no_periodo(primeiro_dia(sistema), ultimo_dia(sistema))
    assert entrou["recebido"] == 3200.0
    assert entrou["diferenca"] == 200.0


def test_sem_recebimento_nao_inventa_diferenca(sistema, contas, salario):
    entrou = sistema.recebido_no_periodo(primeiro_dia(sistema), ultimo_dia(sistema))
    assert entrou == {"recebido": 0.0, "combinado": 0.0, "diferenca": 0.0, "quantas": 0}


def test_criterio_invalido_e_recusado(sistema, contas):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.recebido_no_periodo(primeiro_dia(sistema), ultimo_dia(sistema),
                                    criterio="chute")


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
def test_o_rodape_mostra_o_que_entrou_e_a_diferenca(sistema, contas, salario, raiz_tk):
    titulo, mes = salario
    anterior = sistema._mes_anterior(mes)
    sistema.baixar_titulo(titulo, fim_do_mes(sistema, anterior), 1840.55, contas["banco"])

    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        texto = tela.lbl_entrou.cget("text")
        assert "1.840,55" in texto, "o que caiu, mesmo pago no mês anterior"
        assert "3.000,00" in texto, "e o previsto, para a diferença aparecer"
        assert "a menos" in texto
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_linha_mostra_o_valor_que_realmente_entrou(sistema, contas, salario, raiz_tk):
    titulo, mes = salario
    sistema.baixar_titulo(titulo, f"{mes}-02", 1840.55, contas["banco"])

    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.cb_status.set("Todas")
        tela.recarregar()
        colunas = [c[0] for c in tela.tabela.colunas]
        valores = dict(zip(colunas, tela.tabela.tree.item(str(titulo), "values")))

        assert valores["valor"] == "3.000,00", "o combinado continua à vista"
        assert "1.840,55" in valores["real"], "e o que caiu, ao lado"
        assert "▼" in valores["real"], "com a marca de que veio menos"
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_conta_em_aberto_nao_finge_ter_entrado(sistema, contas, salario, raiz_tk):
    titulo, _mes = salario
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        colunas = [c[0] for c in tela.tabela.colunas]
        valores = dict(zip(colunas, tela.tabela.tree.item(str(titulo), "values")))
        assert valores["real"] == "—"
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()
