"""Importação de extratos bancários e faturas de cartão (OFX e CSV).

O objetivo é acabar com a digitação manual: o arquivo é lido, cada item recebe
uma sugestão de categoria com base no histórico e o usuário só confirma. Itens
já importados antes são reconhecidos e não entram de novo.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app import db, services


@dataclass
class ItemExtrato:
    data: str                       # AAAA-MM-DD
    descricao: str
    valor: float                    # positivo = entrou, negativo = saiu
    id_extrato: str                 # identificador estável do item
    categoria_id: int | None = None
    categoria_nome: str = ""
    ja_importado: bool = False
    importar: bool = True
    origem_sugestao: str = ""       # como a categoria foi sugerida
    tags: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Leitura dos arquivos
# --------------------------------------------------------------------------- #
def ler_arquivo(caminho: str | Path) -> list[ItemExtrato]:
    caminho = Path(caminho)
    if not caminho.exists():
        raise services.RegraNegocioError("Arquivo não encontrado.")
    if caminho.suffix.lower() in (".ofx", ".qfx"):
        itens = _ler_ofx(caminho)
    elif caminho.suffix.lower() in (".csv", ".txt"):
        itens = _ler_csv(caminho)
    else:
        raise services.RegraNegocioError(
            "Formato não reconhecido. Use um arquivo .ofx (extrato do banco) ou .csv.")
    if not itens:
        raise services.RegraNegocioError("Nenhum lançamento foi encontrado no arquivo.")
    return itens


def _texto_do_arquivo(caminho: Path) -> str:
    for codificacao in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return caminho.read_text(encoding=codificacao)
        except UnicodeDecodeError:
            continue
    return caminho.read_bytes().decode("utf-8", errors="ignore")


def _ler_ofx(caminho: Path) -> list[ItemExtrato]:
    """Lê OFX/QFX sem dependências: os arquivos dos bancos são SGML simples."""
    conteudo = _texto_do_arquivo(caminho)
    itens: list[ItemExtrato] = []

    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", conteudo, re.S | re.I):
        def campo(nome: str) -> str:
            achado = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
            return achado.group(1).strip() if achado else ""

        data_bruta = campo("DTPOSTED")[:8]
        if len(data_bruta) != 8 or not data_bruta.isdigit():
            continue
        try:
            data = datetime.strptime(data_bruta, "%Y%m%d").date().isoformat()
        except ValueError:
            continue

        try:
            valor = float(campo("TRNAMT").replace(",", "."))
        except ValueError:
            continue
        if abs(valor) < 0.005:
            continue

        descricao = (campo("MEMO") or campo("NAME") or "Lançamento importado").strip()
        fitid = campo("FITID") or f"{data}|{valor:.2f}|{descricao[:40]}"
        itens.append(ItemExtrato(data=data, descricao=descricao, valor=round(valor, 2),
                                 id_extrato=f"OFX:{fitid}"))
    return itens


def _ler_csv(caminho: Path) -> list[ItemExtrato]:
    """Lê CSV com colunas de data, descrição e valor, em qualquer ordem."""
    texto = _texto_do_arquivo(caminho)
    amostra = texto[:4096]
    delimitador = ";" if amostra.count(";") >= amostra.count(",") else ","

    linhas = list(csv.reader(texto.splitlines(), delimiter=delimitador))
    linhas = [linha for linha in linhas if any(c.strip() for c in linha)]
    if not linhas:
        return []

    cabecalho = [_normalizar(c) for c in linhas[0]]
    col_data = _achar(cabecalho, ("data", "date", "datalancamento", "dtposted"))
    col_desc = _achar(cabecalho, ("descricao", "historico", "memo", "lancamento",
                                  "titulo", "estabelecimento", "description"))
    col_valor = _achar(cabecalho, ("valor", "value", "amount", "montante", "quantia"))
    tem_cabecalho = col_data is not None and col_valor is not None
    if not tem_cabecalho:
        col_data, col_desc, col_valor = 0, 1, 2

    itens: list[ItemExtrato] = []
    for numero, linha in enumerate(linhas[1:] if tem_cabecalho else linhas, start=1):
        if max(col_data, col_valor, col_desc or 0) >= len(linha):
            continue
        data = _converter_data(linha[col_data])
        valor = _converter_valor(linha[col_valor])
        if data is None or valor is None or abs(valor) < 0.005:
            continue
        descricao = (linha[col_desc].strip() if col_desc is not None
                     and col_desc < len(linha) else "Lançamento importado")
        itens.append(ItemExtrato(
            data=data, descricao=descricao or "Lançamento importado", valor=valor,
            id_extrato=f"CSV:{caminho.name}:{numero}:{data}:{valor:.2f}"))
    return itens


def _achar(cabecalho: list[str], nomes: tuple[str, ...]) -> int | None:
    for indice, coluna in enumerate(cabecalho):
        if any(nome in coluna for nome in nomes):
            return indice
    return None


def _converter_data(texto: str) -> str | None:
    texto = texto.strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


def _converter_valor(texto: str) -> float | None:
    bruto = texto.strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not bruto:
        return None
    negativo = bruto.startswith("(") and bruto.endswith(")")
    bruto = bruto.strip("()")
    if "," in bruto and "." in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    elif "," in bruto:
        bruto = bruto.replace(",", ".")
    try:
        valor = round(float(bruto), 2)
    except ValueError:
        return None
    return -valor if negativo else valor


# --------------------------------------------------------------------------- #
# Sugestão de categoria
# --------------------------------------------------------------------------- #
def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower()).strip()


def _palavras_chave(descricao: str) -> list[str]:
    ignoradas = {"compra", "cartao", "debito", "credito", "pagamento", "pix", "ted", "doc",
                 "transferencia", "recebido", "enviado", "com", "para", "ltda", "me", "sa",
                 "brasil", "br", "de", "da", "do", "em", "no", "na"}
    palavras = [p for p in _normalizar(descricao).split()
                if len(p) > 2 and not p.isdigit() and p not in ignoradas]
    return palavras[:4]


def _mesma_palavra(a: str, b: str) -> bool:
    """Iguais ou apenas variação de flexão (assinatura ≈ assinaturas).

    Exige prefixo longo para não confundir palavras curtas parecidas.
    """
    if a == b:
        return True
    menor, maior = sorted((a, b), key=len)
    return len(menor) >= 5 and maior.startswith(menor)


def sugerir_categoria(item: ItemExtrato) -> tuple[int | None, str, str]:
    """Procura a categoria: primeiro nas regras aprendidas, depois no histórico."""
    texto = _normalizar(item.descricao)

    for regra in db.query("SELECT * FROM regra_categoria ORDER BY usos DESC, LENGTH(padrao) DESC"):
        if regra["padrao"] and regra["padrao"] in texto:
            conta = services.obter_conta(regra["conta_id"])
            if conta and conta["ativo"]:
                return conta["id"], conta["nome"], "aprendida"

    # Histórico: lançamentos anteriores com descrição parecida. A comparação
    # ignora acentos, senão "SALARIO" do extrato não acha "Salário" já lançado.
    tipo_alvo = "RECEITA" if item.valor > 0 else "DESPESA"
    palavras = _palavras_chave(item.descricao)
    for palavra in palavras:
        # O LIKE exige início de palavra: sem isso, "posto" casaria com "imposto".
        achado = db.query_one(
            "SELECT c.id, c.nome, COUNT(*) AS usos FROM lancamento l"
            " JOIN partida p ON p.lancamento_id = l.id JOIN conta c ON c.id = p.conta_id"
            " WHERE c.tipo = ? AND c.aceita_lancamento = 1 AND c.ativo = 1"
            " AND (sem_acento(l.historico) LIKE ? OR sem_acento(l.historico) LIKE ?)"
            " GROUP BY c.id ORDER BY usos DESC LIMIT 1",
            (tipo_alvo, f"% {palavra}%", f"{palavra}%"))
        if achado:
            return achado["id"], achado["nome"], "histórico"

    # Sem histórico ainda: casa a palavra com o nome de alguma categoria,
    # comparando palavra inteira para não confundir "posto" com "imposto".
    categorias = db.query(
        "SELECT id, nome FROM conta WHERE tipo = ? AND aceita_lancamento = 1 AND ativo = 1"
        " ORDER BY LENGTH(nome)", (tipo_alvo,))
    for palavra in palavras:
        for categoria in categorias:
            if any(_mesma_palavra(palavra, token)
                   for token in _normalizar(categoria["nome"]).split()):
                return categoria["id"], categoria["nome"], "pelo nome"

    padrao = db.query_one(
        "SELECT id, nome FROM conta WHERE codigo = ?",
        ("4.3.01" if item.valor > 0 else "5.9.01",))
    if padrao:
        return padrao["id"], padrao["nome"], "padrão"
    return None, "", ""


def aprender_categoria(descricao: str, conta_id: int) -> None:
    """Guarda a escolha do usuário para acertar sozinho na próxima importação."""
    palavras = _palavras_chave(descricao)
    if not palavras:
        return
    padrao = palavras[0]
    existente = db.query_one("SELECT * FROM regra_categoria WHERE padrao = ?", (padrao,))
    if existente:
        db.execute("UPDATE regra_categoria SET conta_id = ?, usos = usos + 1 WHERE id = ?",
                   (conta_id, existente["id"]))
    else:
        db.execute("INSERT INTO regra_categoria (padrao, conta_id) VALUES (?,?)",
                   (padrao, conta_id))


# --------------------------------------------------------------------------- #
# Preparação e gravação
# --------------------------------------------------------------------------- #
def preparar(caminho: str | Path) -> list[ItemExtrato]:
    """Lê o arquivo, marca o que já foi importado e sugere as categorias."""
    itens = ler_arquivo(caminho)
    for item in itens:
        ja = db.query_one("SELECT 1 FROM lancamento WHERE id_extrato = ?", (item.id_extrato,))
        item.ja_importado = ja is not None
        item.importar = not item.ja_importado
        conta_id, nome, origem = sugerir_categoria(item)
        item.categoria_id = conta_id
        item.categoria_nome = nome
        item.origem_sugestao = origem
    return itens


def importar(itens: list[ItemExtrato], conta_carteira_id: int,
             centro_custo_id: int | None = None, aprender: bool = True) -> dict:
    """Grava os itens marcados como lançamentos, um por linha do extrato."""
    conta = services.obter_conta(conta_carteira_id)
    if conta is None:
        raise services.RegraNegocioError("Escolha a conta ou o cartão do extrato.")

    criados = ignorados = 0
    for item in itens:
        if not item.importar or item.ja_importado:
            ignorados += 1
            continue
        if item.categoria_id is None:
            ignorados += 1
            continue

        valor = round(abs(item.valor), 2)
        if item.valor > 0:
            partidas = [services.Partida(conta_carteira_id, "D", valor),
                        services.Partida(item.categoria_id, "C", valor)]
        else:
            partidas = [services.Partida(item.categoria_id, "D", valor),
                        services.Partida(conta_carteira_id, "C", valor)]

        lancamento_id = services.salvar_lancamento(
            None, item.data, item.descricao[:120], partidas,
            documento="IMPORTADO", centro_custo_id=centro_custo_id, origem="MANUAL")
        db.execute("UPDATE lancamento SET id_extrato = ?, conferido = 1 WHERE id = ?",
                   (item.id_extrato, lancamento_id))
        if aprender:
            aprender_categoria(item.descricao, item.categoria_id)
        criados += 1

    return {"criados": criados, "ignorados": ignorados}
