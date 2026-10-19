"""Índice fora de sincronia: o sistema precisa detectar e consertar.

Aconteceu de verdade: o índice de partidas por conta apontava para linhas de
outra conta, e um empréstimo de R$ 9.293,22 aparecia como gasto de supermercado.
"""
from __future__ import annotations

import pytest


def test_banco_saudavel_nao_precisa_de_conserto(sistema):
    assert sistema.db.reparar_indices() is None


def test_quick_check_continua_ok_depois_do_reparo(sistema, contas):
    sistema.salvar_lancamento(
        None, "2026-03-10", "Compra",
        [sistema.Partida(contas["despesa"], "D", 100.0),
         sistema.Partida(contas["banco"], "C", 100.0)])

    sistema.db.reparar_indices()

    estado = sistema.db.query_one("PRAGMA quick_check")[0]
    assert estado == "ok"


class ConexaoFalsa:
    """Dublê de conexão: responde ao quick_check e anota o que foi executado."""

    def __init__(self, *respostas: str):
        self._respostas = list(respostas)
        self.comandos: list[str] = []

    def execute(self, sql, *args, **kwargs):
        self.comandos.append(sql.strip())
        if sql.strip().upper().startswith("PRAGMA QUICK_CHECK"):
            valor = self._respostas.pop(0) if self._respostas else "ok"
            return _Resultado(valor)
        return _Resultado("ok")

    def commit(self):
        self.comandos.append("COMMIT")


class _Resultado:
    def __init__(self, valor):
        self._valor = valor

    def fetchone(self):
        return (self._valor,)


def test_reparo_avisa_qual_era_o_problema(sistema, monkeypatch):
    """Quando o SQLite reclama, a função devolve o texto para o aviso na tela."""
    falsa = ConexaoFalsa("wrong # of entries in index ix_partida_conta", "ok")
    monkeypatch.setattr(sistema.db, "get_connection", lambda: falsa)

    problema = sistema.db.reparar_indices()

    assert problema is not None
    assert "ix_partida_conta" in problema
    assert "REINDEX" in falsa.comandos          # e consertou


def test_banco_sem_problema_nao_roda_reindex(sistema, monkeypatch):
    falsa = ConexaoFalsa("ok")
    monkeypatch.setattr(sistema.db, "get_connection", lambda: falsa)

    assert sistema.db.reparar_indices() is None
    assert "REINDEX" not in falsa.comandos


def test_reparo_preserva_os_lancamentos(sistema, contas):
    for dia, valor in ((5, 50.0), (10, 70.0)):
        sistema.salvar_lancamento(
            None, f"2026-03-{dia:02d}", "Compra",
            [sistema.Partida(contas["despesa"], "D", valor),
             sistema.Partida(contas["banco"], "C", valor)])
    antes = sistema.saldo_conta(contas["banco"])

    sistema.db.get_connection().execute("REINDEX")

    assert sistema.saldo_conta(contas["banco"]) == antes
    assert len(sistema.listar_lancamentos()) >= 2
