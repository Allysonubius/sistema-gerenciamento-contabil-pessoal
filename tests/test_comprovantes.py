"""Nota, boleto ou recibo guardados junto do registro.

O arquivo é copiado para a pasta de comprovantes; o banco guarda só o cadastro,
para a cópia diária de segurança não crescer com PDFs dentro.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def lancamento(sistema, contas):
    return sistema.salvar_lancamento(
        None, "2026-04-10", "Farmácia",
        [sistema.Partida(contas["despesa"], "D", 60.0),
         sistema.Partida(contas["banco"], "C", 60.0)])


@pytest.fixture()
def recibo(tmp_path):
    """Um arquivo qualquer, com extensão aceita."""
    def criar(nome: str = "recibo.pdf", tamanho: int = 1024):
        caminho = tmp_path / nome
        caminho.write_bytes(b"x" * tamanho)
        return caminho
    return criar


def test_anexa_e_lista(sistema, lancamento, recibo):
    sistema.anexar_comprovante(lancamento, recibo())
    anexos = sistema.listar_anexos(lancamento)

    assert len(anexos) == 1
    assert anexos[0]["nome"] == "recibo.pdf"
    assert anexos[0]["tamanho"] == 1024
    assert anexos[0]["existe"] is True


def test_o_arquivo_e_copiado_e_o_original_fica_onde_estava(sistema, lancamento, recibo):
    origem = recibo()
    anexo_id = sistema.anexar_comprovante(lancamento, origem)
    guardado = sistema.caminho_do_anexo(anexo_id)

    assert origem.exists()                 # o original não foi movido
    assert guardado.exists()
    assert guardado != origem
    assert guardado.read_bytes() == origem.read_bytes()


def test_o_arquivo_fica_na_pasta_de_dados_separado_por_ano(sistema, lancamento, recibo):
    anexo_id = sistema.anexar_comprovante(lancamento, recibo())
    caminho = sistema.caminho_do_anexo(anexo_id)

    assert caminho.parent.name == "2026"
    assert caminho.parent.parent.name == "comprovantes"


def test_vario_comprovantes_no_mesmo_registro(sistema, lancamento, recibo):
    sistema.anexar_comprovante(lancamento, recibo("nota.pdf"))
    sistema.anexar_comprovante(lancamento, recibo("foto.jpg"))

    assert len(sistema.listar_anexos(lancamento)) == 2


def test_dois_arquivos_de_mesmo_nome_nao_se_sobrescrevem(sistema, lancamento, recibo):
    primeiro = sistema.anexar_comprovante(lancamento, recibo("recibo.pdf", 100))
    segundo = sistema.anexar_comprovante(lancamento, recibo("recibo.pdf", 200))

    assert sistema.caminho_do_anexo(primeiro) != sistema.caminho_do_anexo(segundo)
    assert sistema.caminho_do_anexo(primeiro).stat().st_size == 100
    assert sistema.caminho_do_anexo(segundo).stat().st_size == 200


def test_tipo_de_arquivo_nao_aceito(sistema, lancamento, recibo):
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.anexar_comprovante(lancamento, recibo("virus.exe"))
    assert "não aceito" in str(erro.value)


def test_arquivo_grande_demais(sistema, lancamento, recibo):
    grande = recibo("enorme.pdf", (sistema.LIMITE_ANEXO_MB + 1) * 1024 * 1024)
    with pytest.raises(sistema.RegraNegocioError) as erro:
        sistema.anexar_comprovante(lancamento, grande)
    assert "limite" in str(erro.value)


def test_arquivo_inexistente(sistema, lancamento, tmp_path):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.anexar_comprovante(lancamento, tmp_path / "nao_existe.pdf")


def test_registro_inexistente(sistema, recibo):
    with pytest.raises(sistema.RegraNegocioError):
        sistema.anexar_comprovante(99999, recibo())


def test_nome_de_arquivo_perigoso_e_higienizado(sistema, lancamento, recibo):
    anexo_id = sistema.anexar_comprovante(
        lancamento, recibo("recibo.pdf"), nome="../../fora.pdf")
    caminho = sistema.caminho_do_anexo(anexo_id)

    assert ".." not in caminho.name
    assert caminho.parent.name == "2026"


def test_remover_apaga_o_arquivo_e_o_cadastro(sistema, lancamento, recibo):
    anexo_id = sistema.anexar_comprovante(lancamento, recibo())
    caminho = sistema.caminho_do_anexo(anexo_id)
    sistema.remover_anexo(anexo_id)

    assert not caminho.exists()
    assert sistema.listar_anexos(lancamento) == []


def test_arquivo_sumido_por_fora_e_avisado(sistema, lancamento, recibo):
    anexo_id = sistema.anexar_comprovante(lancamento, recibo())
    sistema.caminho_do_anexo(anexo_id).unlink()

    assert sistema.listar_anexos(lancamento)[0]["existe"] is False
    with pytest.raises(sistema.RegraNegocioError):
        sistema.caminho_do_anexo(anexo_id)


def test_apagar_o_registro_leva_o_cadastro_do_anexo(sistema, lancamento, recibo):
    sistema.anexar_comprovante(lancamento, recibo())
    sistema.excluir_lancamento(lancamento)

    assert sistema.listar_anexos(lancamento) == []


def test_a_lista_de_movimentos_mostra_quantos_comprovantes(sistema, lancamento, recibo):
    sistema.anexar_comprovante(lancamento, recibo("a.pdf"))
    sistema.anexar_comprovante(lancamento, recibo("b.pdf"))
    movimento = next(m for m in sistema.listar_movimentos("2026-04-01", "2026-04-30")
                     if m["id"] == lancamento)

    assert movimento["anexos"] == 2


def test_resumo_dos_comprovantes(sistema, lancamento, recibo):
    sistema.anexar_comprovante(lancamento, recibo("a.pdf", 2048))
    resumo = sistema.resumo_anexos()

    assert resumo["total"] == 1
    assert resumo["registros"] == 1
    assert resumo["bytes"] == 2048
