"""Saber se saiu uma versão nova, sem atrapalhar quem está usando.

A consulta vai à API pública de releases do GitHub — não precisa de token nem
de cadastro. Tudo aqui falha em silêncio: um programa pessoal que não abre
porque a internet caiu seria um péssimo negócio.

Este módulo só avisa. Trocar o executável é outra conversa, e deliberadamente
não acontece sozinho: saber que a versão mudou vale mais do que descobrir
depois que alguma coisa já está diferente na tela.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from app.config import APP_VERSION

def _banco():
    """O módulo do banco, resolvido na hora de usar.

    Importar no topo prenderia este módulo à conexão que existia quando ele foi
    carregado. Os testes trocam o banco por um temporário a cada caso — e, com
    a ligação presa, acabariam escrevendo no arquivo de verdade.
    """
    from app import db

    return db


REPOSITORIO = "Allysonubius/sistema-gerenciamento-contabil-pessoal"
URL_ULTIMA = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
URL_RELEASES = f"https://github.com/{REPOSITORIO}/releases"

# Uma consulta por dia basta. O limite da API sem autenticação é de 60 por
# hora por IP, então sobra folga até para quem abre o programa o dia inteiro.
HORAS_ENTRE_CONSULTAS = 24
TEMPO_LIMITE_S = 8


def _numeros(versao: str) -> tuple[int, ...]:
    """'v1.2.0' e '1.2' viram tuplas comparáveis."""
    limpa = (versao or "").strip().lstrip("vV").split("-")[0].split("+")[0]
    partes: list[int] = []
    for pedaco in limpa.split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes) or (0,)


def comparar_versoes(uma: str, outra: str) -> int:
    """-1 se ``uma`` é mais velha, 0 se iguais, 1 se mais nova."""
    a, b = _numeros(uma), _numeros(outra)
    tamanho = max(len(a), len(b))
    a += (0,) * (tamanho - len(a))
    b += (0,) * (tamanho - len(b))
    return (a > b) - (a < b)


def mais_nova(versao: str) -> bool:
    return comparar_versoes(versao, APP_VERSION) > 0


def verificacao_ligada() -> bool:
    return _banco().get_config("verificar_atualizacoes", "1") == "1"


def definir_verificacao(ligada: bool) -> None:
    _banco().set_config("verificar_atualizacoes", "1" if ligada else "0")


def ultima_consulta() -> datetime | None:
    texto = _banco().get_config("ultima_consulta_versao", "")
    try:
        return datetime.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def esta_na_hora() -> bool:
    """Já passou tempo suficiente desde a última consulta?"""
    if not verificacao_ligada():
        return False
    anterior = ultima_consulta()
    if anterior is None:
        return True
    return datetime.now() - anterior >= timedelta(hours=HORAS_ENTRE_CONSULTAS)


# A última falha da consulta, em linguagem de gente. Fica aqui porque "não
# consegui falar com o GitHub, confira a sua internet" é inútil quando o
# problema é outro — e descobrir qual era dava trabalho demais.
_ultimo_motivo = ""


def ultimo_motivo() -> str:
    return _ultimo_motivo


def _anotar(motivo: str) -> None:
    global _ultimo_motivo
    _ultimo_motivo = motivo
    logging.warning("Consulta de versão falhou: %s", motivo)


def _explicar_http(erro: urllib.error.HTTPError) -> str:
    """Traduz o código HTTP para o que a pessoa pode fazer a respeito."""
    try:
        corpo = json.loads(erro.read() or b"{}")
        recado = str(corpo.get("message", "")).strip()
    except (ValueError, OSError):
        recado = ""
    if erro.code == 403 and "rate limit" in recado.lower():
        return ("O GitHub recusou por excesso de consultas deste computador"
                " (limite de 60 por hora). Tente daqui a pouco.")
    if erro.code == 404:
        return "O repositório ou a release não foi encontrado no GitHub."
    detalhe = f" — {recado}" if recado else ""
    return f"O GitHub respondeu com erro {erro.code}{detalhe}."


def consultar(tempo_limite: float = TEMPO_LIMITE_S) -> dict | None:
    """Pergunta ao GitHub qual é a última versão. ``None`` se não deu.

    Quando não dá, o porquê fica em :func:`ultimo_motivo` e no registro — sem
    isso, a tela só sabia dizer "confira a sua internet", que é um palpite.
    """
    global _ultimo_motivo
    requisicao = urllib.request.Request(URL_ULTIMA)
    requisicao.add_header("Accept", "application/vnd.github+json")
    requisicao.add_header("X-GitHub-Api-Version", "2022-11-28")
    requisicao.add_header("User-Agent", f"SistemaContabil/{APP_VERSION}")
    try:
        with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resposta:
            bruto = resposta.read()
        dados = json.loads(bruto)
    except urllib.error.HTTPError as erro:
        _anotar(_explicar_http(erro))
        return None
    except TimeoutError:
        _anotar(f"O GitHub não respondeu em {tempo_limite:.0f} segundos.")
        return None
    except urllib.error.URLError as erro:
        motivo = getattr(erro, "reason", erro)
        if isinstance(motivo, TimeoutError) or "timed out" in str(motivo).lower():
            _anotar(f"O GitHub não respondeu em {tempo_limite:.0f} segundos.")
        elif "certificate" in str(motivo).lower():
            _anotar(f"A conexão segura foi recusada: {motivo}")
        else:
            _anotar(f"Não cheguei até o GitHub: {motivo}")
        return None
    except ValueError:
        _anotar("O GitHub respondeu algo que não entendi"
                " — pode ser uma rede que exige login (Wi-Fi de hotel, por exemplo).")
        return None
    except OSError as erro:
        _anotar(f"Falha de rede: {erro}")
        return None

    if not isinstance(dados, dict):
        _anotar(f"O GitHub respondeu um {type(dados).__name__}, não os dados de uma"
                " versão.")
        return None
    versao = str(dados.get("tag_name") or "").lstrip("vV")
    if not versao:
        recado = str(dados.get("message", "")).strip()
        _anotar(f"O GitHub respondeu sem versão publicada{f' — {recado}' if recado else ''}"
                f" (campos: {', '.join(sorted(dados))[:120]}).")
        return None
    _ultimo_motivo = ""
    arquivo = next((a for a in dados.get("assets", [])
                    if str(a.get("name", "")).lower().endswith(".exe")), None)
    return {
        "versao": versao,
        "nome": dados.get("name") or f"Versão {versao}",
        "notas": dados.get("body") or "",
        "pagina": dados.get("html_url") or URL_RELEASES,
        "arquivo": (arquivo or {}).get("browser_download_url", ""),
        "tamanho": int((arquivo or {}).get("size", 0)),
        "publicada_em": dados.get("published_at", ""),
    }


def verificar(forcar: bool = False) -> dict:
    """O estado da versão, consultando a rede só quando faz sentido.

    ``forcar`` é o botão "procurar agora": ignora o intervalo e o desligamento,
    porque ali foi o usuário quem pediu.
    """
    if not forcar and not esta_na_hora():
        return estado_guardado()

    dados = consultar()
    if dados is None:
        guardado = estado_guardado()
        guardado["falhou"] = True
        guardado["motivo"] = ultimo_motivo()
        return guardado

    banco = _banco()
    banco.set_config("ultima_consulta_versao", datetime.now().isoformat(timespec="seconds"))
    banco.set_config("ultima_versao_vista", dados["versao"])
    banco.set_config("ultima_pagina_versao", dados["pagina"])
    # O que mudou fica guardado junto: assim a tela conta a novidade sem voltar
    # à rede — e sem mandar ninguém para o navegador.
    banco.set_config("ultima_nota_versao", dados["notas"])
    banco.set_config("ultimo_arquivo_versao", dados["arquivo"])
    banco.set_config("ultimo_tamanho_versao", str(dados["tamanho"]))
    banco.set_config("ultima_data_versao", dados["publicada_em"])
    return _montar(dados["versao"], dados["pagina"], dados)


def estado_guardado() -> dict:
    """O que já se sabia, sem tocar na rede."""
    versao = _banco().get_config("ultima_versao_vista", "")
    pagina = _banco().get_config("ultima_pagina_versao", URL_RELEASES)
    return _montar(versao, pagina, None)


def _montar(versao: str, pagina: str, dados: dict | None) -> dict:
    banco = _banco()
    tem = bool(versao) and mais_nova(versao)
    try:
        tamanho = int(banco.get_config("ultimo_tamanho_versao", "0") or 0)
    except ValueError:
        tamanho = 0
    return {
        "atual": APP_VERSION,
        "disponivel": versao or APP_VERSION,
        "ha_novidade": tem,
        "ignorada": tem and versao == banco.get_config("versao_ignorada", ""),
        "pagina": pagina or URL_RELEASES,
        "consultada_em": banco.get_config("ultima_consulta_versao", ""),
        "notas": banco.get_config("ultima_nota_versao", ""),
        "arquivo": banco.get_config("ultimo_arquivo_versao", ""),
        "tamanho": tamanho,
        "publicada_em": banco.get_config("ultima_data_versao", ""),
        "falhou": False,
        "motivo": "",
        "detalhes": dados,
    }


def notas_desta_versao() -> str:
    """O que mudou na versão que está rodando agora.

    Serve para o aviso que aparece depois de atualizar. Se a última consulta já
    trouxe exatamente esta versão, a resposta está guardada; se não, pergunta
    pela tag correspondente.
    """
    banco = _banco()
    if banco.get_config("ultima_versao_vista", "") == APP_VERSION:
        guardadas = banco.get_config("ultima_nota_versao", "")
        if guardadas:
            return guardadas
    dados = consultar_tag(f"v{APP_VERSION}")
    if dados:
        banco.set_config("notas_versao_atual", dados["notas"])
        return dados["notas"]
    return banco.get_config("notas_versao_atual", "")


def consultar_tag(tag: str) -> dict | None:
    """As informações de uma release específica."""
    url = f"https://api.github.com/repos/{REPOSITORIO}/releases/tags/{tag}"
    requisicao = urllib.request.Request(url)
    requisicao.add_header("Accept", "application/vnd.github+json")
    requisicao.add_header("User-Agent", f"SistemaContabil/{APP_VERSION}")
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE_S) as resposta:
            dados = json.loads(resposta.read())
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as erro:
        logging.info("Não consegui buscar as notas de %s: %s", tag, erro)
        return None
    return {"versao": str(dados.get("tag_name") or "").lstrip("vV"),
            "notas": dados.get("body") or "",
            "publicada_em": dados.get("published_at", "")}


def versao_mudou() -> bool:
    """O programa foi atualizado desde a última vez que abriu?

    Primeira abertura da vida não conta: ali não houve atualização nenhuma, e
    encher a tela de novidade antes de o usuário ter usado o programa seria
    começar pelo fim.
    """
    banco = _banco()
    anterior = banco.get_config("versao_anterior", "")
    return bool(anterior) and anterior != APP_VERSION


def marcar_versao_vista() -> None:
    _banco().set_config("versao_anterior", APP_VERSION)


def versao_anterior() -> str:
    return _banco().get_config("versao_anterior", "")


def ignorar(versao: str) -> None:
    """'Não quero ser avisado desta versão' — a próxima volta a avisar."""
    _banco().set_config("versao_ignorada", (versao or "").strip())


def limpar_ignorada() -> None:
    _banco().set_config("versao_ignorada", "")


def deve_avisar() -> bool:
    """Tem versão nova que o usuário ainda não mandou calar?"""
    estado = estado_guardado()
    return estado["ha_novidade"] and not estado["ignorada"]


# --------------------------------------------------------------------------- #
# Trazer a versão nova para cá
# --------------------------------------------------------------------------- #
# Sem navegador: o programa pergunta, conta o que mudou e, se o usuário mandar,
# busca o arquivo ele mesmo. Mandar a pessoa procurar um .exe numa página e
# achar o botão certo é pedir para ela errar.
def em_texto(notas: str, largura: int = 96) -> str:
    """As notas da release, de Markdown para texto corrido.

    Não é um renderizador: é o bastante para a janela ficar legível sem trazer
    uma biblioteca inteira para dentro do programa.
    """
    linhas = []
    for bruta in (notas or "").replace("\r\n", "\n").split("\n"):
        linha = bruta.rstrip()
        if linha.startswith("```"):
            continue
        texto = linha.lstrip("#").strip() if linha.lstrip().startswith("#") else linha
        texto = texto.replace("**", "").replace("`", "")
        if texto.lstrip().startswith(("- ", "* ")):
            recuo = len(texto) - len(texto.lstrip())
            texto = " " * recuo + "•" + texto.lstrip()[1:]
        if linha.lstrip().startswith("#"):
            linhas.append("")
            linhas.append(texto.upper() if linha.startswith("## ") else texto)
            linhas.append("")
        else:
            linhas.append(texto)
    # Mais de uma linha vazia seguida vira só uma.
    saida: list[str] = []
    for linha in linhas:
        if linha or (saida and saida[-1]):
            saida.append(linha)
    return "\n".join(saida).strip()


def baixar(destino, progresso=None, tempo_limite: float = 60.0):
    """Traz o executável da versão nova. Devolve o caminho baixado.

    ``progresso`` recebe (bytes_vindos, bytes_totais) de tempos em tempos. O
    arquivo é escrito com outro nome e só no fim ganha o definitivo: uma queda
    de conexão deixa lixo, não um executável pela metade.
    """
    from pathlib import Path

    estado = estado_guardado()
    url = estado["arquivo"]
    if not url:
        raise RuntimeError("Esta versão não trouxe um arquivo para baixar.")

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")

    requisicao = urllib.request.Request(url)
    requisicao.add_header("User-Agent", f"SistemaContabil/{APP_VERSION}")
    try:
        with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resposta:
            total = int(resposta.headers.get("Content-Length") or estado["tamanho"] or 0)
            vindos = 0
            with open(parcial, "wb") as arquivo:
                while True:
                    pedaco = resposta.read(262144)
                    if not pedaco:
                        break
                    arquivo.write(pedaco)
                    vindos += len(pedaco)
                    if progresso is not None:
                        progresso(vindos, total)
    except (urllib.error.URLError, OSError, TimeoutError) as erro:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(f"Não consegui baixar a versão nova: {erro}") from erro

    if estado["tamanho"] and vindos != estado["tamanho"]:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            "O arquivo veio incompleto"
            f" ({vindos:,} de {estado['tamanho']:,} bytes). Tente de novo.")

    destino.unlink(missing_ok=True)
    parcial.rename(destino)
    logging.info("Versão %s baixada em %s", estado["disponivel"], destino)
    return destino
