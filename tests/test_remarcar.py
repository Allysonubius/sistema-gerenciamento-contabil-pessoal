"""Mudar a data em que uma conta vence.

A conta que não foi paga no dia não deixa de existir: ela passa a vencer noutro
dia. E quando é conta fixa, quase sempre o dia novo vale dali para a frente.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def conta(sistema, contas):
    """Um boleto avulso vencendo no dia 10 do mês que vem."""
    vencimento = f"{sistema._mes_seguinte(sistema.mes_atual())}-10"
    return sistema.salvar_titulo(None, "PAGAR", "Internet", "Provedor", 139.9,
                                 vencimento, contas["despesa"], None)


@pytest.fixture()
def fixa(sistema, contas):
    """Uma conta fixa que vence todo dia 10, com vários meses gerados."""
    recorrencia = sistema.salvar_recorrencia(
        None, "PAGAR", "Streaming", "", 23.9, 10, contas["despesa"], None,
        sistema.mes_atual())
    sistema.gerar_titulos_recorrentes()
    titulos = [t for t in sistema.listar_titulos(status="ABERTO")
               if t["recorrencia_id"] == recorrencia]
    titulos.sort(key=lambda t: t["vencimento"])
    return recorrencia, titulos


# --------------------------------------------------------------------------- #
# Só esta conta
# --------------------------------------------------------------------------- #
def test_remarcar_muda_so_a_data(sistema, conta):
    antes = sistema.obter_titulo(conta)
    novo = f"{antes['vencimento'][:7]}-25"
    resultado = sistema.remarcar_titulo(conta, novo)

    depois = sistema.obter_titulo(conta)
    assert depois["vencimento"] == novo
    assert depois["valor"] == antes["valor"]
    assert depois["descricao"] == antes["descricao"]
    assert resultado["de"] == antes["vencimento"]
    assert resultado["seguintes"] == 0


def test_remarcar_para_outro_mes(sistema, conta):
    """Empurrar para o mês seguinte é o caso mais comum de todos."""
    novo = f"{sistema._mes_seguinte(sistema.obter_titulo(conta)['vencimento'][:7])}-05"
    sistema.remarcar_titulo(conta, novo)

    assert sistema.obter_titulo(conta)["vencimento"] == novo


def test_a_competencia_nao_muda_com_a_data(sistema, conta):
    """A conta de outubro paga em novembro continua sendo a conta de outubro."""
    antes = sistema.obter_titulo(conta)["competencia"]
    sistema.remarcar_titulo(conta, f"{sistema._mes_seguinte(antes)}-05")

    assert sistema.obter_titulo(conta)["competencia"] == antes


def test_data_sem_sentido_e_recusada(sistema, conta):
    for texto in ("2026-13-01", "", "amanhã"):
        with pytest.raises(sistema.RegraNegocioError):
            sistema.remarcar_titulo(conta, texto)


def test_conta_ja_paga_nao_se_remarca(sistema, conta, contas):
    sistema.baixar_titulo(conta, sistema.hoje_iso(), 139.9, contas["banco"])

    with pytest.raises(sistema.RegraNegocioError, match="já foi paga"):
        sistema.remarcar_titulo(conta, sistema.hoje_iso())


def test_mes_fechado_nao_deixa_remarcar(sistema, contas):
    anterior = sistema._mes_anterior(sistema.mes_atual())
    titulo = sistema.salvar_titulo(None, "PAGAR", "Luz", "", 100.0, f"{anterior}-10",
                                   contas["despesa"], None)
    sistema.fechar_competencia(anterior)

    with pytest.raises(sistema.RegraNegocioError, match="fechado"):
        sistema.remarcar_titulo(titulo, sistema.hoje_iso())


def test_nao_da_para_jogar_uma_conta_para_dentro_de_um_mes_fechado(sistema, conta):
    anterior = sistema._mes_anterior(sistema.mes_atual())
    sistema.fechar_competencia(anterior)

    with pytest.raises(sistema.RegraNegocioError, match="fechado"):
        sistema.remarcar_titulo(conta, f"{anterior}-15")


# --------------------------------------------------------------------------- #
# Daqui para a frente
# --------------------------------------------------------------------------- #
def test_remarcar_os_meses_seguintes(sistema, fixa):
    recorrencia, titulos = fixa
    primeiro = titulos[0]
    novo = f"{primeiro['vencimento'][:7]}-25"

    resultado = sistema.remarcar_titulo(primeiro["id"], novo, seguintes=True)

    assert resultado["seguintes"] > 0
    assert sistema.obter_titulo(primeiro["id"])["vencimento"] == novo
    seguintes = [t for t in sistema.listar_titulos(status="ABERTO")
                 if t["recorrencia_id"] == recorrencia
                 and t["competencia"] > primeiro["competencia"]]
    assert seguintes
    assert all(t["vencimento"].endswith("-25") for t in seguintes)


def test_a_conta_fixa_passa_a_nascer_no_dia_novo(sistema, fixa):
    """Os meses ainda não gerados também têm de vir no dia certo."""
    recorrencia, titulos = fixa
    sistema.remarcar_titulo(titulos[0]["id"],
                            f"{titulos[0]['vencimento'][:7]}-25", seguintes=True)

    from app import db

    assert db.query_one("SELECT dia_vencimento FROM recorrencia WHERE id = ?",
                        (recorrencia,))["dia_vencimento"] == 25


def test_sem_seguintes_os_outros_meses_ficam_como_estavam(sistema, fixa):
    recorrencia, titulos = fixa
    seguinte_antes = titulos[1]["vencimento"]

    sistema.remarcar_titulo(titulos[0]["id"], f"{titulos[0]['vencimento'][:7]}-25")

    assert sistema.obter_titulo(titulos[1]["id"])["vencimento"] == seguinte_antes


def test_mes_ja_pago_nunca_e_remarcado(sistema, fixa, contas):
    """Mês pago é história, e história não se remarca."""
    _recorrencia, titulos = fixa
    pago, atual = titulos[0], titulos[1]
    sistema.baixar_titulo(pago["id"], pago["vencimento"], 23.9, contas["banco"])
    venc_pago = sistema.obter_titulo(pago["id"])["vencimento"]

    sistema.remarcar_titulo(atual["id"], f"{atual['vencimento'][:7]}-28", seguintes=True)

    assert sistema.obter_titulo(pago["id"])["vencimento"] == venc_pago


def test_dia_31_cabe_em_mes_curto(sistema, fixa):
    """Fevereiro não tem 31: o vencimento cai no último dia que existe."""
    _recorrencia, titulos = fixa
    sistema.remarcar_titulo(titulos[0]["id"], f"{titulos[0]['vencimento'][:7]}-31",
                            seguintes=True)

    for titulo in sistema.listar_titulos(status="ABERTO"):
        if titulo["recorrencia_id"]:
            ano, mes, dia = (int(p) for p in titulo["vencimento"].split("-"))
            assert dia <= sistema._ultimo_dia(ano, mes)


def test_conta_avulsa_ignora_o_pedido_de_seguintes(sistema, conta):
    """Não há conta fixa atrás dela: não há o que propagar."""
    resultado = sistema.remarcar_titulo(
        conta, f"{sistema.obter_titulo(conta)['vencimento'][:7]}-25", seguintes=True)

    assert resultado["seguintes"] == 0


# --------------------------------------------------------------------------- #
# Ajudas da tela
# --------------------------------------------------------------------------- #
def test_as_sugestoes_nunca_apontam_para_tras(sistema, contas):
    atrasada = sistema.salvar_titulo(
        None, "PAGAR", "Atrasada", "", 50.0,
        (sistema.date.today() - sistema.timedelta(days=30)).isoformat(),
        contas["despesa"], None)
    sugestoes = sistema.sugestoes_de_remarcacao(atrasada)

    assert sugestoes
    assert all(o["data"] >= sistema.hoje_iso() for o in sugestoes)


def test_as_sugestoes_nao_se_repetem(sistema, conta):
    datas = [o["data"] for o in sistema.sugestoes_de_remarcacao(conta)]

    assert len(datas) == len(set(datas))


def test_pode_remarcar_explica_o_nao(sistema, conta, contas):
    assert sistema.pode_remarcar(conta) == (True, "")

    sistema.baixar_titulo(conta, sistema.hoje_iso(), 139.9, contas["banco"])
    pode, motivo = sistema.pode_remarcar(conta)

    assert pode is False
    assert "em aberto" in motivo


# --------------------------------------------------------------------------- #
# A janela
# --------------------------------------------------------------------------- #
class AppFalso:
    def __init__(self):
        self.avisos: list[str] = []

    def notificar(self, texto: str) -> None:
        self.avisos.append(texto)

    def atualizar_dependentes(self) -> None:
        pass


def test_a_janela_remarca(sistema, conta, raiz_tk):
    import importlib

    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    recados = []
    janela = modulo.DialogoRemarcar(raiz_tk, conta, recados.append)
    janela.grab_release()
    try:
        novo = f"{sistema.obter_titulo(conta)['vencimento'][:7]}-28"
        janela.dt_nova.set_iso(novo)
        janela.salvar()

        assert sistema.obter_titulo(conta)["vencimento"] == novo
        assert recados and "remarcada" in recados[0]
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_janela_diz_o_que_vai_acontecer(sistema, fixa, raiz_tk):
    import importlib

    _recorrencia, titulos = fixa
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    janela = modulo.DialogoRemarcar(raiz_tk, titulos[0]["id"], lambda _r: None)
    janela.grab_release()
    try:
        janela.var_seguintes.set(False)
        janela._explicar()
        assert "continuam no dia de sempre" in janela.lbl_efeito.cget("text")

        janela.var_seguintes.set(True)
        janela._explicar()
        assert "próximos meses em aberto" in janela.lbl_efeito.cget("text")
        assert "já pagos não são tocados" in janela.lbl_efeito.cget("text")
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_janela_mostra_ha_quantos_dias_venceu(sistema, contas, raiz_tk):
    import importlib

    atrasada = sistema.salvar_titulo(
        None, "PAGAR", "Atrasada", "", 50.0,
        (sistema.date.today() - sistema.timedelta(days=5)).isoformat(),
        contas["despesa"], None)
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    janela = modulo.DialogoRemarcar(raiz_tk, atrasada, lambda _r: None)
    janela.grab_release()
    try:
        assert "venceu há 5 dia(s)" in janela._situacao()
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()
