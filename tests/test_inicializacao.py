"""Abrir junto com o Windows.

O registro de verdade nunca é tocado: os testes usam um winreg de mentira, com
o mesmo comportamento das poucas funções que o sistema usa.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager

import pytest

from app import inicializacao


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self):
        self.valores: dict[str, str] = {}

    @contextmanager
    def _chave(self):
        yield self

    def OpenKey(self, raiz, caminho):          # noqa: N802 - nome do winreg
        return self._chave()

    def CreateKey(self, raiz, caminho):        # noqa: N802
        return self._chave()

    def QueryValueEx(self, chave, nome):       # noqa: N802
        if nome not in self.valores:
            raise FileNotFoundError(nome)
        return self.valores[nome], self.REG_SZ

    def SetValueEx(self, chave, nome, reservado, tipo, valor):  # noqa: N802
        self.valores[nome] = valor

    def DeleteValue(self, chave, nome):        # noqa: N802
        if nome not in self.valores:
            raise FileNotFoundError(nome)
        del self.valores[nome]


@pytest.fixture()
def registro(monkeypatch):
    falso = FakeWinreg()
    monkeypatch.setattr(inicializacao, "_winreg", lambda: falso)
    monkeypatch.setattr(inicializacao, "disponivel", lambda: True)
    return falso


def test_comeca_desligado(registro):
    assert inicializacao.ativo() is False
    assert inicializacao.situacao() == {"ativo": False, "minimizado": False, "comando": ""}


def test_ligar_grava_o_caminho_do_programa(registro):
    inicializacao.definir(True)

    valor = registro.valores[inicializacao.NOME_ENTRADA]
    assert sys.executable.replace("/", "\\") in valor.replace("/", "\\")
    assert valor.startswith('"')            # caminho com espaços precisa de aspas
    assert inicializacao.ativo() is True
    assert inicializacao.situacao()["minimizado"] is False


def test_ligar_minimizado_guarda_o_argumento(registro):
    inicializacao.definir(True, minimizado=True)

    assert inicializacao.ARGUMENTO_MINIMIZADO in registro.valores[inicializacao.NOME_ENTRADA]
    assert inicializacao.situacao()["minimizado"] is True


def test_ligar_duas_vezes_nao_duplica(registro):
    inicializacao.definir(True)
    inicializacao.definir(True, minimizado=True)

    assert len(registro.valores) == 1
    assert inicializacao.situacao()["minimizado"] is True


def test_desligar_remove_a_entrada(registro):
    inicializacao.definir(True)
    inicializacao.definir(False)

    assert registro.valores == {}
    assert inicializacao.ativo() is False


def test_desligar_o_que_nunca_foi_ligado_nao_quebra(registro):
    assert inicializacao.definir(False) is False


def test_programa_que_mudou_de_pasta_e_reapontado(registro):
    inicializacao.definir(True)
    registro.valores[inicializacao.NOME_ENTRADA] = r'"C:\pasta\antiga\SistemaContabil.exe"'

    inicializacao.sincronizar()

    assert registro.valores[inicializacao.NOME_ENTRADA] == inicializacao.comando()


def test_sincronizar_preserva_o_minimizado(registro):
    inicializacao.definir(True, minimizado=True)
    registro.valores[inicializacao.NOME_ENTRADA] = (
        r'"C:\antiga\SistemaContabil.exe" ' + inicializacao.ARGUMENTO_MINIMIZADO)

    inicializacao.sincronizar()

    assert registro.valores[inicializacao.NOME_ENTRADA] == inicializacao.comando(True)


def test_sincronizar_nao_liga_sozinho(registro):
    inicializacao.sincronizar()
    assert registro.valores == {}


def test_fora_do_windows_a_opcao_some(monkeypatch):
    monkeypatch.setattr(inicializacao, "disponivel", lambda: False)
    assert inicializacao.ativo() is False
    assert inicializacao.definir(True) is False
