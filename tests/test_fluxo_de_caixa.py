"""O painel fala de dinheiro, e o número tem de fechar com o saldo.

Antes, "sobrou este mês" vinha da DRE (receitas − despesas) e ignorava o
dinheiro que saiu para pagar dívida ou virar aplicação: dizia que haviam
sobrado 459,48 num mês que terminou com 8,99 na conta.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def mes(sistema, contas):
    """Ferramentas para montar um mês inteiro de movimento."""
    def recebeu(valor: float, data_iso: str = "2026-03-05") -> None:
        sistema.salvar_lancamento(
            None, data_iso, "Salário",
            [sistema.Partida(contas["banco"], "D", valor),
             sistema.Partida(contas["receita"], "C", valor)])

    def gastou(valor: float, data_iso: str = "2026-03-10") -> None:
        sistema.salvar_lancamento(
            None, data_iso, "Mercado",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])

    return {"recebeu": recebeu, "gastou": gastou}


def fluxo(sistema):
    return sistema.fluxo_de_caixa("2026-03-01", "2026-03-31")


def test_o_saldo_do_comeco_mais_o_que_sobrou_da_o_saldo_de_hoje(sistema, contas, mes):
    mes["recebeu"](2000.0)
    mes["gastou"](500.0)
    f = fluxo(sistema)

    assert f["saldo_inicial"] + f["sobrou"] == f["saldo_final"]
    assert f["saldo_final"] == sistema.total_disponivel("2026-03-31")["tem"]


def test_entrou_menos_saiu_e_o_que_sobrou(sistema, contas, mes):
    mes["recebeu"](2000.0)
    mes["gastou"](500.0)
    f = fluxo(sistema)

    assert f["entrou"] == 2000.0
    assert f["saiu"] == 500.0
    assert f["sobrou"] == 1500.0


def test_pagar_divida_sai_do_caixa_mesmo_sem_ser_despesa(sistema, contas, mes):
    """É exatamente o que fazia o painel mentir."""
    divida = sistema.criar_divida("Mensalidade", "Escola", 440.0, "2026-02-01")
    mes["recebeu"](1000.0)
    sistema.pagar_divida(divida, 440.0, contas["banco"], "2026-03-15")
    f = fluxo(sistema)

    assert f["saiu"] == 440.0
    assert f["saidas"]["dividas"] == 440.0
    assert f["sobrou"] == 560.0
    # A DRE não enxerga esse pagamento: ele não é gasto, é dívida que diminuiu.
    assert sistema.dre("2026-03-01", "2026-03-31")["resultado"] == 1000.0


def test_dinheiro_aplicado_sai_do_caixa(sistema, contas, mes):
    aplicacao = sistema.criar_carteira("CDB", "Investimento")
    sistema.marcar_como_investimento(aplicacao)
    mes["recebeu"](1000.0)
    sistema.transferir(contas["banco"], aplicacao, 300.0, "2026-03-20")
    f = fluxo(sistema)

    assert f["saidas"]["aplicado"] == 300.0
    assert f["sobrou"] == 700.0


def test_transferir_entre_contas_de_dinheiro_nao_conta(sistema, contas, mes):
    """O dinheiro só mudou de lugar: não entrou nem saiu."""
    mes["recebeu"](1000.0)
    sistema.transferir(contas["banco"], contas["outra"], 250.0, "2026-03-20")
    f = fluxo(sistema)

    assert f["entrou"] == 1000.0
    assert f["saiu"] == 0.0
    assert f["sobrou"] == 1000.0


def test_gasto_no_cartao_nao_sai_do_caixa_agora(sistema, contas, mes):
    mes["recebeu"](1000.0)
    sistema.salvar_lancamento(
        None, "2026-03-12", "Compra no cartão",
        [sistema.Partida(contas["despesa"], "D", 200.0),
         sistema.Partida(contas["cartao"], "C", 200.0)])
    f = fluxo(sistema)

    assert f["saiu"] == 0.0            # o dinheiro sai quando a fatura for paga
    assert f["despesas_fora"] == 200.0  # mas o gasto aconteceu, e fica visível


def test_mes_sem_movimento(sistema, contas):
    f = fluxo(sistema)

    assert f["entrou"] == 0.0
    assert f["saiu"] == 0.0
    assert f["sobrou"] == 0.0
    assert f["saldo_inicial"] == f["saldo_final"]


def test_as_saidas_vem_separadas_por_motivo(sistema, contas, mes):
    divida = sistema.criar_divida("Loja", "Loja", 100.0, "2026-02-01")
    mes["recebeu"](1000.0)
    mes["gastou"](300.0)
    sistema.pagar_divida(divida, 100.0, contas["banco"], "2026-03-18")
    f = fluxo(sistema)

    assert f["saidas"] == {"gastos": 300.0, "dividas": 100.0}
    assert "300,00 em gastos" in sistema.detalhe_do_fluxo(f["saidas"])


def test_o_painel_mostra_o_caixa_e_nao_a_dre(sistema, contas):
    """O painel sempre fala do mês corrente: a história acontece nele."""
    hoje = sistema.hoje_iso()
    divida = sistema.criar_divida("Mensalidade", "Escola", 440.0,
                                  sistema.primeiro_dia_mes())
    inicial = sistema.total_disponivel()["tem"]
    sistema.salvar_lancamento(
        None, hoje, "Salário",
        [sistema.Partida(contas["banco"], "D", 2000.0),
         sistema.Partida(contas["receita"], "C", 2000.0)])
    sistema.salvar_lancamento(
        None, hoje, "Mercado",
        [sistema.Partida(contas["despesa"], "D", 1000.0),
         sistema.Partida(contas["banco"], "C", 1000.0)])
    sistema.pagar_divida(divida, 440.0, contas["banco"], hoje)
    resumo = sistema.resumo_dashboard()

    assert resumo["sobrou_mes"] == 560.0          # o que de fato sobrou
    assert resumo["resultado_mes"] == 1000.0      # ganhos menos gastos
    assert resumo["disponivel"] == inicial + 560.0
    assert resumo["saldo_inicio_mes"] + resumo["sobrou_mes"] == resumo["disponivel"]


# --------------------------------------------------------------------------- #
# O painel na tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass

    def abrir_relatorio(self, indice: int) -> None:
        pass

    def abrir_tela(self, nome: str) -> None:
        pass


def test_os_cartoes_do_mes_mostram_o_caixa(sistema, contas, raiz_tk):
    """O cartão 'Sobrou' explica, embaixo, de onde para onde o dinheiro foi."""
    import importlib

    hoje = sistema.hoje_iso()
    divida = sistema.criar_divida("Mensalidade", "Escola", 440.0,
                                  sistema.primeiro_dia_mes())
    sistema.salvar_lancamento(
        None, hoje, "Salário",
        [sistema.Partida(contas["banco"], "D", 2000.0),
         sistema.Partida(contas["receita"], "C", 2000.0)])
    sistema.pagar_divida(divida, 440.0, contas["banco"], hoje)

    modulo = importlib.import_module("app.ui.dashboard")
    importlib.reload(modulo)
    tela = modulo.Dashboard(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        assert tela.cartoes["sobrou_mes"]._valor == sistema.moeda(1560.0)
        assert "e tem" in tela.cartoes["sobrou_mes"]._nota
        assert "em dívidas" in tela.cartoes["saiu_mes"]._nota
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()
