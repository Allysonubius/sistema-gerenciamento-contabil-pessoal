"""Base dos testes: cada teste roda em um banco novo e descartável.

O banco de produção fica em %LOCALAPPDATA%\\SistemaContabil. Apontando essa
variável para uma pasta temporária antes de importar `app.db`, os testes nunca
tocam nos dados reais.
"""
from __future__ import annotations

import importlib
import sys
import tkinter as tk
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


@pytest.fixture()
def sistema(tmp_path, monkeypatch):
    """Devolve o módulo `services` ligado a um banco limpo e isolado."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    # Recarrega a cadeia de módulos para que os caminhos sejam relidos.
    for nome in ("app.services", "app.db", "app.config"):
        if nome in sys.modules:
            del sys.modules[nome]
    config = importlib.import_module("app.config")
    assert str(tmp_path) in str(config.DB_PATH), "o teste não pode usar o banco real"

    db = importlib.import_module("app.db")
    services = importlib.import_module("app.services")
    db.get_connection()
    try:
        yield services
    finally:
        db.fechar()


@pytest.fixture()
def fixar_hoje(sistema, monkeypatch):
    """Simula a data de hoje para testes que contam uma história no passado.

    Movimentos em cartão atualizam a fatura com a data de hoje; sem isto, uma
    compra "de fevereiro" fecharia todas as faturas até a data real.
    """
    def fixar(data_iso: str) -> None:
        monkeypatch.setattr(sistema, "hoje_iso", lambda: data_iso)
    return fixar


@pytest.fixture()
def contas(sistema):
    """Um conjunto mínimo de contas para os testes: banco, categoria e cartão."""
    banco = sistema.criar_carteira("Banco Teste", "Conta corrente", "Teste", 1000.0, "2026-01-01")
    outra = sistema.criar_carteira("Carteira", "Dinheiro em espécie", "", 100.0, "2026-01-01")
    cartao = sistema.criar_carteira("Cartão Teste",
                                    "Cartão de crédito (você paga a fatura depois)", "Teste")
    despesa = sistema._conta_por_codigo("5.2.01")     # Supermercado
    receita = sistema._conta_por_codigo("4.1.01")     # Salário
    return {"banco": banco, "outra": outra, "cartao": cartao,
            "despesa": despesa, "receita": receita}


@pytest.fixture(scope="session")
def raiz_tk():
    """Uma única janela Tk para toda a sessão de testes.

    Dois Tk() no mesmo processo falham no Windows: quando cada arquivo criava o
    seu, os testes de tela do segundo arquivo eram pulados em silêncio.
    """
    try:
        raiz = tk.Tk()
    except tk.TclError:                       # pragma: no cover - máquina sem tela
        pytest.skip("sem ambiente gráfico")
    raiz.withdraw()
    yield raiz
    raiz.destroy()
