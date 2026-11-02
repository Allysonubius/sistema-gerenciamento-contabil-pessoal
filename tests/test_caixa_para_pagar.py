"""A lista de contas a pagar diz quanto se deve, não se dá para pagar.

Quem decide o que fazer no mês precisa das duas coisas na mesma tela: o que
falta pagar e o que há em conta para isso.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def contas_a_pagar(sistema, contas):
    """Ferramenta para montar contas e devolver as linhas como a tela as vê."""
    def criar(valor: float, conta_pagamento=..., tipo: str = "PAGAR"):
        destino = contas["banco"] if conta_pagamento is ... else conta_pagamento
        return sistema.salvar_titulo(
            None, tipo, "Conta", "", valor, sistema.hoje_iso(),
            contas["despesa"] if tipo == "PAGAR" else contas["receita"], None,
            conta_pagamento_id=destino)

    def linhas():
        return sistema.titulos_com_encargos(status="ABERTO")

    return criar, linhas


def test_sem_contas_o_caixa_e_so_o_saldo(sistema, contas, contas_a_pagar):
    _criar, linhas = contas_a_pagar
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["tem"] == sistema.total_disponivel()["tem"]
    assert caixa["a_pagar"] == 0.0
    assert caixa["depois_de_pagar"] == caixa["tem"]
    assert caixa["cobre"] is True


def test_o_que_sai_do_banco_desconta_do_saldo(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(300.0)
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["sai_do_dinheiro"] == 300.0
    assert caixa["depois_de_pagar"] == round(caixa["tem"] - 300.0, 2)
    assert caixa["cobre"] is True


def test_quando_nao_cobre_diz_quanto_falta(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(5000.0)                       # bem mais do que há em conta
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["cobre"] is False
    assert caixa["falta"] == round(5000.0 - caixa["tem"], 2)
    assert "Faltam" in sistema.recado_do_caixa(caixa)


def test_o_que_ainda_entra_pode_salvar_o_mes(sistema, contas, contas_a_pagar):
    criar, linhas = contas_a_pagar
    criar(5000.0)
    criar(6000.0, tipo="RECEBER")
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["cobre"] is False
    assert caixa["cobre_com_recebimentos"] is True
    assert "o que ainda entra cobre" in sistema.recado_do_caixa(caixa)


def test_conta_paga_no_cartao_nao_sai_do_banco(sistema, contas, contas_a_pagar):
    """Ela entra na fatura e sai quando a fatura vencer."""
    criar, linhas = contas_a_pagar
    criar(200.0, conta_pagamento=contas["cartao"])
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["a_pagar"] == 200.0
    assert caixa["no_cartao"] == 200.0
    assert caixa["sai_do_dinheiro"] == 0.0
    assert caixa["depois_de_pagar"] == caixa["tem"]
    assert "vão para o cartão" in sistema.recado_do_caixa(caixa)


def test_conta_sem_conta_escolhida_conta_mesmo_assim(sistema, contas, contas_a_pagar):
    """Ela vai sair de algum lugar; fingir que não existe só adia o susto."""
    criar, linhas = contas_a_pagar
    criar(150.0, conta_pagamento=None)
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["sem_conta"] == 150.0
    assert caixa["sai_do_dinheiro"] == 150.0


def test_os_totais_sempre_fecham(sistema, contas, contas_a_pagar):
    """O número do rodapé tem de bater com a lista logo acima dele."""
    criar, linhas = contas_a_pagar
    criar(100.0)
    criar(200.0, conta_pagamento=contas["cartao"])
    criar(50.0, conta_pagamento=None)
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["a_pagar"] == 350.0
    assert caixa["a_pagar"] == round(caixa["sai_do_dinheiro"] + caixa["no_cartao"], 2)
    assert caixa["depois_de_pagar"] == round(caixa["tem"] - caixa["sai_do_dinheiro"], 2)


def test_conta_ja_paga_nao_entra_na_conta(sistema, contas, contas_a_pagar):
    criar, _linhas = contas_a_pagar
    titulo = criar(100.0)
    sistema.baixar_titulo(titulo, sistema.hoje_iso(), 100.0, contas["banco"])
    caixa = sistema.caixa_para_as_contas(sistema.titulos_com_encargos())

    assert caixa["a_pagar"] == 0.0


def test_o_total_pode_cobrir_e_faltar_numa_conta(sistema, contas, contas_a_pagar):
    """O dinheiro existe, só está no lugar errado — e é isso que trava o Pix."""
    criar, linhas = contas_a_pagar
    criar(500.0, conta_pagamento=contas["outra"])    # tem 100,00 nela
    caixa = sistema.caixa_para_as_contas(linhas())

    assert caixa["cobre"] is True, "no total sobra dinheiro"
    assert caixa["contas_negativas"], "mas aquela conta não tem o bastante"
    faltando = caixa["contas_negativas"][0]
    assert faltando["nome"] == "Carteira"
    assert faltando["fica"] == -400.0


def test_multa_e_juros_entram_no_que_falta_pagar(sistema, contas):
    """Quem olha o rodapé quer o valor que vai sair, não o do boleto antigo."""
    vencida = sistema.salvar_titulo(
        None, "PAGAR", "Atrasada", "", 100.0,
        (sistema.date.today() - sistema.timedelta(days=40)).isoformat(),
        contas["despesa"], None, conta_pagamento_id=contas["banco"],
        multa_pct=10.0, juros_mes_pct=12.0)
    linhas = sistema.titulos_com_encargos(status="ABERTO")
    caixa = sistema.caixa_para_as_contas(linhas)

    assert caixa["a_pagar"] > 100.0, "o valor atualizado é que importa"
    assert sistema.obter_titulo(vencida)["valor"] == 100.0


# --------------------------------------------------------------------------- #
# Na tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


def test_o_rodape_mostra_o_saldo_e_o_que_sobra(sistema, contas, raiz_tk):
    sistema.salvar_titulo(None, "PAGAR", "Luz", "", 200.0, sistema.hoje_iso(),
                          contas["despesa"], None, conta_pagamento_id=contas["banco"])
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        assert "Tenho em conta:" in tela.lbl_tenho.cget("text")
        assert "Depois de pagar:" in tela.lbl_depois.cget("text")
        esperado = sistema.moeda(round(sistema.total_disponivel()["tem"] - 200.0, 2))
        assert esperado in tela.lbl_depois.cget("text")
        assert "cobre" in tela.lbl_recado.cget("text")
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_o_rodape_avisa_quando_nao_cobre(sistema, contas, raiz_tk):
    sistema.salvar_titulo(None, "PAGAR", "Carro", "", 9000.0, sistema.hoje_iso(),
                          contas["despesa"], None, conta_pagamento_id=contas["banco"])
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        assert "Faltam" in tela.lbl_recado.cget("text")
        assert "-" in tela.lbl_depois.cget("text")
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()
