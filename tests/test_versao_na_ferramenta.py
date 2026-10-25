"""A versão nova se explica dentro do programa, sem navegador.

Mandar a pessoa procurar um .exe numa página e achar o botão certo é pedir para
ela errar. O programa já sabe o que mudou e onde está o arquivo.
"""
from __future__ import annotations

import importlib

import pytest

from app import atualizacao


@pytest.fixture()
def versao_nova(sistema, monkeypatch):
    """Finge que saiu a 99.0.0, com notas e arquivo."""
    dados = {
        "versao": "99.0.0",
        "nome": "Minhas Contas v99.0.0",
        "notas": "# Titulo\n\n## Uma seção\n\nTexto **forte** com `codigo`.\n\n"
                 "- primeiro item\n- segundo item\n",
        "pagina": "https://exemplo/99",
        "arquivo": "https://exemplo/99/SistemaContabil.exe",
        "tamanho": 2048,
        "publicada_em": "2026-10-24T23:00:00Z",
    }
    monkeypatch.setattr(atualizacao, "consultar", lambda *a, **k: dados)
    atualizacao.verificar(forcar=True)
    return dados


# --------------------------------------------------------------------------- #
# O que mudou vem junto
# --------------------------------------------------------------------------- #
def test_as_notas_ficam_guardadas(sistema, versao_nova):
    """Sem isso, a tela teria de voltar à rede para contar a novidade."""
    estado = atualizacao.estado_guardado()

    assert "primeiro item" in estado["notas"]
    assert estado["arquivo"].endswith(".exe")
    assert estado["tamanho"] == 2048
    assert estado["publicada_em"].startswith("2026-10-24")


def test_markdown_vira_texto_legivel():
    texto = atualizacao.em_texto(
        "# Titulo\n\n## Uma seção\n\nTexto **forte** com `codigo`.\n\n- um\n- dois\n")

    assert "**" not in texto and "`" not in texto and "#" not in texto
    assert "UMA SEÇÃO" in texto          # as seções ficam em destaque
    assert "• um" in texto


def test_markdown_vazio_nao_quebra():
    assert atualizacao.em_texto("") == ""
    assert atualizacao.em_texto(None) == ""


def test_blocos_de_codigo_saem_do_caminho():
    texto = atualizacao.em_texto("Antes\n```bash\ncomando\n```\nDepois")

    assert "```" not in texto
    assert "Antes" in texto and "Depois" in texto


def test_linhas_vazias_seguidas_viram_uma():
    assert "\n\n\n" not in atualizacao.em_texto("a\n\n\n\n\nb")


# --------------------------------------------------------------------------- #
# Baixar
# --------------------------------------------------------------------------- #
class _Resposta:
    def __init__(self, conteudo: bytes, tamanho=None):
        self._conteudo = conteudo
        self._lido = False
        self.headers = {"Content-Length": str(tamanho if tamanho is not None
                                               else len(conteudo))}

    def read(self, _n=None):
        if self._lido:
            return b""
        self._lido = True
        return self._conteudo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_baixa_e_guarda_o_arquivo(sistema, versao_nova, monkeypatch, tmp_path):
    monkeypatch.setattr(atualizacao.urllib.request, "urlopen",
                        lambda *a, **k: _Resposta(b"x" * 2048))
    destino = tmp_path / "baixado" / "novo.exe"
    caminho = atualizacao.baixar(destino)

    assert caminho == destino
    assert destino.read_bytes() == b"x" * 2048


def test_o_progresso_e_informado(sistema, versao_nova, monkeypatch, tmp_path):
    monkeypatch.setattr(atualizacao.urllib.request, "urlopen",
                        lambda *a, **k: _Resposta(b"x" * 2048))
    passos = []
    atualizacao.baixar(tmp_path / "novo.exe", lambda v, t: passos.append((v, t)))

    assert passos
    assert passos[-1] == (2048, 2048)


def test_arquivo_incompleto_e_recusado(sistema, versao_nova, monkeypatch, tmp_path):
    """Meio executável é pior do que nenhum."""
    monkeypatch.setattr(atualizacao.urllib.request, "urlopen",
                        lambda *a, **k: _Resposta(b"x" * 100, tamanho=2048))
    destino = tmp_path / "novo.exe"

    with pytest.raises(RuntimeError, match="incompleto"):
        atualizacao.baixar(destino)
    assert not destino.exists()


def test_queda_de_conexao_nao_deixa_executavel_pela_metade(sistema, versao_nova,
                                                            monkeypatch, tmp_path):
    def cair(*_a, **_k):
        raise OSError("conexão perdida")

    monkeypatch.setattr(atualizacao.urllib.request, "urlopen", cair)
    destino = tmp_path / "novo.exe"

    with pytest.raises(RuntimeError, match="Não consegui baixar"):
        atualizacao.baixar(destino)
    assert not destino.exists()
    assert not destino.with_suffix(".exe.parcial").exists()


def test_versao_sem_arquivo_avisa(sistema, monkeypatch, tmp_path):
    monkeypatch.setattr(atualizacao, "consultar", lambda *a, **k: {
        "versao": "99.0.0", "nome": "", "notas": "", "pagina": "p",
        "arquivo": "", "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)

    with pytest.raises(RuntimeError, match="arquivo"):
        atualizacao.baixar(tmp_path / "novo.exe")


# --------------------------------------------------------------------------- #
# Instalar a partir do que foi baixado
# --------------------------------------------------------------------------- #
def test_instalar_aceita_um_arquivo_baixado(sistema, monkeypatch, tmp_path):
    from app import instalacao

    pasta = tmp_path / "Programs" / "SistemaContabil"
    monkeypatch.setattr(instalacao, "pasta_de_instalacao", lambda: pasta)
    monkeypatch.setattr(instalacao, "caminho_instalado",
                        lambda: pasta / "SistemaContabil.exe")
    monkeypatch.setattr(instalacao, "portatil", lambda: False)
    monkeypatch.setattr(instalacao, "criar_atalho", lambda *a, **k: True)
    monkeypatch.setattr(instalacao, "_registrar_na_lista_de_programas", lambda _a: None)

    baixado = tmp_path / "SistemaContabil-99.exe"
    baixado.write_bytes(b"programa novo")
    resultado = instalacao.instalar(origem=baixado)

    assert resultado["caminho"].read_bytes() == b"programa novo"


def test_instalar_de_arquivo_inexistente(sistema, monkeypatch, tmp_path):
    from app import instalacao

    monkeypatch.setattr(instalacao, "portatil", lambda: False)
    with pytest.raises(RuntimeError, match="não encontrado"):
        instalacao.instalar(origem=tmp_path / "nao_existe.exe")


# --------------------------------------------------------------------------- #
# A janela
# --------------------------------------------------------------------------- #
def test_a_janela_conta_o_que_mudou(sistema, versao_nova, raiz_tk):
    modulo = importlib.reload(importlib.import_module("app.ui.versao"))
    janela = modulo.JanelaNovaVersao(raiz_tk)
    janela.grab_release()
    try:
        texto = janela.txt.get("1.0", "end")
        assert "primeiro item" in texto
        assert "**" not in texto
        assert janela.estado["disponivel"] == "99.0.0"
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_janela_diz_o_tamanho_antes_de_baixar(sistema, versao_nova, raiz_tk,
                                                monkeypatch):
    modulo = importlib.reload(importlib.import_module("app.ui.versao"))
    monkeypatch.setattr(modulo.instalacao, "disponivel", lambda: True)
    janela = modulo.JanelaNovaVersao(raiz_tk)
    janela.grab_release()
    try:
        janela._explicar()
        assert "MB" in janela.lbl_situacao.cget("text")
        assert "dados ficam" in janela.lbl_situacao.cget("text")
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_a_janela_avisa_quando_nao_da_para_atualizar_daqui(sistema, versao_nova,
                                                           raiz_tk):
    """Rodando pelo código-fonte não há executável para trocar."""
    modulo = importlib.reload(importlib.import_module("app.ui.versao"))
    janela = modulo.JanelaNovaVersao(raiz_tk)
    janela.grab_release()
    try:
        assert "código-fonte" in janela.lbl_situacao.cget("text")
        assert "disabled" in janela.btn_baixar.state()
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_ignorar_pela_janela(sistema, versao_nova, raiz_tk):
    modulo = importlib.reload(importlib.import_module("app.ui.versao"))
    janela = modulo.JanelaNovaVersao(raiz_tk)
    janela.grab_release()
    try:
        janela.ignorar()
        assert atualizacao.deve_avisar() is False
    finally:
        for filho in raiz_tk.winfo_children():
            filho.destroy()


def test_o_programa_nao_abre_mais_navegador():
    """O pedido era explícito: resolver tudo aqui dentro."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "app"
    for arquivo in raiz.rglob("*.py"):
        assert "webbrowser" not in arquivo.read_text(encoding="utf-8"), arquivo


def test_sem_novidade_a_janela_so_relembra(sistema, monkeypatch, raiz_tk):
    """O botão continua servindo: ver o que mudou na versão que está rodando."""
    monkeypatch.setattr(atualizacao, "consultar", lambda *a, **k: {
        "versao": atualizacao.APP_VERSION, "nome": "", "notas": "## Novidades\n\n- algo",
        "pagina": "p", "arquivo": "", "tamanho": 0, "publicada_em": ""})
    atualizacao.verificar(forcar=True)

    modulo = importlib.reload(importlib.import_module("app.ui.versao"))
    janela = modulo.JanelaNovaVersao(raiz_tk)
    janela.grab_release()
    try:
        assert "mais recente" in janela.lbl_situacao.cget("text")
        assert "algo" in janela.txt.get("1.0", "end")
        # Sem novidade não há o que baixar: o botão nem aparece.
        assert not janela.btn_baixar.winfo_ismapped()
    finally:
        janela.destroy()
        for filho in raiz_tk.winfo_children():
            filho.destroy()
