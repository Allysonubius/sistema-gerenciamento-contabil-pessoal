"""O orçamento contra a vida real: quanto entra, quanto saiu, quanto passou.

Duas coisas se encontram aqui. A primeira é a renda: o mês em andamento mostra
só o que já caiu, e planejar por esse número mandava cortar tudo para caber num
salário que ainda ia chegar. A segunda é a régua: onde não há teto definido, o
gasto não tinha com o que ser comparado — e é exatamente ali que ele cresce sem
ninguém notar.
"""
from __future__ import annotations

from datetime import date

import pytest


def meses_anteriores(sistema, quantos: int) -> list[str]:
    base = date.fromisoformat(f"{sistema.mes_atual()}-01")
    return [sistema.somar_meses(base, -n).strftime("%Y-%m")
            for n in range(quantos, 0, -1)]


@pytest.fixture(autouse=True)
def caixa_cheio(sistema, contas):
    inicio = meses_anteriores(sistema, 6)[0]
    sistema.registrar_saldo_inicial(contas["banco"], 100000.0, f"{inicio}-01")


def gastar_em(sistema, contas, competencia, valor, categoria=None, dia=10):
    return sistema.salvar_lancamento(
        None, f"{competencia}-{dia:02d}", "Compra",
        [sistema.Partida(categoria or contas["despesa"], "D", valor),
         sistema.Partida(contas["banco"], "C", valor)])


def receber_em(sistema, contas, competencia, valor, dia=5):
    return sistema.salvar_lancamento(
        None, f"{competencia}-{dia:02d}", "Salário",
        [sistema.Partida(contas["banco"], "D", valor),
         sistema.Partida(contas["receita"], "C", valor)])


@pytest.fixture()
def tres_meses(sistema, contas):
    """Três meses fechados: entraram 3.000 por mês, saíram 200, 600 e 400."""
    for competencia, gasto in zip(meses_anteriores(sistema, 3), (200.0, 600.0, 400.0)):
        receber_em(sistema, contas, competencia, 3000.0)
        gastar_em(sistema, contas, competencia, gasto)
    return contas["despesa"]


# --------------------------------------------------------------------------- #
# A renda
# --------------------------------------------------------------------------- #
def test_a_renda_tipica_sai_dos_tres_meses(sistema, contas, tres_meses):
    assert sistema.renda_tipica()["tipica"] == 3000.0
    assert sistema.renda_tipica()["meses"] == 3


def test_mes_sem_salario_ainda_planeja_pelo_que_costuma_entrar(sistema, contas, tres_meses):
    """Antes de o salário cair, o mês conhece quase nada do que vai entrar."""
    receber_em(sistema, contas, sistema.mes_atual(), 50.0)

    referencia = sistema.renda_de_referencia()
    assert referencia["do_mes"] == 50.0
    assert referencia["tipica"] == 3000.0
    assert referencia["usada"] == 3000.0
    assert referencia["origem"] == "historico"


def test_quando_o_mes_ja_supera_o_costume_vale_o_mes(sistema, contas, tres_meses):
    """Recebeu mais do que o normal? Então o número do mês é o verdadeiro."""
    receber_em(sistema, contas, sistema.mes_atual(), 8000.0)

    referencia = sistema.renda_de_referencia()
    assert referencia["usada"] == 8000.0
    assert referencia["origem"] == "mes"


def test_mes_fechado_vale_o_que_realmente_entrou(sistema, contas, tres_meses):
    """História não se corrige com média: ali vale o que aconteceu."""
    passado = meses_anteriores(sistema, 1)[0]
    referencia = sistema.renda_de_referencia(passado)

    assert referencia["origem"] == "mes"
    assert referencia["usada"] == referencia["do_mes"]


def test_o_plano_nao_corta_tudo_so_porque_o_salario_nao_caiu(sistema, contas, tres_meses):
    """Era o defeito visível: renda de 300 no mês, e o plano apertava tudo."""
    receber_em(sistema, contas, sistema.mes_atual(), 300.0)

    plano = sistema.plano_sugerido()
    assert plano["renda"] == 3000.0
    assert plano["aperta"] is False, "com a renda de verdade, o mínimo cabe"


# --------------------------------------------------------------------------- #
# O limite em vigor
# --------------------------------------------------------------------------- #
def test_sem_teto_o_limite_vem_do_historico(sistema, contas, tres_meses):
    receber_em(sistema, contas, sistema.mes_atual(), 3000.0)
    gastar_em(sistema, contas, sistema.mes_atual(), 500.0)

    linha = next(c for c in sistema.controle_de_gastos()["categorias"]
                 if c["conta_id"] == tres_meses)
    assert linha["teto"] == 0.0
    assert linha["origem_do_limite"] == "historico"
    assert linha["limite"] == 200.0, "o mês mais barato dos três"
    assert linha["excesso"] == 300.0


def test_com_teto_o_teto_e_que_manda(sistema, contas, tres_meses):
    """O que a pessoa decidiu vale mais do que o que o histórico propõe."""
    receber_em(sistema, contas, sistema.mes_atual(), 3000.0)
    sistema.definir_orcamento(tres_meses, 450.0)
    gastar_em(sistema, contas, sistema.mes_atual(), 500.0)

    linha = next(c for c in sistema.controle_de_gastos()["categorias"]
                 if c["conta_id"] == tres_meses)
    assert linha["origem_do_limite"] == "teto"
    assert linha["limite"] == 450.0
    assert linha["excesso"] == 50.0


def test_categoria_sem_historico_e_sem_teto_nao_e_cobrada(sistema, contas, tres_meses):
    receber_em(sistema, contas, sistema.mes_atual(), 3000.0)
    nova = sistema._conta_por_codigo("5.2.02")
    gastar_em(sistema, contas, sistema.mes_atual(), 900.0, nova)

    linha = next(c for c in sistema.controle_de_gastos()["categorias"]
                 if c["conta_id"] == nova)
    assert linha["origem_do_limite"] == "nenhum"
    assert linha["extrapolou"] is False


# --------------------------------------------------------------------------- #
# O excesso, em dinheiro e em fatia da renda
# --------------------------------------------------------------------------- #
def test_o_excesso_aparece_em_valor_e_em_porcentagem(sistema, contas, tres_meses):
    receber_em(sistema, contas, sistema.mes_atual(), 3000.0)
    gastar_em(sistema, contas, sistema.mes_atual(), 800.0)

    controle = sistema.controle_de_gastos()
    linha = next(c for c in controle["categorias"] if c["conta_id"] == tres_meses)

    assert linha["excesso"] == 600.0                      # 800 contra 200
    assert linha["percentual_excesso_renda"] == 20.0      # 600 de 3.000
    assert linha["percentual_gasto_renda"] == 26.7        # 800 de 3.000
    assert controle["total_extrapolado"] == 600.0
    assert controle["percentual_extrapolado"] == 20.0


def test_as_maiores_sangrias_vem_primeiro(sistema, contas, tres_meses):
    """A pergunta é onde o dinheiro vazou, e a resposta não começa no centavo."""
    outra = sistema._conta_por_codigo("5.2.02")
    for competencia in meses_anteriores(sistema, 3):
        gastar_em(sistema, contas, competencia, 100.0, outra)

    mes = sistema.mes_atual()
    receber_em(sistema, contas, mes, 3000.0)
    gastar_em(sistema, contas, mes, 300.0)             # +100 sobre 200
    gastar_em(sistema, contas, mes, 900.0, outra)      # +800 sobre 100

    extrapoladas = sistema.controle_de_gastos()["extrapoladas"]
    assert [c["conta_id"] for c in extrapoladas] == [outra, tres_meses]
    assert extrapoladas[0]["excesso"] == 800.0


def test_mes_dentro_do_orcamento_nao_acusa_nada(sistema, contas, tres_meses):
    receber_em(sistema, contas, sistema.mes_atual(), 3000.0)
    gastar_em(sistema, contas, sistema.mes_atual(), 150.0)

    controle = sistema.controle_de_gastos()
    assert controle["extrapoladas"] == []
    assert controle["total_extrapolado"] == 0.0


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


def test_a_tela_tem_um_caminho_so_para_montar_o_orcamento(sistema, contas, raiz_tk):
    """Dois botões partindo do mesmo histórico davam números diferentes."""
    import importlib

    modulo = importlib.reload(importlib.import_module("app.ui.orcamento"))
    tela = modulo.Orcamento(raiz_tk, AppFalso())
    try:
        assert not hasattr(tela, "sugerir_todos")
        assert hasattr(tela, "aplicar_plano")
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_tela_mostra_a_fatia_da_renda_e_o_excesso(sistema, contas, tres_meses, raiz_tk):
    import importlib

    mes = sistema.mes_atual()
    receber_em(sistema, contas, mes, 3000.0)
    gastar_em(sistema, contas, mes, 800.0)

    modulo = importlib.reload(importlib.import_module("app.ui.orcamento"))
    tela = modulo.Orcamento(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        colunas = [c[0] for c in tela.tabela.colunas]
        valores = dict(zip(colunas, tela.tabela.tree.item(str(tres_meses), "values")))

        assert valores["pct_gasto"] == "26.7%"
        assert "600" in valores["excesso"]
        assert "20.0%" in valores["excesso"]
        assert "Passou do orçamento" in tela.lbl_aviso.cget("text")
        assert "% do que recebo" in tela.lbl_aviso.cget("text")
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_tela_explica_quando_planeja_pelo_costume(sistema, contas, tres_meses, raiz_tk):
    """Ver 3.000 planejados com 50 na conta assusta — a tela diz de onde vem."""
    import importlib

    receber_em(sistema, contas, sistema.mes_atual(), 50.0)
    modulo = importlib.reload(importlib.import_module("app.ui.orcamento"))
    tela = modulo.Orcamento(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        assert "costumam entrar" in tela.lbl_aviso.cget("text")
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()
