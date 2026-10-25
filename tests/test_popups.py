"""Os avisos que param na frente: fechar o mês, o que mudou e a instalação.

Faixa no alto da janela é fácil demais de não ver. Estas três coisas merecem um
passo a mais do usuário.
"""
from __future__ import annotations

import importlib

import pytest

from app import atualizacao


class AppFalso:
    def __init__(self):
        self.avisos: list[str] = []

    def notificar(self, texto: str) -> None:
        self.avisos.append(texto)

    def atualizar_dependentes(self) -> None:
        pass


@pytest.fixture()
def limpar(raiz_tk):
    yield
    for filho in raiz_tk.winfo_children():
        filho.destroy()


@pytest.fixture()
def mes_aberto(sistema, contas):
    """Um lançamento no mês passado, para haver o que fechar."""
    anterior = sistema._mes_anterior(sistema.mes_atual())
    sistema.salvar_lancamento(
        None, f"{anterior}-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 100.0),
         sistema.Partida(contas["banco"], "C", 100.0)])
    return anterior


@pytest.fixture()
def avisos(sistema, limpar):
    return importlib.reload(importlib.import_module("app.ui.avisos"))


# --------------------------------------------------------------------------- #
# Pop-up de fechamento
# --------------------------------------------------------------------------- #
def test_o_popup_diz_qual_mes_e_quantos_registros(avisos, sistema, mes_aberto, raiz_tk):
    primeiro = sistema.meses_a_fechar()[0]
    janela = avisos.DialogoFechamento(raiz_tk)
    janela.grab_release()
    try:
        manchete = janela._manchete()
        assert sistema.mes_nome(primeiro).split()[0] in manchete.lower()
        assert "registro(s) ainda podem ser alterados" in manchete
        assert mes_aberto in sistema.meses_a_fechar()
    finally:
        janela.destroy()


def test_fechar_um_mes_pelo_popup(avisos, sistema, mes_aberto, raiz_tk):
    recados = []
    primeiro = sistema.meses_a_fechar()[0]
    janela = avisos.DialogoFechamento(raiz_tk, recados.append)
    janela.grab_release()

    janela.fechar_um()

    assert sistema.competencia_fechada() == primeiro
    assert recados and "fechada" in recados[0]


def test_fechar_todos_de_uma_vez(avisos, sistema, contas, raiz_tk):
    """Quem deixou vários meses para trás fecha tudo num clique."""
    for mes in ("2026-01", "2026-02"):
        sistema.salvar_lancamento(
            None, f"{mes}-10", "Mercado",
            [sistema.Partida(contas["despesa"], "D", 10.0),
             sistema.Partida(contas["banco"], "C", 10.0)])
    pendentes = sistema.meses_a_fechar()
    janela = avisos.DialogoFechamento(raiz_tk, lambda _r: None)
    janela.grab_release()

    janela.fechar_todos()

    assert sistema.competencia_fechada() == pendentes[-1]
    assert sistema.meses_a_fechar() == []


def test_depois_adia_o_aviso(avisos, sistema, mes_aberto, raiz_tk):
    recados = []
    janela = avisos.DialogoFechamento(raiz_tk, recados.append)
    janela.grab_release()

    janela.depois()

    assert sistema.deve_lembrar_fechamento() is False
    assert sistema.competencia_fechada() == ""
    assert recados and "lembrar" in recados[0]


def test_nunca_mais_desliga(avisos, sistema, mes_aberto, raiz_tk, monkeypatch):
    monkeypatch.setattr(avisos.messagebox, "askyesno", lambda *a, **k: True)
    janela = avisos.DialogoFechamento(raiz_tk, lambda _r: None)
    janela.grab_release()

    janela.nunca_mais()

    assert sistema.lembrete_ligado() is False


def test_nunca_mais_desistindo_nao_desliga(avisos, sistema, mes_aberto, raiz_tk,
                                           monkeypatch):
    monkeypatch.setattr(avisos.messagebox, "askyesno", lambda *a, **k: False)
    janela = avisos.DialogoFechamento(raiz_tk, lambda _r: None)
    janela.grab_release()
    try:
        janela.nunca_mais()
        assert sistema.lembrete_ligado() is True
    finally:
        janela.destroy()


# --------------------------------------------------------------------------- #
# A regra de quando avisar
# --------------------------------------------------------------------------- #
def test_o_mes_corrente_nunca_entra_no_aviso(sistema, contas):
    """Lançar hoje não faz o programa pedir para fechar o mês de hoje."""
    sistema.salvar_lancamento(
        None, sistema.hoje_iso(), "Mercado",
        [sistema.Partida(contas["despesa"], "D", 10.0),
         sistema.Partida(contas["banco"], "C", 10.0)])

    assert sistema.mes_atual() not in sistema.meses_a_fechar()


def test_fechado_ate_o_mes_passado_o_aviso_cala(sistema, mes_aberto):
    """É o estado normal de quem está em dia: nada a cobrar até virar o mês."""
    sistema.fechar_competencia(mes_aberto)

    assert sistema.meses_a_fechar() == []
    assert sistema.deve_lembrar_fechamento() is False


def test_o_aviso_volta_quando_o_mes_seguinte_chega(sistema, contas, monkeypatch):
    """Fechado até setembro, outubro só é cobrado quando novembro começa."""
    import datetime as _dt

    real = _dt.date

    def viajar(ano, mes, dia):
        class Hoje(real):
            @classmethod
            def today(cls):
                return real(ano, mes, dia)
        monkeypatch.setattr(sistema, "date", Hoje)

    viajar(2026, 10, 24)
    sistema.salvar_lancamento(
        None, "2026-09-10", "Mercado",
        [sistema.Partida(contas["despesa"], "D", 10.0),
         sistema.Partida(contas["banco"], "C", 10.0)])
    sistema.fechar_competencia("2026-09")
    assert sistema.deve_lembrar_fechamento() is False, "outubro ainda está em curso"

    viajar(2026, 11, 2)

    assert sistema.meses_a_fechar() == ["2026-10"]
    assert sistema.deve_lembrar_fechamento() is True


# --------------------------------------------------------------------------- #
# Pop-up das notas depois de atualizar
# --------------------------------------------------------------------------- #
def test_primeira_abertura_da_vida_nao_anuncia_nada(sistema):
    """Não houve atualização nenhuma: seria começar pelo fim."""
    assert atualizacao.versao_mudou() is False


def test_depois_de_trocar_de_versao_anuncia(sistema):
    from app import db

    db.set_config("versao_anterior", "0.9.0")

    assert atualizacao.versao_mudou() is True
    assert atualizacao.versao_anterior() == "0.9.0"


def test_marcar_vista_cala_ate_a_proxima(sistema):
    from app import db

    db.set_config("versao_anterior", "0.9.0")
    atualizacao.marcar_versao_vista()

    assert atualizacao.versao_mudou() is False


def test_as_notas_da_versao_atual_vem_do_que_ja_estava_guardado(sistema, monkeypatch):
    from app import db

    db.set_config("ultima_versao_vista", atualizacao.APP_VERSION)
    db.set_config("ultima_nota_versao", "## Novidades\n\n- uma coisa")

    def nao_deve_ir_a_rede(*_a, **_k):
        raise AssertionError("a resposta já estava guardada")

    monkeypatch.setattr(atualizacao, "consultar_tag", nao_deve_ir_a_rede)

    assert "uma coisa" in atualizacao.notas_desta_versao()


def test_sem_rede_as_notas_nao_quebram_nada(sistema, monkeypatch):
    monkeypatch.setattr(atualizacao, "consultar_tag", lambda _t: None)

    assert atualizacao.notas_desta_versao() == ""


def test_o_popup_de_notas_mostra_o_texto(avisos, sistema, raiz_tk):
    janela = avisos.DialogoNotasAtualizacao(
        raiz_tk, "## Novidades\n\n- **primeira** coisa\n", anterior="1.0.0")
    janela.grab_release()
    try:
        texto = janela.txt.get("1.0", "end")
        assert "primeira coisa" in texto
        assert "**" not in texto
    finally:
        janela.destroy()


# --------------------------------------------------------------------------- #
# A tela de instalação
# --------------------------------------------------------------------------- #
@pytest.fixture()
def instalador(sistema, limpar, monkeypatch, tmp_path):
    modulo = importlib.reload(importlib.import_module("app.ui.instalador"))
    # Só a pasta padrão é trocada: a escolhida tem de vir do caminho de verdade,
    # senão o teste não exercita o que ele diz exercitar.
    monkeypatch.setattr(modulo.instalacao, "pasta_padrao", lambda: tmp_path / "Programs")
    falso = tmp_path / "SistemaContabil.exe"
    falso.write_bytes(b"x" * 2048)
    monkeypatch.setattr(modulo.instalacao, "executavel_atual", lambda: falso)
    return modulo, falso


def test_a_tela_mostra_a_pasta_e_o_que_vai_acontecer(instalador, raiz_tk, tmp_path):
    modulo, _falso = instalador
    janela = modulo.DialogoInstalar(raiz_tk)
    janela.grab_release()
    try:
        assert str(tmp_path / "Programs") in janela.var_pasta.get()
        assert "SistemaContabil.exe" in janela.lbl_pasta.cget("text")
        explicacao = janela._explicacao()
        assert "Aplicativos" in explicacao
        assert "NÃO mudam de lugar" in explicacao
        assert "administrador" in explicacao
    finally:
        janela.destroy()


def test_a_tela_avisa_sobre_arquivos_de_programas(instalador, raiz_tk):
    modulo, _falso = instalador
    janela = modulo.DialogoInstalar(raiz_tk)
    janela.grab_release()
    try:
        janela.var_pasta.set(r"C:\Program Files\SistemaContabil")
        assert "administrador" in janela.lbl_pasta.cget("text")
    finally:
        janela.destroy()


def test_a_tela_diz_quando_a_pasta_ainda_nao_existe(instalador, raiz_tk, tmp_path):
    modulo, _falso = instalador
    janela = modulo.DialogoInstalar(raiz_tk)
    janela.grab_release()
    try:
        janela.var_pasta.set(str(tmp_path / "lugar novo"))
        assert "não existe e será criada" in janela.lbl_pasta.cget("text")
    finally:
        janela.destroy()


def test_instalar_pela_tela_respeita_as_escolhas(instalador, raiz_tk, tmp_path,
                                                 monkeypatch):
    modulo, falso = instalador
    criados = []
    monkeypatch.setattr(modulo.instalacao, "criar_atalho",
                        lambda destino, *a, **k: criados.append(destino) or True)
    monkeypatch.setattr(modulo.instalacao, "_registrar_na_lista_de_programas",
                        lambda _a: None)
    monkeypatch.setattr(modulo.instalacao, "portatil", lambda: False)
    monkeypatch.setattr(modulo.instalacao, "disponivel", lambda: True)
    monkeypatch.setattr(modulo.inicializacao, "disponivel", lambda: False)

    resultados = []
    janela = modulo.DialogoInstalar(raiz_tk, ao_instalar=lambda c, a: resultados.append((c, a)))
    janela.grab_release()
    destino = tmp_path / "escolhida"
    janela.var_pasta.set(str(destino))
    janela.var_area.set(False)          # só o menu Iniciar
    janela.instalar()

    assert resultados
    caminho, recado = resultados[0]
    assert caminho == destino / "SistemaContabil.exe"
    assert caminho.read_bytes() == b"x" * 2048
    assert len(criados) == 1
    assert "menu Iniciar" in recado


def test_a_pasta_escolhida_fica_lembrada(sistema, tmp_path):
    """Escolhida uma vez, é lá que o programa se procura depois."""
    from app import instalacao

    instalacao.lembrar_pasta(tmp_path / "minha pasta")

    assert instalacao.pasta_de_instalacao() == tmp_path / "minha pasta"
    assert instalacao.caminho_instalado().parent == tmp_path / "minha pasta"
