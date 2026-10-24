"""A meta de poupança nasce do que entrou no mês, não do que sobrou.

Guardar o que sobra é não guardar nada: num mês apertado sobra zero e a
poupança some. A meta é uma fatia do que foi recebido — recebeu menos, guarda
menos — e o medidor diz, antes de o mês acabar, se o gasto está comendo ela.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def poupanca(sistema):
    conta = sistema.criar_carteira("Reserva", "Investimento")
    sistema.marcar_como_investimento(conta)
    return conta


@pytest.fixture()
def mes(sistema, contas, poupanca):
    """O mês corrente, porque é dele que o medidor fala."""
    hoje = sistema.hoje_iso()

    def recebeu(valor: float) -> None:
        sistema.salvar_lancamento(
            None, hoje, "Salário",
            [sistema.Partida(contas["banco"], "D", valor),
             sistema.Partida(contas["receita"], "C", valor)])

    def gastou(valor: float) -> None:
        sistema.salvar_lancamento(
            None, hoje, "Mercado",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])

    def guardou(valor: float) -> None:
        sistema.transferir(contas["banco"], poupanca, valor, hoje)

    def resgatou(valor: float) -> None:
        sistema.transferir(poupanca, contas["banco"], valor, hoje)

    return {"recebeu": recebeu, "gastou": gastou,
            "guardou": guardou, "resgatou": resgatou}


# --------------------------------------------------------------------------- #
# A porcentagem
# --------------------------------------------------------------------------- #
def test_a_meta_comeca_em_dez_por_cento(sistema):
    assert sistema.percentual_de_poupanca() == 10.0


def test_a_porcentagem_pode_ser_mudada(sistema):
    sistema.definir_percentual_de_poupanca(25)

    assert sistema.percentual_de_poupanca() == 25.0


def test_porcentagem_fora_da_faixa_e_recusada(sistema):
    for valor in (-1, 101, 500):
        with pytest.raises(sistema.RegraNegocioError):
            sistema.definir_percentual_de_poupanca(valor)


def test_porcentagem_estragada_no_banco_volta_ao_padrao(sistema):
    from app import db

    db.set_config("meta_poupanca_pct", "muito")
    assert sistema.percentual_de_poupanca() == 10.0


# --------------------------------------------------------------------------- #
# O medidor
# --------------------------------------------------------------------------- #
def test_a_meta_e_uma_fatia_do_que_entrou(sistema, mes):
    mes["recebeu"](2000.0)
    meta = sistema.meta_de_poupanca()

    assert meta["recebido"] == 2000.0
    assert meta["alvo"] == 200.0          # 10%


def test_a_meta_encolhe_num_mes_magro(sistema, mes):
    """É o ponto de amarrar a meta na renda, e não num valor fixo."""
    mes["recebeu"](800.0)

    assert sistema.meta_de_poupanca()["alvo"] == 80.0


def test_guardou_o_combinado(sistema, mes):
    mes["recebeu"](2000.0)
    mes["guardou"](200.0)
    meta = sistema.meta_de_poupanca()

    assert meta["guardado"] == 200.0
    assert meta["situacao"] == "em_dia"
    assert meta["falta"] == 0.0
    assert meta["atingido"] == 100.0


def test_guardou_mais_do_que_o_combinado(sistema, mes):
    mes["recebeu"](2000.0)
    mes["guardou"](500.0)
    meta = sistema.meta_de_poupanca()

    assert meta["situacao"] == "em_dia"
    assert meta["do_que_entrou"] == 25.0


def test_guardou_menos_do_que_o_combinado(sistema, mes):
    mes["recebeu"](2000.0)
    mes["guardou"](50.0)
    meta = sistema.meta_de_poupanca()

    assert meta["situacao"] == "parcial"
    assert meta["falta"] == 150.0
    assert meta["atingido"] == 25.0


def test_nao_guardou_nada(sistema, mes):
    mes["recebeu"](2000.0)
    mes["gastou"](1900.0)
    meta = sistema.meta_de_poupanca()

    assert meta["guardado"] == 0.0
    assert meta["situacao"] == "nada"
    assert meta["falta"] == 200.0


def test_resgatar_desconta_do_que_foi_guardado(sistema, mes):
    """Guardar 300 e tirar 250 de volta não é ter guardado 300."""
    mes["recebeu"](2000.0)
    mes["guardou"](300.0)
    mes["resgatou"](250.0)
    meta = sistema.meta_de_poupanca()

    assert meta["aplicou"] == 300.0
    assert meta["resgatou"] == 250.0
    assert meta["guardado"] == 50.0
    assert meta["situacao"] == "parcial"


def test_tirar_mais_do_que_guardou_fica_negativo(sistema, mes, poupanca):
    sistema.registrar_saldo_inicial(poupanca, 500.0, sistema.primeiro_dia_mes())
    mes["recebeu"](2000.0)
    mes["resgatou"](400.0)
    meta = sistema.meta_de_poupanca()

    assert meta["guardado"] == -400.0
    assert meta["situacao"] == "nada"


def test_mes_sem_renda_nao_cobra_meta(sistema, mes):
    meta = sistema.meta_de_poupanca()

    assert meta["situacao"] == "sem_renda"
    assert meta["alvo"] == 0.0
    assert "quando o dinheiro cair" in sistema.recado_da_poupanca(meta)


def test_o_medidor_mostra_quanto_ja_existe_guardado(sistema, mes, poupanca):
    sistema.registrar_saldo_inicial(poupanca, 1500.0, sistema.primeiro_dia_mes())
    mes["recebeu"](2000.0)
    mes["guardou"](100.0)

    assert sistema.meta_de_poupanca()["total_guardado"] == 1600.0


def test_acerto_de_saldo_nao_conta_como_renda(sistema, contas, mes):
    """Corrigir um saldo não é dinheiro recebido: não aumenta a meta."""
    mes["recebeu"](1000.0)
    sistema.ajustar_saldo(contas["banco"], 5000.0)

    assert sistema.meta_de_poupanca()["recebido"] == 1000.0


def test_o_recado_tem_os_numeros_dentro(sistema, mes):
    mes["recebeu"](2000.0)
    mes["guardou"](50.0)
    recado = sistema.recado_da_poupanca(sistema.meta_de_poupanca())

    assert "2.000,00" in recado
    assert "200,00" in recado
    assert "150,00" in recado


def test_a_porcentagem_escolhida_muda_a_meta(sistema, mes):
    sistema.definir_percentual_de_poupanca(30)
    mes["recebeu"](2000.0)
    mes["guardou"](200.0)
    meta = sistema.meta_de_poupanca()

    assert meta["alvo"] == 600.0
    assert meta["situacao"] == "parcial"


# --------------------------------------------------------------------------- #
# O histórico
# --------------------------------------------------------------------------- #
def test_resumo_conta_quantos_meses_bateram_a_meta(sistema, mes):
    mes["recebeu"](2000.0)
    mes["guardou"](200.0)
    resumo = sistema.resumo_poupanca()

    assert resumo["meses"] == 1
    assert resumo["em_dia"] == 1
    assert resumo["media_guardado"] == 200.0
    assert resumo["media_pct"] == 10.0


def test_mes_sem_renda_fica_fora_da_media(sistema, mes):
    """Um mês sem nada entrando puxaria a média para baixo sem motivo."""
    resumo = sistema.resumo_poupanca()

    assert resumo["meses"] == 0
    assert resumo["media_pct"] == 0.0


def test_o_painel_traz_a_poupanca(sistema, mes):
    mes["recebeu"](2000.0)
    mes["guardou"](50.0)
    resumo = sistema.resumo_dashboard()

    assert resumo["poupanca"]["falta"] == 150.0
    assert resumo["poupanca"]["situacao"] == "parcial"


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        pass

    def atualizar_dependentes(self) -> None:
        pass


def test_a_janela_da_poupanca_abre_e_avisa(sistema, mes, raiz_tk):
    import importlib

    mes["recebeu"](2000.0)
    mes["guardou"](50.0)
    modulo = importlib.import_module("app.ui.orcamento")
    importlib.reload(modulo)
    janela = modulo.JanelaPoupanca(raiz_tk)
    janela.grab_release()
    try:
        assert "menos do que o combinado" in janela.lbl_recado.cget("text")
        assert janela.var_pct.get() == "10"
        assert janela.tabela.tree.get_children()
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_mudar_a_porcentagem_pela_tela(sistema, mes, raiz_tk):
    import importlib

    mes["recebeu"](2000.0)
    modulo = importlib.import_module("app.ui.orcamento")
    importlib.reload(modulo)
    janela = modulo.JanelaPoupanca(raiz_tk)
    janela.grab_release()
    try:
        janela.var_pct.set("20")
        janela.salvar_pct()
        assert sistema.percentual_de_poupanca() == 20.0
        assert janela.meta["alvo"] == 400.0
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()
