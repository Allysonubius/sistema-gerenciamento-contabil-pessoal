"""Campos de digitação: dinheiro em BRL e datas com limite de período."""
from __future__ import annotations

import importlib
import tkinter as tk
from types import SimpleNamespace

import pytest



@pytest.fixture()
def tela(sistema, raiz_tk):
    widgets = importlib.import_module("app.ui.widgets")
    yield raiz_tk, widgets
    for filho in raiz_tk.winfo_children():
        filho.destroy()


def tecla(texto: str = "", keysym: str | None = None, state: int = 0):
    return SimpleNamespace(char=texto, keysym=keysym or texto, state=state)


def digitar(campo, texto: str) -> None:
    for caractere in texto:
        campo._tecla(tecla(caractere))


# --- dinheiro --------------------------------------------------------------- #
def test_digitar_numeros_enche_os_centavos(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    digitar(campo, "1")
    assert campo.get() == "R$ 0,01"
    digitar(campo, "2345")
    assert campo.get() == "R$ 123,45"
    digitar(campo, "67")
    assert campo.get() == "R$ 12.345,67"
    assert campo.get_valor() == 12345.67


def test_valor_nao_trava_depois_de_formatado(tela):
    """O defeito: depois do primeiro dígito o campo parava de aceitar números."""
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    digitar(campo, "15090")
    assert campo.get_valor() == 150.90


def test_backspace_apaga_o_ultimo_digito(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    digitar(campo, "12345")
    campo._tecla(tecla(keysym="BackSpace"))
    assert campo.get() == "R$ 12,34"
    for _ in range(4):
        campo._tecla(tecla(keysym="BackSpace"))
    assert campo.get() == ""


def test_letras_e_simbolos_nao_entram(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    digitar(campo, "1a2-,3")
    assert campo.get() == "R$ 1,23"


def test_valor_selecionado_e_substituido_ao_digitar(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    campo.set_valor(110.0)
    campo.select_range(0, tk.END)
    digitar(campo, "5")
    assert campo.get() == "R$ 0,05"


def test_set_valor_formata_em_reais(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    campo.set_valor(1234567.8)
    assert campo.get() == "R$ 1.234.567,80"
    campo.set_valor(0)
    assert campo.get() == "R$ 0,00"
    campo.set_valor(-50.5)
    assert campo.get_valor() == -50.5


def test_colar_valor_ja_formatado(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    raiz.clipboard_clear()
    raiz.clipboard_append("1.234,56")
    campo._colar()
    assert campo.get_valor() == 1234.56


def test_campo_travado_nao_muda(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    campo.set_valor(125.17)
    campo.configure(state="readonly")
    digitar(campo, "9")
    assert campo.get_valor() == 125.17


def test_teclas_de_navegacao_passam(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    for nome in ("Tab", "Left", "Return"):
        assert campo._tecla(tecla(keysym=nome)) is None
    # Ctrl+V deve seguir para a colagem normal
    assert campo._tecla(tecla("v", state=campo.CONTROL)) is None


def test_ao_mudar_espera_parar_de_digitar(tela):
    raiz, widgets = tela
    campo = widgets.CampoValor(raiz)
    chamadas = []
    campo.ao_mudar(lambda: chamadas.append(campo.get_valor()), atraso=10)
    digitar(campo, "1000")
    assert chamadas == []                     # nada durante a digitação
    raiz.after(60, raiz.quit)
    raiz.mainloop()
    assert chamadas == [10.0]                 # uma única chamada no fim


# --- datas ------------------------------------------------------------------ #
def test_intervalo_liga_inicio_e_fim(tela):
    raiz, widgets = tela
    inicio = widgets.CampoData(raiz, "2026-09-10")
    fim = widgets.CampoData(raiz, "2026-09-30")
    inicio.ligar_intervalo(fim)

    assert fim._minimo == "2026-09-10"
    assert inicio._maximo == "2026-09-30"
    assert fim._dentro_dos_limites("2026-09-05") is not None
    assert fim._dentro_dos_limites("2026-09-15") is None

    inicio.set_iso("2026-09-20")
    assert fim._minimo == "2026-09-20"
