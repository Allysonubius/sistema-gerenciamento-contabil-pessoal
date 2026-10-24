"""A senha de abertura: uma tranca na porta, presa a este computador.

O que ela protege e o que não protege está escrito no módulo, na tela e aqui —
uma tranca anunciada como cofre é pior do que nenhuma.
"""
from __future__ import annotations

import pytest

from app import seguranca


@pytest.fixture()
def limpo(sistema):
    """Banco sem senha nenhuma."""
    seguranca._limpar()
    return sistema


# --------------------------------------------------------------------------- #
# Criar e conferir
# --------------------------------------------------------------------------- #
def test_no_comeco_nao_ha_senha(limpo):
    assert seguranca.tem_senha() is False


def test_criar_e_conferir(limpo):
    seguranca.definir_senha("segredo123", "segredo123")

    assert seguranca.tem_senha() is True
    assert seguranca.conferir_senha("segredo123") is True
    assert seguranca.criada_em()


def test_senha_errada_nao_entra(limpo):
    seguranca.definir_senha("segredo123", "segredo123")

    assert seguranca.conferir_senha("segredo124") is False
    assert seguranca.conferir_senha("") is False
    assert seguranca.conferir_senha("SEGREDO123") is False


def test_a_senha_nao_fica_guardada_em_texto(limpo):
    from app import db

    seguranca.definir_senha("segredo123", "segredo123")
    guardado = db.get_config(seguranca.CHAVE_HASH, "")

    assert "segredo123" not in guardado
    assert len(guardado) == 64            # sha256 em hexadecimal


def test_cada_senha_tem_o_seu_sal(limpo):
    from app import db

    seguranca.definir_senha("segredo123", "segredo123")
    primeiro = db.get_config(seguranca.CHAVE_HASH, "")
    seguranca.definir_senha("segredo123", "segredo123")

    # Mesma senha, hash diferente: o sal é sorteado a cada vez.
    assert db.get_config(seguranca.CHAVE_HASH, "") != primeiro


def test_conferir_sem_senha_cadastrada(limpo):
    assert seguranca.conferir_senha("qualquer") is False


# --------------------------------------------------------------------------- #
# As regras da senha
# --------------------------------------------------------------------------- #
def test_senha_curta_e_recusada(limpo):
    with pytest.raises(ValueError, match="pelo menos"):
        seguranca.definir_senha("abc", "abc")


def test_senha_de_um_caractere_repetido_e_recusada(limpo):
    with pytest.raises(ValueError, match="repetido"):
        seguranca.definir_senha("aaaaaaaa", "aaaaaaaa")


def test_confirmacao_diferente_e_recusada(limpo):
    with pytest.raises(ValueError, match="iguais"):
        seguranca.definir_senha("segredo123", "segredo124")


def test_espaco_nas_pontas_e_recusado(limpo):
    with pytest.raises(ValueError, match="espaço"):
        seguranca.definir_senha(" segredo123 ", " segredo123 ")


def test_senha_recusada_nao_fica_pela_metade(limpo):
    with pytest.raises(ValueError):
        seguranca.definir_senha("abc", "abc")

    assert seguranca.tem_senha() is False


# --------------------------------------------------------------------------- #
# Presa a este computador
# --------------------------------------------------------------------------- #
def test_a_maquina_entra_na_conta(limpo, monkeypatch):
    """O mesmo banco levado para outro computador não abre com a mesma senha."""
    seguranca.definir_senha("segredo123", "segredo123")
    assert seguranca.conferir_senha("segredo123") is True

    monkeypatch.setattr(seguranca, "_id_da_maquina", lambda: "outro-computador")

    assert seguranca.conferir_senha("segredo123") is False


def test_o_programa_sabe_dizer_que_a_maquina_e_outra(limpo, monkeypatch):
    """Para a tela poder explicar, em vez de só dizer 'senha errada'."""
    seguranca.definir_senha("segredo123", "segredo123")
    assert seguranca.maquina_confere() is True

    monkeypatch.setattr(seguranca, "_id_da_maquina", lambda: "outro-computador")

    assert seguranca.maquina_confere() is False


def test_sem_senha_a_maquina_nao_importa(limpo, monkeypatch):
    monkeypatch.setattr(seguranca, "_id_da_maquina", lambda: "outro-computador")

    assert seguranca.maquina_confere() is True


def test_a_impressao_da_maquina_e_estavel(limpo):
    assert seguranca.impressao_da_maquina() == seguranca.impressao_da_maquina()
    assert len(seguranca.impressao_da_maquina()) == 64


# --------------------------------------------------------------------------- #
# Trocar, tirar e esquecer
# --------------------------------------------------------------------------- #
def test_trocar_sabendo_a_atual(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    seguranca.trocar_senha("segredo123", "outrosegredo", "outrosegredo")

    assert seguranca.conferir_senha("outrosegredo") is True
    assert seguranca.conferir_senha("segredo123") is False


def test_trocar_sem_saber_a_atual(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    with pytest.raises(ValueError, match="não confere"):
        seguranca.trocar_senha("chute", "outrosegredo", "outrosegredo")

    assert seguranca.conferir_senha("segredo123") is True


def test_tirar_a_senha(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    seguranca.remover_senha("segredo123")

    assert seguranca.tem_senha() is False


def test_tirar_sem_saber_a_senha(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    with pytest.raises(ValueError):
        seguranca.remover_senha("chute")

    assert seguranca.tem_senha() is True


def test_esqueci_exige_a_palavra_exata(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    for errada in ("", "apagar", "APAGAR", "sim"):
        with pytest.raises(ValueError):
            seguranca.apagar_senha_esquecida(errada)

    assert seguranca.tem_senha() is True


def test_esqueci_com_a_palavra_certa_destrava(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    seguranca.apagar_senha_esquecida(seguranca.PALAVRA_DE_RESET)

    assert seguranca.tem_senha() is False


def test_esqueci_aceita_minusculas_e_espacos(limpo):
    seguranca.definir_senha("segredo123", "segredo123")
    seguranca.apagar_senha_esquecida("  apagar senha  ")

    assert seguranca.tem_senha() is False


def test_apagar_a_senha_nao_mexe_nos_dados(limpo, contas):
    """A tranca sai; o que está guardado atrás dela fica."""
    antes = limpo.saldo_conta(contas["banco"])
    seguranca.definir_senha("segredo123", "segredo123")
    seguranca.apagar_senha_esquecida(seguranca.PALAVRA_DE_RESET)

    assert limpo.saldo_conta(contas["banco"]) == antes


# --------------------------------------------------------------------------- #
# Castigo para quem fica chutando
# --------------------------------------------------------------------------- #
def test_a_espera_cresce_a_cada_erro(limpo):
    esperas = [seguranca.espera_apos_erro(n) for n in range(1, 7)]

    assert esperas == sorted(esperas)
    assert esperas[0] <= 2


def test_a_espera_tem_teto(limpo):
    assert seguranca.espera_apos_erro(50) == 30.0


def test_sem_erro_nao_ha_espera(limpo):
    assert seguranca.espera_apos_erro(0) == 0.0
