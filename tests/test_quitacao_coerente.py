"""O histórico de quitadas tem de dizer a verdade — e não levar nada junto.

Aconteceu de verdade: o lançamento de uma quitação foi desfeito por fora, a
dívida voltou com saldo, e o histórico seguia dizendo que ela estava encerrada.
Pior: reabrir essa quitação apagaria um lançamento do usuário, porque o id
guardado já pertencia a outro registro.
"""
from __future__ import annotations

import pytest


def existe(sistema, lancamento_id: int) -> bool:
    return sistema.db.query_one("SELECT 1 FROM lancamento WHERE id = ?",
                                (lancamento_id,)) is not None


@pytest.fixture()
def divida(sistema, contas):
    return sistema.criar_divida("Mensalidade", "Escola", 885.0, "2026-01-10")


def test_quitacao_guarda_quanto_foi_pago(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                          valor_pago=440.0, aceitar_desconto=True)

    item = sistema.listar_dividas_quitadas()[0]
    assert item["valor"] == 885.0          # o que faltava
    assert item["valor_pago"] == 440.0     # o que saiu da conta
    assert item["desconto"] == 445.0       # o que o credor abriu mão


def test_perdao_registra_pago_zero(sistema, contas, divida):
    sistema.quitar_divida(divida, "PERDAO", data_iso=sistema.hoje_iso())

    item = sistema.listar_dividas_quitadas()[0]
    assert item["valor_pago"] == 0.0
    assert item["desconto"] == 885.0


def test_pagamento_integral_nao_tem_desconto(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                          valor_pago=885.0)

    item = sistema.listar_dividas_quitadas()[0]
    assert item["valor_pago"] == 885.0
    assert item["desconto"] == 0.0


def test_reabrir_apaga_so_o_lancamento_da_quitacao(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                          valor_pago=400.0, aceitar_desconto=True)
    quitacao = sistema.listar_dividas_quitadas()[0]
    outro = sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Supermercado",
        [sistema.Partida(contas["despesa"], "D", 50.0),
         sistema.Partida(contas["banco"], "C", 50.0)])

    sistema.desfazer_quitacao(quitacao["id"])

    assert existe(sistema, outro)      # o registro do usuário fica
    assert sistema.saldo_conta(divida) == 885.0             # a dívida volta inteira
    assert sistema.listar_dividas_quitadas() == []


def test_id_reaproveitado_nao_leva_registro_do_usuario(sistema, contas, divida):
    """O vínculo é conferido pelo documento, não só pelo número."""
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                          valor_pago=400.0, aceitar_desconto=True)
    quitacao = sistema.listar_dividas_quitadas()[0]
    inocente = sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Compra do mês",
        [sistema.Partida(contas["despesa"], "D", 30.0),
         sistema.Partida(contas["banco"], "C", 30.0)])
    # Simula o estrago: a quitação passa a apontar para o lançamento alheio.
    sistema.db.execute("UPDATE divida_quitacao SET lancamento_id = ? WHERE id = ?",
                       (inocente, quitacao["id"]))

    sistema.desfazer_quitacao(quitacao["id"])

    assert existe(sistema, inocente)


def test_divida_que_voltou_sai_do_historico(sistema, contas, divida):
    sistema.quitar_divida(divida, "PERDAO", data_iso=sistema.hoje_iso())
    # A dívida volta por outro caminho (correção de valor, por exemplo).
    sistema.db.execute("UPDATE conta SET ativo = 1 WHERE id = ?", (divida,))
    sistema.alterar_valor_divida(divida, 500.0, sistema.hoje_iso())

    removidas = sistema.limpar_quitacoes_incoerentes()

    assert removidas == 1
    assert sistema.listar_dividas_quitadas() == []
    assert sistema.saldo_conta(divida) == 500.0


def test_limpeza_nao_mexe_em_quitacao_correta(sistema, contas, divida):
    sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                          valor_pago=885.0)

    assert sistema.limpar_quitacoes_incoerentes() == 0
    assert len(sistema.listar_dividas_quitadas()) == 1


def test_pagar_menos_nao_quita_sozinho(sistema, contas, divida):
    """Pagar 440 de 885 é pagamento parcial — a dívida continua com o resto."""
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"], sistema.hoje_iso(),
                              valor_pago=440.0)

    assert "não quita" in str(erro.value)
    assert sistema.saldo_conta(divida) == 885.0
    assert sistema.listar_dividas_quitadas() == []


def test_acordo_declarado_encerra_a_divida(sistema, contas, divida):
    resultado = sistema.quitar_divida(divida, "PAGAMENTO", contas["banco"],
                                      sistema.hoje_iso(), valor_pago=440.0,
                                      aceitar_desconto=True)

    assert resultado["pago"] == 440.0
    assert resultado["desconto"] == 445.0
    assert sistema.saldo_conta(divida) == 0.0


def test_pagamento_parcial_mantem_a_divida_na_lista(sistema, contas, divida):
    sistema.pagar_divida(divida, 440.0, contas["banco"], sistema.hoje_iso())

    assert sistema.saldo_conta(divida) == 445.0
    assert divida in [d["conta_id"] for d in sistema.listar_dividas()]
    assert sistema.listar_dividas_quitadas() == []


def partidas_do(sistema, lancamento_id):
    return sistema.db.query(
        "SELECT p.tipo, p.valor, c.nome, c.codigo, c.tipo AS tipo_conta FROM partida p"
        " JOIN conta c ON c.id = p.conta_id WHERE p.lancamento_id = ?", (lancamento_id,))


def test_pagar_divida_aparece_como_saida(sistema, contas, divida):
    """Dívida de um lado e dinheiro do outro não é transferência."""
    lancamento = sistema.pagar_divida(divida, 440.0, contas["banco"], sistema.hoje_iso())

    info = sistema.classificar_lancamento(partidas_do(sistema, lancamento))
    assert info["tipo"] == "SAIDA"
    assert info["rotulo"] == "Pagamento de dívida"
    assert info["categoria"] == "Mensalidade"
    assert info["conta"] == "Banco Teste"


def test_dinheiro_tomado_emprestado_aparece_como_entrada(sistema, contas):
    conta_divida = sistema.criar_divida("Empréstimo", "Banco X", 1.0, "2026-01-10")
    lancamento = sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Empréstimo recebido",
        [sistema.Partida(contas["banco"], "D", 2000.0),
         sistema.Partida(conta_divida, "C", 2000.0)])

    info = sistema.classificar_lancamento(partidas_do(sistema, lancamento))
    assert info["tipo"] == "ENTRADA"
    assert info["rotulo"] == "Dívida tomada"


def test_transferencia_entre_contas_continua_transferencia(sistema, contas):
    lancamento = sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Saque",
        [sistema.Partida(contas["outra"], "D", 100.0),
         sistema.Partida(contas["banco"], "C", 100.0)])

    info = sistema.classificar_lancamento(partidas_do(sistema, lancamento))
    assert info["tipo"] == "TRANSFERENCIA"


def test_pagar_fatura_do_cartao_e_pagamento_de_divida(sistema, contas):
    sistema.salvar_lancamento(
        None, "2026-02-01", "Compra no cartão",
        [sistema.Partida(contas["despesa"], "D", 300.0),
         sistema.Partida(contas["cartao"], "C", 300.0)])
    lancamento = sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Pagamento da fatura",
        [sistema.Partida(contas["cartao"], "D", 300.0),
         sistema.Partida(contas["banco"], "C", 300.0)])

    info = sistema.classificar_lancamento(partidas_do(sistema, lancamento))
    assert info["tipo"] == "SAIDA"
    assert info["rotulo"] == "Pagamento de dívida"
