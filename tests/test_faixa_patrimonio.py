"""O retrato do dinheiro — e por que ele é um só.

Dinheiro, investido, outros saldos, dívida e sobra aparecem em mais de uma
tela. O cálculo mora num lugar só porque duas cópias viram, com o tempo, dois
números diferentes para a mesma pergunta — e foi exatamente esse o defeito que
já apareceu antes nesta ferramenta.
"""
from __future__ import annotations

import importlib

import pytest


class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass

    def ir_para(self, _destino) -> None:
        pass


@pytest.fixture()
def telas(sistema, raiz_tk):
    criadas = []

    def abrir(modulo_nome: str, classe: str):
        modulo = importlib.reload(importlib.import_module(modulo_nome))
        tela = getattr(modulo, classe)(raiz_tk, AppFalso())
        criadas.append(tela)
        return tela

    yield abrir
    for filho in raiz_tk.winfo_children():
        filho.destroy()


def _numeros(faixa) -> dict:
    return {chave: rotulo.cget("text") for chave, rotulo in faixa._rotulos.items()}


# --------------------------------------------------------------------------- #
def test_contas_a_pagar_mostra_o_retrato_do_dinheiro(sistema, contas, telas):
    tela = telas("app.ui.financeiro", "Financeiro")
    tela.recarregar()

    textos = _numeros(tela.faixa)
    assert "Dinheiro:" in textos["tem"]
    assert "Investido:" in textos["investido"]
    assert "Outros saldos:" in textos["outros"]
    assert "Deve:" in textos["deve"]
    assert "Sobra:" in textos["liquido"]


def test_as_duas_telas_dizem_o_mesmo(sistema, contas, telas):
    """Minhas Contas e Contas a Pagar não podem divergir sobre o mesmo saldo."""
    pagar = telas("app.ui.financeiro", "Financeiro")
    pagar.recarregar()
    carteiras = telas("app.ui.carteiras", "Carteiras")
    carteiras.recarregar()

    assert _numeros(pagar.faixa) == _numeros(carteiras.faixa)


def test_a_faixa_acompanha_o_saldo(sistema, contas, telas):
    tela = telas("app.ui.financeiro", "Financeiro")
    tela.recarregar()
    antes = _numeros(tela.faixa)["tem"]

    sistema.registrar_saldo_inicial(contas["banco"], 250.0, sistema.hoje_iso())
    tela.recarregar()
    assert _numeros(tela.faixa)["tem"] != antes


def test_o_investido_nao_entra_na_sobra(sistema, contas):
    """Dinheiro aplicado existe, mas não está à mão para pagar o boleto de hoje."""
    aplicacao = sistema.criar_carteira("Reserva", "Investimento")
    sistema.marcar_como_investimento(aplicacao)
    sistema.registrar_saldo_inicial(aplicacao, 700.0, sistema.hoje_iso())

    totais = sistema.total_disponivel()
    assert totais["investido"] == 700.0
    assert totais["liquido"] == round(totais["tem"] - totais["deve"], 2)
    assert totais["com_investimentos"] == round(totais["liquido"] + 700.0
                                                + totais["outros"], 2)
