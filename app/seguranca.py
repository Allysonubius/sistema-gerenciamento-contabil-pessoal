"""Senha de abertura, presa a este computador.

O que esta senha é: uma tranca na porta. Quem senta no seu computador não abre
o programa nem vê os seus números sem saber a senha.

O que ela não é: criptografia. O arquivo do banco continua legível por quem
tiver acesso a ele e souber abrir um SQLite. Isso está dito aqui, na tela e no
README de propósito — uma tranca anunciada como cofre é pior do que nenhuma,
porque faz a pessoa guardar coisas que não guardaria.

"Presa ao computador" quer dizer que o identificador da máquina entra na conta
que gera o hash. A mesma senha digitada noutro computador não abre o banco
copiado para lá — e o programa diz exatamente isso, em vez de fingir que a
senha está errada.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import platform
import sys


def _banco():
    """O módulo do banco, resolvido na hora de usar.

    Importar no topo prenderia este módulo à conexão que existia quando ele foi
    carregado. Os testes trocam o banco por um temporário a cada caso — e, com
    a ligação presa, acabariam escrevendo no arquivo de verdade.
    """
    from app import db

    return db


ITERACOES = 240_000
TAMANHO_SAL = 16
TAMANHO_MINIMO = 6

# Chaves na tabela de configuração.
CHAVE_HASH = "senha_hash"
CHAVE_SAL = "senha_sal"
CHAVE_ITERACOES = "senha_iteracoes"
CHAVE_MAQUINA = "senha_maquina"
CHAVE_CRIADA = "senha_criada_em"

PALAVRA_DE_RESET = "APAGAR SENHA"


def _id_da_maquina() -> str:
    """Identificador estável deste computador.

    No Windows é o MachineGuid, que nasce com a instalação do sistema e não
    muda ao trocar o nome da máquina. Fora do Windows, e se a leitura falhar,
    cai para o nome da máquina — pior, mas melhor do que nada.
    """
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as chave:
                valor, _tipo = winreg.QueryValueEx(chave, "MachineGuid")
            if valor:
                return str(valor)
        except OSError:
            logging.info("MachineGuid indisponível; usando o nome do computador")
    return platform.node() or os.environ.get("COMPUTERNAME", "desconhecido")


def impressao_da_maquina() -> str:
    """O identificador já resumido, que é o que fica guardado."""
    return hashlib.sha256(_id_da_maquina().encode("utf-8")).hexdigest()


def _derivar(senha: str, sal: bytes, iteracoes: int) -> bytes:
    """A senha e a máquina, juntas, viram a chave guardada.

    Misturar o identificador aqui é o que faz a senha valer só neste
    computador: levar o banco para outro e digitar a mesma senha não bate.
    """
    material = f"{senha}\x00{_id_da_maquina()}".encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", material, sal, iteracoes)


def tem_senha() -> bool:
    return bool(_banco().get_config(CHAVE_HASH, ""))


def criada_em() -> str:
    return _banco().get_config(CHAVE_CRIADA, "")


def maquina_confere() -> bool:
    """O banco foi protegido neste computador?"""
    guardada = _banco().get_config(CHAVE_MAQUINA, "")
    return not guardada or hmac.compare_digest(guardada, impressao_da_maquina())


def problemas_da_senha(senha: str, confirmacao: str | None = None) -> list[str]:
    """Tudo que está errado com a senha escolhida, em linguagem de gente."""
    problemas: list[str] = []
    senha = senha or ""
    if len(senha) < TAMANHO_MINIMO:
        problemas.append(f"A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres.")
    if senha and senha == senha[0] * len(senha):
        problemas.append("Uma senha de um caractere repetido não protege nada.")
    if senha.strip() != senha:
        problemas.append("A senha não pode começar nem terminar com espaço.")
    if confirmacao is not None and senha != confirmacao:
        problemas.append("As duas senhas digitadas não são iguais.")
    return problemas


def definir_senha(senha: str, confirmacao: str) -> None:
    """Cria ou substitui a senha. Para trocar sabendo a atual, use trocar_senha."""
    problemas = problemas_da_senha(senha, confirmacao)
    if problemas:
        raise ValueError("\n".join(problemas))

    from datetime import datetime

    sal = os.urandom(TAMANHO_SAL)
    _banco().set_config(CHAVE_SAL, sal.hex())
    _banco().set_config(CHAVE_ITERACOES, str(ITERACOES))
    _banco().set_config(CHAVE_HASH, _derivar(senha, sal, ITERACOES).hex())
    _banco().set_config(CHAVE_MAQUINA, impressao_da_maquina())
    _banco().set_config(CHAVE_CRIADA, datetime.now().isoformat(timespec="seconds"))


def conferir_senha(senha: str) -> bool:
    """Compara em tempo constante — sem atalho quando os primeiros bytes batem."""
    guardado = _banco().get_config(CHAVE_HASH, "")
    sal_hex = _banco().get_config(CHAVE_SAL, "")
    if not guardado or not sal_hex:
        return False
    try:
        iteracoes = int(_banco().get_config(CHAVE_ITERACOES, str(ITERACOES)))
        sal = bytes.fromhex(sal_hex)
    except ValueError:
        logging.warning("Dados da senha corrompidos")
        return False
    return hmac.compare_digest(_derivar(senha or "", sal, iteracoes).hex(), guardado)


def trocar_senha(atual: str, nova: str, confirmacao: str) -> None:
    if not conferir_senha(atual):
        raise ValueError("A senha atual não confere.")
    definir_senha(nova, confirmacao)


def remover_senha(atual: str) -> None:
    """Tira a tranca, sabendo a senha."""
    if not conferir_senha(atual):
        raise ValueError("A senha atual não confere.")
    _limpar()


def apagar_senha_esquecida(palavra: str) -> None:
    """Saída para quem esqueceu a senha.

    Existe de propósito, e de propósito está documentada: como a tranca não
    criptografa o banco, esconder o caminho de volta não protegeria os dados e
    só criaria o risco de a pessoa se trancar para fora da própria vida
    financeira. Quem tem o arquivo já tem os números, com ou sem este botão.
    """
    if (palavra or "").strip().upper() != PALAVRA_DE_RESET:
        raise ValueError(f'Digite exatamente "{PALAVRA_DE_RESET}" para confirmar.')
    _limpar()


def _limpar() -> None:
    for chave in (CHAVE_HASH, CHAVE_SAL, CHAVE_ITERACOES, CHAVE_MAQUINA, CHAVE_CRIADA):
        _banco().set_config(chave, "")


def espera_apos_erro(tentativas: int) -> float:
    """Segundos de espera depois de cada erro, para cansar quem chuta.

    Cresce rápido e para em meio minuto: o suficiente para inviabilizar
    tentativa e erro, sem transformar um dedo escorregado em castigo.
    """
    if tentativas <= 0:
        return 0.0
    return min(2.0 ** (tentativas - 1), 30.0)
