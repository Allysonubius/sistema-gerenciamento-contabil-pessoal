"""Camada de acesso ao SQLite: conexão, esquema, migrações e carga inicial."""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import threading
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.config import BACKUP_DIR, DB_PATH, ensure_dirs

SCHEMA_VERSION = 12

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conta (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo            TEXT    NOT NULL UNIQUE,
    nome              TEXT    NOT NULL,
    tipo              TEXT    NOT NULL CHECK (tipo IN ('ATIVO','PASSIVO','PATRIMONIO','RECEITA','DESPESA')),
    natureza          TEXT    NOT NULL CHECK (natureza IN ('D','C')),
    pai_id            INTEGER REFERENCES conta(id) ON DELETE RESTRICT,
    aceita_lancamento INTEGER NOT NULL DEFAULT 1 CHECK (aceita_lancamento IN (0,1)),
    ativo             INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    observacao        TEXT    NOT NULL DEFAULT '',
    -- Carteira = lugar onde o dinheiro fica de fato (banco, espécie, pré-pago, cartão).
    -- É o que a tela "Minhas Contas" acompanha e o que soma no dinheiro disponível.
    eh_carteira       INTEGER NOT NULL DEFAULT 0 CHECK (eh_carteira IN (0,1)),
    instituicao       TEXT    NOT NULL DEFAULT '',
    -- Cartões de crédito: ciclo da fatura e juros do rotativo (% ao mês).
    dia_fechamento    INTEGER,
    dia_vencimento    INTEGER,
    juros_rotativo    REAL    NOT NULL DEFAULT 0,
    limite            REAL    NOT NULL DEFAULT 0,
    -- Só as contas marcadas aqui somam em "Dinheiro que você tem hoje". Serve
    -- para deixar de fora saldos que não são dinheiro livre (crédito de loja,
    -- vale, cripto), que continuam aparecendo na lista de contas.
    entra_no_disponivel INTEGER NOT NULL DEFAULT 1 CHECK (entra_no_disponivel IN (0,1)),
    -- Cartão com limite garantido: a aplicação dada em garantia define o limite.
    conta_garantia_id INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    validade          TEXT NOT NULL DEFAULT '',  -- validade impressa no cartão (MM/AAAA)
    -- Cartão: conta de onde sai o dinheiro para pagar a fatura todo mês.
    conta_pagamento_id INTEGER REFERENCES conta(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS centro_custo (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT    NOT NULL UNIQUE,
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1))
);

CREATE TABLE IF NOT EXISTS lancamento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    data            TEXT    NOT NULL,
    historico       TEXT    NOT NULL,
    documento       TEXT    NOT NULL DEFAULT '',
    centro_custo_id INTEGER REFERENCES centro_custo(id) ON DELETE SET NULL,
    valor           REAL    NOT NULL CHECK (valor > 0),
    criado_em       TEXT    NOT NULL,
    origem          TEXT    NOT NULL DEFAULT 'MANUAL',
    compra_id       INTEGER REFERENCES compra_parcelada(id) ON DELETE CASCADE,
    conferido       INTEGER NOT NULL DEFAULT 0 CHECK (conferido IN (0,1)),
    id_extrato      TEXT     -- identificador do item importado, evita duplicar
);

CREATE TABLE IF NOT EXISTS compra_parcelada (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao      TEXT    NOT NULL,
    cartao_id      INTEGER NOT NULL REFERENCES conta(id) ON DELETE CASCADE,
    categoria_id   INTEGER NOT NULL REFERENCES conta(id) ON DELETE RESTRICT,
    valor_total    REAL    NOT NULL CHECK (valor_total > 0),
    parcelas       INTEGER NOT NULL CHECK (parcelas > 0),
    valor_parcela  REAL    NOT NULL,
    primeira       TEXT    NOT NULL,
    data_compra    TEXT    NOT NULL,
    centro_custo_id INTEGER REFERENCES centro_custo(id) ON DELETE SET NULL,
    criada_em      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS partida (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lancamento_id INTEGER NOT NULL REFERENCES lancamento(id) ON DELETE CASCADE,
    conta_id      INTEGER NOT NULL REFERENCES conta(id) ON DELETE RESTRICT,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('D','C')),
    valor         REAL    NOT NULL CHECK (valor > 0)
);

CREATE TABLE IF NOT EXISTS recorrencia (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT    NOT NULL CHECK (tipo IN ('PAGAR','RECEBER')),
    descricao       TEXT    NOT NULL,
    pessoa          TEXT    NOT NULL DEFAULT '',
    valor           REAL    NOT NULL CHECK (valor > 0),
    dia_vencimento  INTEGER NOT NULL CHECK (dia_vencimento BETWEEN 1 AND 31),
    conta_id        INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    centro_custo_id INTEGER REFERENCES centro_custo(id) ON DELETE SET NULL,
    inicio          TEXT    NOT NULL,
    fim             TEXT,
    ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    observacao      TEXT    NOT NULL DEFAULT '',
    criado_em       TEXT    NOT NULL,
    multa_pct       REAL    NOT NULL DEFAULT 0,
    juros_mes_pct   REAL    NOT NULL DEFAULT 0,
    conta_pagamento_id INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    pagamento_automatico INTEGER NOT NULL DEFAULT 0 CHECK (pagamento_automatico IN (0,1))
);

CREATE TABLE IF NOT EXISTS fatura (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id       INTEGER NOT NULL REFERENCES conta(id) ON DELETE CASCADE,
    competencia    TEXT    NOT NULL,
    fechamento     TEXT    NOT NULL,
    vencimento     TEXT    NOT NULL,
    saldo_anterior REAL    NOT NULL DEFAULT 0,
    compras        REAL    NOT NULL DEFAULT 0,
    pagamentos     REAL    NOT NULL DEFAULT 0,
    encargos       REAL    NOT NULL DEFAULT 0,
    total          REAL    NOT NULL DEFAULT 0,
    titulo_id      INTEGER REFERENCES titulo(id) ON DELETE SET NULL,
    criada_em      TEXT    NOT NULL,
    -- 0 = fatura atual, ainda recebendo compras; 1 = o dia do fechamento já passou.
    fechada        INTEGER NOT NULL DEFAULT 1,
    UNIQUE (conta_id, competencia)
);

CREATE TABLE IF NOT EXISTS emprestimo (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao        TEXT    NOT NULL,
    credor           TEXT    NOT NULL DEFAULT '',
    valor_contratado REAL    NOT NULL CHECK (valor_contratado > 0),
    juros_mes_pct    REAL    NOT NULL DEFAULT 0,
    parcelas         INTEGER NOT NULL CHECK (parcelas > 0),
    valor_parcela    REAL    NOT NULL,
    primeira_parcela TEXT    NOT NULL,
    dia_vencimento   INTEGER NOT NULL,
    conta_id         INTEGER NOT NULL REFERENCES conta(id) ON DELETE RESTRICT,
    centro_custo_id  INTEGER REFERENCES centro_custo(id) ON DELETE SET NULL,
    observacao       TEXT    NOT NULL DEFAULT '',
    criado_em        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS emprestimo_parcela (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    emprestimo_id INTEGER NOT NULL REFERENCES emprestimo(id) ON DELETE CASCADE,
    numero        INTEGER NOT NULL,
    competencia   TEXT    NOT NULL,
    vencimento    TEXT    NOT NULL,
    juros         REAL    NOT NULL,
    amortizacao   REAL    NOT NULL,
    total         REAL    NOT NULL,
    saldo_depois  REAL    NOT NULL,
    titulo_id     INTEGER REFERENCES titulo(id) ON DELETE SET NULL,
    UNIQUE (emprestimo_id, numero)
);

CREATE TABLE IF NOT EXISTS titulo (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT    NOT NULL CHECK (tipo IN ('PAGAR','RECEBER')),
    descricao       TEXT    NOT NULL,
    pessoa          TEXT    NOT NULL DEFAULT '',
    valor           REAL    NOT NULL CHECK (valor > 0),
    vencimento      TEXT    NOT NULL,
    competencia     TEXT    NOT NULL DEFAULT '',
    conta_id        INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    centro_custo_id INTEGER REFERENCES centro_custo(id) ON DELETE SET NULL,
    status          TEXT    NOT NULL DEFAULT 'ABERTO' CHECK (status IN ('ABERTO','QUITADO','CANCELADO')),
    liquidado_em    TEXT,
    valor_liquidado REAL,
    lancamento_id   INTEGER REFERENCES lancamento(id) ON DELETE SET NULL,
    observacao      TEXT    NOT NULL DEFAULT '',
    recorrencia_id  INTEGER REFERENCES recorrencia(id) ON DELETE SET NULL,
    -- Atraso: multa fixa (%) cobrada uma vez e juros (% ao mês) proporcionais aos dias.
    multa_pct       REAL    NOT NULL DEFAULT 0,
    juros_mes_pct   REAL    NOT NULL DEFAULT 0,
    encargos_lancados REAL  NOT NULL DEFAULT 0,   -- já provisionado na contabilidade
    encargos_ate    TEXT,                         -- data do último lançamento de encargos
    juros_embutido  REAL    NOT NULL DEFAULT 0,   -- parcela de empréstimo: parte de juros
    -- Conta de onde o dinheiro sai (ou onde entra) quando a conta for paga.
    conta_pagamento_id INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    -- Débito automático: no vencimento o sistema já dá a baixa sozinho.
    pagamento_automatico INTEGER NOT NULL DEFAULT 0 CHECK (pagamento_automatico IN (0,1))
);

-- Histórico das dívidas quitadas: quitar zera a dívida, e a linha fica aqui
-- para o usuário poder olhar depois o que já terminou de pagar.
CREATE TABLE IF NOT EXISTS divida_quitacao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id      INTEGER NOT NULL REFERENCES conta(id) ON DELETE CASCADE,
    nome          TEXT    NOT NULL,
    credor        TEXT    NOT NULL DEFAULT '',
    data          TEXT    NOT NULL,
    valor         REAL    NOT NULL,          -- quanto faltava no dia da quitação
    forma         TEXT    NOT NULL CHECK (forma IN ('PAGAMENTO','PERDAO')),
    conta_dinheiro_id INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    lancamento_id INTEGER REFERENCES lancamento(id) ON DELETE SET NULL,
    observacao    TEXT    NOT NULL DEFAULT '',
    criado_em     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS orcamento (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id    INTEGER NOT NULL REFERENCES conta(id) ON DELETE CASCADE,
    -- '' = teto que vale para todos os meses; 'AAAA-MM' = ajuste só daquele mês.
    competencia TEXT    NOT NULL DEFAULT '',
    valor       REAL    NOT NULL CHECK (valor >= 0),
    UNIQUE (conta_id, competencia)
);

CREATE TABLE IF NOT EXISTS meta (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    valor_alvo  REAL    NOT NULL CHECK (valor_alvo > 0),
    data_alvo   TEXT,
    conta_id    INTEGER REFERENCES conta(id) ON DELETE SET NULL,
    valor_base  REAL    NOT NULL DEFAULT 0,   -- saldo da conta quando a meta começou
    concluida   INTEGER NOT NULL DEFAULT 0 CHECK (concluida IN (0,1)),
    observacao  TEXT    NOT NULL DEFAULT '',
    criada_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS regra_categoria (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    padrao    TEXT    NOT NULL UNIQUE,
    conta_id  INTEGER NOT NULL REFERENCES conta(id) ON DELETE CASCADE,
    usos      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS configuracao (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_partida_lancamento ON partida(lancamento_id);
CREATE INDEX IF NOT EXISTS ix_partida_conta      ON partida(conta_id);
CREATE INDEX IF NOT EXISTS ix_lancamento_data    ON lancamento(data);
CREATE INDEX IF NOT EXISTS ix_titulo_venc        ON titulo(vencimento);
CREATE INDEX IF NOT EXISTS ix_titulo_status      ON titulo(status);
CREATE INDEX IF NOT EXISTS ix_conta_pai          ON conta(pai_id);
"""

# Criado só depois da migração: em bancos da v1 a coluna ainda não existe.
INDICES_V2 = "CREATE INDEX IF NOT EXISTS ix_titulo_recorrencia" \
             " ON titulo(recorrencia_id, competencia);"

INDICES_V5 = (
    "CREATE INDEX IF NOT EXISTS ix_lancamento_compra ON lancamento(compra_id);"
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_lancamento_extrato"
    " ON lancamento(id_extrato) WHERE id_extrato IS NOT NULL;"
)


# Plano de contas padrão: (código, nome, tipo, natureza, aceita lançamento)
PLANO_PADRAO: list[tuple[str, str, str, str, int]] = [
    ("1", "ATIVO", "ATIVO", "D", 0),
    ("1.1", "Ativo Circulante", "ATIVO", "D", 0),
    ("1.1.01", "Dinheiro em Espécie", "ATIVO", "D", 1),
    ("1.1.02", "Conta Corrente", "ATIVO", "D", 1),
    ("1.1.03", "Poupança", "ATIVO", "D", 1),
    ("1.1.04", "Carteira Digital", "ATIVO", "D", 1),
    ("1.1.05", "Investimentos de Curto Prazo", "ATIVO", "D", 1),
    ("1.1.06", "Contas a Receber", "ATIVO", "D", 1),
    ("1.1.07", "Cartão Pré-pago", "ATIVO", "D", 1),
    ("1.1.08", "Vale Alimentação / Refeição", "ATIVO", "D", 1),
    ("1.2", "Ativo Não Circulante", "ATIVO", "D", 0),
    ("1.2.01", "Investimentos de Longo Prazo", "ATIVO", "D", 1),
    ("1.2.02", "Imóveis", "ATIVO", "D", 1),
    ("1.2.03", "Veículos", "ATIVO", "D", 1),
    ("1.2.04", "Bens e Equipamentos", "ATIVO", "D", 1),
    ("2", "PASSIVO", "PASSIVO", "C", 0),
    ("2.1", "Passivo Circulante", "PASSIVO", "C", 0),
    ("2.1.01", "Cartão de Crédito", "PASSIVO", "C", 1),
    ("2.1.02", "Contas a Pagar", "PASSIVO", "C", 1),
    ("2.1.03", "Empréstimos de Curto Prazo", "PASSIVO", "C", 1),
    ("2.1.04", "Impostos a Pagar", "PASSIVO", "C", 1),
    ("2.2", "Passivo Não Circulante", "PASSIVO", "C", 0),
    ("2.2.01", "Financiamento Imobiliário", "PASSIVO", "C", 1),
    ("2.2.02", "Financiamento de Veículo", "PASSIVO", "C", 1),
    ("3", "PATRIMÔNIO LÍQUIDO", "PATRIMONIO", "C", 0),
    ("3.1", "Patrimônio Inicial", "PATRIMONIO", "C", 1),
    ("3.2", "Resultado Acumulado", "PATRIMONIO", "C", 1),
    ("4", "RECEITAS", "RECEITA", "C", 0),
    ("4.1", "Receitas Operacionais", "RECEITA", "C", 0),
    ("4.1.01", "Salário", "RECEITA", "C", 1),
    ("4.1.02", "Serviços Prestados / Freelance", "RECEITA", "C", 1),
    ("4.1.03", "Aluguéis Recebidos", "RECEITA", "C", 1),
    ("4.2", "Receitas Financeiras", "RECEITA", "C", 0),
    ("4.2.01", "Rendimentos de Investimentos", "RECEITA", "C", 1),
    ("4.3", "Outras Receitas", "RECEITA", "C", 0),
    ("4.3.01", "Reembolsos e Restituições", "RECEITA", "C", 1),
    ("5", "DESPESAS", "DESPESA", "D", 0),
    ("5.1", "Moradia", "DESPESA", "D", 0),
    ("5.1.01", "Aluguel / Condomínio", "DESPESA", "D", 1),
    ("5.1.02", "Energia Elétrica", "DESPESA", "D", 1),
    ("5.1.03", "Água e Esgoto", "DESPESA", "D", 1),
    ("5.1.04", "Internet e Telefonia", "DESPESA", "D", 1),
    ("5.1.05", "Manutenção Residencial", "DESPESA", "D", 1),
    ("5.2", "Alimentação", "DESPESA", "D", 0),
    ("5.2.01", "Supermercado", "DESPESA", "D", 1),
    ("5.2.02", "Restaurantes e Delivery", "DESPESA", "D", 1),
    ("5.3", "Transporte", "DESPESA", "D", 0),
    ("5.3.01", "Combustível", "DESPESA", "D", 1),
    ("5.3.02", "Manutenção de Veículo", "DESPESA", "D", 1),
    ("5.3.03", "Transporte Público / Aplicativos", "DESPESA", "D", 1),
    ("5.4", "Saúde", "DESPESA", "D", 0),
    ("5.4.01", "Plano de Saúde", "DESPESA", "D", 1),
    ("5.4.02", "Medicamentos", "DESPESA", "D", 1),
    ("5.4.03", "Consultas e Exames", "DESPESA", "D", 1),
    ("5.5", "Educação", "DESPESA", "D", 0),
    ("5.5.01", "Cursos e Mensalidades", "DESPESA", "D", 1),
    ("5.5.02", "Livros e Materiais", "DESPESA", "D", 1),
    ("5.6", "Lazer e Pessoal", "DESPESA", "D", 0),
    ("5.6.01", "Assinaturas e Streaming", "DESPESA", "D", 1),
    ("5.6.02", "Viagens", "DESPESA", "D", 1),
    ("5.6.03", "Vestuário", "DESPESA", "D", 1),
    ("5.7", "Despesas Financeiras", "DESPESA", "D", 0),
    ("5.7.01", "Juros e Multas", "DESPESA", "D", 1),
    ("5.7.02", "Tarifas Bancárias", "DESPESA", "D", 1),
    ("5.8", "Impostos e Taxas", "DESPESA", "D", 0),
    ("5.8.01", "IPTU / IPVA", "DESPESA", "D", 1),
    ("5.8.02", "Imposto de Renda", "DESPESA", "D", 1),
    ("5.9", "Outras Despesas", "DESPESA", "D", 0),
    ("5.9.01", "Despesas Diversas", "DESPESA", "D", 1),
]

CENTROS_PADRAO = ["Pessoal", "Família", "Trabalho"]

# Contas que guardam dinheiro de fato — acompanhadas na tela "Minhas Contas".
# 1.1.06 (Contas a Receber) fica de fora: é promessa, não saldo disponível.
CODIGOS_CARTEIRA = ("1.1.01", "1.1.02", "1.1.03", "1.1.04", "1.1.05",
                    "1.1.07", "1.1.08", "2.1.01")

# Acrescentadas na v3: bancos criados antes disso recebem estas contas na migração.
CONTAS_V3 = [
    ("1.1.07", "Cartão Pré-pago", "ATIVO", "D", "1.1"),
    ("1.1.08", "Vale Alimentação / Refeição", "ATIVO", "D", "1.1"),
]


def _sem_acento(texto: str | None) -> str:
    """Usada dentro do SQL para comparar textos ignorando acentos e maiúsculas."""
    if not texto:
        return ""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def get_connection() -> sqlite3.Connection:
    """Retorna a conexão única (criando e migrando o banco na primeira chamada)."""
    global _conn
    with _lock:
        if _conn is None:
            ensure_dirs()
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.create_function("sem_acento", 1, _sem_acento, deterministic=True)
            _conn.execute("PRAGMA foreign_keys = ON")
            _conn.execute("PRAGMA journal_mode = WAL")
            _conn.execute("PRAGMA synchronous = NORMAL")
            _migrate(_conn)
        return _conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Bloco transacional serializado — commit ao sair, rollback em exceção."""
    conn = get_connection()
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def query(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    with _lock:
        return get_connection().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    with _lock:
        return get_connection().execute(sql, params).fetchone()


def execute(sql: str, params: tuple | dict = ()) -> int:
    """Executa uma instrução de escrita e devolve o lastrowid."""
    with transaction() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)


def _migrate(conn: sqlite3.Connection) -> None:
    """Cria/atualiza o esquema e, só depois, carrega ou completa os dados.

    A ordem importa: as colunas novas precisam existir antes do seed, e o seed
    precisa rodar antes das migrações de dados — senão um banco novo receberia
    apenas as contas da migração e o plano padrão seria pulado.
    """
    conn.executescript(SCHEMA_SQL)
    versao = int(conn.execute("PRAGMA user_version").fetchone()[0])

    # --- estrutura ------------------------------------------------------
    if versao < 2:
        colunas = {c["name"] for c in conn.execute("PRAGMA table_info(titulo)")}
        if "recorrencia_id" not in colunas:
            conn.execute("ALTER TABLE titulo ADD COLUMN recorrencia_id INTEGER"
                         " REFERENCES recorrencia(id) ON DELETE SET NULL")
    conn.executescript(INDICES_V2)

    if versao < 3:
        colunas = {c["name"] for c in conn.execute("PRAGMA table_info(conta)")}
        if "eh_carteira" not in colunas:
            conn.execute("ALTER TABLE conta ADD COLUMN eh_carteira INTEGER NOT NULL DEFAULT 0")
        if "instituicao" not in colunas:
            conn.execute("ALTER TABLE conta ADD COLUMN instituicao TEXT NOT NULL DEFAULT ''")

    if versao < 4:
        # v4: encargos por atraso, faturas de cartão e empréstimos.
        novas = {
            "conta": [("dia_fechamento", "INTEGER"), ("dia_vencimento", "INTEGER"),
                      ("juros_rotativo", "REAL NOT NULL DEFAULT 0")],
            "titulo": [("multa_pct", "REAL NOT NULL DEFAULT 0"),
                       ("juros_mes_pct", "REAL NOT NULL DEFAULT 0"),
                       ("encargos_lancados", "REAL NOT NULL DEFAULT 0"),
                       ("encargos_ate", "TEXT"),
                       ("juros_embutido", "REAL NOT NULL DEFAULT 0")],
            "recorrencia": [("multa_pct", "REAL NOT NULL DEFAULT 0"),
                            ("juros_mes_pct", "REAL NOT NULL DEFAULT 0")],
        }
        for tabela, colunas_novas in novas.items():
            existentes = {c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})")}
            for nome, tipo in colunas_novas:
                if nome not in existentes:
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")

    if versao < 5:
        # v5: orçamento, metas, parcelamento, importação de extrato e limite do cartão.
        novas_v5 = {
            "conta": [("limite", "REAL NOT NULL DEFAULT 0")],
            "lancamento": [("compra_id", "INTEGER REFERENCES compra_parcelada(id)"),
                           ("conferido", "INTEGER NOT NULL DEFAULT 0"),
                           ("id_extrato", "TEXT")],
        }
        for tabela, colunas_novas in novas_v5.items():
            existentes = {c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})")}
            for nome, tipo in colunas_novas:
                if nome not in existentes:
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")

    if versao < 6:
        # v6: conta de onde sai o dinheiro do título e recorrência.
        for tabela, coluna, tipo in (
                ("titulo", "conta_pagamento_id", "INTEGER REFERENCES conta(id)"),
                ("recorrencia", "conta_pagamento_id", "INTEGER REFERENCES conta(id)")):
            existentes = {c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})")}
            if coluna not in existentes:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")

    if versao < 7:
        # v7: o usuário escolhe quais contas contam como dinheiro disponível.
        existentes = {c["name"] for c in conn.execute("PRAGMA table_info(conta)")}
        if "entra_no_disponivel" not in existentes:
            conn.execute("ALTER TABLE conta ADD COLUMN entra_no_disponivel"
                         " INTEGER NOT NULL DEFAULT 1")

    if versao < 8:
        # v8: cartões — limite garantido por uma aplicação e validade do plástico.
        existentes = {c["name"] for c in conn.execute("PRAGMA table_info(conta)")}
        for nome, tipo in (("conta_garantia_id", "INTEGER REFERENCES conta(id)"),
                           ("validade", "TEXT NOT NULL DEFAULT ''")):
            if nome not in existentes:
                conn.execute(f"ALTER TABLE conta ADD COLUMN {nome} {tipo}")

    if versao < 9:
        # v9: de qual conta sai o pagamento da fatura do cartão.
        existentes = {c["name"] for c in conn.execute("PRAGMA table_info(conta)")}
        if "conta_pagamento_id" not in existentes:
            conn.execute("ALTER TABLE conta ADD COLUMN conta_pagamento_id INTEGER"
                         " REFERENCES conta(id)")

    if versao < 10:
        # v10: a fatura do ciclo atual existe antes de fechar e recebe as compras.
        existentes = {c["name"] for c in conn.execute("PRAGMA table_info(fatura)")}
        if "fechada" not in existentes:
            conn.execute("ALTER TABLE fatura ADD COLUMN fechada INTEGER NOT NULL DEFAULT 1")

    if versao < 11:
        # v11: débito automático — a conta é baixada sozinha no vencimento.
        for tabela in ("titulo", "recorrencia"):
            existentes = {c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})")}
            if "pagamento_automatico" not in existentes:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN pagamento_automatico"
                             " INTEGER NOT NULL DEFAULT 0")

    conn.executescript(INDICES_V5)

    # --- dados ----------------------------------------------------------
    _seed(conn)

    if versao < 3:
        for codigo, nome, tipo, natureza, pai in CONTAS_V3:
            if conn.execute("SELECT 1 FROM conta WHERE codigo = ?", (codigo,)).fetchone():
                continue
            pai_row = conn.execute("SELECT id FROM conta WHERE codigo = ?", (pai,)).fetchone()
            conn.execute(
                "INSERT INTO conta (codigo, nome, tipo, natureza, pai_id, aceita_lancamento)"
                " VALUES (?,?,?,?,?,1)",
                (codigo, nome, tipo, natureza, pai_row["id"] if pai_row else None))
        marcadores = ",".join("?" * len(CODIGOS_CARTEIRA))
        conn.execute(f"UPDATE conta SET eh_carteira = 1 WHERE codigo IN ({marcadores})",
                     CODIGOS_CARTEIRA)

    if versao < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM conta").fetchone()[0] == 0:
        ids: dict[str, int] = {}
        for codigo, nome, tipo, natureza, aceita in PLANO_PADRAO:
            pai = codigo.rsplit(".", 1)[0] if "." in codigo else None
            cur = conn.execute(
                "INSERT INTO conta (codigo, nome, tipo, natureza, pai_id, aceita_lancamento)"
                " VALUES (?,?,?,?,?,?)",
                (codigo, nome, tipo, natureza, ids.get(pai or ""), aceita),
            )
            ids[codigo] = int(cur.lastrowid)
        marcadores = ",".join("?" * len(CODIGOS_CARTEIRA))
        conn.execute(f"UPDATE conta SET eh_carteira = 1 WHERE codigo IN ({marcadores})",
                     CODIGOS_CARTEIRA)

    if conn.execute("SELECT COUNT(*) FROM centro_custo").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO centro_custo (nome) VALUES (?)", [(c,) for c in CENTROS_PADRAO]
        )

    padroes = {
        "empresa": "Contabilidade Pessoal",
        "minimizar_bandeja": "1",
        "fechar_para_bandeja": "1",
        "backup_ao_sair": "1",
        "manter_backups": "15",
        "multa_padrao": "2",        # % sobre o valor, cobrada uma vez no atraso
        "juros_padrao": "1",        # % ao mês, proporcional aos dias de atraso
        "encargos_automaticos": "1",
    }
    for chave, valor in padroes.items():
        conn.execute(
            "INSERT INTO configuracao (chave, valor) VALUES (?,?)"
            " ON CONFLICT(chave) DO NOTHING",
            (chave, valor),
        )


# --------------------------------------------------------------------------- #
# Configurações
# --------------------------------------------------------------------------- #
def get_config(chave: str, padrao: str = "") -> str:
    row = query_one("SELECT valor FROM configuracao WHERE chave = ?", (chave,))
    return row["valor"] if row else padrao


def set_config(chave: str, valor: str) -> None:
    execute(
        "INSERT INTO configuracao (chave, valor) VALUES (?,?)"
        " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, str(valor)),
    )


# --------------------------------------------------------------------------- #
# Backup / manutenção
# --------------------------------------------------------------------------- #
def fazer_backup(destino: Path | None = None) -> Path:
    """Cópia consistente do banco usando a API de backup do SQLite."""
    ensure_dirs()
    if destino is None:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = BACKUP_DIR / f"contabil_{carimbo}.db"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        origem = get_connection()
        alvo = sqlite3.connect(destino)
        try:
            origem.backup(alvo)
            # Consolida o WAL para a cópia ficar num único arquivo, sem -wal/-shm
            # sobrando na pasta. O resultado do PRAGMA precisa ser consumido,
            # senão a mudança de journal não chega a ser aplicada.
            alvo.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
            alvo.execute("PRAGMA journal_mode = DELETE").fetchall()
            alvo.commit()
        finally:
            alvo.close()
    for sufixo in ("-wal", "-shm"):
        resto = destino.with_name(destino.name + sufixo)
        if resto.exists():
            try:
                resto.unlink()
            except OSError:
                pass
    return destino


def limpar_backups_antigos(manter: int) -> int:
    if manter <= 0:
        return 0
    arquivos = sorted(BACKUP_DIR.glob("contabil_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removidos = 0
    for arquivo in arquivos[manter:]:
        try:
            arquivo.unlink()
            removidos += 1
        except OSError:
            pass
    return removidos


def assinatura_dados(conexao: sqlite3.Connection | None = None) -> str:
    """Resumo do conteúdo do banco — muda sempre que algum dado muda."""
    conexao = conexao or get_connection()
    row = conexao.execute(
        "SELECT (SELECT COUNT(*) FROM lancamento) a, (SELECT COUNT(*) FROM partida) b,"
        " (SELECT COUNT(*) FROM titulo) c, (SELECT COUNT(*) FROM conta) d,"
        " (SELECT COALESCE(ROUND(SUM(valor),2),0) FROM lancamento) e,"
        " (SELECT COALESCE(MAX(id),0) FROM lancamento) f").fetchone()
    return "-".join(str(v) for v in tuple(row))


def _assinatura_do_arquivo(caminho: Path) -> str | None:
    # 'immutable' garante leitura sem criar arquivos -wal/-shm ao lado da cópia.
    try:
        outro = sqlite3.connect(f"file:{caminho}?immutable=1", uri=True)
        try:
            return assinatura_dados(outro)
        finally:
            outro.close()
    except sqlite3.Error:
        return None


def backup_automatico() -> Path | None:
    """Uma cópia por dia, e só quando algo realmente mudou.

    Evita encher a pasta: o arquivo do dia é sobrescrito e o histórico é
    enxugado por :func:`rotacionar_backups`.
    """
    ensure_dirs()
    destino = BACKUP_DIR / f"contabil_{datetime.now():%Y%m%d}.db"
    if destino.exists() and _assinatura_do_arquivo(destino) == assinatura_dados():
        return None
    caminho = fazer_backup(destino)
    rotacionar_backups()
    copiar_para_nuvem(caminho)
    return caminho


# --------------------------------------------------------------------------- #
# Cópia fora do computador (OneDrive, Google Drive, pen drive, rede)
# --------------------------------------------------------------------------- #
def pastas_de_nuvem_detectadas() -> list[Path]:
    """Pastas de sincronização que existem nesta máquina.

    Só olha variáveis de ambiente e caminhos padrão — nada é enviado para
    lugar nenhum: quem sincroniza é o próprio programa da nuvem.
    """
    candidatas: list[Path] = []
    for variavel in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        valor = os.environ.get(variavel)
        if valor:
            candidatas.append(Path(valor))
    casa = Path.home()
    for nome in ("OneDrive", "Google Drive", "GoogleDrive", "Dropbox",
                 "Meu Drive", "iCloudDrive"):
        candidatas.append(casa / nome)

    vistas: list[Path] = []
    for caminho in candidatas:
        try:
            if caminho.is_dir() and caminho not in vistas:
                vistas.append(caminho)
        except OSError:      # pragma: no cover - caminho de rede indisponível
            continue
    return vistas


def pasta_backup_nuvem() -> Path | None:
    """Pasta escolhida pelo usuário para a cópia de segurança externa."""
    valor = get_config("pasta_backup_nuvem", "")
    return Path(valor) if valor else None


def definir_pasta_backup_nuvem(caminho: str | Path | None) -> None:
    set_config("pasta_backup_nuvem", str(caminho) if caminho else "")


def copiar_para_nuvem(origem: Path) -> Path | None:
    """Duplica a cópia do dia na pasta sincronizada, se houver uma configurada.

    Mantém sempre os últimos 15 arquivos lá, para a pasta da nuvem não crescer
    sem controle. Falhas (pasta offline, sem permissão) não interrompem o uso.
    """
    pasta = pasta_backup_nuvem()
    if pasta is None:
        return None
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / origem.name
        shutil.copy2(origem, destino)
        copias = sorted(pasta.glob("contabil_*.db"), key=lambda p: p.stat().st_mtime,
                        reverse=True)
        for antiga in copias[15:]:
            try:
                antiga.unlink()
            except OSError:
                pass
        set_config("ultimo_backup_nuvem", datetime.now().isoformat(timespec="seconds"))
        return destino
    except OSError:
        import logging
        logging.exception("Não foi possível copiar o backup para a nuvem")
        return None


def rotacionar_backups(dias: int = 7, semanas: int = 4, meses: int = 6) -> int:
    """Mantém as cópias dos últimos dias, uma por semana e uma por mês.

    Os backups manuais (com outro nome) nunca são tocados.
    """
    from datetime import date as _date

    # Uma cópia por dia: se houver mais de uma (formato antigo, com hora), fica
    # apenas a mais recente daquele dia.
    por_dia: dict[_date, list[Path]] = {}
    for arquivo in BACKUP_DIR.glob("contabil_*.db"):
        carimbo = arquivo.stem.replace("contabil_", "")[:8]
        try:
            data = datetime.strptime(carimbo, "%Y%m%d").date()
        except ValueError:
            continue
        por_dia.setdefault(data, []).append(arquivo)

    if not por_dia:
        return 0

    removidos = 0
    arquivos: list[tuple[_date, Path]] = []
    for data, lista in por_dia.items():
        lista.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        arquivos.append((data, lista[0]))
        for excedente in lista[1:]:
            try:
                excedente.unlink()
                removidos += 1
            except OSError:
                pass

    arquivos.sort(key=lambda item: item[0], reverse=True)
    hoje = arquivos[0][0]

    manter: set[Path] = set()
    vistos_semana: set[tuple[int, int]] = set()
    vistos_mes: set[tuple[int, int]] = set()
    for data, arquivo in arquivos:
        idade = (hoje - data).days
        if idade <= dias:
            manter.add(arquivo)
            continue
        semana = data.isocalendar()[:2]
        if idade <= dias + semanas * 7 and semana not in vistos_semana:
            vistos_semana.add(semana)
            manter.add(arquivo)
            continue
        mes = (data.year, data.month)
        if idade <= 31 * meses and mes not in vistos_mes:
            vistos_mes.add(mes)
            manter.add(arquivo)

    for _data, arquivo in arquivos:
        if arquivo not in manter:
            try:
                arquivo.unlink()
                removidos += 1
            except OSError:
                pass
    return removidos


def restaurar_backup(origem: Path) -> None:
    """Substitui o banco atual pelo arquivo informado e reabre a conexão."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        for sufixo in ("-wal", "-shm"):
            extra = DB_PATH.with_name(DB_PATH.name + sufixo)
            if extra.exists():
                extra.unlink()
        shutil.copy2(origem, DB_PATH)
    get_connection()


def compactar() -> None:
    with _lock:
        get_connection().execute("VACUUM")


def reparar_indices() -> str | None:
    """Conserta índices quebrados do SQLite, se houver algum.

    Um índice fora de sincronia faz consultas filtradas devolverem linhas de
    outra conta — na prática, gasto de uma categoria aparecendo em outra. O
    conteúdo das tabelas não se perde: basta reconstruir os índices.

    Devolve o problema encontrado (texto do SQLite) ou None quando está tudo bem.
    """
    with _lock:
        conexao = get_connection()
        resultado = conexao.execute("PRAGMA quick_check").fetchone()
        estado = resultado[0] if resultado else "ok"
        if estado == "ok":
            return None
        logging.warning("Banco com índice inconsistente: %s — reconstruindo", estado)
        conexao.execute("REINDEX")
        conexao.commit()
        depois = conexao.execute("PRAGMA quick_check").fetchone()
        if depois and depois[0] != "ok":
            logging.error("Reconstrução não resolveu: %s", depois[0])
        return estado


def fechar() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.commit()
            _conn.close()
            _conn = None
