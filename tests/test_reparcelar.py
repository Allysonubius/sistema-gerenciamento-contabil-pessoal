"""Parar uma série, e refazer o que falta dela.

Dois pedidos que a ferramenta não atendia. O primeiro: apagar a mensalidade de
uma assinatura cancelada apagava só aquele mês — a conta fixa continuava ativa,
os meses fora da tela sobreviviam, e cancelar virava tarefa mensal. O segundo:
não havia como quitar o que falta de uma vez, nem refazer o número de parcelas
quando o acordo muda.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def assinatura(sistema, contas):
    """Conta fixa sem prazo, com o mês atual pago e os seguintes em aberto."""
    mes = sistema.mes_atual()
    rec = sistema.salvar_recorrencia(None, "PAGAR", "Linkedin", "", 99.0, 2,
                                     contas["despesa"], None, mes)
    sistema.gerar_titulos_recorrentes()
    return rec, mes


@pytest.fixture()
def parcelado(sistema, contas):
    """Três parcelas de 166,67, a primeira neste mês."""
    mes = sistema.mes_atual()
    fim = sistema.somar_meses(__import__("datetime").date.fromisoformat(f"{mes}-01"), 2)
    rec = sistema.salvar_recorrencia(None, "PAGAR", "Michelson", "", 166.67, 1,
                                     contas["despesa"], None, mes,
                                     fim.strftime("%Y-%m"))
    sistema.gerar_titulos_recorrentes()
    return rec


def abertos(sistema, rec_id: int) -> list:
    from app import db
    return [dict(t) for t in db.query(
        "SELECT * FROM titulo WHERE recorrencia_id = ? AND status = 'ABERTO'"
        " ORDER BY competencia", (rec_id,))]


# --------------------------------------------------------------------------- #
# Parar a série
# --------------------------------------------------------------------------- #
def test_apagar_a_serie_leva_todos_os_meses_em_aberto(sistema, contas, assinatura):
    rec, _mes = assinatura
    primeiro = abertos(sistema, rec)[0]
    quantos = len(abertos(sistema, rec))
    assert quantos > 1, "a conta fixa lança meses à frente"

    resultado = sistema.encerrar_serie_do_titulo(primeiro["id"])

    assert resultado["removidos"] == quantos
    assert abertos(sistema, rec) == []


def test_parar_a_serie_impede_que_ela_renasca(sistema, contas, assinatura):
    """Era o defeito: a geração recriava no dia seguinte o que se apagou hoje."""
    rec, _mes = assinatura
    sistema.encerrar_serie_do_titulo(abertos(sistema, rec)[0]["id"])

    sistema.gerar_titulos_recorrentes()
    assert abertos(sistema, rec) == []
    assert sistema.db.query_one("SELECT ativo FROM recorrencia WHERE id = ?",
                                (rec,))["ativo"] == 0


def test_o_que_ja_foi_pago_nao_e_tocado(sistema, contas, assinatura):
    rec, mes = assinatura
    deste_mes = next(t for t in abertos(sistema, rec) if t["competencia"] == mes)
    sistema.baixar_titulo(deste_mes["id"], f"{mes}-02", 99.0, contas["banco"])

    seguinte = abertos(sistema, rec)[0]
    sistema.encerrar_serie_do_titulo(seguinte["id"])

    pago = sistema.obter_titulo(deste_mes["id"])
    assert pago is not None and pago["status"] == "QUITADO"


def test_a_serie_de_um_titulo_avulso_e_ele_mesmo(sistema, contas):
    titulo = sistema.salvar_titulo(None, "PAGAR", "Boleto", "", 50.0,
                                   f"{sistema.mes_atual()}-20", contas["despesa"], None)
    serie = sistema.serie_do_titulo(titulo)

    assert serie["quantas"] == 1
    assert serie["e_fixa"] is False


# --------------------------------------------------------------------------- #
# Pagar num mês só
# --------------------------------------------------------------------------- #
def test_juntar_tudo_num_mes_so(sistema, contas, parcelado):
    restantes = abertos(sistema, parcelado)
    total = round(sum(t["valor"] for t in restantes), 2)
    primeiro = restantes[0]

    resultado = sistema.reparcelar(primeiro["id"], 1, primeiro["vencimento"])

    assert resultado["parcelas"] == 1
    assert resultado["total_agora"] == total
    assert abertos(sistema, parcelado) == [], "as antigas saíram"
    novo = sistema.obter_titulo(resultado["ids"][0])
    assert novo["valor"] == total
    assert novo["recorrencia_id"] is None, "acordo novo não fica preso à série velha"


def test_quitar_de_uma_vez_nao_deixa_a_serie_renascer(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    sistema.reparcelar(primeiro["id"], 1, primeiro["vencimento"])

    sistema.gerar_titulos_recorrentes()
    assert abertos(sistema, parcelado) == []


# --------------------------------------------------------------------------- #
# Mudar o número de parcelas
# --------------------------------------------------------------------------- #
def test_esticar_em_mais_parcelas(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    total = round(sum(t["valor"] for t in abertos(sistema, parcelado)), 2)

    resultado = sistema.reparcelar(primeiro["id"], 6, primeiro["vencimento"])

    assert resultado["parcelas"] == 6
    criados = [sistema.obter_titulo(i) for i in resultado["ids"]]
    assert round(sum(t["valor"] for t in criados), 2) == total, "o total não muda"
    assert "(1/6)" in criados[0]["descricao"]


def test_a_sobra_de_centavos_fica_na_primeira(sistema, contas, parcelado):
    """A última parcela diferente das outras é a que assusta na hora de pagar."""
    primeiro = abertos(sistema, parcelado)[0]
    resultado = sistema.reparcelar(primeiro["id"], 3, primeiro["vencimento"],
                                   valor_total=100.0)

    valores = [sistema.obter_titulo(i)["valor"] for i in resultado["ids"]]
    assert round(sum(valores), 2) == 100.0
    assert valores[0] >= valores[-1]
    assert len(set(valores[1:])) == 1, "as demais são todas iguais"


def test_desconto_combinado_entra_como_total_menor(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    antes = round(sum(t["valor"] for t in abertos(sistema, parcelado)), 2)

    resultado = sistema.reparcelar(primeiro["id"], 2, primeiro["vencimento"],
                                   valor_total=antes - 33.34)

    assert resultado["desconto"] == 33.34
    assert resultado["total_agora"] == round(antes - 33.34, 2)


def test_as_parcelas_novas_caem_em_meses_seguidos(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    resultado = sistema.reparcelar(primeiro["id"], 3, f"{sistema.mes_atual()}-15")

    meses = [sistema.obter_titulo(i)["competencia"] for i in resultado["ids"]]
    assert meses == sorted(set(meses)), "um mês cada, sem repetir"
    assert len(meses) == 3


# --------------------------------------------------------------------------- #
# O que não se pode fazer
# --------------------------------------------------------------------------- #
def test_conta_fixa_sem_prazo_nao_se_reparcela(sistema, contas, assinatura):
    """Sem prazo não há total a dividir — dividir o quê, por quantos meses?"""
    rec, _mes = assinatura
    pode, motivo = sistema.pode_reparcelar(abertos(sistema, rec)[0]["id"])

    assert pode is False
    assert "sem prazo" in motivo

    with pytest.raises(sistema.RegraNegocioError):
        sistema.reparcelar(abertos(sistema, rec)[0]["id"], 1, sistema.hoje_iso())


def test_conta_paga_nao_se_reparcela(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    sistema.baixar_titulo(primeiro["id"], primeiro["vencimento"], primeiro["valor"],
                          contas["banco"])

    pode, motivo = sistema.pode_reparcelar(primeiro["id"])
    assert pode is False
    assert "paga" in motivo


def test_numero_de_parcelas_absurdo_e_recusado(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    for quantas in (0, -3, 999):
        with pytest.raises(sistema.RegraNegocioError):
            sistema.reparcelar(primeiro["id"], quantas, primeiro["vencimento"])


def test_total_zerado_e_recusado(sistema, contas, parcelado):
    primeiro = abertos(sistema, parcelado)[0]
    with pytest.raises(sistema.RegraNegocioError):
        sistema.reparcelar(primeiro["id"], 2, primeiro["vencimento"], valor_total=0.0)


# --------------------------------------------------------------------------- #
# A tela
# --------------------------------------------------------------------------- #
class AppFalso:
    def notificar(self, texto: str) -> None:
        self.recado = texto

    def atualizar_dependentes(self) -> None:
        pass

    def ir_para(self, _destino) -> None:
        pass


def test_o_dialogo_conta_o_que_vai_lancar(sistema, contas, parcelado, raiz_tk):
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))
    primeiro = abertos(sistema, parcelado)[0]
    janela = modulo.DialogoReparcelar(raiz_tk, primeiro["id"], lambda _r: None)
    janela.grab_release()
    try:
        janela.var_parcelas.set("1")
        assert "Uma parcela só" in janela.lbl_conta.cget("text")

        janela.var_parcelas.set("4")
        assert "4 parcelas" in janela.lbl_conta.cget("text")
        assert "substituídas" in janela.lbl_aviso.cget("text")
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_apagar_uma_fixa_oferece_parar_a_serie(sistema, contas, assinatura, raiz_tk,
                                               monkeypatch):
    rec, _mes = assinatura
    modulo = importlib.reload(importlib.import_module("app.ui.financeiro"))

    class Falsas:
        def __init__(self):
            self.opcoes = []

        def avisar(self, *_a, **_k):
            pass

        def escolher(self, _master, _titulo, _pergunta, opcoes, detalhe=""):
            self.opcoes = [o[2] for o in opcoes]
            return "serie"

    falsas = Falsas()
    monkeypatch.setattr(modulo, "perguntas", falsas)
    tela = modulo.Financeiro(raiz_tk, AppFalso())
    try:
        tela.recarregar()
        alvo = abertos(sistema, rec)[0]
        tela.tabela.tree.selection_set(str(alvo["id"]))
        tela.excluir()

        assert falsas.opcoes == ["um", "serie"], "apagar só este mês vem primeiro"
        assert abertos(sistema, rec) == []
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()
