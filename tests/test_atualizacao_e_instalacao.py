"""Saber que saiu versão nova, e morar no computador em vez de numa pasta.

A consulta à rede nunca pode atrapalhar: todo caminho de erro aqui termina em
"não sei, e o programa abre do mesmo jeito".
"""
from __future__ import annotations

import urllib.error

import pytest

from app import atualizacao, instalacao


@pytest.fixture()
def rede(monkeypatch):
    """Troca a conversa com o GitHub por uma resposta que eu escolho."""
    def responder(dados):
        monkeypatch.setattr(atualizacao, "consultar", lambda *a, **k: dados)
    return responder


# --------------------------------------------------------------------------- #
# Comparar versões
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("uma, outra, esperado", [
    ("1.2.0", "1.2.0", 0),
    ("1.2.1", "1.2.0", 1),
    ("1.2.0", "1.2.1", -1),
    ("1.10.0", "1.9.0", 1),          # dez é maior que nove, não menor
    ("2.0.0", "1.99.99", 1),
    ("v1.3.0", "1.3.0", 0),          # o "v" da tag não conta
    ("1.3", "1.3.0", 0),             # faltar um pedaço é zero
    ("1.3.0-beta", "1.3.0", 0),      # sufixo ignorado
])
def test_comparar_versoes(uma, outra, esperado):
    assert atualizacao.comparar_versoes(uma, outra) == esperado


def test_versao_estragada_nao_quebra():
    assert atualizacao.comparar_versoes("", "1.0.0") == -1
    assert atualizacao.comparar_versoes("abc", "1.0.0") == -1


# --------------------------------------------------------------------------- #
# A verificação
# --------------------------------------------------------------------------- #
def test_versao_igual_nao_avisa(sistema, rede):
    rede({"versao": atualizacao.APP_VERSION, "pagina": "p", "nome": "", "notas": "",
          "arquivo": "", "tamanho": 0, "publicada_em": ""})
    estado = atualizacao.verificar(forcar=True)

    assert estado["ha_novidade"] is False
    assert atualizacao.deve_avisar() is False


def test_versao_nova_avisa(sistema, rede):
    rede({"versao": "99.0.0", "pagina": "https://exemplo/99", "nome": "", "notas": "",
          "arquivo": "", "tamanho": 0, "publicada_em": ""})
    estado = atualizacao.verificar(forcar=True)

    assert estado["ha_novidade"] is True
    assert estado["disponivel"] == "99.0.0"
    assert estado["pagina"] == "https://exemplo/99"
    assert atualizacao.deve_avisar() is True


def test_versao_mais_velha_la_fora_nao_avisa(sistema, rede):
    rede({"versao": "0.0.1", "pagina": "p", "nome": "", "notas": "", "arquivo": "",
          "tamanho": 0, "publicada_em": ""})

    assert atualizacao.verificar(forcar=True)["ha_novidade"] is False


def test_sem_internet_o_programa_segue(sistema, monkeypatch):
    """O caminho que mais importa: falhar sem estorvar."""
    def explodir(*_a, **_k):
        raise urllib.error.URLError("sem rede")

    monkeypatch.setattr(atualizacao.urllib.request, "urlopen", explodir)
    estado = atualizacao.verificar(forcar=True)

    assert estado["falhou"] is True
    assert estado["ha_novidade"] is False
    assert estado["atual"] == atualizacao.APP_VERSION


def test_resposta_sem_tag_e_ignorada(sistema, monkeypatch):
    class Falsa:
        def read(self): return b'{"name": "sem tag"}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(atualizacao.urllib.request, "urlopen", lambda *a, **k: Falsa())

    assert atualizacao.consultar() is None


def test_o_que_foi_visto_fica_guardado(sistema, rede):
    rede({"versao": "99.0.0", "pagina": "https://exemplo/99", "nome": "", "notas": "",
          "arquivo": "", "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)

    # Sem tocar na rede de novo, o programa continua sabendo.
    assert atualizacao.estado_guardado()["ha_novidade"] is True


def test_nao_pergunta_duas_vezes_no_mesmo_dia(sistema, rede):
    rede({"versao": "99.0.0", "pagina": "p", "nome": "", "notas": "", "arquivo": "",
          "tamanho": 0, "publicada_em": ""})
    assert atualizacao.esta_na_hora() is True
    atualizacao.verificar(forcar=True)

    assert atualizacao.esta_na_hora() is False


def test_desligar_a_verificacao(sistema):
    atualizacao.definir_verificacao(False)

    assert atualizacao.verificacao_ligada() is False
    assert atualizacao.esta_na_hora() is False


def test_desligada_o_botao_ainda_procura(sistema, rede):
    """'Procurar agora' é pedido do usuário: ignora o desligamento."""
    atualizacao.definir_verificacao(False)
    rede({"versao": "99.0.0", "pagina": "p", "nome": "", "notas": "", "arquivo": "",
          "tamanho": 0, "publicada_em": ""})

    assert atualizacao.verificar(forcar=True)["ha_novidade"] is True


def test_ignorar_uma_versao(sistema, rede):
    rede({"versao": "99.0.0", "pagina": "p", "nome": "", "notas": "", "arquivo": "",
          "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)
    atualizacao.ignorar("99.0.0")

    assert atualizacao.deve_avisar() is False
    assert atualizacao.estado_guardado()["ignorada"] is True


def test_a_versao_seguinte_volta_a_avisar(sistema, rede):
    rede({"versao": "99.0.0", "pagina": "p", "nome": "", "notas": "", "arquivo": "",
          "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)
    atualizacao.ignorar("99.0.0")

    rede({"versao": "99.0.1", "pagina": "p", "nome": "", "notas": "", "arquivo": "",
          "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)

    assert atualizacao.deve_avisar() is True


# --------------------------------------------------------------------------- #
# Instalação
# --------------------------------------------------------------------------- #
def test_fora_do_executavel_nao_ha_instalacao(sistema):
    """Rodando pelo código-fonte não existe .exe para copiar."""
    assert instalacao.disponivel() is False
    assert instalacao.deve_oferecer_instalacao() is False


def test_a_pasta_fica_dentro_do_perfil_do_usuario(sistema, tmp_path):
    caminho = instalacao.pasta_de_instalacao()

    assert "Programs" in str(caminho)
    assert caminho.name == "SistemaContabil"


def test_instalar_fora_do_executavel_e_recusado(sistema):
    with pytest.raises(RuntimeError, match="executável"):
        instalacao.instalar()


def test_o_convite_so_aparece_uma_vez(sistema, monkeypatch):
    monkeypatch.setattr(instalacao, "disponivel", lambda: True)
    monkeypatch.setattr(instalacao, "portatil", lambda: False)
    monkeypatch.setattr(instalacao, "rodando_do_local_instalado", lambda: False)
    assert instalacao.deve_oferecer_instalacao() is True

    instalacao.recusar_convite()

    assert instalacao.deve_oferecer_instalacao() is False


def test_modo_portatil_nunca_e_convidado(sistema, monkeypatch):
    monkeypatch.setattr(instalacao, "disponivel", lambda: True)
    monkeypatch.setattr(instalacao, "portatil", lambda: True)

    assert instalacao.deve_oferecer_instalacao() is False


def test_ja_instalado_nao_e_convidado(sistema, monkeypatch):
    monkeypatch.setattr(instalacao, "disponivel", lambda: True)
    monkeypatch.setattr(instalacao, "portatil", lambda: False)
    monkeypatch.setattr(instalacao, "rodando_do_local_instalado", lambda: True)

    assert instalacao.deve_oferecer_instalacao() is False


def test_limpar_restos_sem_pasta_nao_quebra(sistema):
    assert instalacao.limpar_restos() == 0


def test_limpar_restos_apaga_os_old(sistema, monkeypatch, tmp_path):
    pasta = tmp_path / "Programs" / "SistemaContabil"
    pasta.mkdir(parents=True)
    (pasta / "SistemaContabil.old").write_bytes(b"velho")
    (pasta / "SistemaContabil.exe").write_bytes(b"novo")
    monkeypatch.setattr(instalacao, "pasta_de_instalacao", lambda: pasta)

    assert instalacao.limpar_restos() == 1
    assert not (pasta / "SistemaContabil.old").exists()
    assert (pasta / "SistemaContabil.exe").exists()


def test_a_situacao_descreve_tudo_que_a_tela_precisa(sistema):
    estado = instalacao.situacao()

    assert set(estado) == {"disponivel", "portatil", "instalado", "aqui",
                           "caminho_atual", "caminho_instalado", "oferecer"}


def test_a_chave_do_windows_nao_tem_barra_dobrada(sistema):
    """Uma barra a mais e o programa não apareceria na lista de aplicativos."""
    assert "\\\\" not in instalacao.CHAVE_DESINSTALAR
    assert instalacao.CHAVE_DESINSTALAR.endswith("\\SistemaContabil")


# --------------------------------------------------------------------------- #
# Trocar para a cópia instalada
# --------------------------------------------------------------------------- #
def test_a_trava_sai_antes_de_a_copia_instalada_subir(sistema, monkeypatch):
    """A ordem do desligamento é o que fazia a instalação parecer não acontecer.

    A trava de instância única é um mutex preso ao processo. Subindo a cópia
    instalada antes de soltá-la, ela se enxerga como segunda janela, avisa esta
    e encerra sozinha — nada novo abre, e nada fecha.
    """
    import subprocess

    from app import db, instancia
    from app.ui import main_window

    ordem = []
    monkeypatch.setattr(instancia, "liberar", lambda: ordem.append("soltou a trava"))
    monkeypatch.setattr(db, "fechar", lambda: ordem.append("fechou o banco"))
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: ordem.append("abriu a cópia"))

    class JanelaFalsa:
        _encerrando = False
        bandeja = type("B", (), {"parar": lambda self: None})()
        _trocar_para_a_copia_instalada = main_window.Aplicacao._trocar_para_a_copia_instalada

        def destroy(self):
            ordem.append("fechou a janela")

    JanelaFalsa()._trocar_para_a_copia_instalada("C:/qualquer/SistemaContabil.exe")

    assert ordem.index("soltou a trava") < ordem.index("abriu a cópia")
    assert ordem[-1] == "fechou a janela"


def test_a_troca_fecha_a_janela_mesmo_se_a_copia_nao_subir(sistema, monkeypatch):
    import subprocess

    from app import db, instancia
    from app.ui import main_window

    fechou = []
    monkeypatch.setattr(instancia, "liberar", lambda: None)
    monkeypatch.setattr(db, "fechar", lambda: None)
    monkeypatch.setattr(main_window.messagebox, "showwarning",
                        lambda *a, **k: None)

    def falhar(*_a, **_k):
        raise OSError("sem permissão")

    monkeypatch.setattr(subprocess, "Popen", falhar)

    class JanelaFalsa:
        _encerrando = False
        bandeja = type("B", (), {"parar": lambda self: None})()
        _trocar_para_a_copia_instalada = main_window.Aplicacao._trocar_para_a_copia_instalada

        def destroy(self):
            fechou.append(True)

    JanelaFalsa()._trocar_para_a_copia_instalada("C:/qualquer/SistemaContabil.exe")

    assert fechou == [True]
