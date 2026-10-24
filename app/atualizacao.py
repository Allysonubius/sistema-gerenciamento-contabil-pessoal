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


def consultar(tempo_limite: float = TEMPO_LIMITE_S) -> dict | None:
    """Pergunta ao GitHub qual é a última versão. ``None`` se não deu."""
    requisicao = urllib.request.Request(URL_ULTIMA)
    requisicao.add_header("Accept", "application/vnd.github+json")
    requisicao.add_header("X-GitHub-Api-Version", "2022-11-28")
    requisicao.add_header("User-Agent", f"SistemaContabil/{APP_VERSION}")
    try:
        with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resposta:
            dados = json.loads(resposta.read())
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as erro:
        logging.info("Não foi possível conferir se há versão nova: %s", erro)
        return None

    versao = str(dados.get("tag_name") or "").lstrip("vV")
    if not versao:
        return None
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
        return guardado

    _banco().set_config("ultima_consulta_versao", datetime.now().isoformat(timespec="seconds"))
    _banco().set_config("ultima_versao_vista", dados["versao"])
    _banco().set_config("ultima_pagina_versao", dados["pagina"])
    return _montar(dados["versao"], dados["pagina"], dados)


def estado_guardado() -> dict:
    """O que já se sabia, sem tocar na rede."""
    versao = _banco().get_config("ultima_versao_vista", "")
    pagina = _banco().get_config("ultima_pagina_versao", URL_RELEASES)
    return _montar(versao, pagina, None)


def _montar(versao: str, pagina: str, dados: dict | None) -> dict:
    tem = bool(versao) and mais_nova(versao)
    return {
        "atual": APP_VERSION,
        "disponivel": versao or APP_VERSION,
        "ha_novidade": tem,
        "ignorada": tem and versao == _banco().get_config("versao_ignorada", ""),
        "pagina": pagina or URL_RELEASES,
        "consultada_em": _banco().get_config("ultima_consulta_versao", ""),
        "falhou": False,
        "detalhes": dados,
    }


def ignorar(versao: str) -> None:
    """'Não quero ser avisado desta versão' — a próxima volta a avisar."""
    _banco().set_config("versao_ignorada", (versao or "").strip())


def limpar_ignorada() -> None:
    _banco().set_config("versao_ignorada", "")


def deve_avisar() -> bool:
    """Tem versão nova que o usuário ainda não mandou calar?"""
    estado = estado_guardado()
    return estado["ha_novidade"] and not estado["ignorada"]
