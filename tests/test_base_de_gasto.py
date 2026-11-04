"""A base de gasto dos três meses, e o custo que saiu dela.

Um mês só é um retrato, e retrato não distingue hábito de acidente: o mês do
conserto virava o teto do ano. Três meses separam as duas coisas — e, onde
nunca se definiu um teto, a base passa a ser a única régua que existe, que é
justamente onde o gasto crescia sem ninguém notar.
"""
from __future__ import annotations

import pytest


def meses_anteriores(sistema, quantos: int) -> list[str]:
    """Os ``quantos`` meses fechados antes deste, do mais antigo ao mais novo."""
    from datetime import date
    base = date.fromisoformat(f"{sistema.mes_atual()}-01")
    return [sistema.somar_meses(base, -n).strftime("%Y-%m")
            for n in range(quantos, 0, -1)]


def gastar_em(sistema, contas, competencia: str, valor: float, categoria=None):
    return sistema.salvar_lancamento(
        None, f"{competencia}-10", "Compra",
        [sistema.Partida(categoria or contas["despesa"], "D", valor),
         sistema.Partida(contas["banco"], "C", valor)])


@pytest.fixture(autouse=True)
def caixa_cheio(sistema, contas):
    """Dinheiro em conta bem antes do período: estes testes falam de gasto.

    Sem isto, o primeiro lançamento antigo esbarra na regra de saldo e o teste
    deixa de medir o que foi escrito para medir.
    """
    inicio = meses_anteriores(sistema, 6)[0]
    sistema.registrar_saldo_inicial(contas["banco"], 100000.0, f"{inicio}-01")


@pytest.fixture()
def historico(sistema, contas):
    """Três meses fechados na categoria: 200, 600 e 400."""
    for competencia, valor in zip(meses_anteriores(sistema, 3), (200.0, 600.0, 400.0)):
        gastar_em(sistema, contas, competencia, valor)
    return contas["despesa"]


def linha_de(sistema, conta_id: int) -> dict:
    return next(l for l in sistema.orcamento_do_mes() if l["conta_id"] == conta_id)


# --------------------------------------------------------------------------- #
# A base
# --------------------------------------------------------------------------- #
def test_a_base_e_o_valor_do_meio_dos_tres_meses(sistema, contas, historico):
    gastar_em(sistema, contas, sistema.mes_atual(), 10.0)
    linha = linha_de(sistema, historico)

    assert linha["base"] == 400.0, "entre 200, 400 e 600, o do meio"
    assert linha["meses_base"] == 3
    assert linha["piso_historico"] == 200.0
    assert linha["topo_historico"] == 600.0


def test_um_mes_atipico_nao_vira_a_base(sistema, contas):
    """O conserto do carro não pode definir o quanto se gasta todo mês."""
    for competencia, valor in zip(meses_anteriores(sistema, 3), (300.0, 3000.0, 320.0)):
        gastar_em(sistema, contas, competencia, valor)
    gastar_em(sistema, contas, sistema.mes_atual(), 10.0)

    linha = linha_de(sistema, contas["despesa"])
    assert linha["base"] == 320.0
    assert linha["media_historica"] > linha["base"], "a média é que se deixa levar"


def test_a_janela_anda_com_o_tempo(sistema, contas, historico):
    """O quarto mês mais antigo sai da conta — a base fala da vida de agora."""
    antigo = meses_anteriores(sistema, 4)[0]
    gastar_em(sistema, contas, antigo, 9000.0)
    gastar_em(sistema, contas, sistema.mes_atual(), 10.0)

    linha = linha_de(sistema, contas["despesa"])
    assert linha["base"] == 400.0
    assert linha["topo_historico"] == 600.0, "o mês de 9.000 ficou fora da janela"


# --------------------------------------------------------------------------- #
# O custo que extrapolou
# --------------------------------------------------------------------------- #
def test_gasto_acima_da_base_e_apontado_mesmo_sem_teto(sistema, contas, historico):
    """Sem teto definido, a base é a única régua — e é onde o gasto crescia."""
    gastar_em(sistema, contas, sistema.mes_atual(), 700.0)
    linha = linha_de(sistema, historico)

    assert linha["teto"] == 0.0, "o caso é justamente o da categoria sem teto"
    assert linha["acima_da_base"] is True
    assert linha["excesso_sobre_base"] == 300.0      # 700 contra a base de 400


def test_gasto_dentro_da_base_nao_acusa_nada(sistema, contas, historico):
    gastar_em(sistema, contas, sistema.mes_atual(), 350.0)
    linha = linha_de(sistema, historico)

    assert linha["acima_da_base"] is False
    assert linha["excesso_sobre_base"] == 0.0


def test_categoria_nova_nao_e_acusada_de_extrapolar(sistema, contas):
    """Sem histórico não há base, e sem base não há do que acusar ninguém."""
    gastar_em(sistema, contas, sistema.mes_atual(), 800.0)
    linha = linha_de(sistema, contas["despesa"])

    assert linha["base"] == 0.0
    assert linha["acima_da_base"] is False
    assert linha["excesso_sobre_base"] == 0.0


def test_o_ritmo_avisa_antes_de_passar_da_base(sistema, contas, historico, fixar_hoje):
    """Avisar depois de estourar é tarde: a conta já foi."""
    mes = sistema.mes_atual()
    fixar_hoje(f"{mes}-10")
    gastar_em(sistema, contas, mes, 300.0)
    linha = linha_de(sistema, historico)

    assert linha["acima_da_base"] is False, "ainda não passou"
    assert linha["projecao"] > linha["base"]
    assert linha["vai_passar_da_base"] is True


# --------------------------------------------------------------------------- #
# O resumo
# --------------------------------------------------------------------------- #
def test_o_resumo_soma_e_ordena_os_excessos(sistema, contas, historico):
    outra = sistema._conta_por_codigo("5.2.02")
    for competencia in meses_anteriores(sistema, 3):
        gastar_em(sistema, contas, competencia, 100.0, outra)

    mes = sistema.mes_atual()
    gastar_em(sistema, contas, mes, 700.0)            # +300 sobre a base de 400
    gastar_em(sistema, contas, mes, 1200.0, outra)    # +1.100 sobre a base de 100

    resumo = sistema.resumo_orcamento()
    assert resumo["excesso_sobre_base"] == 1400.0
    nomes = [l["conta_id"] for l in resumo["acima_da_base"]]
    assert nomes[0] == outra, "o maior vazamento vem primeiro"
    assert len(nomes) == 2


def test_sem_excesso_o_resumo_fica_vazio(sistema, contas, historico):
    gastar_em(sistema, contas, sistema.mes_atual(), 50.0)
    resumo = sistema.resumo_orcamento()

    assert resumo["acima_da_base"] == []
    assert resumo["excesso_sobre_base"] == 0.0


# --------------------------------------------------------------------------- #
# O plano enxuto
# --------------------------------------------------------------------------- #
def test_a_meta_de_corte_e_um_mes_que_ja_aconteceu(sistema, contas, historico, mes_com_renda):
    """Meta inventada não se cumpre; mês que já aconteceu, sim."""
    linha = next(l for l in sistema.plano_sugerido()["categorias"]
                 if l["conta_id"] == historico)

    assert linha["minimo"] == 200.0, "o mais barato dos três"
    assert linha["sugerido"] == 200.0
    assert linha["minimo"] in (200.0, 400.0, 600.0), "é um valor real, não uma média"


@pytest.fixture()
def mes_com_renda(sistema, contas):
    mes = sistema.mes_atual()
    titulo = sistema.salvar_titulo(None, "RECEBER", "Salário", "", 5000.0, f"{mes}-05",
                                   contas["receita"], None)
    sistema.baixar_titulo(titulo, f"{mes}-05", 5000.0, contas["banco"])
    return mes


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


def test_a_tela_mostra_a_base_e_o_quanto_passou(sistema, contas, historico, raiz_tk):
    import importlib

    gastar_em(sistema, contas, sistema.mes_atual(), 700.0)
    modulo = importlib.reload(importlib.import_module("app.ui.orcamento"))
    tela = modulo.Orcamento(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        colunas = [c[0] for c in tela.tabela.colunas]
        valores = dict(zip(colunas, tela.tabela.tree.item(str(historico), "values")))

        assert "400" in valores["base"], "a base dos três meses"
        assert valores["excesso"].startswith("+"), "e quanto passou dela"
        assert "300" in valores["excesso"]
        assert "negativo" in tela.tabela.tree.item(str(historico), "tags")
        assert "Passou do que costuma gastar" in tela.lbl_aviso.cget("text")
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()
