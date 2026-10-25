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


# --------------------------------------------------------------------------- #
# Banco que não abre
# --------------------------------------------------------------------------- #
def _quebrar_indice(caminho, nome: str) -> None:
    """Faz um índice apontar para uma página além do fim do arquivo.

    É o estrago típico de um VACUUM interrompido: o arquivo encolhe e o
    catálogo continua apontando para páginas que não existem mais.
    """
    import sqlite3

    conexao = sqlite3.connect(caminho)
    paginas = conexao.execute("PRAGMA page_count").fetchone()[0]
    conexao.execute("PRAGMA writable_schema = ON")
    conexao.execute("UPDATE sqlite_schema SET rootpage = ? WHERE name = ?",
                    (paginas + 50, nome))
    conexao.commit()
    conexao.close()


def test_indice_orfao_e_consertado_na_abertura(sistema, contas):
    """Antes, o programa morria aqui — sem janela, sem aviso, sem nada."""
    import importlib
    import sys

    from app import db

    caminho = db.DB_PATH
    db.fechar()
    _quebrar_indice(caminho, "ix_lancamento_data")

    importlib.reload(sys.modules["app.db"])
    novo = sys.modules["app.db"]
    conexao = novo.get_connection()

    assert conexao.execute("SELECT COUNT(*) FROM conta").fetchone()[0] > 0
    # O índice volta pela própria migração, que roda a cada abertura.
    assert novo.query_one(
        "SELECT 1 AS x FROM sqlite_master WHERE name = 'ix_lancamento_data'")


def test_banco_sem_conserto_vira_erro_com_as_copias_na_mao(sistema, monkeypatch):
    """Não dando para consertar, o programa precisa dizer isso e apontar a saída."""
    import sqlite3

    from app import db

    db.fazer_backup()
    monkeypatch.setattr(db, "_curar_indices", lambda _c: [])

    def recusar(*_a, **_k):
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(db, "_abrir_arquivo", recusar)
    db.fechar()

    with pytest.raises(db.BancoDanificadoError) as erro:
        db.get_connection()

    assert "malformed" in erro.value.motivo
    assert erro.value.copias, "o aviso precisa trazer as cópias de segurança"


def test_as_copias_vem_da_mais_recente_para_a_mais_antiga(sistema):
    import time

    from app import db

    primeira = db.fazer_backup()
    time.sleep(1.1)
    segunda = db.fazer_backup()
    copias = db.copias_disponiveis()

    assert copias[0] == segunda
    assert primeira in copias
