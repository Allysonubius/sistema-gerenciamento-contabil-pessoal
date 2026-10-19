"""Regras de negócio: plano de contas, lançamentos por partidas dobradas,
títulos a pagar/receber e apuração de relatórios contábeis."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app import db

TIPOS_CONTA = ("ATIVO", "PASSIVO", "PATRIMONIO", "RECEITA", "DESPESA")
ROTULO_TIPO = {
    "ATIVO": "Ativo",
    "PASSIVO": "Passivo",
    "PATRIMONIO": "Patrimônio Líquido",
    "RECEITA": "Receita",
    "DESPESA": "Despesa",
}
NATUREZA_PADRAO = {"ATIVO": "D", "DESPESA": "D", "PASSIVO": "C", "PATRIMONIO": "C", "RECEITA": "C"}
CENTAVO = 0.005


class RegraNegocioError(Exception):
    """Violação de regra de negócio — mensagem exibida ao usuário."""


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def hoje_iso() -> str:
    return date.today().isoformat()


def para_iso(texto: str) -> str:
    """Converte 'dd/mm/aaaa' (ou já ISO) em 'aaaa-mm-dd'."""
    texto = (texto or "").strip()
    if not texto:
        raise RegraNegocioError("Informe uma data.")
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    raise RegraNegocioError(f"Data inválida: {texto!r}. Use dd/mm/aaaa.")


def para_br(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def moeda(valor: float | None) -> str:
    valor = float(valor or 0.0)
    texto = f"{abs(valor):,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"-{texto}" if valor < 0 else texto


def para_float(texto: str) -> float:
    """Aceita '1.234,56', '1234.56' ou '1234,56'."""
    bruto = (texto or "").strip().replace("R$", "").replace(" ", "")
    if not bruto:
        raise RegraNegocioError("Informe um valor.")
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        return round(float(bruto), 2)
    except ValueError as exc:
        raise RegraNegocioError(f"Valor inválido: {texto!r}") from exc


def primeiro_dia_mes(referencia: date | None = None) -> str:
    ref = referencia or date.today()
    return ref.replace(day=1).isoformat()


def ultimo_dia_mes(referencia: date | None = None) -> str:
    ref = referencia or date.today()
    proximo = (ref.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (proximo - timedelta(days=1)).isoformat()


# --------------------------------------------------------------------------- #
# Plano de contas
# --------------------------------------------------------------------------- #
def listar_contas(apenas_ativas: bool = False, apenas_analiticas: bool = False) -> list[db.sqlite3.Row]:
    filtros = []
    if apenas_ativas:
        filtros.append("ativo = 1")
    if apenas_analiticas:
        filtros.append("aceita_lancamento = 1")
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    return db.query(f"SELECT * FROM conta {where} ORDER BY codigo")


def obter_conta(conta_id: int) -> db.sqlite3.Row | None:
    return db.query_one("SELECT * FROM conta WHERE id = ?", (conta_id,))


def salvar_conta(
    conta_id: int | None,
    codigo: str,
    nome: str,
    tipo: str,
    natureza: str,
    aceita_lancamento: bool,
    ativo: bool,
    observacao: str = "",
) -> int:
    codigo, nome = codigo.strip(), nome.strip()
    if not codigo:
        raise RegraNegocioError("O código da conta é obrigatório.")
    if not nome:
        raise RegraNegocioError("O nome da conta é obrigatório.")
    if tipo not in TIPOS_CONTA:
        raise RegraNegocioError("Tipo de conta inválido.")
    if natureza not in ("D", "C"):
        raise RegraNegocioError("Natureza deve ser Devedora (D) ou Credora (C).")

    duplicada = db.query_one(
        "SELECT id FROM conta WHERE codigo = ? AND id IS NOT ?", (codigo, conta_id)
    )
    if duplicada:
        raise RegraNegocioError(f"Já existe uma conta com o código {codigo}.")

    pai_codigo = codigo.rsplit(".", 1)[0] if "." in codigo else None
    pai = db.query_one("SELECT id, tipo, nome, codigo FROM conta WHERE codigo = ?",
                       (pai_codigo,)) if pai_codigo else None
    pai_id = pai["id"] if pai else None

    # O código define onde a conta entra na árvore. Um gasto pendurado no grupo
    # do patrimônio (3.x) é contado como patrimônio no balanço e como despesa no
    # resultado — e o balanço deixa de fechar.
    if pai is not None and pai["tipo"] != tipo:
        raise RegraNegocioError(
            f"O código {codigo} coloca esta conta dentro de '{pai['nome']}'"
            f" ({pai['codigo']}), que é do tipo {ROTULO_TIPO.get(pai['tipo'], pai['tipo'])}."
            f" Uma conta do tipo {ROTULO_TIPO.get(tipo, tipo)} precisa de um código"
            f" do grupo certo — veja os códigos já usados na lista.")

    if conta_id and not aceita_lancamento and _tem_partidas(conta_id):
        raise RegraNegocioError("A conta possui lançamentos e não pode virar sintética.")

    if conta_id:
        db.execute(
            "UPDATE conta SET codigo=?, nome=?, tipo=?, natureza=?, pai_id=?,"
            " aceita_lancamento=?, ativo=?, observacao=? WHERE id=?",
            (codigo, nome, tipo, natureza, pai_id, int(aceita_lancamento), int(ativo), observacao, conta_id),
        )
        # Reencadeia filhos caso o código tenha mudado.
        db.execute("UPDATE conta SET pai_id = ? WHERE codigo LIKE ? AND id <> ?",
                   (conta_id, f"{codigo}.%", conta_id))
        return conta_id

    return db.execute(
        "INSERT INTO conta (codigo, nome, tipo, natureza, pai_id, aceita_lancamento, ativo, observacao)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (codigo, nome, tipo, natureza, pai_id, int(aceita_lancamento), int(ativo), observacao),
    )


def excluir_conta(conta_id: int) -> None:
    if _tem_partidas(conta_id):
        raise RegraNegocioError("Conta com lançamentos não pode ser excluída. Inative-a.")
    if db.query_one("SELECT 1 FROM conta WHERE pai_id = ?", (conta_id,)):
        raise RegraNegocioError("Conta possui subcontas. Exclua-as primeiro.")
    if db.query_one("SELECT 1 FROM titulo WHERE conta_id = ?", (conta_id,)):
        raise RegraNegocioError("Conta vinculada a títulos financeiros.")
    db.execute("DELETE FROM conta WHERE id = ?", (conta_id,))


def _tem_partidas(conta_id: int) -> bool:
    return db.query_one("SELECT 1 FROM partida WHERE conta_id = ?", (conta_id,)) is not None


def saldo_conta(conta_id: int, ate: str | None = None, desde: str | None = None) -> float:
    """Saldo na natureza da conta (positivo = saldo normal)."""
    conta = obter_conta(conta_id)
    if conta is None:
        return 0.0
    filtros, params = ["p.conta_id = ?"], [conta_id]
    if desde:
        filtros.append("l.data >= ?")
        params.append(desde)
    if ate:
        filtros.append("l.data <= ?")
        params.append(ate)
    row = db.query_one(
        "SELECT COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE 0 END),0) AS d,"
        "       COALESCE(SUM(CASE WHEN p.tipo='C' THEN p.valor ELSE 0 END),0) AS c"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        f" WHERE {' AND '.join(filtros)}",
        tuple(params),
    )
    debito, credito = float(row["d"]), float(row["c"])
    return round(debito - credito if conta["natureza"] == "D" else credito - debito, 2)


def saldo_com_filhos(conta_id: int, ate: str | None = None) -> float:
    conta = obter_conta(conta_id)
    if conta is None:
        return 0.0
    total = saldo_conta(conta_id, ate)
    for filho in db.query("SELECT id FROM conta WHERE pai_id = ?", (conta_id,)):
        total += saldo_com_filhos(filho["id"], ate)
    return round(total, 2)


# --------------------------------------------------------------------------- #
# Carteiras — onde o dinheiro fica de fato
# --------------------------------------------------------------------------- #
CODIGO_PRE_PAGO = "1.1.07"        # Cartão Pré-pago, no plano de contas padrão
CODIGO_CARTAO_CREDITO = "2.1.01"  # Cartão de Crédito, no plano de contas padrão

# rótulo -> (tipo contábil, natureza, prefixo do código, negativo é normal?)
TIPOS_CARTEIRA: dict[str, tuple[str, str, str, bool]] = {
    "Conta corrente": ("ATIVO", "D", "1.1", False),
    "Poupança": ("ATIVO", "D", "1.1", False),
    "Dinheiro em espécie": ("ATIVO", "D", "1.1", False),
    "Carteira digital (Pix, PicPay, Mercado Pago)": ("ATIVO", "D", "1.1", False),
    "Cartão pré-pago (você carrega antes de usar)": ("ATIVO", "D", "1.1", False),
    "Vale alimentação / refeição": ("ATIVO", "D", "1.1", False),
    "Investimento": ("ATIVO", "D", "1.1", False),
    "Cartão de crédito (você paga a fatura depois)": ("PASSIVO", "C", "2.1", True),
}


def listar_carteiras(apenas_ativas: bool = True) -> list[db.sqlite3.Row]:
    where = "AND ativo = 1" if apenas_ativas else ""
    return db.query(f"SELECT * FROM conta WHERE eh_carteira = 1 {where} ORDER BY tipo, codigo")


def resumo_carteiras(desde: str | None = None, ate: str | None = None) -> list[dict]:
    """Saldo atual de cada conta de dinheiro e a movimentação do período."""
    hoje = hoje_iso()
    desde = desde or primeiro_dia_mes()
    ate = ate or ultimo_dia_mes()
    linhas = []
    for conta in listar_carteiras():
        movimento = db.query_one(
            "SELECT COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor END),0) AS d,"
            "       COALESCE(SUM(CASE WHEN p.tipo='C' THEN p.valor END),0) AS c"
            " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ? AND l.data BETWEEN ? AND ?",
            (conta["id"], desde, ate))
        entrou = float(movimento["d"]) if conta["natureza"] == "D" else float(movimento["c"])
        saiu = float(movimento["c"]) if conta["natureza"] == "D" else float(movimento["d"])
        ultimo = db.query_one(
            "SELECT MAX(l.data) AS d FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ?", (conta["id"],))
        linhas.append({
            "id": conta["id"],
            "codigo": conta["codigo"],
            "nome": conta["nome"],
            "instituicao": conta["instituicao"],
            "divida": conta["tipo"] == "PASSIVO",
            "saldo": saldo_conta(conta["id"], ate=hoje),
            "entrou": round(entrou, 2),
            "saiu": round(saiu, 2),
            "ultimo_movimento": ultimo["d"] if ultimo else None,
            "grupo": grupo_da_conta(conta),
        })
    return linhas


def grupo_da_conta(conta: db.sqlite3.Row) -> str:
    """Em que bolso a conta entra: dinheiro, investimento, outro saldo ou dívida."""
    if conta["tipo"] == "PASSIVO":
        return "divida"
    if eh_investimento(conta):
        return "investimento"
    return "disponivel" if conta["entra_no_disponivel"] else "outro"


def total_disponivel(ate: str | None = None) -> dict:
    """Quanto você tem para usar, quanto está aplicado e quanto deve em cartões.

    Só entra em ``tem`` o que está nas contas marcadas como dinheiro. Saldos que
    não são dinheiro livre (crédito de loja, vale) vão para ``outros``, e
    aplicações vão para ``investido``.
    """
    ate = ate or hoje_iso()
    tem = deve = investido = outros = 0.0
    for conta in listar_carteiras():
        saldo = saldo_conta(conta["id"], ate=ate)
        grupo = grupo_da_conta(conta)
        if grupo == "divida":
            deve += saldo
        elif grupo == "investimento":
            investido += saldo
        elif grupo == "outro":
            outros += saldo
        else:
            tem += saldo
    return {
        "tem": round(tem, 2),
        "investido": round(investido, 2),
        "outros": round(outros, 2),
        "deve": round(deve, 2),
        "liquido": round(tem - deve, 2),
        "com_investimentos": round(tem + investido + outros - deve, 2),
    }


def renomear_carteira(conta_id: int, nome: str, instituicao: str = "") -> None:
    """Muda o nome e o banco/bandeira da conta, sem tocar no histórico."""
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Conta não encontrada.")
    nome = nome.strip()
    if not nome:
        raise RegraNegocioError("Dê um nome para a conta.")
    db.execute("UPDATE conta SET nome = ?, instituicao = ? WHERE id = ?",
               (nome, instituicao.strip(), conta_id))


def definir_conta_dinheiro(conta_id: int, entra: bool) -> None:
    """Marca (ou desmarca) a conta como dinheiro disponível para gastar."""
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Conta não encontrada.")
    if conta["tipo"] == "PASSIVO":
        raise RegraNegocioError(
            "Cartão e dívida nunca somam no dinheiro disponível — eles aparecem"
            " no que você deve.")
    db.execute("UPDATE conta SET entra_no_disponivel = ? WHERE id = ?",
               (1 if entra else 0, conta_id))


def criar_carteira(nome: str, rotulo_tipo: str, instituicao: str = "",
                   saldo_inicial: float = 0.0, data_saldo: str | None = None,
                   conta_origem_id: int | None = None) -> int:
    """Cria a conta de dinheiro e, se informado, registra o saldo que ela já tem.

    Quando ``conta_origem_id`` é informado, o valor sai dessa conta (é uma
    aplicação de dinheiro que você já tinha); sem ela, entra como saldo que já
    existia antes de o sistema começar a acompanhar.
    """
    nome = nome.strip()
    if not nome:
        raise RegraNegocioError("Dê um nome para a conta (ex.: Nubank, Caixa, Vale refeição).")
    if rotulo_tipo not in TIPOS_CARTEIRA:
        raise RegraNegocioError("Escolha o tipo da conta.")
    tipo, natureza, prefixo, _ = TIPOS_CARTEIRA[rotulo_tipo]

    codigo = _proximo_codigo_livre(prefixo)
    pai = db.query_one("SELECT id FROM conta WHERE codigo = ?", (prefixo,))
    conta_id = db.execute(
        "INSERT INTO conta (codigo, nome, tipo, natureza, pai_id, aceita_lancamento, ativo,"
        " observacao, eh_carteira, instituicao) VALUES (?,?,?,?,?,1,1,?,1,?)",
        (codigo, nome, tipo, natureza, pai["id"] if pai else None, rotulo_tipo,
         instituicao.strip()))

    if abs(saldo_inicial) > CENTAVO:
        if conta_origem_id:
            transferir(conta_origem_id, conta_id, saldo_inicial,
                       data_saldo or hoje_iso(), f"Aplicação — {nome}")
        else:
            registrar_saldo_inicial(conta_id, saldo_inicial, data_saldo or hoje_iso())
    return conta_id


def _proximo_codigo_livre(prefixo: str) -> str:
    usados = []
    for conta in db.query("SELECT codigo FROM conta WHERE codigo LIKE ?", (f"{prefixo}.%",)):
        sufixo = conta["codigo"][len(prefixo) + 1:]
        if sufixo.isdigit():
            usados.append(int(sufixo))
    return f"{prefixo}.{max(usados, default=0) + 1:02d}"


def conta_patrimonio_inicial() -> int:
    conta = db.query_one("SELECT id FROM conta WHERE codigo = '3.1'")
    if conta is None:
        raise RegraNegocioError("A conta 3.1 (Patrimônio Inicial) não existe no plano de contas.")
    return conta["id"]


def registrar_saldo_inicial(conta_id: int, valor: float, data_iso: str | None = None) -> int:
    """Lança contra o patrimônio inicial o saldo que a conta já possuía."""
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Conta não encontrada.")
    if valor <= 0:
        raise RegraNegocioError("O saldo informado deve ser maior que zero.")
    patrimonio = conta_patrimonio_inicial()
    data_iso = data_iso or hoje_iso()
    if conta["tipo"] == "ATIVO":
        partidas = [Partida(conta_id, "D", valor), Partida(patrimonio, "C", valor)]
    else:
        partidas = [Partida(patrimonio, "D", valor), Partida(conta_id, "C", valor)]
    return salvar_lancamento(None, data_iso, f"Saldo inicial — {conta['nome']}", partidas)


def ajustar_saldo(conta_id: int, saldo_real: float, data_iso: str | None = None,
                  motivo: str = "") -> int | None:
    """Acerta a conta pelo extrato real, lançando apenas a diferença.

    Devolve o id do lançamento criado ou None quando já estava correto.
    """
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Conta não encontrada.")
    data_iso = data_iso or hoje_iso()
    atual = saldo_conta(conta_id, ate=data_iso)
    diferenca = round(saldo_real - atual, 2)
    if abs(diferenca) < CENTAVO:
        return None

    ajuste = db.query_one("SELECT id FROM conta WHERE codigo = '5.9.01'")
    ganho = db.query_one("SELECT id FROM conta WHERE codigo = '4.3.01'")
    if ajuste is None or ganho is None:
        raise RegraNegocioError("As contas de ajuste (5.9.01 e 4.3.01) não existem.")

    historico = motivo.strip() or f"Acerto de saldo — {conta['nome']}"
    valor = abs(diferenca)
    aumentar = diferenca > 0  # diferença já está na natureza da conta

    # Subir o saldo de um ativo é ganho; subir o saldo de uma dívida é despesa.
    if conta["natureza"] == "D":
        partidas = ([Partida(conta_id, "D", valor), Partida(ganho["id"], "C", valor)]
                    if aumentar
                    else [Partida(ajuste["id"], "D", valor), Partida(conta_id, "C", valor)])
    else:
        partidas = ([Partida(ajuste["id"], "D", valor), Partida(conta_id, "C", valor)]
                    if aumentar
                    else [Partida(conta_id, "D", valor), Partida(ganho["id"], "C", valor)])
    return salvar_lancamento(None, data_iso, historico, partidas)


def transferir(origem_id: int, destino_id: int, valor: float, data_iso: str | None = None,
               descricao: str = "") -> int:
    if origem_id == destino_id:
        raise RegraNegocioError("As duas contas não podem ser a mesma.")
    if valor <= 0:
        raise RegraNegocioError("O valor deve ser maior que zero.")
    origem = obter_conta(origem_id)
    destino = obter_conta(destino_id)
    texto = descricao.strip() or f"Transferência — {origem['nome']} para {destino['nome']}"
    return salvar_lancamento(
        None, data_iso or hoje_iso(), texto,
        [Partida(destino_id, "D", valor), Partida(origem_id, "C", valor)])


def evolucao_carteira(conta_id: int, meses: int = 6) -> list[dict]:
    """Saldo da conta no fim de cada um dos últimos meses."""
    historico = meses_do_historico(meses)
    return [{"mes": m, "nome": mes_nome(m),
             "saldo": saldo_conta(conta_id, ate=_fim_do_mes(m))} for m in historico]


# --------------------------------------------------------------------------- #
# Faturas de cartão de crédito
# --------------------------------------------------------------------------- #
def configurar_cartao(conta_id: int, dia_fechamento: int | None, dia_vencimento: int | None,
                      juros_rotativo: float = 0.0) -> None:
    conta = obter_conta(conta_id)
    if conta is None or conta["tipo"] != "PASSIVO":
        raise RegraNegocioError("O ciclo de fatura só vale para cartões de crédito.")
    if dia_fechamento and not 1 <= dia_fechamento <= 31:
        raise RegraNegocioError("O dia de fechamento deve estar entre 1 e 31.")
    if dia_vencimento and not 1 <= dia_vencimento <= 31:
        raise RegraNegocioError("O dia de vencimento deve estar entre 1 e 31.")
    mudou = ((conta["dia_fechamento"], conta["dia_vencimento"])
             != (dia_fechamento, dia_vencimento))
    db.execute("UPDATE conta SET dia_fechamento=?, dia_vencimento=?, juros_rotativo=?"
               " WHERE id=?", (dia_fechamento, dia_vencimento, juros_rotativo, conta_id))
    if mudou and dia_fechamento:
        _refazer_faturas_em_aberto(conta_id)


def _refazer_faturas_em_aberto(cartao_id: int) -> int:
    """O ciclo mudou: as faturas ainda não pagas são refeitas com as datas novas.

    Faturas pagas (ou canceladas) são história e nunca são tocadas; só as que
    vêm depois da última paga são refeitas.
    """
    corte = db.query_one(
        "SELECT MAX(f.competencia) AS m FROM fatura f JOIN titulo t ON t.id = f.titulo_id"
        " WHERE f.conta_id = ? AND t.status IN ('QUITADO', 'CANCELADO')",
        (cartao_id,))["m"] or ""
    refeitas = 0
    with db.transaction() as conn:
        for f in conn.execute(
                "SELECT f.*, t.encargos_lancados FROM fatura f"
                " LEFT JOIN titulo t ON t.id = f.titulo_id"
                " WHERE f.conta_id = ? AND f.competencia > ?"
                " AND (t.id IS NULL OR t.status = 'ABERTO')"
                " ORDER BY f.competencia", (cartao_id, corte)).fetchall():
            if f["encargos_lancados"]:      # já tem multa/juros contabilizados: não mexe
                continue
            if float(f["encargos"]) > CENTAVO:
                conn.execute(
                    "DELETE FROM lancamento WHERE documento = ? AND origem = 'ENCARGO'"
                    " AND id IN (SELECT lancamento_id FROM partida WHERE conta_id = ?)",
                    (f"ROT-{f['competencia']}", cartao_id))
            conn.execute("DELETE FROM fatura WHERE id = ?", (f["id"],))
            if f["titulo_id"]:
                conn.execute("DELETE FROM titulo WHERE id = ?", (f["titulo_id"],))
            refeitas += 1
    fechar_faturas()
    return refeitas


def cartoes_com_fatura() -> list[db.sqlite3.Row]:
    return db.query("SELECT * FROM conta WHERE tipo='PASSIVO' AND eh_carteira=1"
                    " AND dia_fechamento IS NOT NULL AND ativo=1 ORDER BY nome")


def listar_faturas(conta_id: int | None = None, limite: int = 24) -> list[db.sqlite3.Row]:
    where = "WHERE f.conta_id = ?" if conta_id else ""
    params = (conta_id, limite) if conta_id else (limite,)
    return db.query(
        "SELECT f.*, c.nome AS cartao, t.status AS status_titulo, t.valor_liquidado"
        " FROM fatura f JOIN conta c ON c.id = f.conta_id"
        f" LEFT JOIN titulo t ON t.id = f.titulo_id {where}"
        " ORDER BY f.competencia DESC LIMIT ?", params)


def fechar_faturas(hoje: str | None = None) -> int:
    """Mantém as faturas de cada cartão em dia com as compras.

    * A fatura do ciclo atual existe desde a primeira compra dele e recebe cada
      compra feita até o dia do fechamento — é a "fatura atual".
    * Chegado o fechamento, cobra o rotativo (se houver) e a fatura fica fechada.
    * Enquanto não for paga, uma compra com data dentro do período ainda
      atualiza o valor dela. Fatura paga é história e não muda mais.

    Devolve quantas faturas foram criadas.
    """
    global _faturas_em_sincronia
    if _faturas_em_sincronia:
        return 0
    _faturas_em_sincronia = True
    try:
        return _fechar_faturas(hoje)
    finally:
        _faturas_em_sincronia = False


def _fechar_faturas(hoje: str | None = None) -> int:
    hoje = hoje or hoje_iso()
    referencia = date.fromisoformat(hoje)
    criadas = 0

    for cartao in cartoes_com_fatura():
        dia = int(cartao["dia_fechamento"])
        ciclo = _primeiro_ciclo_pendente(cartao)
        # Sempre do mais antigo para o mais novo: cada fatura precisa da anterior
        # para saber o que rolou e cobrar o rotativo certo.
        for _ in range(120 if ciclo else 0):
            fechamento = _data_no_mes(ciclo, dia)
            inicio = _data_no_mes(somar_meses(fechamento.replace(day=1), -1), dia) \
                + timedelta(days=1)
            if inicio > referencia:
                break
            competencia = fechamento.strftime("%Y-%m")
            if not db.query_one("SELECT 1 FROM fatura WHERE conta_id=? AND competencia=?",
                                (cartao["id"], competencia)):
                if _criar_fatura(cartao, competencia, fechamento):
                    criadas += 1
            ciclo = somar_meses(ciclo, 1)
        _sincronizar_faturas(cartao, referencia)
    return criadas


def _vencimento_da_fatura(cartao: db.sqlite3.Row, fechamento: date) -> date:
    """Vence no mesmo mês se o dia de vencimento não vem antes do fechamento.

    Fecha e vence no mesmo dia (ex.: 15 e 15): as compras até o dia 15 entram
    na fatura e ela é cobrada no próprio dia 15.
    """
    dia_venc = int(cartao["dia_vencimento"] or cartao["dia_fechamento"])
    base = fechamento if dia_venc >= fechamento.day else somar_meses(fechamento, 1)
    return _data_no_mes(base, dia_venc)


def _valores_da_fatura(cartao: db.sqlite3.Row, competencia: str, fechamento: date) -> dict:
    """Compras, pagamentos e total da fatura, sempre recalculados do zero.

    O total é a dívida do cartão no fechamento, menos o que já está cobrado em
    faturas anteriores ainda não pagas — assim nenhum real aparece em duas
    contas a pagar ao mesmo tempo.
    """
    anterior = db.query_one(
        "SELECT * FROM fatura WHERE conta_id = ? AND competencia < ?"
        " ORDER BY competencia DESC LIMIT 1", (cartao["id"], competencia))
    inicio = (date.fromisoformat(anterior["fechamento"]) + timedelta(days=1)
              if anterior else date(1900, 1, 1))
    movimento = db.query_one(
        "SELECT COALESCE(SUM(CASE WHEN p.tipo='C' AND l.origem <> 'ENCARGO'"
        "                    THEN p.valor END),0) AS compras,"
        "       COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor END),0) AS pagamentos"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " WHERE p.conta_id = ? AND l.data BETWEEN ? AND ?",
        (cartao["id"], inicio.isoformat(), fechamento.isoformat()))
    ja_cobrado = db.query_one(
        "SELECT COALESCE(SUM(valor),0) AS t FROM titulo"
        " WHERE conta_id = ? AND status = 'ABERTO' AND competencia < ?",
        (cartao["id"], competencia))["t"]
    total = round(saldo_conta(cartao["id"], ate=fechamento.isoformat()) - float(ja_cobrado), 2)
    return {
        "inicio": inicio.isoformat(),
        "compras": round(float(movimento["compras"]), 2),
        "pagamentos": round(float(movimento["pagamentos"]), 2),
        "saldo_anterior": round(float(anterior["total"]) if anterior else 0.0, 2),
        "total": max(total, 0.0),
    }


def _criar_fatura(cartao: db.sqlite3.Row, competencia: str, fechamento: date) -> bool:
    valores = _valores_da_fatura(cartao, competencia, fechamento)
    if valores["total"] <= CENTAVO and valores["compras"] <= CENTAVO:
        return False
    vencimento = _vencimento_da_fatura(cartao, fechamento)
    titulo_id = None
    if valores["total"] > CENTAVO:
        titulo_id = _criar_titulo_fatura(cartao, competencia, valores["total"],
                                         vencimento, fechamento)
    db.execute(
        "INSERT INTO fatura (conta_id, competencia, fechamento, vencimento, saldo_anterior,"
        " compras, pagamentos, encargos, total, titulo_id, criada_em, fechada)"
        " VALUES (?,?,?,?,?,?,?,0,?,?,?,0)",
        (cartao["id"], competencia, fechamento.isoformat(), vencimento.isoformat(),
         valores["saldo_anterior"], valores["compras"], valores["pagamentos"],
         valores["total"], titulo_id, datetime.now().isoformat(timespec="seconds")))
    return True


def _texto_fatura(fechamento: date, fechada: bool) -> str:
    if fechada:
        return f"Fatura fechada em {para_br(fechamento.isoformat())}"
    return (f"Fatura atual: recebe as compras até {para_br(fechamento.isoformat())}"
            " e o valor muda a cada compra")


def _criar_titulo_fatura(cartao: db.sqlite3.Row, competencia: str, total: float,
                         vencimento: date, fechamento: date) -> int:
    return db.execute(
        "INSERT INTO titulo (tipo, descricao, pessoa, valor, vencimento, competencia,"
        " conta_id, observacao, multa_pct, juros_mes_pct, conta_pagamento_id)"
        " VALUES ('PAGAR',?,?,?,?,?,?,?,?,?,?)",
        (f"Fatura {cartao['nome']} — {mes_nome(competencia)}", cartao["instituicao"],
         total, vencimento.isoformat(), competencia, cartao["id"],
         _texto_fatura(fechamento, False), 0.0, float(cartao["juros_rotativo"] or 0),
         # A fatura já nasce sabendo de qual conta sai o dinheiro: sem isso
         # ela ficaria de fora da previsão de saldo.
         cartao["conta_pagamento_id"]))


def _sincronizar_faturas(cartao: db.sqlite3.Row, referencia: date) -> None:
    """Atualiza valores das faturas não pagas e fecha as que chegaram ao dia."""
    for f in db.query(
            "SELECT f.*, t.status AS status_titulo, t.encargos_lancados FROM fatura f"
            " LEFT JOIN titulo t ON t.id = f.titulo_id"
            " WHERE f.conta_id = ? ORDER BY f.competencia", (cartao["id"],)):
        if f["titulo_id"] and f["status_titulo"] != "ABERTO":
            continue                                    # paga ou cancelada: é história
        fechamento = date.fromisoformat(f["fechamento"])
        fechada = bool(f["fechada"])
        encargos = float(f["encargos"])
        if not fechada and fechamento <= referencia:
            encargos = _cobrar_rotativo(cartao, f)
            fechada = True

        valores = _valores_da_fatura(cartao, f["competencia"], fechamento)
        titulo_id = f["titulo_id"]
        if valores["total"] > CENTAVO:
            if titulo_id:
                db.execute("UPDATE titulo SET valor = ?, observacao = ? WHERE id = ?",
                           (valores["total"], _texto_fatura(fechamento, fechada), titulo_id))
            else:
                titulo_id = _criar_titulo_fatura(
                    cartao, f["competencia"], valores["total"],
                    date.fromisoformat(f["vencimento"]), fechamento)
                if fechada:
                    db.execute("UPDATE titulo SET observacao = ? WHERE id = ?",
                               (_texto_fatura(fechamento, True), titulo_id))
        elif titulo_id and not f["encargos_lancados"]:
            db.execute("DELETE FROM titulo WHERE id = ?", (titulo_id,))
            titulo_id = None

        db.execute(
            "UPDATE fatura SET saldo_anterior = ?, compras = ?, pagamentos = ?, encargos = ?,"
            " total = ?, titulo_id = ?, fechada = ? WHERE id = ?",
            (valores["saldo_anterior"], valores["compras"], valores["pagamentos"], encargos,
             valores["total"], titulo_id, int(fechada), f["id"]))


def _cobrar_rotativo(cartao: db.sqlite3.Row, fatura: db.sqlite3.Row) -> float:
    """No fechamento: juros sobre o que ficou sem pagar da fatura anterior."""
    juros_pct = float(cartao["juros_rotativo"] or 0)
    if juros_pct <= 0:
        return 0.0
    anterior = db.query_one(
        "SELECT f.*, t.status, t.valor AS valor_titulo, t.valor_liquidado FROM fatura f"
        " JOIN titulo t ON t.id = f.titulo_id WHERE f.conta_id = ? AND f.competencia < ?"
        " ORDER BY f.competencia DESC LIMIT 1", (cartao["id"], fatura["competencia"]))
    if anterior is None or anterior["vencimento"] >= fatura["fechamento"]:
        return 0.0                                      # a anterior ainda nem venceu
    if anterior["status"] == "ABERTO":
        nao_pago = float(anterior["valor_titulo"])
    elif anterior["status"] == "QUITADO":
        nao_pago = float(anterior["total"]) - float(anterior["valor_liquidado"] or 0)
    else:
        nao_pago = 0.0
    encargos = round(nao_pago * juros_pct / 100, 2) if nao_pago > CENTAVO else 0.0
    if encargos > CENTAVO:
        salvar_lancamento(
            None, fatura["fechamento"], f"Juros do rotativo — {cartao['nome']}",
            [Partida(_conta_por_codigo(CONTA_ENCARGOS), "D", encargos),
             Partida(cartao["id"], "C", encargos)],
            documento=f"ROT-{fatura['competencia']}", origem="ENCARGO")
    return encargos


def fatura_da_data(cartao_id: int, data_iso: str) -> dict | None:
    """Em qual fatura cai uma compra feita nesta data."""
    cartao = obter_conta(cartao_id)
    if cartao is None or not cartao["dia_fechamento"]:
        return None
    dia = int(cartao["dia_fechamento"])
    compra = date.fromisoformat(data_iso)
    fechamento = _data_no_mes(compra, dia)
    if compra > fechamento:
        fechamento = _data_no_mes(somar_meses(compra.replace(day=1), 1), dia)
    competencia = fechamento.strftime("%Y-%m")
    existente = db.query_one(
        "SELECT t.status FROM fatura f JOIN titulo t ON t.id = f.titulo_id"
        " WHERE f.conta_id = ? AND f.competencia = ?", (cartao_id, competencia))
    return {
        "competencia": competencia,
        "nome": mes_nome(competencia),
        "fechamento": fechamento.isoformat(),
        "vencimento": _vencimento_da_fatura(cartao, fechamento).isoformat(),
        "ja_paga": bool(existente and existente["status"] == "QUITADO"),
    }


def registrar_compra_cartao(cartao_id: int, categoria_id: int, valor: float, data_iso: str,
                            descricao: str = "", parcelas: int = 1,
                            centro_custo_id: int | None = None) -> dict:
    """Compra no cartão de crédito: à vista entra inteira na fatura da data;
    parcelada, uma parcela em cada fatura. A fatura é atualizada na hora."""
    cartao = obter_conta(cartao_id)
    if cartao is None or cartao["tipo"] != "PASSIVO":
        raise RegraNegocioError("Escolha um cartão de crédito.")
    categoria = obter_conta(categoria_id) if categoria_id else None
    if categoria is None or categoria["tipo"] != "DESPESA":
        raise RegraNegocioError("Escolha a categoria do gasto.")
    if valor <= 0:
        raise RegraNegocioError("Informe o valor da compra.")
    if not 1 <= parcelas <= 48:
        raise RegraNegocioError("O número de parcelas deve estar entre 1 e 48.")
    descricao = descricao.strip() or categoria["nome"]

    if parcelas > 1:
        criar_compra_parcelada(descricao, cartao_id, categoria_id, valor, parcelas,
                               data_iso[:7], data_iso, centro_custo_id)
    else:
        # Origem própria: a compra é corrigida/removida na tela do cartão.
        salvar_lancamento(None, data_iso, descricao,
                          [Partida(categoria_id, "D", valor), Partida(cartao_id, "C", valor)],
                          centro_custo_id=centro_custo_id, origem=ORIGEM_COMPRA_CARTAO)
    fechar_faturas()
    return fatura_da_data(cartao_id, data_iso) or {}


ORIGEM_COMPRA_CARTAO = "CARTAO"
ORIGENS_COMPRA_EDITAVEL = ("MANUAL", ORIGEM_COMPRA_CARTAO)


def _fatura_paga_na_data(cartao_id: int, data_iso: str) -> bool:
    info = fatura_da_data(cartao_id, data_iso)
    return bool(info and info["ja_paga"])


MOTIVO_TRAVA = {
    "BAIXA": "Conta paga com o cartão em Contas a Pagar: corrija por lá"
             " (Desfazer pagamento).",
    "ENCARGO": "Juros do rotativo, calculados automaticamente.",
}


def listar_compras_cartao(cartao_id: int, competencia: str | None = None) -> list[dict]:
    """Tudo o que foi cobrado no cartão, com a fatura de cada item e se dá para corrigir.

    Aparecem também as contas pagas com o cartão em Contas a Pagar e os juros do
    rotativo — eles compõem a fatura, mas são corrigidos onde nasceram.
    """
    compras = []
    for lanc in db.query(
            "SELECT l.*, pc.valor AS valor_cartao, cp.parcelas AS total_parcelas,"
            " (SELECT GROUP_CONCAT(c.nome, ' + ') FROM partida q JOIN conta c ON c.id = q.conta_id"
            "   WHERE q.lancamento_id = l.id AND q.tipo = 'D') AS categoria,"
            " (SELECT q.conta_id FROM partida q JOIN conta c ON c.id = q.conta_id"
            "   WHERE q.lancamento_id = l.id AND q.tipo = 'D' AND c.tipo = 'DESPESA'"
            "   LIMIT 1) AS categoria_id,"
            " (SELECT COUNT(*) FROM partida q WHERE q.lancamento_id = l.id) AS n_partidas"
            " FROM lancamento l"
            " JOIN partida pc ON pc.lancamento_id = l.id AND pc.conta_id = ? AND pc.tipo = 'C'"
            " LEFT JOIN compra_parcelada cp ON cp.id = l.compra_id"
            " ORDER BY l.data DESC, l.id DESC", (cartao_id,)):
        info = fatura_da_data(cartao_id, lanc["data"])
        comp = info["competencia"] if info else lanc["data"][:7]
        if competencia and comp != competencia:
            continue
        paga = bool(info and info["ja_paga"])
        motivo = ""
        if paga:
            motivo = "Está numa fatura já paga: não pode mais ser alterada."
        elif lanc["origem"] in MOTIVO_TRAVA:
            motivo = MOTIVO_TRAVA[lanc["origem"]]
        elif lanc["origem"] not in ("MANUAL", "CARTAO", "PARCELA"):
            motivo = "Lançado em outra tela: corrija por lá."
        elif not lanc["compra_id"] and (lanc["n_partidas"] != 2 or not lanc["categoria_id"]):
            motivo = "Registro com várias contas: corrija em Entradas e Saídas."
        parcela = ""
        if lanc["compra_id"]:
            numero = lanc["historico"].rsplit("(", 1)[-1].split("/")[0] \
                if lanc["historico"].endswith(")") else "?"
            parcela = f"{numero}/{lanc['total_parcelas']}"
        compras.append({
            "id": lanc["id"],
            "data": lanc["data"],
            "descricao": lanc["historico"],
            "categoria_id": lanc["categoria_id"],
            "categoria": lanc["categoria"] or "—",
            "valor": round(float(lanc["valor_cartao"]), 2),
            "compra_id": lanc["compra_id"],
            "parcela": parcela,
            "competencia": comp,
            "fatura_vence": info["vencimento"] if info else None,
            "origem": lanc["origem"],
            "paga": paga,
            "editavel": not motivo,
            "motivo": motivo,
        })
    return compras


def _compra_do_cartao(lancamento_id: int) -> dict:
    """Confere que o registro é uma compra simples de cartão e devolve as partes."""
    lanc = db.query_one("SELECT * FROM lancamento WHERE id = ?", (lancamento_id,))
    if lanc is None:
        raise RegraNegocioError("Compra não encontrada.")
    partidas = db.query(
        "SELECT p.*, c.tipo AS tipo_conta FROM partida p JOIN conta c ON c.id = p.conta_id"
        " WHERE p.lancamento_id = ?", (lancamento_id,))
    credito = [p for p in partidas if p["tipo"] == "C" and p["tipo_conta"] == "PASSIVO"]
    debito = [p for p in partidas if p["tipo"] == "D" and p["tipo_conta"] == "DESPESA"]
    if len(partidas) != 2 or len(credito) != 1 or len(debito) != 1:
        raise RegraNegocioError("Este registro não é uma compra simples no cartão.")
    return {"lancamento": lanc, "cartao_id": credito[0]["conta_id"],
            "categoria_id": debito[0]["conta_id"]}


def editar_compra_cartao(lancamento_id: int, categoria_id: int, valor: float, data_iso: str,
                         descricao: str) -> dict:
    """Corrige uma compra à vista. A fatura (antiga e nova, se a data mudar) se ajusta."""
    compra = _compra_do_cartao(lancamento_id)
    lanc = compra["lancamento"]
    if lanc["compra_id"]:
        raise RegraNegocioError("Compra parcelada: corrija pela compra inteira.")
    if lanc["origem"] not in ORIGENS_COMPRA_EDITAVEL:
        raise RegraNegocioError("Este registro não pode ser corrigido por aqui.")
    cartao_id = compra["cartao_id"]
    if _fatura_paga_na_data(cartao_id, lanc["data"]):
        raise RegraNegocioError(
            "Esta compra está numa fatura já paga e não pode mais ser alterada."
            " Se foi lançada errado, registre um ajuste na fatura atual.")
    if _fatura_paga_na_data(cartao_id, data_iso):
        raise RegraNegocioError("A nova data cai numa fatura que já foi paga. Escolha outra data.")
    categoria = obter_conta(categoria_id) if categoria_id else None
    if categoria is None or categoria["tipo"] != "DESPESA":
        raise RegraNegocioError("Escolha a categoria do gasto.")
    if valor <= 0:
        raise RegraNegocioError("Informe o valor da compra.")
    descricao = descricao.strip() or categoria["nome"]

    with db.transaction() as conn:
        conn.execute("UPDATE lancamento SET data = ?, historico = ?, valor = ? WHERE id = ?",
                     (data_iso, descricao, round(valor, 2), lancamento_id))
        conn.execute("UPDATE partida SET valor = ? WHERE lancamento_id = ?",
                     (round(valor, 2), lancamento_id))
        conn.execute("UPDATE partida SET conta_id = ? WHERE lancamento_id = ? AND tipo = 'D'",
                     (categoria_id, lancamento_id))
    fechar_faturas()
    return fatura_da_data(cartao_id, data_iso) or {}


def editar_compra_parcelada(compra_id: int, descricao: str, categoria_id: int,
                            novo_total: float | None = None) -> int:
    """Corrige descrição, categoria e (se informado) o valor total da compra parcelada.

    Parcelas em faturas já pagas não mudam. O valor segue a regra de
    `ajustar_compra_parcelada`: o que já foi faturado fica, o resto é redividido.
    Devolve quantas parcelas foram atualizadas.
    """
    compra = db.query_one("SELECT * FROM compra_parcelada WHERE id = ?", (compra_id,))
    if compra is None:
        raise RegraNegocioError("Compra parcelada não encontrada.")
    categoria = obter_conta(categoria_id) if categoria_id else None
    if categoria is None or categoria["tipo"] != "DESPESA":
        raise RegraNegocioError("Escolha a categoria do gasto.")
    descricao = descricao.strip() or categoria["nome"]

    abertas = [l for l in db.query("SELECT * FROM lancamento WHERE compra_id = ? ORDER BY data",
                                   (compra_id,))
               if not _fatura_paga_na_data(compra["cartao_id"], l["data"])]
    if not abertas:
        raise RegraNegocioError("Todas as parcelas estão em faturas já pagas.")

    with db.transaction() as conn:
        conn.execute("UPDATE compra_parcelada SET descricao = ?, categoria_id = ? WHERE id = ?",
                     (descricao, categoria_id, compra_id))
        for lanc in abertas:
            numero = lanc["historico"].rsplit("(", 1)[-1] if lanc["historico"].endswith(")") else ""
            conn.execute("UPDATE lancamento SET historico = ? WHERE id = ?",
                         (f"{descricao} ({numero}" if numero else descricao, lanc["id"]))
            conn.execute("UPDATE partida SET conta_id = ? WHERE lancamento_id = ? AND tipo = 'D'",
                         (categoria_id, lanc["id"]))

    if novo_total is not None and abs(novo_total - float(compra["valor_total"])) > CENTAVO:
        ajustar_compra_parcelada(compra_id, novo_total)
    fechar_faturas()
    return len(abertas)


def remover_compra_cartao(lancamento_id: int) -> dict:
    """Remove uma compra lançada errado. Parcelada: remove a compra inteira,
    menos as parcelas que já estão em faturas pagas."""
    lanc = db.query_one("SELECT * FROM lancamento WHERE id = ?", (lancamento_id,))
    if lanc is None:
        raise RegraNegocioError("Compra não encontrada.")

    if lanc["compra_id"]:
        compra = db.query_one("SELECT * FROM compra_parcelada WHERE id = ?", (lanc["compra_id"],))
        parcelas = db.query("SELECT * FROM lancamento WHERE compra_id = ?", (lanc["compra_id"],))
        remover = [p["id"] for p in parcelas
                   if not _fatura_paga_na_data(compra["cartao_id"], p["data"])]
        if not remover:
            raise RegraNegocioError("Todas as parcelas estão em faturas já pagas.")
        with db.transaction() as conn:
            conn.executemany("DELETE FROM lancamento WHERE id = ?", [(i,) for i in remover])
            if len(remover) == len(parcelas):
                conn.execute("DELETE FROM compra_parcelada WHERE id = ?", (compra["id"],))
        fechar_faturas()
        return {"removidas": len(remover), "mantidas": len(parcelas) - len(remover)}

    compra = _compra_do_cartao(lancamento_id)
    if lanc["origem"] not in ORIGENS_COMPRA_EDITAVEL:
        raise RegraNegocioError("Este registro não pode ser removido por aqui.")
    if _fatura_paga_na_data(compra["cartao_id"], lanc["data"]):
        raise RegraNegocioError(
            "Esta compra está numa fatura já paga e não pode mais ser removida.")
    db.execute("DELETE FROM lancamento WHERE id = ?", (lancamento_id,))
    fechar_faturas()
    return {"removidas": 1, "mantidas": 0}


def descontar_faturas_da_garantia(hoje: str | None = None) -> list[dict]:
    """Cartão com saldo em garantia: fatura não paga é descontada da garantia.

    Vale no dia seguinte ao vencimento — o dia do vencimento ainda é seu para
    pagar pela conta de sempre. O desconto leva a data do vencimento. Se a
    garantia não cobrir tudo, desconta o que houver e o resto fica em aberto.
    """
    hoje = hoje or hoje_iso()
    fechar_faturas(hoje)
    descontos = []
    for cartao in cartoes_com_fatura():
        garantia_id = cartao["conta_garantia_id"]
        if not garantia_id:
            continue
        for f in db.query(
                "SELECT f.competencia, t.id AS titulo_id, t.valor, t.vencimento FROM fatura f"
                " JOIN titulo t ON t.id = f.titulo_id WHERE f.conta_id = ?"
                " AND t.status = 'ABERTO' AND t.vencimento < ? ORDER BY t.vencimento",
                (cartao["id"], hoje)):
            disponivel = round(saldo_conta(garantia_id), 2)
            if disponivel <= CENTAVO:
                continue
            valor = float(f["valor"])
            pago = round(min(valor, disponivel), 2)
            baixar_titulo(f["titulo_id"], f["vencimento"], pago, garantia_id,
                          saldo_em_aberto=pago < valor - CENTAVO)
            descontos.append({"cartao": cartao["nome"], "competencia": f["competencia"],
                              "valor": pago, "faltou": round(valor - pago, 2),
                              "garantia": obter_conta(garantia_id)["nome"]})
    if descontos:
        fechar_faturas(hoje)
    return descontos


def _primeiro_ciclo_pendente(cartao: db.sqlite3.Row) -> date | None:
    """Mês a partir do qual ainda há faturas a fechar."""
    ultima = db.query_one("SELECT MAX(competencia) AS m FROM fatura WHERE conta_id = ?",
                          (cartao["id"],))
    if ultima and ultima["m"]:
        return date.fromisoformat(f"{_mes_seguinte(ultima['m'])}-01")
    primeiro = db.query_one(
        "SELECT MIN(l.data) AS d FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " WHERE p.conta_id = ?", (cartao["id"],))
    if primeiro is None or not primeiro["d"]:
        return None
    return date.fromisoformat(primeiro["d"][:8] + "01")


def _data_no_mes(referencia: date, dia: int) -> date:
    return date(referencia.year, referencia.month,
                min(dia, _ultimo_dia(referencia.year, referencia.month)))



def resumo_fatura_aberta(conta_id: int, hoje: str | None = None) -> dict:
    """Quanto já está lançado no ciclo que ainda não fechou."""
    hoje = hoje or hoje_iso()
    cartao = obter_conta(conta_id)
    ultima = db.query_one(
        "SELECT * FROM fatura WHERE conta_id=? AND fechada=1"
        " ORDER BY competencia DESC LIMIT 1", (conta_id,))
    inicio = (date.fromisoformat(ultima["fechamento"]) + timedelta(days=1)
              if ultima else date(1900, 1, 1))
    movimento = db.query_one(
        "SELECT COALESCE(SUM(CASE WHEN p.tipo='C' THEN p.valor END),0) AS compras"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " WHERE p.conta_id = ? AND l.data BETWEEN ? AND ?",
        (conta_id, inicio.isoformat(), hoje))
    proximo_fechamento = None
    if cartao and cartao["dia_fechamento"]:
        referencia = date.fromisoformat(hoje)
        proximo = _data_no_mes(referencia, int(cartao["dia_fechamento"]))
        if proximo < referencia:
            proximo = _data_no_mes(somar_meses(referencia, 1), int(cartao["dia_fechamento"]))
        proximo_fechamento = proximo.isoformat()
    return {
        "compras": round(float(movimento["compras"]), 2),
        "desde": inicio.isoformat() if ultima else None,
        "proximo_fechamento": proximo_fechamento,
        "saldo_total": saldo_conta(conta_id, ate=hoje),
    }


# --------------------------------------------------------------------------- #
# Empréstimos e financiamentos
# --------------------------------------------------------------------------- #
def tabela_price(valor: float, juros_mes_pct: float, parcelas: int) -> list[dict]:
    """Plano de amortização: parcela fixa, juros sobre o saldo devedor."""
    if parcelas <= 0:
        raise RegraNegocioError("Informe o número de parcelas.")
    taxa = juros_mes_pct / 100
    if taxa > 0:
        fator = (1 + taxa) ** parcelas
        parcela = valor * taxa * fator / (fator - 1)
    else:
        parcela = valor / parcelas

    plano, saldo = [], valor
    for numero in range(1, parcelas + 1):
        juros = round(saldo * taxa, 2)
        if numero == parcelas:
            amortizacao = round(saldo, 2)
            total = round(amortizacao + juros, 2)
        else:
            total = round(parcela, 2)
            amortizacao = round(total - juros, 2)
        saldo = round(saldo - amortizacao, 2)
        plano.append({"numero": numero, "juros": juros, "amortizacao": amortizacao,
                      "total": total, "saldo_depois": max(saldo, 0.0)})
    return plano


def criar_emprestimo(
    descricao: str,
    credor: str,
    valor: float,
    juros_mes_pct: float,
    parcelas: int,
    primeira_parcela: str,
    dia_vencimento: int,
    conta_recebimento_id: int | None = None,
    data_contratacao: str | None = None,
    centro_custo_id: int | None = None,
    observacao: str = "",
) -> int:
    """Cadastra o empréstimo, cria a conta da dívida e gera todas as parcelas."""
    descricao = descricao.strip()
    if not descricao:
        raise RegraNegocioError("Descreva o empréstimo (ex.: Empréstimo do carro).")
    if valor <= 0:
        raise RegraNegocioError("O valor contratado deve ser maior que zero.")
    if not 1 <= dia_vencimento <= 31:
        raise RegraNegocioError("O dia de vencimento deve estar entre 1 e 31.")

    prefixo = "2.1" if parcelas <= 12 else "2.2"
    codigo = _proximo_codigo_livre(prefixo)
    pai = db.query_one("SELECT id FROM conta WHERE codigo = ?", (prefixo,))
    conta_id = db.execute(
        "INSERT INTO conta (codigo, nome, tipo, natureza, pai_id, aceita_lancamento, ativo,"
        " observacao, eh_carteira, instituicao) VALUES (?,?,'PASSIVO','C',?,1,1,?,1,?)",
        (codigo, descricao, pai["id"] if pai else None, "Empréstimo / financiamento",
         credor.strip()))

    plano = tabela_price(valor, juros_mes_pct, parcelas)
    total_parcela = plano[0]["total"]
    emprestimo_id = db.execute(
        "INSERT INTO emprestimo (descricao, credor, valor_contratado, juros_mes_pct, parcelas,"
        " valor_parcela, primeira_parcela, dia_vencimento, conta_id, centro_custo_id,"
        " observacao, criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (descricao, credor.strip(), valor, juros_mes_pct, parcelas, total_parcela,
         primeira_parcela, dia_vencimento, conta_id, centro_custo_id, observacao,
         datetime.now().isoformat(timespec="seconds")))

    # Dinheiro recebido: entra na carteira e cria a dívida.
    if conta_recebimento_id:
        salvar_lancamento(
            None, data_contratacao or hoje_iso(),
            f"Empréstimo recebido — {descricao}",
            [Partida(conta_recebimento_id, "D", valor), Partida(conta_id, "C", valor)])

    base = date.fromisoformat(f"{primeira_parcela}-01")
    for item in plano:
        vencimento = _data_no_mes(somar_meses(base, item["numero"] - 1), dia_vencimento)
        competencia = vencimento.strftime("%Y-%m")
        titulo_id = db.execute(
            "INSERT INTO titulo (tipo, descricao, pessoa, valor, vencimento, competencia,"
            " conta_id, centro_custo_id, observacao, multa_pct, juros_mes_pct, juros_embutido)"
            " VALUES ('PAGAR',?,?,?,?,?,?,?,?,?,?,?)",
            (f"{descricao} — parcela {item['numero']}/{parcelas}", credor.strip(),
             item["total"], vencimento.isoformat(), competencia, conta_id, centro_custo_id,
             "Parcela de empréstimo",
             float(db.get_config("multa_padrao", "0") or 0),
             float(db.get_config("juros_padrao", "0") or 0),
             item["juros"]))
        db.execute(
            "INSERT INTO emprestimo_parcela (emprestimo_id, numero, competencia, vencimento,"
            " juros, amortizacao, total, saldo_depois, titulo_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (emprestimo_id, item["numero"], competencia, vencimento.isoformat(),
             item["juros"], item["amortizacao"], item["total"], item["saldo_depois"], titulo_id))
    return emprestimo_id


def listar_dividas(incluir_quitadas: bool = False) -> list[dict]:
    """Todas as dívidas ativas — com ou sem parcelas cadastradas.

    Junta os empréstimos criados com plano de parcelas e as dívidas registradas
    apenas pelo saldo devedor (cartão, financiamento, empréstimo já em curso).
    """
    emprestimos = {e["conta_id"]: e for e in db.query("SELECT * FROM emprestimo")}
    saida = []
    # Dívida quitada tem a conta desativada: ela só volta com incluir_quitadas.
    filtro_ativo = "" if incluir_quitadas else " AND ativo=1"
    for conta in db.query("SELECT * FROM conta WHERE tipo='PASSIVO' AND aceita_lancamento=1"
                          f"{filtro_ativo} ORDER BY codigo"):
        # A provisão de multa e juros é conta interna do sistema, não uma dívida
        # que o usuário contraiu — ela não entra na lista.
        if conta["codigo"] == CONTA_PROVISAO:
            continue
        saldo = saldo_conta(conta["id"])
        if abs(saldo) < CENTAVO and not incluir_quitadas:
            continue

        emprestimo = emprestimos.get(conta["id"])
        parcelas = pagas = 0
        valor_parcela = juros = 0.0
        proxima = None
        if emprestimo:
            linhas = db.query(
                "SELECT p.*, t.status, t.vencimento FROM emprestimo_parcela p"
                " LEFT JOIN titulo t ON t.id = p.titulo_id WHERE p.emprestimo_id = ?"
                " ORDER BY p.numero", (emprestimo["id"],))
            parcelas = len(linhas)
            pagas = sum(1 for linha in linhas if linha["status"] == "QUITADO")
            valor_parcela = float(emprestimo["valor_parcela"])
            juros = float(emprestimo["juros_mes_pct"])
            aberta = next((linha for linha in linhas if linha["status"] == "ABERTO"), None)
            proxima = aberta["vencimento"] if aberta else None
        else:
            # Sem plano de parcelas: procura títulos em aberto ligados à conta.
            aberto = db.query_one(
                "SELECT vencimento, valor FROM titulo WHERE conta_id=? AND status='ABERTO'"
                " ORDER BY vencimento LIMIT 1", (conta["id"],))
            if aberto:
                proxima = aberto["vencimento"]
                valor_parcela = float(aberto["valor"])

        # Só conta como pago o que saiu de uma conta de dinheiro. Correção do
        # valor da dívida e baixa sem pagamento também debitam a conta, mas não
        # são pagamento — antes entravam aqui e inflavam o "já pago".
        pago_total = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) t FROM partida p"
            " JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ? AND p.tipo = 'D'"
            " AND EXISTS (SELECT 1 FROM partida c JOIN conta a ON a.id = c.conta_id"
            "             WHERE c.lancamento_id = l.id AND c.tipo = 'C'"
            "               AND a.tipo = 'ATIVO' AND a.eh_carteira = 1)",
            (conta["id"],))["t"]
        tomado = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) t FROM partida p WHERE p.conta_id=? AND p.tipo='C'",
            (conta["id"],))["t"]

        saida.append({
            "conta_id": conta["id"],
            "codigo": conta["codigo"],
            "nome": conta["nome"],
            "credor": conta["instituicao"] or (emprestimo["credor"] if emprestimo else ""),
            "saldo": saldo,
            "tomado": round(float(tomado), 2),
            "pago": round(float(pago_total), 2),
            "emprestimo_id": emprestimo["id"] if emprestimo else None,
            "parcelas": parcelas,
            "pagas": pagas,
            "valor_parcela": valor_parcela,
            "juros_mes_pct": juros,
            "proxima": proxima,
            "eh_cartao": bool(conta["dia_fechamento"]),
        })
    return saida


def resumo_dividas() -> dict:
    itens = listar_dividas()
    return {
        "total": round(sum(i["saldo"] for i in itens), 2),
        "quantidade": len(itens),
        "parcela_mensal": round(sum(i["valor_parcela"] for i in itens
                                    if i["parcelas"] and i["pagas"] < i["parcelas"]), 2),
    }


def criar_divida(nome: str, credor: str, saldo_devedor: float, data_iso: str | None = None,
                 observacao: str = "") -> int:
    """Registra uma dívida que já existe, pelo saldo devedor atual.

    Não cria dinheiro em conta nenhuma: a contrapartida é o patrimônio, do mesmo
    jeito que o saldo inicial de uma conta.
    """
    nome = nome.strip()
    if not nome:
        raise RegraNegocioError("Dê um nome para a dívida (ex.: Financiamento do carro).")
    if saldo_devedor <= 0:
        raise RegraNegocioError("Informe quanto você ainda deve.")

    codigo = _proximo_codigo_livre("2.1")
    pai = db.query_one("SELECT id FROM conta WHERE codigo = '2.1'")
    conta_id = db.execute(
        "INSERT INTO conta (codigo, nome, tipo, natureza, pai_id, aceita_lancamento, ativo,"
        " observacao, eh_carteira, instituicao) VALUES (?,?,'PASSIVO','C',?,1,1,?,0,?)",
        (codigo, nome, pai["id"] if pai else None,
         observacao or "Dívida registrada pelo saldo devedor", credor.strip()))
    salvar_lancamento(
        None, data_iso or hoje_iso(), f"Saldo devedor — {nome}",
        [Partida(conta_patrimonio_inicial(), "D", saldo_devedor),
         Partida(conta_id, "C", saldo_devedor)], documento="SALDO-INICIAL")
    return conta_id


def pagar_divida(conta_divida_id: int, valor: float, conta_dinheiro_id: int,
                 data_iso: str | None = None, juros: float = 0.0,
                 descricao: str = "") -> int:
    """Abate a dívida. A parte de juros, se houver, vira despesa financeira."""
    divida = obter_conta(conta_divida_id)
    if divida is None or divida["tipo"] != "PASSIVO":
        raise RegraNegocioError("Escolha uma dívida válida.")
    if valor <= 0:
        raise RegraNegocioError("O valor pago deve ser maior que zero.")
    if juros < 0 or juros > valor:
        raise RegraNegocioError("Os juros não podem ser maiores que o valor pago.")

    # Pagar mais do que se deve deixaria a dívida negativa — o que sobra não é
    # dívida, é crédito com o credor, e isso se resolve fora daqui.
    saldo = saldo_conta(conta_divida_id, ate=data_iso or hoje_iso())
    if round(valor - juros, 2) > round(saldo, 2) + CENTAVO:
        raise RegraNegocioError(
            f"Você deve {moeda(saldo)} nesta dívida e está pagando"
            f" {moeda(round(valor - juros, 2))} de abatimento."
            " Ajuste o valor ou use 'Quitar dívida' para encerrar de uma vez.")

    amortizacao = round(valor - juros, 2)
    partidas = []
    if amortizacao > CENTAVO:
        partidas.append(Partida(conta_divida_id, "D", amortizacao))
    if juros > CENTAVO:
        partidas.append(Partida(_conta_por_codigo(CONTA_ENCARGOS), "D", round(juros, 2)))
    partidas.append(Partida(conta_dinheiro_id, "C", round(valor, 2)))
    texto = descricao.strip() or f"Pagamento — {divida['nome']}"
    return salvar_lancamento(None, data_iso or hoje_iso(), texto, partidas)


def extrato_da_divida(conta_divida_id: int) -> list[dict]:
    """Tudo o que mexeu nesta dívida, com o saldo depois de cada movimento.

    Separa o que é pagamento (saiu dinheiro de uma conta sua) do que é só
    correção de valor — os dois diminuem a dívida, mas significam coisas
    diferentes.
    """
    linhas = db.query(
        "SELECT p.id, p.tipo, p.valor, l.id AS lancamento_id, l.data, l.historico,"
        " l.documento,"
        " (SELECT c2.nome FROM partida p2 JOIN conta c2 ON c2.id = p2.conta_id"
        "   WHERE p2.lancamento_id = l.id AND p2.tipo = 'C' AND c2.tipo = 'ATIVO'"
        "     AND c2.eh_carteira = 1 LIMIT 1) AS conta_dinheiro"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " WHERE p.conta_id = ? ORDER BY l.data, l.id, p.id", (conta_divida_id,))

    saida, saldo = [], 0.0
    for linha in linhas:
        valor = round(float(linha["valor"]), 2)
        if linha["tipo"] == "C":                      # dívida aumentou
            saldo = round(saldo + valor, 2)
            tipo = ("Dívida registrada" if linha["documento"] == "SALDO-INICIAL"
                    else "Aumentou o valor")
        else:                                         # dívida diminuiu
            saldo = round(saldo - valor, 2)
            tipo = "Pagamento" if linha["conta_dinheiro"] else "Correção do valor"
        saida.append({
            "lancamento_id": linha["lancamento_id"],
            "data": linha["data"],
            "historico": linha["historico"],
            "tipo": tipo,
            "valor": valor,
            "aumentou": linha["tipo"] == "C",
            "conta_dinheiro": linha["conta_dinheiro"] or "",
            "saldo_depois": saldo,
        })
    saida.reverse()          # mais recente primeiro
    return saida


def alterar_valor_divida(conta_divida_id: int, saldo_real: float,
                         data_iso: str | None = None) -> int | None:
    """Corrige quanto você deve — isto não é pagamento.

    Serve quando o credor informa outro saldo (juros, correção, renegociação).
    Zerar a dívida por aqui não é aceito: dívida que acabou se encerra em
    :func:`quitar_divida`, que registra como ela terminou.
    """
    divida = obter_conta(conta_divida_id)
    if divida is None or divida["tipo"] != "PASSIVO":
        raise RegraNegocioError("Escolha uma dívida válida.")
    if saldo_real < 0:
        raise RegraNegocioError("O valor da dívida não pode ser negativo.")
    if saldo_real < CENTAVO:
        raise RegraNegocioError(
            "Para encerrar a dívida use 'Quitar dívida' — assim ela entra no histórico"
            " como paga. Alterar o valor serve só para corrigir quanto você deve.")
    return ajustar_saldo(conta_divida_id, saldo_real, data_iso,
                         motivo=f"Correção do valor da dívida — {divida['nome']}")


# Mantido para não quebrar chamadas antigas; o nome novo diz melhor o que faz.
ajustar_saldo_divida = alterar_valor_divida


FORMAS_QUITACAO = {
    "PAGAMENTO": "Paguei o que faltava",
    "PERDAO": "Perdoada / baixada sem pagar",
}


def quitar_divida(conta_divida_id: int, forma: str = "PAGAMENTO",
                  conta_dinheiro_id: int | None = None, data_iso: str | None = None,
                  juros: float = 0.0, observacao: str = "") -> dict:
    """Encerra a dívida: zera o saldo e guarda a linha no histórico.

    Com ``forma`` PAGAMENTO o que faltava sai da conta escolhida, como um
    pagamento comum. Com PERDAO nada sai do bolso — a dívida foi perdoada ou
    baixada — e o valor vira ganho, não pagamento.
    """
    if forma not in FORMAS_QUITACAO:
        raise RegraNegocioError("Escolha como a dívida foi encerrada.")
    divida = obter_conta(conta_divida_id)
    if divida is None or divida["tipo"] != "PASSIVO":
        raise RegraNegocioError("Escolha uma dívida válida.")

    data_iso = data_iso or hoje_iso()
    saldo = saldo_conta(conta_divida_id, ate=data_iso)
    if saldo < CENTAVO:
        raise RegraNegocioError("Esta dívida já está zerada.")

    if forma == "PAGAMENTO":
        if conta_dinheiro_id is None:
            raise RegraNegocioError("Escolha de qual conta saiu o dinheiro.")
        lancamento_id = pagar_divida(conta_divida_id, saldo, conta_dinheiro_id, data_iso,
                                     juros=juros,
                                     descricao=f"Quitação — {divida['nome']}")
    else:
        conta_dinheiro_id = None
        lancamento_id = ajustar_saldo(conta_divida_id, 0.0, data_iso,
                                      motivo=f"Dívida baixada sem pagamento — {divida['nome']}")

    quitacao_id = db.execute(
        "INSERT INTO divida_quitacao (conta_id, nome, credor, data, valor, forma,"
        " conta_dinheiro_id, lancamento_id, observacao, criado_em)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (conta_divida_id, divida["nome"], divida["instituicao"] or "", data_iso,
         round(saldo, 2), forma, conta_dinheiro_id, lancamento_id, observacao.strip(),
         datetime.now().isoformat(timespec="seconds")))
    # Zerada e fora da lista de dívidas ativas; o histórico guarda a memória.
    db.execute("UPDATE conta SET ativo = 0 WHERE id = ?", (conta_divida_id,))
    return {"id": quitacao_id, "valor": round(saldo, 2), "forma": forma,
            "lancamento_id": lancamento_id}


def listar_dividas_quitadas(texto: str = "") -> list[dict]:
    """Histórico das dívidas já encerradas, da mais recente para a mais antiga."""
    filtros, params = ["1=1"], []
    if texto.strip():
        filtros.append("(sem_acento(q.nome) LIKE sem_acento(?)"
                       " OR sem_acento(q.credor) LIKE sem_acento(?))")
        params += [f"%{texto.strip()}%", f"%{texto.strip()}%"]
    linhas = db.query(
        "SELECT q.*, c.nome AS conta_dinheiro_nome FROM divida_quitacao q"
        " LEFT JOIN conta c ON c.id = q.conta_dinheiro_id"
        f" WHERE {' AND '.join(filtros)} ORDER BY q.data DESC, q.id DESC", tuple(params))
    return [{**dict(linha), "forma_texto": FORMAS_QUITACAO.get(linha["forma"], linha["forma"])}
            for linha in linhas]


def desfazer_quitacao(quitacao_id: int) -> None:
    """Volta atrás: a dívida reabre com o valor que tinha e sai do histórico."""
    quitacao = db.query_one("SELECT * FROM divida_quitacao WHERE id = ?", (quitacao_id,))
    if quitacao is None:
        raise RegraNegocioError("Quitação não encontrada.")
    with db.transaction() as conn:
        if quitacao["lancamento_id"]:
            conn.execute("DELETE FROM lancamento WHERE id = ?", (quitacao["lancamento_id"],))
        conn.execute("UPDATE conta SET ativo = 1 WHERE id = ?", (quitacao["conta_id"],))
        conn.execute("DELETE FROM divida_quitacao WHERE id = ?", (quitacao_id,))


def listar_emprestimos() -> list[dict]:
    saida = []
    for emp in db.query("SELECT * FROM emprestimo ORDER BY criado_em DESC"):
        parcelas = db.query(
            "SELECT p.*, t.status FROM emprestimo_parcela p"
            " LEFT JOIN titulo t ON t.id = p.titulo_id"
            " WHERE p.emprestimo_id = ? ORDER BY p.numero", (emp["id"],))
        pagas = [p for p in parcelas if p["status"] == "QUITADO"]
        proxima = next((p for p in parcelas if p["status"] == "ABERTO"), None)
        saida.append({
            "id": emp["id"],
            "descricao": emp["descricao"],
            "credor": emp["credor"],
            "valor_contratado": float(emp["valor_contratado"]),
            "juros_mes_pct": float(emp["juros_mes_pct"]),
            "parcelas": int(emp["parcelas"]),
            "valor_parcela": float(emp["valor_parcela"]),
            "pagas": len(pagas),
            "saldo_devedor": saldo_conta(emp["conta_id"]),
            "total_a_pagar": round(sum(float(p["total"]) for p in parcelas), 2),
            "juros_totais": round(sum(float(p["juros"]) for p in parcelas), 2),
            "proxima": dict(proxima) if proxima else None,
            "conta_id": emp["conta_id"],
        })
    return saida


def parcelas_do_emprestimo(emprestimo_id: int) -> list[db.sqlite3.Row]:
    return db.query(
        "SELECT p.*, t.status, t.liquidado_em, t.valor_liquidado FROM emprestimo_parcela p"
        " LEFT JOIN titulo t ON t.id = p.titulo_id"
        " WHERE p.emprestimo_id = ? ORDER BY p.numero", (emprestimo_id,))


def excluir_conta_com_lancamentos(conta_id: int) -> None:
    """Remove uma conta de dívida e tudo que foi lançado nela.

    Só permitido quando os lançamentos são exclusivos dessa conta — ou seja,
    quando apagá-los não desfaz movimento de dinheiro em outra conta real.
    """
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Conta não encontrada.")
    if conta["tipo"] != "PASSIVO":
        raise RegraNegocioError("Só dívidas podem ser removidas por aqui.")

    lancamentos = db.query(
        "SELECT DISTINCT l.id FROM lancamento l JOIN partida p ON p.lancamento_id = l.id"
        " WHERE p.conta_id = ?", (conta_id,))
    for lanc in lancamentos:
        toca_carteira = db.query_one(
            "SELECT 1 FROM partida p JOIN conta c ON c.id = p.conta_id"
            " WHERE p.lancamento_id = ? AND c.eh_carteira = 1 AND c.tipo = 'ATIVO'",
            (lanc["id"],))
        if toca_carteira:
            raise RegraNegocioError(
                "Esta dívida tem lançamentos ligados a contas de dinheiro.\n"
                "Apague ou corrija esses lançamentos antes, em Entradas e Saídas.")

    if db.query_one("SELECT 1 FROM titulo WHERE conta_id = ?", (conta_id,)):
        raise RegraNegocioError("Existem contas a pagar ligadas a esta dívida.")

    with db.transaction() as conn:
        for lanc in lancamentos:
            conn.execute("DELETE FROM partida WHERE lancamento_id = ?", (lanc["id"],))
            conn.execute("DELETE FROM lancamento WHERE id = ?", (lanc["id"],))
        conn.execute("DELETE FROM conta WHERE id = ?", (conta_id,))


def excluir_emprestimo(emprestimo_id: int) -> None:
    """Só permite apagar enquanto nenhuma parcela tiver sido paga."""
    pagas = db.query_one(
        "SELECT COUNT(*) AS c FROM emprestimo_parcela p JOIN titulo t ON t.id = p.titulo_id"
        " WHERE p.emprestimo_id = ? AND t.status = 'QUITADO'", (emprestimo_id,))
    if pagas and pagas["c"]:
        raise RegraNegocioError(
            "Este empréstimo já tem parcelas pagas e não pode ser apagado.\n"
            "Desfaça os pagamentos antes, na tela Contas a Pagar.")
    emp = db.query_one("SELECT * FROM emprestimo WHERE id = ?", (emprestimo_id,))
    if emp is None:
        return
    with db.transaction() as conn:
        conn.execute(
            "DELETE FROM titulo WHERE id IN (SELECT titulo_id FROM emprestimo_parcela"
            " WHERE emprestimo_id = ? AND titulo_id IS NOT NULL)", (emprestimo_id,))
        conn.execute("DELETE FROM emprestimo WHERE id = ?", (emprestimo_id,))
    if abs(saldo_conta(emp["conta_id"])) < CENTAVO and not _tem_partidas(emp["conta_id"]):
        db.execute("DELETE FROM conta WHERE id = ?", (emp["conta_id"],))


# --------------------------------------------------------------------------- #
# Investimentos
# --------------------------------------------------------------------------- #
CONTA_RENDIMENTO = "4.2.01"      # Rendimentos de Investimentos


def eh_investimento(conta: db.sqlite3.Row) -> bool:
    return (conta["tipo"] == "ATIVO"
            and (conta["codigo"] == "1.1.05"
                 or "investimento" in (conta["observacao"] or "").lower()))


def listar_investimentos() -> list[dict]:
    """Cada aplicação com aportes, resgates, rendimento e rentabilidade."""
    conta_rendimento = db.query_one("SELECT id FROM conta WHERE codigo = ?",
                                    (CONTA_RENDIMENTO,))
    saida = []
    for conta in db.query("SELECT * FROM conta WHERE tipo='ATIVO' AND aceita_lancamento=1"
                          " AND ativo=1 ORDER BY codigo"):
        if not eh_investimento(conta):
            continue

        rendimento = 0.0
        if conta_rendimento:
            row = db.query_one(
                "SELECT COALESCE(SUM(p.valor),0) t FROM partida p"
                " WHERE p.conta_id = ? AND p.tipo='D' AND EXISTS ("
                "   SELECT 1 FROM partida r WHERE r.lancamento_id = p.lancamento_id"
                "   AND r.conta_id = ? AND r.tipo='C')", (conta["id"], conta_rendimento["id"]))
            rendimento = round(float(row["t"]), 2)

        entradas = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) t FROM partida p WHERE p.conta_id=? AND p.tipo='D'",
            (conta["id"],))["t"]
        saidas = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) t FROM partida p WHERE p.conta_id=? AND p.tipo='C'",
            (conta["id"],))["t"]
        aportes = round(float(entradas) - rendimento, 2)
        resgates = round(float(saidas), 2)
        saldo = saldo_conta(conta["id"])
        aplicado = round(aportes - resgates, 2)
        ultimo = db.query_one(
            "SELECT MAX(l.data) d FROM partida p JOIN lancamento l ON l.id=p.lancamento_id"
            " WHERE p.conta_id=?", (conta["id"],))
        # A conta genérica do plano (1.1.05) só aparece se realmente for usada.
        if abs(saldo) < CENTAVO and ultimo["d"] is None:
            continue

        saida.append({
            "id": conta["id"],
            "codigo": conta["codigo"],
            "nome": conta["nome"],
            "instituicao": conta["instituicao"],
            "aportes": aportes,
            "resgates": resgates,
            "aplicado": aplicado,
            "rendimento": rendimento,
            "saldo": saldo,
            "rentabilidade": round(rendimento / aportes * 100, 2) if aportes > CENTAVO else 0.0,
            "ultimo_movimento": ultimo["d"] if ultimo else None,
        })
    return saida


def resumo_investimentos() -> dict:
    itens = listar_investimentos()
    total = round(sum(i["saldo"] for i in itens), 2)
    rendimento = round(sum(i["rendimento"] for i in itens), 2)
    aportes = round(sum(i["aportes"] for i in itens), 2)
    return {
        "total": total,
        "rendimento": rendimento,
        "aportes": aportes,
        "resgates": round(sum(i["resgates"] for i in itens), 2),
        "rentabilidade": round(rendimento / aportes * 100, 2) if aportes > CENTAVO else 0.0,
        "quantidade": len(itens),
    }


def registrar_rendimento(conta_id: int, valor: float, data_iso: str | None = None,
                         descricao: str = "") -> int:
    """Lança o rendimento do período: aumenta a aplicação e entra como receita."""
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Aplicação não encontrada.")
    if abs(valor) < CENTAVO:
        raise RegraNegocioError("Informe o valor do rendimento.")
    rendimento = db.query_one("SELECT id FROM conta WHERE codigo = ?", (CONTA_RENDIMENTO,))
    if rendimento is None:
        raise RegraNegocioError(f"A conta {CONTA_RENDIMENTO} não existe no plano de contas.")

    texto = descricao.strip() or f"Rendimento — {conta['nome']}"
    if valor > 0:
        partidas = [Partida(conta_id, "D", valor), Partida(rendimento["id"], "C", valor)]
    else:  # prejuízo: devolve parte do rendimento
        partidas = [Partida(rendimento["id"], "D", abs(valor)),
                    Partida(conta_id, "C", abs(valor))]
    return salvar_lancamento(None, data_iso or hoje_iso(), texto, partidas)


def marcar_como_investimento(conta_id: int, sim: bool = True) -> None:
    conta = obter_conta(conta_id)
    if conta is None:
        raise RegraNegocioError("Conta não encontrada.")
    if conta["tipo"] != "ATIVO":
        raise RegraNegocioError("Só contas de dinheiro podem ser marcadas como aplicação.")
    observacao = "Investimento" if sim else ""
    db.execute("UPDATE conta SET observacao=?, eh_carteira=1 WHERE id=?", (observacao, conta_id))


def evolucao_investimentos(meses: int = 12) -> list[dict]:
    """Saldo total aplicado no fim de cada mês."""
    historico = meses_do_historico(meses)
    contas = [i["id"] for i in listar_investimentos()]
    saida = []
    for competencia in historico:
        fim = _fim_do_mes(competencia)
        total = round(sum(saldo_conta(cid, ate=fim) for cid in contas), 2)
        saida.append({"mes": competencia, "nome": mes_nome(competencia), "saldo": total})
    return saida


# --------------------------------------------------------------------------- #
# Centros de custo
# --------------------------------------------------------------------------- #
def listar_centros(apenas_ativos: bool = False) -> list[db.sqlite3.Row]:
    where = "WHERE ativo = 1" if apenas_ativos else ""
    return db.query(f"SELECT * FROM centro_custo {where} ORDER BY nome")


def salvar_centro(centro_id: int | None, nome: str, ativo: bool = True) -> int:
    nome = nome.strip()
    if not nome:
        raise RegraNegocioError("Informe o nome do centro de custo.")
    if db.query_one("SELECT 1 FROM centro_custo WHERE nome = ? AND id IS NOT ?", (nome, centro_id)):
        raise RegraNegocioError(f"O centro de custo {nome!r} já existe.")
    if centro_id:
        db.execute("UPDATE centro_custo SET nome=?, ativo=? WHERE id=?", (nome, int(ativo), centro_id))
        return centro_id
    return db.execute("INSERT INTO centro_custo (nome, ativo) VALUES (?,?)", (nome, int(ativo)))


def excluir_centro(centro_id: int) -> None:
    if db.query_one("SELECT 1 FROM lancamento WHERE centro_custo_id = ?", (centro_id,)):
        raise RegraNegocioError("Centro de custo em uso por lançamentos. Inative-o.")
    db.execute("DELETE FROM centro_custo WHERE id = ?", (centro_id,))


# --------------------------------------------------------------------------- #
# Lançamentos (partidas dobradas)
# --------------------------------------------------------------------------- #
@dataclass
class Partida:
    conta_id: int
    tipo: str  # 'D' ou 'C'
    valor: float


def validar_partidas(partidas: list[Partida]) -> float:
    if len(partidas) < 2:
        raise RegraNegocioError("Um lançamento exige ao menos um débito e um crédito.")
    debitos = round(sum(p.valor for p in partidas if p.tipo == "D"), 2)
    creditos = round(sum(p.valor for p in partidas if p.tipo == "C"), 2)
    if debitos <= 0 or creditos <= 0:
        raise RegraNegocioError("Informe pelo menos um débito e um crédito.")
    if abs(debitos - creditos) > CENTAVO:
        raise RegraNegocioError(
            f"Partidas desbalanceadas: débitos {moeda(debitos)} × créditos {moeda(creditos)}."
        )
    for p in partidas:
        conta = obter_conta(p.conta_id)
        if conta is None:
            raise RegraNegocioError("Conta inexistente em uma das partidas.")
        if not conta["aceita_lancamento"]:
            raise RegraNegocioError(f"A conta {conta['codigo']} é sintética e não aceita lançamentos.")
        if not conta["ativo"]:
            raise RegraNegocioError(f"A conta {conta['codigo']} está inativa.")
        if p.valor <= 0:
            raise RegraNegocioError("Valores das partidas devem ser positivos.")
    return debitos


def salvar_lancamento(
    lancamento_id: int | None,
    data_iso: str,
    historico: str,
    partidas: list[Partida],
    documento: str = "",
    centro_custo_id: int | None = None,
    origem: str = "MANUAL",
    atualizar_faturas: bool = True,
) -> int:
    historico = historico.strip()
    if not historico:
        raise RegraNegocioError("Escreva uma descrição para este registro.")
    total = validar_partidas(partidas)
    if lancamento_id:
        _garantir_edicao_permitida(lancamento_id, "alterado")

    with db.transaction() as conn:
        if lancamento_id:
            conn.execute(
                "UPDATE lancamento SET data=?, historico=?, documento=?, centro_custo_id=?, valor=?"
                " WHERE id=?",
                (data_iso, historico, documento, centro_custo_id, total, lancamento_id),
            )
            conn.execute("DELETE FROM partida WHERE lancamento_id = ?", (lancamento_id,))
        else:
            # Com a conferência automática ligada, o registro já nasce conferido:
            # o usuário não precisa marcar um a um.
            conferido = 1 if (conferencia_automatica() and data_iso <= hoje_iso()) else 0
            cur = conn.execute(
                "INSERT INTO lancamento (data, historico, documento, centro_custo_id, valor,"
                " criado_em, origem, conferido) VALUES (?,?,?,?,?,?,?,?)",
                (data_iso, historico, documento, centro_custo_id, total,
                 datetime.now().isoformat(timespec="seconds"), origem, conferido),
            )
            lancamento_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT INTO partida (lancamento_id, conta_id, tipo, valor) VALUES (?,?,?,?)",
            [(lancamento_id, p.conta_id, p.tipo, p.valor) for p in partidas],
        )
    if atualizar_faturas:
        _atualizar_faturas_se_cartao(p.conta_id for p in partidas)
    return lancamento_id


_faturas_em_sincronia = False


def _atualizar_faturas_se_cartao(conta_ids) -> None:
    """Movimento em cartão com ciclo de fatura: a fatura se atualiza na hora.

    Protegido contra reentrada — o próprio fechamento lança os juros do
    rotativo, e isso não pode disparar outro fechamento no meio.
    """
    if _faturas_em_sincronia:
        return
    ids = tuple(set(conta_ids))
    if not ids:
        return
    marcadores = ",".join("?" * len(ids))
    if db.query_one(f"SELECT 1 FROM conta WHERE id IN ({marcadores}) AND tipo = 'PASSIVO'"
                    " AND dia_fechamento IS NOT NULL LIMIT 1", ids):
        fechar_faturas()


def _garantir_edicao_permitida(lancamento_id: int, acao: str) -> None:
    """Um registro só pode ser mexido na tela em que foi criado."""
    lanc = db.query_one("SELECT origem FROM lancamento WHERE id = ?", (lancamento_id,))
    if lanc is None:
        raise RegraNegocioError("Registro não encontrado.")
    if lanc["origem"] != "MANUAL":
        raise RegraNegocioError(
            f"Este registro nasceu do pagamento de uma conta e não pode ser {acao} aqui.\n\n"
            "Vá até a tela 'Contas a Pagar e Receber', selecione a conta correspondente e"
            " clique em 'Desfazer pagamento'."
        )
    if db.query_one("SELECT id FROM titulo WHERE lancamento_id = ?", (lancamento_id,)):
        raise RegraNegocioError(
            f"Este registro está ligado a uma conta a pagar/receber e não pode ser {acao} aqui."
        )


def excluir_lancamento(lancamento_id: int) -> None:
    _garantir_edicao_permitida(lancamento_id, "apagado")
    contas = [p["conta_id"] for p in db.query(
        "SELECT conta_id FROM partida WHERE lancamento_id = ?", (lancamento_id,))]
    db.execute("DELETE FROM lancamento WHERE id = ?", (lancamento_id,))
    _atualizar_faturas_se_cartao(contas)


def listar_lancamentos(
    desde: str | None = None,
    ate: str | None = None,
    texto: str = "",
    conta_id: int | None = None,
    centro_custo_id: int | None = None,
    limite: int = 1000,
) -> list[db.sqlite3.Row]:
    filtros, params = ["1=1"], []
    if desde:
        filtros.append("l.data >= ?")
        params.append(desde)
    if ate:
        filtros.append("l.data <= ?")
        params.append(ate)
    if texto:
        filtros.append("(l.historico LIKE ? OR l.documento LIKE ?)")
        params += [f"%{texto}%", f"%{texto}%"]
    if centro_custo_id:
        filtros.append("l.centro_custo_id = ?")
        params.append(centro_custo_id)
    if conta_id:
        filtros.append("EXISTS (SELECT 1 FROM partida p WHERE p.lancamento_id = l.id AND p.conta_id = ?)")
        params.append(conta_id)
    params.append(limite)
    return db.query(
        "SELECT l.*, cc.nome AS centro_custo,"
        " (SELECT GROUP_CONCAT(c.codigo || ' ' || c.nome, ' | ') FROM partida p"
        "   JOIN conta c ON c.id = p.conta_id WHERE p.lancamento_id = l.id AND p.tipo='D') AS debitos,"
        " (SELECT GROUP_CONCAT(c.codigo || ' ' || c.nome, ' | ') FROM partida p"
        "   JOIN conta c ON c.id = p.conta_id WHERE p.lancamento_id = l.id AND p.tipo='C') AS creditos"
        " FROM lancamento l LEFT JOIN centro_custo cc ON cc.id = l.centro_custo_id"
        f" WHERE {' AND '.join(filtros)} ORDER BY l.data DESC, l.id DESC LIMIT ?",
        tuple(params),
    )


def classificar_lancamento(partidas: list[db.sqlite3.Row]) -> dict:
    """Traduz as partidas contábeis para a linguagem do dia a dia.

    Devolve ``tipo`` (ENTRADA, SAIDA, TRANSFERENCIA ou AJUSTE), a categoria
    envolvida e a conta de dinheiro movimentada.
    """
    tipos = {p["tipo_conta"] for p in partidas}
    debitos = [p for p in partidas if p["tipo"] == "D"]
    creditos = [p for p in partidas if p["tipo"] == "C"]

    def nomes(itens, tipos_desejados=None) -> str:
        alvo = [i for i in itens if tipos_desejados is None or i["tipo_conta"] in tipos_desejados]
        return ", ".join(i["nome"] for i in alvo)

    if "RECEITA" in tipos:
        return {"tipo": "ENTRADA", "rotulo": "Entrada",
                "categoria": nomes(creditos, {"RECEITA"}),
                "conta": nomes(debitos, {"ATIVO", "PASSIVO"})}
    if "DESPESA" in tipos:
        return {"tipo": "SAIDA", "rotulo": "Saída",
                "categoria": nomes(debitos, {"DESPESA"}),
                "conta": nomes(creditos, {"ATIVO", "PASSIVO"})}
    if "PATRIMONIO" in tipos:
        return {"tipo": "AJUSTE", "rotulo": "Saldo inicial",
                "categoria": "Ajuste de saldo",
                "conta": nomes(debitos + creditos, {"ATIVO", "PASSIVO"})}
    return {"tipo": "TRANSFERENCIA", "rotulo": "Transferência",
            "categoria": "Entre suas contas",
            "conta": f"{nomes(creditos)} → {nomes(debitos)}"}


def listar_movimentos(
    desde: str | None = None,
    ate: str | None = None,
    texto: str = "",
    conta_id: int | None = None,
    apenas_tipo: str | None = None,
    limite: int = 1000,
    apenas_pendentes: bool = False,
) -> list[dict]:
    """Lançamentos já traduzidos para exibição em linguagem simples."""
    saida: list[dict] = []
    for lanc in listar_lancamentos(desde, ate, texto, conta_id, limite=limite):
        if apenas_pendentes and lanc["conferido"]:
            continue
        partidas = db.query(
            "SELECT p.tipo, p.valor, c.nome, c.codigo, c.tipo AS tipo_conta"
            " FROM partida p JOIN conta c ON c.id = p.conta_id WHERE p.lancamento_id = ?",
            (lanc["id"],),
        )
        info = classificar_lancamento(partidas)
        if apenas_tipo and info["tipo"] != apenas_tipo:
            continue
        saida.append({
            "id": lanc["id"],
            "data": lanc["data"],
            "descricao": lanc["historico"],
            "documento": lanc["documento"],
            "centro_custo": lanc["centro_custo"] or "",
            "valor": float(lanc["valor"]),
            "editavel": lanc["origem"] == "MANUAL",
            "origem": lanc["origem"],
            "conferido": bool(lanc["conferido"]),
            **info,
        })
    return saida


# --------------------------------------------------------------------------- #
# Conferência (conciliação com o extrato do banco)
# --------------------------------------------------------------------------- #
def marcar_conferido(lancamento_id: int, conferido: bool = True) -> None:
    """Marca (ou desmarca) um movimento como já conferido no extrato do banco."""
    if db.query_one("SELECT 1 FROM lancamento WHERE id = ?", (lancamento_id,)) is None:
        raise RegraNegocioError("Movimento não encontrado.")
    db.execute("UPDATE lancamento SET conferido = ? WHERE id = ?",
               (1 if conferido else 0, lancamento_id))


def conferencia_automatica() -> bool:
    """Conferir sozinho é o padrão: só fica desligado se o usuário desmarcar."""
    return db.get_config("conferencia_automatica", "1") == "1"


def conferir_automatico(ate: str | None = None) -> int:
    """Confere sozinho tudo o que já aconteceu, sem o usuário marcar nada.

    Roda ao abrir o programa e ao entrar na tela de Entradas e Saídas. Registros
    com data no futuro ficam de fora — eles são conferidos quando o dia chegar.
    """
    if not conferencia_automatica():
        return 0
    ate = ate or hoje_iso()
    with db.transaction() as conn:
        cursor = conn.execute(
            "UPDATE lancamento SET conferido = 1 WHERE conferido = 0 AND data <= ?", (ate,))
    return cursor.rowcount


def conferir_periodo(desde: str, ate: str, conta_id: int | None = None) -> int:
    """Marca de uma vez tudo o que está no período (e na conta, se informada)."""
    clausulas = ["l.data BETWEEN ? AND ?", "l.conferido = 0"]
    params: list = [desde, ate]
    if conta_id:
        clausulas.append("EXISTS (SELECT 1 FROM partida p WHERE p.lancamento_id = l.id"
                         " AND p.conta_id = ?)")
        params.append(conta_id)
    with db.transaction() as conn:
        cursor = conn.execute(
            f"UPDATE lancamento SET conferido = 1 WHERE id IN ("
            f"  SELECT l.id FROM lancamento l WHERE {' AND '.join(clausulas)})", tuple(params))
    return cursor.rowcount


def resumo_conferencia(desde: str, ate: str, conta_id: int | None = None) -> dict:
    """Quanto do período já foi conferido — e quanto ainda falta."""
    clausulas = ["l.data BETWEEN ? AND ?"]
    params: list = [desde, ate]
    if conta_id:
        clausulas.append("EXISTS (SELECT 1 FROM partida p WHERE p.lancamento_id = l.id"
                         " AND p.conta_id = ?)")
        params.append(conta_id)
    row = db.query_one(
        f"SELECT COUNT(*) AS total,"
        f" COALESCE(SUM(CASE WHEN l.conferido = 1 THEN 1 ELSE 0 END), 0) AS conferidos,"
        f" COALESCE(SUM(CASE WHEN l.conferido = 0 THEN l.valor ELSE 0 END), 0) AS valor_pendente"
        f" FROM lancamento l WHERE {' AND '.join(clausulas)}", tuple(params))
    total = int(row["total"])
    conferidos = int(row["conferidos"])
    return {
        "total": total,
        "conferidos": conferidos,
        "pendentes": total - conferidos,
        "valor_pendente": round(float(row["valor_pendente"]), 2),
        "percentual": round(conferidos / total * 100, 1) if total else 100.0,
    }


def partidas_do_lancamento(lancamento_id: int) -> list[db.sqlite3.Row]:
    return db.query(
        "SELECT p.*, c.codigo, c.nome FROM partida p JOIN conta c ON c.id = p.conta_id"
        " WHERE p.lancamento_id = ? ORDER BY p.tipo DESC, p.id",
        (lancamento_id,),
    )


# --------------------------------------------------------------------------- #
# Títulos a pagar / receber
# --------------------------------------------------------------------------- #
ORIGENS_TITULO = ("AVULSA", "FIXA", "EMPRESTIMO", "FATURA")


def listar_titulos(
    tipo: str | None = None,
    status: str | None = None,
    desde: str | None = None,
    ate: str | None = None,
    texto: str = "",
    conta_id: int | None = None,
    centro_custo_id: int | None = None,
    origem: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    apenas_vencidas: bool = False,
    criterio: str = "vencimento",
    trazer_atrasadas: bool = False,
) -> list[db.sqlite3.Row]:
    """Lista os títulos. ``criterio`` escolhe se o período filtra pela data de
    vencimento ou pelo mês a que a conta se refere (competência).

    Com ``trazer_atrasadas``, as contas de antes do período que continuam sem
    pagamento (já vencidas) entram junto: a pendência não some ao virar o mês.
    """
    filtros, params = ["1=1"], []
    if tipo:
        filtros.append("t.tipo = ?")
        params.append(tipo)
    if status:
        filtros.append("t.status = ?")
        params.append(status)

    por_competencia = criterio == "competencia"
    periodo, params_periodo = [], []
    if desde:
        periodo.append("IFNULL(NULLIF(t.competencia,''), substr(t.vencimento,1,7)) >= ?"
                       if por_competencia else "t.vencimento >= ?")
        params_periodo.append(desde[:7] if por_competencia else desde)
    if ate:
        periodo.append("IFNULL(NULLIF(t.competencia,''), substr(t.vencimento,1,7)) <= ?"
                       if por_competencia else "t.vencimento <= ?")
        params_periodo.append(ate[:7] if por_competencia else ate)
    if periodo:
        clausula = " AND ".join(periodo)
        if trazer_atrasadas and desde:
            clausula = (f"(({clausula}) OR (t.status = 'ABERTO' AND t.vencimento < ?"
                        " AND t.vencimento < ?))")
            params_periodo += [desde, hoje_iso()]
        filtros.append(clausula)
        params += params_periodo
    if texto:
        filtros.append("(sem_acento(t.descricao) LIKE sem_acento(?)"
                       " OR sem_acento(t.pessoa) LIKE sem_acento(?))")
        params += [f"%{texto}%", f"%{texto}%"]
    if conta_id:
        filtros.append("t.conta_id = ?")
        params.append(conta_id)
    if centro_custo_id:
        filtros.append("t.centro_custo_id = ?")
        params.append(centro_custo_id)
    if valor_min is not None:
        filtros.append("t.valor >= ?")
        params.append(valor_min)
    if valor_max is not None:
        filtros.append("t.valor <= ?")
        params.append(valor_max)
    if apenas_vencidas:
        filtros.append("t.status = 'ABERTO' AND t.vencimento < ?")
        params.append(hoje_iso())

    if origem == "FIXA":
        filtros.append("t.recorrencia_id IS NOT NULL")
    elif origem == "EMPRESTIMO":
        filtros.append("EXISTS (SELECT 1 FROM emprestimo_parcela ep WHERE ep.titulo_id = t.id)")
    elif origem == "FATURA":
        filtros.append("EXISTS (SELECT 1 FROM fatura f WHERE f.titulo_id = t.id)")
    elif origem == "AVULSA":
        filtros.append("t.recorrencia_id IS NULL"
                       " AND NOT EXISTS (SELECT 1 FROM emprestimo_parcela ep"
                       "                 WHERE ep.titulo_id = t.id)"
                       " AND NOT EXISTS (SELECT 1 FROM fatura f WHERE f.titulo_id = t.id)")

    return db.query(
        "SELECT t.*, c.codigo AS conta_codigo, c.nome AS conta_nome, cc.nome AS centro_custo,"
        " cp.nome AS conta_pagamento_nome,"
        " (SELECT 1 FROM emprestimo_parcela ep WHERE ep.titulo_id = t.id) AS de_emprestimo,"
        " (SELECT 1 FROM fatura f WHERE f.titulo_id = t.id) AS de_fatura"
        " FROM titulo t LEFT JOIN conta c ON c.id = t.conta_id"
        " LEFT JOIN conta cp ON cp.id = t.conta_pagamento_id"
        " LEFT JOIN centro_custo cc ON cc.id = t.centro_custo_id"
        f" WHERE {' AND '.join(filtros)} ORDER BY t.status, t.vencimento, t.id",
        tuple(params),
    )


def obter_titulo(titulo_id: int) -> db.sqlite3.Row | None:
    return db.query_one("SELECT * FROM titulo WHERE id = ?", (titulo_id,))


def titulos_com_encargos(**filtros) -> list[dict]:
    """Títulos com multa e juros calculados até hoje (o lançado e o estimado).

    Aceita os mesmos filtros de :func:`listar_titulos`.
    """
    hoje = hoje_iso()
    saida = []
    for titulo in listar_titulos(**filtros):
        encargos = encargos_do_titulo(titulo, hoje)
        item = dict(titulo)
        item["encargos"] = encargos
        item["valor_atualizado"] = encargos["valor_atualizado"]
        saida.append(item)
    return saida


def salvar_titulo(
    titulo_id: int | None,
    tipo: str,
    descricao: str,
    pessoa: str,
    valor: float,
    vencimento_iso: str,
    conta_id: int | None,
    centro_custo_id: int | None,
    observacao: str = "",
    multa_pct: float | None = None,
    juros_mes_pct: float | None = None,
    conta_pagamento_id: int | None = None,
    pagamento_automatico: bool = False,
) -> int:
    if tipo not in ("PAGAR", "RECEBER"):
        raise RegraNegocioError("Tipo de título inválido.")
    if not descricao.strip():
        raise RegraNegocioError("Informe a descrição do título.")
    if valor <= 0:
        raise RegraNegocioError("O valor deve ser maior que zero.")
    if multa_pct is None:
        multa_pct = float(db.get_config("multa_padrao", "0") or 0) if tipo == "PAGAR" else 0.0
    if juros_mes_pct is None:
        juros_mes_pct = float(db.get_config("juros_padrao", "0") or 0) if tipo == "PAGAR" else 0.0

    if titulo_id:
        atual = db.query_one("SELECT status FROM titulo WHERE id = ?", (titulo_id,))
        if atual and atual["status"] == "QUITADO":
            raise RegraNegocioError("Título quitado não pode ser editado. Estorne a baixa antes.")
        db.execute(
            "UPDATE titulo SET tipo=?, descricao=?, pessoa=?, valor=?, vencimento=?,"
            " conta_id=?, centro_custo_id=?, observacao=?, multa_pct=?, juros_mes_pct=?,"
            " conta_pagamento_id=?, pagamento_automatico=? WHERE id=?",
            (tipo, descricao.strip(), pessoa.strip(), valor, vencimento_iso,
             conta_id, centro_custo_id, observacao, multa_pct, juros_mes_pct,
             conta_pagamento_id, int(bool(pagamento_automatico)), titulo_id),
        )
        return titulo_id
    return db.execute(
        "INSERT INTO titulo (tipo, descricao, pessoa, valor, vencimento, competencia,"
        " conta_id, centro_custo_id, observacao, multa_pct, juros_mes_pct,"
        " conta_pagamento_id, pagamento_automatico) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tipo, descricao.strip(), pessoa.strip(), valor, vencimento_iso,
         vencimento_iso[:7], conta_id, centro_custo_id, observacao, multa_pct, juros_mes_pct,
         conta_pagamento_id, int(bool(pagamento_automatico))),
    )


# --------------------------------------------------------------------------- #
# Contas fixas (recorrência mensal)
# --------------------------------------------------------------------------- #
MESES_GERADOS_A_FRENTE = 12

MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
            "agosto", "setembro", "outubro", "novembro", "dezembro"]


def mes_atual() -> str:
    return date.today().strftime("%Y-%m")


def mes_nome(competencia: str) -> str:
    """'2026-08' -> 'agosto de 2026'."""
    ano, mes = competencia.split("-")
    return f"{MESES_PT[int(mes) - 1]} de {ano}"


def mes_curto(competencia: str) -> str:
    """'2026-08' -> 'ago/2026'."""
    if not competencia or len(competencia) < 7:
        return ""
    ano, mes = competencia[:4], competencia[5:7]
    return f"{MESES_PT[int(mes) - 1][:3]}/{ano}"


def somar_meses(base: date, meses: int) -> date:
    """Avança meses preservando o dia sempre que ele existir no mês de destino."""
    indice = base.month - 1 + meses
    ano = base.year + indice // 12
    mes = indice % 12 + 1
    ultimo = _ultimo_dia(ano, mes)
    return date(ano, mes, min(base.day, ultimo))


def _ultimo_dia(ano: int, mes: int) -> int:
    bissexto = ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)
    return [31, 29 if bissexto else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]


def _mes_seguinte(competencia: str) -> str:
    ano, mes = (int(p) for p in competencia.split("-"))
    return f"{ano + mes // 12}-{mes % 12 + 1:02d}"


def listar_recorrencias(apenas_ativas: bool = False) -> list[db.sqlite3.Row]:
    where = "WHERE r.ativo = 1" if apenas_ativas else ""
    return db.query(
        "SELECT r.*, c.nome AS conta_nome, cc.nome AS centro_custo,"
        " cp.nome AS conta_pagamento_nome,"
        " (SELECT COUNT(*) FROM titulo t WHERE t.recorrencia_id = r.id) AS gerados,"
        " (SELECT COUNT(*) FROM titulo t WHERE t.recorrencia_id = r.id AND t.status='QUITADO')"
        "   AS pagos,"
        # Conta fixa não tem parcelas: o que interessa é quando foi paga pela
        # última vez e quando vence a próxima.
        " (SELECT MAX(t.liquidado_em) FROM titulo t WHERE t.recorrencia_id = r.id"
        "   AND t.status='QUITADO') AS ultimo_pagamento,"
        " (SELECT MIN(t.vencimento) FROM titulo t WHERE t.recorrencia_id = r.id"
        "   AND t.status='ABERTO') AS proxima_cobranca"
        " FROM recorrencia r LEFT JOIN conta c ON c.id = r.conta_id"
        " LEFT JOIN conta cp ON cp.id = r.conta_pagamento_id"
        f" LEFT JOIN centro_custo cc ON cc.id = r.centro_custo_id {where}"
        " ORDER BY r.ativo DESC, r.descricao")


def listar_rendas_fixas(incluir_encerradas: bool = True) -> list[dict]:
    """As fontes de renda que se repetem todo mês — salário, aluguel, pensão.

    Traz quanto já entrou de cada uma e quando foi a última vez, para a tela de
    Salários mostrar a história completa mesmo depois de a fonte acabar.
    """
    saida = []
    for rec in listar_recorrencias():
        if rec["tipo"] != "RECEBER":
            continue
        if not incluir_encerradas and not rec["ativo"]:
            continue
        recebido = db.query_one(
            "SELECT COALESCE(SUM(IFNULL(valor_liquidado, valor)),0) AS total,"
            " COUNT(*) AS vezes FROM titulo"
            " WHERE recorrencia_id = ? AND status = 'QUITADO'", (rec["id"],))
        previsto = db.query_one(
            "SELECT COALESCE(SUM(valor),0) AS total FROM titulo"
            " WHERE recorrencia_id = ? AND status = 'ABERTO'", (rec["id"],))
        item = dict(rec)
        item["recebido"] = round(float(recebido["total"]), 2)
        item["vezes"] = int(recebido["vezes"])
        item["a_receber"] = round(float(previsto["total"]), 2)
        item["encerrada"] = not rec["ativo"]
        saida.append(item)
    # Primeiro as que ainda entram, depois as encerradas (mais recentes antes).
    saida.sort(key=lambda r: (r["encerrada"], -(r["valor"] or 0)))
    return saida


def historico_da_renda(recorrencia_id: int) -> list[dict]:
    """Mês a mês de uma fonte de renda: o que estava previsto e o que entrou."""
    linhas = db.query(
        "SELECT t.*, c.nome AS conta_nome, cp.nome AS conta_entrada"
        " FROM titulo t LEFT JOIN conta c ON c.id = t.conta_id"
        " LEFT JOIN conta cp ON cp.id = t.conta_pagamento_id"
        " WHERE t.recorrencia_id = ? ORDER BY t.competencia DESC, t.id DESC",
        (recorrencia_id,))
    saida = []
    for linha in linhas:
        recebido = (float(linha["valor_liquidado"]) if linha["valor_liquidado"] is not None
                    else None)
        item = dict(linha)
        item["recebido"] = recebido
        item["diferenca"] = (round(recebido - float(linha["valor"]), 2)
                             if recebido is not None else None)
        saida.append(item)
    return saida


def total_recebido_por_fonte(desde: str, ate: str) -> list[dict]:
    """Quanto cada fonte de renda trouxe no período (só o que foi recebido)."""
    linhas = db.query(
        "SELECT COALESCE(r.descricao, t.descricao) AS fonte,"
        " t.recorrencia_id, SUM(IFNULL(t.valor_liquidado, t.valor)) AS total,"
        " COUNT(*) AS vezes FROM titulo t"
        " LEFT JOIN recorrencia r ON r.id = t.recorrencia_id"
        " WHERE t.tipo = 'RECEBER' AND t.status = 'QUITADO'"
        "   AND t.liquidado_em BETWEEN ? AND ?"
        " GROUP BY fonte ORDER BY total DESC", (desde, ate))
    return [{"fonte": l["fonte"], "recorrencia_id": l["recorrencia_id"],
             "total": round(float(l["total"]), 2), "vezes": int(l["vezes"])}
            for l in linhas]


def salvar_recorrencia(
    recorrencia_id: int | None,
    tipo: str,
    descricao: str,
    pessoa: str,
    valor: float,
    dia_vencimento: int,
    conta_id: int | None,
    centro_custo_id: int | None,
    inicio: str,
    fim: str | None = None,
    observacao: str = "",
    ativo: bool = True,
    multa_pct: float | None = None,
    juros_mes_pct: float | None = None,
    conta_pagamento_id: int | None = None,
    pagamento_automatico: bool = False,
) -> int:
    if tipo not in ("PAGAR", "RECEBER"):
        raise RegraNegocioError("Tipo inválido para a conta fixa.")
    if not descricao.strip():
        raise RegraNegocioError("Escreva a descrição da conta fixa.")
    if valor <= 0:
        raise RegraNegocioError("O valor deve ser maior que zero.")
    if not 1 <= dia_vencimento <= 31:
        raise RegraNegocioError("O dia do vencimento deve estar entre 1 e 31.")
    if conta_id is None:
        raise RegraNegocioError("Escolha a categoria da conta fixa.")
    if fim and fim < inicio:
        raise RegraNegocioError("O mês final não pode ser anterior ao inicial.")

    if multa_pct is None:
        multa_pct = float(db.get_config("multa_padrao", "0") or 0) if tipo == "PAGAR" else 0.0
    if juros_mes_pct is None:
        juros_mes_pct = float(db.get_config("juros_padrao", "0") or 0) if tipo == "PAGAR" else 0.0

    if recorrencia_id:
        db.execute(
            "UPDATE recorrencia SET tipo=?, descricao=?, pessoa=?, valor=?, dia_vencimento=?,"
            " conta_id=?, centro_custo_id=?, inicio=?, fim=?, observacao=?, ativo=?,"
            " multa_pct=?, juros_mes_pct=?, conta_pagamento_id=?, pagamento_automatico=?"
            " WHERE id=?",
            (tipo, descricao.strip(), pessoa.strip(), valor, dia_vencimento, conta_id,
             centro_custo_id, inicio, fim, observacao, int(ativo), multa_pct, juros_mes_pct,
             conta_pagamento_id, int(bool(pagamento_automatico)), recorrencia_id))
        return recorrencia_id

    return db.execute(
        "INSERT INTO recorrencia (tipo, descricao, pessoa, valor, dia_vencimento, conta_id,"
        " centro_custo_id, inicio, fim, observacao, ativo, criado_em, multa_pct, juros_mes_pct,"
        " conta_pagamento_id, pagamento_automatico) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tipo, descricao.strip(), pessoa.strip(), valor, dia_vencimento, conta_id,
         centro_custo_id, inicio, fim, observacao, int(ativo),
         datetime.now().isoformat(timespec="seconds"), multa_pct, juros_mes_pct,
         conta_pagamento_id, int(bool(pagamento_automatico))))


MESES_MAXIMO_A_FRENTE = 120      # teto de segurança para "ver o futuro": 10 anos


def gerar_titulos_recorrentes(ate_meses: int = MESES_GERADOS_A_FRENTE,
                              ate_competencia: str | None = None) -> int:
    """Cria os títulos ainda inexistentes das contas fixas ativas.

    Conta fixa não tem fim até ser desmarcada: sempre há pelo menos
    `ate_meses` lançados à frente, e navegar para um mês mais distante
    (`ate_competencia`) lança também os meses até lá. Idempotente: cada
    competência de cada recorrência só é gerada uma vez.
    """
    # Conta fixa pausada ou encerrada não pode deixar meses futuros na lista.
    limpar_futuros_de_inativas()

    limite = mes_atual()
    for _ in range(ate_meses):
        limite = _mes_seguinte(limite)
    if ate_competencia:
        teto = mes_atual()
        for _ in range(MESES_MAXIMO_A_FRENTE):
            teto = _mes_seguinte(teto)
        limite = max(limite, min(ate_competencia[:7], teto))

    criados = 0
    for rec in db.query("SELECT * FROM recorrencia WHERE ativo = 1"):
        # Com prazo definido, cada mês é uma parcela: a descrição numera (3/10)
        # para você saber quanto já andou e quanto falta.
        total_parcelas = _parcelas_da_recorrencia(rec)
        existentes = {t["competencia"] for t in db.query(
            "SELECT competencia FROM titulo WHERE recorrencia_id = ?", (rec["id"],))}
        competencia = max(rec["inicio"], _competencia_minima(rec, existentes))
        while competencia <= limite and (not rec["fim"] or competencia <= rec["fim"]):
            if competencia not in existentes:
                ano, mes = (int(p) for p in competencia.split("-"))
                dia = min(int(rec["dia_vencimento"]), _ultimo_dia(ano, mes))
                db.execute(
                    "INSERT INTO titulo (tipo, descricao, pessoa, valor, vencimento, competencia,"
                    " conta_id, centro_custo_id, observacao, recorrencia_id,"
                    " multa_pct, juros_mes_pct, conta_pagamento_id, pagamento_automatico)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rec["tipo"], _descricao_da_parcela(rec, competencia, total_parcelas),
                     rec["pessoa"], rec["valor"],
                     date(ano, mes, dia).isoformat(), competencia, rec["conta_id"],
                     rec["centro_custo_id"], rec["observacao"], rec["id"],
                     rec["multa_pct"] or 0, rec["juros_mes_pct"] or 0,
                     rec["conta_pagamento_id"], rec["pagamento_automatico"] or 0))
                criados += 1
            competencia = _mes_seguinte(competencia)
    return criados


def _meses_entre(inicio: str, fim: str) -> int:
    """Quantos meses de `inicio` até `fim`, contando os dois."""
    ano_i, mes_i = (int(p) for p in inicio[:7].split("-"))
    ano_f, mes_f = (int(p) for p in fim[:7].split("-"))
    return (ano_f * 12 + mes_f) - (ano_i * 12 + mes_i) + 1


def _parcelas_da_recorrencia(rec) -> int:
    """Total de parcelas quando a conta tem prazo; 0 quando é sem fim."""
    if not rec["fim"]:
        return 0
    return max(_meses_entre(rec["inicio"], rec["fim"]), 0)


def _descricao_da_parcela(rec, competencia: str, total: int) -> str:
    """'Notebook' vira 'Notebook (3/10)' quando a conta tem prazo."""
    if total <= 1:
        return rec["descricao"]
    numero = _meses_entre(rec["inicio"], competencia)
    if numero < 1 or numero > total:
        return rec["descricao"]
    return f"{rec['descricao']} ({numero}/{total})"


def _competencia_minima(rec: db.sqlite3.Row, existentes: set[str]) -> str:
    """De qual mês em diante vale gerar.

    Nunca volta ao passado: a geração continua do mês seguinte ao último título
    já criado. Sem isso, a segunda execução recriava todos os meses entre o
    início da conta fixa e hoje — meses que o usuário nunca teve a pagar, ou que
    apagou de propósito.
    """
    piso = max(rec["inicio"], mes_atual())
    if existentes:
        return max(piso, _mes_seguinte(max(existentes)))
    return piso


def aplicar_reajuste(recorrencia_id: int, competencia_base: str, valor: float,
                     descricao: str | None = None, pessoa: str | None = None,
                     conta_id: int | None = None,
                     centro_custo_id: int | None = None) -> int:
    """Propaga a alteração para a competência informada e todas as seguintes.

    Títulos já pagos ou cancelados nunca são tocados.
    """
    campos = ["valor = ?"]
    params: list = [valor]
    for coluna, novo in (("descricao", descricao), ("pessoa", pessoa),
                         ("conta_id", conta_id), ("centro_custo_id", centro_custo_id)):
        if novo is not None:
            campos.append(f"{coluna} = ?")
            params.append(novo)
    params += [recorrencia_id, competencia_base]

    with db.transaction() as conn:
        cursor = conn.execute(
            f"UPDATE titulo SET {', '.join(campos)}"
            " WHERE recorrencia_id = ? AND competencia >= ? AND status = 'ABERTO'",
            tuple(params))
        atingidos = cursor.rowcount
        conn.execute("UPDATE recorrencia SET valor = ? WHERE id = ?", (valor, recorrencia_id))
    return atingidos


def aplicar_pagamento_automatico(recorrencia_id: int, competencia_base: str,
                                 automatico: bool) -> int:
    """Liga/desliga o débito automático da fixa e dos meses em aberto daqui em diante."""
    valor = int(bool(automatico))
    with db.transaction() as conn:
        cursor = conn.execute(
            "UPDATE titulo SET pagamento_automatico = ?"
            " WHERE recorrencia_id = ? AND competencia >= ? AND status = 'ABERTO'",
            (valor, recorrencia_id, competencia_base))
        conn.execute("UPDATE recorrencia SET pagamento_automatico = ? WHERE id = ?",
                     (valor, recorrencia_id))
    return cursor.rowcount


def definir_pagamento_automatico(titulo_id: int, automatico: bool,
                                 propagar_fixa: bool = False) -> int:
    """Marca uma conta como paga por débito automático (ou volta para manual).

    Em conta fixa, ``propagar_fixa`` leva a marca para este mês e os seguintes
    ainda em aberto — é o caso normal: débito automático não é coisa de um mês só.
    """
    titulo = obter_titulo(titulo_id)
    if titulo is None:
        raise RegraNegocioError("Conta não encontrada.")
    if titulo["status"] != "ABERTO":
        raise RegraNegocioError("Só dá para mudar isso em conta que ainda está em aberto.")
    if automatico and not titulo["conta_pagamento_id"]:
        raise RegraNegocioError(
            "Escolha antes de qual conta o dinheiro sai: sem isso o sistema não tem"
            " de onde descontar no vencimento.")
    if propagar_fixa and titulo["recorrencia_id"]:
        return aplicar_pagamento_automatico(
            titulo["recorrencia_id"], titulo["competencia"] or titulo["vencimento"][:7],
            automatico)
    db.execute("UPDATE titulo SET pagamento_automatico = ? WHERE id = ?",
               (int(bool(automatico)), titulo_id))
    return 1


def titulos_automaticos_do_periodo(desde: str, ate: str) -> list[db.sqlite3.Row]:
    """Contas em aberto marcadas como débito automático com vencimento no período."""
    return db.query(
        "SELECT t.*, cp.nome AS conta_pagamento_nome FROM titulo t"
        " LEFT JOIN conta cp ON cp.id = t.conta_pagamento_id"
        " WHERE t.status = 'ABERTO' AND t.pagamento_automatico = 1"
        " AND t.vencimento BETWEEN ? AND ? ORDER BY t.vencimento, t.id", (desde, ate))


def pagar_automaticos(hoje: str | None = None) -> dict:
    """Dá baixa nas contas de débito automático que já venceram.

    O desconto é o mesmo de um pagamento manual: sai da conta escolhida, na data
    do vencimento. Quem não tem conta de desconto definida fica de fora e volta
    na lista de pendentes, para o usuário resolver.
    """
    hoje = hoje or hoje_iso()
    pagos, pendentes = [], []
    for titulo in db.query(
            "SELECT * FROM titulo WHERE status = 'ABERTO' AND pagamento_automatico = 1"
            " AND vencimento <= ? ORDER BY vencimento, id", (hoje,)):
        if not titulo["conta_pagamento_id"]:
            pendentes.append({"id": titulo["id"], "descricao": titulo["descricao"],
                              "vencimento": titulo["vencimento"],
                              "motivo": "sem conta de desconto definida"})
            continue
        # Multa e juros de atraso entram, como entrariam em um débito de verdade.
        devido = encargos_do_titulo(titulo, ate=titulo["vencimento"])["valor_atualizado"]
        try:
            baixar_titulo(titulo["id"], titulo["vencimento"], devido,
                          titulo["conta_pagamento_id"])
        except RegraNegocioError as erro:
            pendentes.append({"id": titulo["id"], "descricao": titulo["descricao"],
                              "vencimento": titulo["vencimento"], "motivo": str(erro)})
            continue
        pagos.append({"id": titulo["id"], "descricao": titulo["descricao"],
                      "vencimento": titulo["vencimento"], "valor": devido,
                      "conta": titulo["conta_pagamento_id"]})
    return {"pagos": pagos, "pendentes": pendentes}


def ajustar_valor_do_mes(recorrencia_id: int, competencia: str, valor: float) -> int:
    """Muda o valor de um único mês da conta fixa, sem mexer na regra.

    É o caso do mês fora da curva — adiantamento, 13º, desconto pontual: o valor
    combinado continua valendo para os outros meses.
    """
    if valor <= 0:
        raise RegraNegocioError("O valor deve ser maior que zero.")
    with db.transaction() as conn:
        cursor = conn.execute(
            "UPDATE titulo SET valor = ? WHERE recorrencia_id = ? AND competencia = ?"
            " AND status = 'ABERTO'", (round(valor, 2), recorrencia_id, competencia[:7]))
    if not cursor.rowcount:
        raise RegraNegocioError(
            f"{mes_nome(competencia)} não tem nenhum mês em aberto para corrigir.")
    return cursor.rowcount


def aplicar_conta_pagamento(recorrencia_id: int, competencia_base: str,
                            conta_pagamento_id: int | None) -> int:
    """Define a conta de desconto da fixa e dos meses em aberto daqui em diante."""
    with db.transaction() as conn:
        cursor = conn.execute(
            "UPDATE titulo SET conta_pagamento_id = ?"
            " WHERE recorrencia_id = ? AND competencia >= ? AND status = 'ABERTO'",
            (conta_pagamento_id, recorrencia_id, competencia_base))
        conn.execute("UPDATE recorrencia SET conta_pagamento_id = ? WHERE id = ?",
                     (conta_pagamento_id, recorrencia_id))
    return cursor.rowcount


def ajustar_dia_recorrencia(recorrencia_id: int, novo_dia: int,
                            a_partir_de: str | None = None) -> int:
    """Muda o dia de vencimento da conta fixa e reajusta os meses em aberto.

    Meses já pagos não são tocados. Devolve quantos vencimentos foram corrigidos.
    """
    if not 1 <= novo_dia <= 31:
        raise RegraNegocioError("O dia do vencimento deve estar entre 1 e 31.")
    rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (recorrencia_id,))
    if rec is None:
        raise RegraNegocioError("Conta fixa não encontrada.")

    a_partir_de = a_partir_de or mes_atual()
    db.execute("UPDATE recorrencia SET dia_vencimento = ? WHERE id = ?",
               (novo_dia, recorrencia_id))

    ajustados = 0
    for titulo in db.query(
            "SELECT id, competencia FROM titulo WHERE recorrencia_id = ? AND status = 'ABERTO'"
            " AND competencia >= ?", (recorrencia_id, a_partir_de)):
        ano, mes = (int(p) for p in titulo["competencia"].split("-"))
        dia = min(novo_dia, _ultimo_dia(ano, mes))
        db.execute("UPDATE titulo SET vencimento = ? WHERE id = ?",
                   (date(ano, mes, dia).isoformat(), titulo["id"]))
        ajustados += 1
    return ajustados


def ajustar_inicio_recorrencia(recorrencia_id: int, novo_inicio: str,
                               apagar_anteriores: bool = True) -> int:
    """Muda o mês em que a conta fixa começa, removendo cobranças anteriores em aberto."""
    rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (recorrencia_id,))
    if rec is None:
        raise RegraNegocioError("Conta fixa não encontrada.")
    removidos = 0
    with db.transaction() as conn:
        conn.execute("UPDATE recorrencia SET inicio = ? WHERE id = ?",
                     (novo_inicio, recorrencia_id))
        if apagar_anteriores:
            cursor = conn.execute(
                "DELETE FROM titulo WHERE recorrencia_id = ? AND status = 'ABERTO'"
                " AND competencia < ?", (recorrencia_id, novo_inicio))
            removidos = cursor.rowcount
    return removidos


def encerrar_recorrencia(recorrencia_id: int, apagar_futuros: bool = True,
                         ultimo_mes: str | None = None) -> int:
    """Desmarca a conta fixa: ela deixa de se repetir depois de `ultimo_mes`.

    O último mês (padrão: o atual) continua na lista; os meses seguintes ainda
    em aberto são removidos. Meses pagos nunca são apagados.
    """
    ultimo = (ultimo_mes or mes_atual())[:7]
    removidos = 0
    with db.transaction() as conn:
        conn.execute("UPDATE recorrencia SET ativo = 0, fim = ? WHERE id = ?",
                     (ultimo, recorrencia_id))
        if apagar_futuros:
            cursor = conn.execute(
                "DELETE FROM titulo WHERE recorrencia_id = ? AND status = 'ABERTO'"
                " AND competencia > ?", (recorrencia_id, ultimo))
            removidos = cursor.rowcount
    return removidos


def reativar_recorrencia(recorrencia_id: int) -> int:
    """Volta a repetir uma conta fixa pausada ou encerrada, sem prazo de fim.

    Sem limpar o fim, a conta ficava "ativa" mas nunca mais gerava um mês.
    """
    rec = db.query_one("SELECT * FROM recorrencia WHERE id = ?", (recorrencia_id,))
    if rec is None:
        raise RegraNegocioError("Conta fixa não encontrada.")
    # Um prazo que ainda está por vir é mantido; um fim já alcançado (inclusive o
    # deste mês, que é o que "encerrar" grava) é apagado.
    fim = rec["fim"] if rec["fim"] and rec["fim"] > mes_atual() else None
    db.execute("UPDATE recorrencia SET ativo = 1, fim = ? WHERE id = ?", (fim, recorrencia_id))
    return gerar_titulos_recorrentes()


def _mes_anterior(competencia: str) -> str:
    ano, mes = (int(p) for p in competencia[:7].split("-"))
    return f"{ano - 1}-12" if mes == 1 else f"{ano}-{mes - 1:02d}"


def pausar_recorrencia(recorrencia_id: int) -> int:
    """Desativa a conta fixa: ela some do mês atual em diante.

    Quem desativa não vai mais pagar (nem receber) — inclusive o mês corrente,
    que ainda estava pendente. O que já foi pago ou recebido nunca é tocado, e os
    meses anteriores continuam na lista para você resolver. Devolve quantos meses
    saíram.
    """
    with db.transaction() as conn:
        conn.execute("UPDATE recorrencia SET ativo = 0 WHERE id = ?", (recorrencia_id,))
        cursor = conn.execute(
            "DELETE FROM titulo WHERE recorrencia_id = ? AND status = 'ABERTO'"
            " AND competencia >= ?", (recorrencia_id, mes_atual()))
    return cursor.rowcount


def limpar_futuros_de_inativas() -> int:
    """Tira da lista o que contas fixas inativas ainda têm lançado à frente.

    Vale para o que ficou para trás: antes, pausar só parava de gerar, e os meses
    já lançados continuavam aparecendo em Contas a Pagar e Receber.
    """
    anterior = _mes_anterior(mes_atual())
    with db.transaction() as conn:
        # Quem encerrou com um mês final combinado mantém os meses até lá; quem
        # apenas desativou sai do mês atual em diante.
        cursor = conn.execute(
            "DELETE FROM titulo WHERE status = 'ABERTO' AND EXISTS ("
            "  SELECT 1 FROM recorrencia r WHERE r.id = titulo.recorrencia_id"
            "    AND r.ativo = 0 AND titulo.competencia > IFNULL(r.fim, ?))",
            (anterior,))
    return cursor.rowcount


def tornar_recorrente(titulo_id: int, meses: int = 0) -> int:
    """Marca uma conta já cadastrada como fixa: ela passa a se repetir todo mês.

    A própria conta vira o primeiro mês da série — não é duplicada. Com
    `meses` = 0 repete até ser desmarcada. Devolve quantos meses foram lançados.
    """
    titulo = obter_titulo(titulo_id)
    if titulo is None:
        raise RegraNegocioError("Conta não encontrada.")
    if titulo["recorrencia_id"]:
        raise RegraNegocioError("Esta conta já é fixa.")
    competencia = titulo["competencia"] or titulo["vencimento"][:7]
    base = date.fromisoformat(titulo["vencimento"])
    fim = (somar_meses(date.fromisoformat(f"{competencia}-01"), meses - 1).strftime("%Y-%m")
           if meses else None)
    recorrencia_id = salvar_recorrencia(
        None, titulo["tipo"], titulo["descricao"], titulo["pessoa"], float(titulo["valor"]),
        base.day, titulo["conta_id"], titulo["centro_custo_id"], competencia, fim,
        titulo["observacao"], multa_pct=titulo["multa_pct"],
        juros_mes_pct=titulo["juros_mes_pct"],
        conta_pagamento_id=titulo["conta_pagamento_id"],
        pagamento_automatico=bool(titulo["pagamento_automatico"]))
    db.execute("UPDATE titulo SET recorrencia_id = ?, competencia = ? WHERE id = ?",
               (recorrencia_id, competencia, titulo_id))
    if meses > 1:
        # O título que virou a primeira parcela também ganha o "(1/N)".
        db.execute("UPDATE titulo SET descricao = ? WHERE id = ?",
                   (f"{titulo['descricao']} (1/{meses})", titulo_id))
    return gerar_titulos_recorrentes()


def criar_conta_fixa(tipo: str, descricao: str, pessoa: str, valor: float, vencimento: str,
                     conta_id: int | None, centro_custo_id: int | None = None,
                     observacao: str = "", meses: int = 0, multa_pct: float | None = None,
                     juros_mes_pct: float | None = None,
                     conta_pagamento_id: int | None = None,
                     pagamento_automatico: bool = False) -> tuple[int, int]:
    """Cria a conta fixa já com o primeiro mês lançado, mesmo que ele seja passado.

    A geração automática nunca volta ao passado (para não ressuscitar meses
    apagados). Por isso o mês escolhido no cadastro é lançado aqui, de forma
    explícita. Devolve (id da conta fixa, meses lançados).
    """
    titulo_id = salvar_titulo(None, tipo, descricao, pessoa, valor, vencimento, conta_id,
                              centro_custo_id, observacao, multa_pct, juros_mes_pct,
                              conta_pagamento_id=conta_pagamento_id,
                              pagamento_automatico=pagamento_automatico)
    lancados = 1 + tornar_recorrente(titulo_id, meses)
    return obter_titulo(titulo_id)["recorrencia_id"], lancados


# --------------------------------------------------------------------------- #
# Atraso: multa e juros
# --------------------------------------------------------------------------- #
CONTA_ENCARGOS = "5.7.01"      # Juros e Multas (despesa financeira)
CONTA_PROVISAO = "2.1.02"      # Contas a Pagar (obrigação já reconhecida)


def _conta_por_codigo(codigo: str) -> int:
    conta = db.query_one("SELECT id FROM conta WHERE codigo = ?", (codigo,))
    if conta is None:
        raise RegraNegocioError(f"A conta {codigo} não existe no plano de contas.")
    return conta["id"]


def encargos_do_titulo(titulo: db.sqlite3.Row, ate: str | None = None) -> dict:
    """Multa e juros de um título em atraso até a data informada.

    A multa incide uma única vez; os juros são proporcionais aos dias de atraso
    (juros simples, sem capitalização).
    """
    ate = ate or hoje_iso()
    if titulo["status"] != "ABERTO":
        return {"dias": 0, "multa": 0.0, "juros": 0.0, "total": 0.0,
                "valor_atualizado": float(titulo["valor"])}

    dias = (date.fromisoformat(ate) - date.fromisoformat(titulo["vencimento"])).days
    if dias <= 0:
        return {"dias": 0, "multa": 0.0, "juros": 0.0, "total": 0.0,
                "valor_atualizado": float(titulo["valor"])}

    valor = float(titulo["valor"])
    multa = round(valor * float(titulo["multa_pct"] or 0) / 100, 2)
    juros = round(valor * float(titulo["juros_mes_pct"] or 0) / 100 * dias / 30, 2)
    total = round(multa + juros, 2)
    return {"dias": dias, "multa": multa, "juros": juros, "total": total,
            "valor_atualizado": round(valor + total, 2)}


def lancar_encargos_do_mes(hoje: str | None = None) -> int:
    """Lança na contabilidade os encargos dos títulos em atraso.

    Roda uma vez por mês, sempre no fechamento do mês anterior: o que se deve de
    multa e juros até o último dia daquele mês vira despesa financeira e uma
    obrigação em Contas a Pagar. Devolve quantos títulos foram atualizados.
    """
    if db.get_config("encargos_automaticos", "1") != "1":
        return 0

    hoje = hoje or hoje_iso()
    referencia = date.fromisoformat(hoje)
    fim_mes_anterior = referencia.replace(day=1) - timedelta(days=1)
    corte = fim_mes_anterior.isoformat()

    atualizados = 0
    for titulo in db.query(
            "SELECT * FROM titulo WHERE status = 'ABERTO' AND tipo = 'PAGAR'"
            " AND vencimento <= ? AND (multa_pct > 0 OR juros_mes_pct > 0)"
            " AND (encargos_ate IS NULL OR encargos_ate < ?)", (corte, corte)):
        devidos = encargos_do_titulo(titulo, corte)["total"]
        diferenca = round(devidos - float(titulo["encargos_lancados"] or 0), 2)
        if diferenca <= CENTAVO:
            db.execute("UPDATE titulo SET encargos_ate = ? WHERE id = ?", (corte, titulo["id"]))
            continue

        salvar_lancamento(
            None, corte,
            f"Multa e juros por atraso — {titulo['descricao']}",
            [Partida(_conta_por_codigo(CONTA_ENCARGOS), "D", diferenca),
             Partida(_conta_por_codigo(CONTA_PROVISAO), "C", diferenca)],
            documento=f"ENC-{titulo['id']}", origem="ENCARGO")
        db.execute(
            "UPDATE titulo SET encargos_lancados = ?, encargos_ate = ? WHERE id = ?",
            (round(float(titulo["encargos_lancados"] or 0) + diferenca, 2), corte, titulo["id"]))
        atualizados += 1
    return atualizados


def estornar_provisao(titulo_id: int, data_iso: str | None = None) -> None:
    """Desfaz a provisão de encargos de um título que não será mais cobrado."""
    titulo = db.query_one("SELECT * FROM titulo WHERE id = ?", (titulo_id,))
    if titulo is None:
        return
    provisionado = round(float(titulo["encargos_lancados"] or 0), 2)
    if provisionado <= CENTAVO:
        return
    salvar_lancamento(
        None, data_iso or hoje_iso(),
        f"Estorno de multa e juros — {titulo['descricao']}",
        [Partida(_conta_por_codigo(CONTA_PROVISAO), "D", provisionado),
         Partida(_conta_por_codigo(CONTA_ENCARGOS), "C", provisionado)],
        documento=f"ENC-{titulo_id}", origem="ENCARGO")
    db.execute("UPDATE titulo SET encargos_lancados = 0, encargos_ate = NULL WHERE id = ?",
               (titulo_id,))


def baixar_titulo(
    titulo_id: int,
    data_iso: str,
    valor_pago: float,
    conta_caixa_id: int,
    saldo_em_aberto: bool = False,
    vencimento_do_saldo: str | None = None,
) -> int:
    """Liquida o título gerando o lançamento contábil correspondente.

    Pagou menos do que devia? Com ``saldo_em_aberto`` o que faltou vira uma nova
    conta a pagar, ligada a esta, para você quitar depois. Sem ela, o título é
    encerrado pelo valor pago — é o caso de desconto ou acordo.
    """
    titulo = db.query_one("SELECT * FROM titulo WHERE id = ?", (titulo_id,))
    if titulo is None:
        raise RegraNegocioError("Título não encontrado.")
    if titulo["status"] != "ABERTO":
        raise RegraNegocioError("Somente títulos em aberto podem ser baixados.")
    if titulo["conta_id"] is None:
        raise RegraNegocioError("Defina a conta de resultado/contrapartida do título antes de baixar.")
    if valor_pago <= 0:
        raise RegraNegocioError("Valor da baixa deve ser maior que zero.")

    encargos = encargos_do_titulo(titulo, ate=data_iso)
    devido = encargos["valor_atualizado"]
    restante = round(devido - valor_pago, 2)
    if saldo_em_aberto and restante <= CENTAVO:
        raise RegraNegocioError(
            "Não sobrou nada a pagar: o valor informado já cobre a conta inteira.")

    if titulo["tipo"] == "PAGAR":
        partidas = _partidas_pagamento(titulo, valor_pago, conta_caixa_id)
        historico = f"Pagamento — {titulo['descricao']}"
    else:
        partidas = [
            Partida(conta_caixa_id, "D", valor_pago),
            Partida(titulo["conta_id"], "C", valor_pago),
        ]
        historico = f"Recebimento — {titulo['descricao']}"
    if titulo["pessoa"]:
        historico += f" ({titulo['pessoa']})"

    lancamento_id = salvar_lancamento(
        None, data_iso, historico, partidas,
        documento=f"TIT-{titulo_id}",
        centro_custo_id=titulo["centro_custo_id"],
        origem="BAIXA",
        # Só depois de a conta estar marcada como paga: no meio do caminho a
        # fatura seria recalculada com o dinheiro já lançado e a conta ainda aberta.
        atualizar_faturas=False,
    )
    db.execute(
        "UPDATE titulo SET status='QUITADO', liquidado_em=?, valor_liquidado=?, lancamento_id=?"
        " WHERE id=?",
        (data_iso, valor_pago, lancamento_id, titulo_id),
    )

    if saldo_em_aberto and restante > CENTAVO:
        _criar_titulo_do_saldo(titulo, restante, vencimento_do_saldo or titulo["vencimento"])
    _atualizar_faturas_se_cartao(p.conta_id for p in partidas)
    return lancamento_id


def _criar_titulo_do_saldo(titulo: db.sqlite3.Row, valor: float, vencimento: str) -> int:
    """Cria a conta com o que faltou pagar, apontando para a conta de origem."""
    observacao = (MARCA_SALDO_PARCIAL.format(id=titulo["id"])
                  + f" — {titulo['descricao']}.")
    if titulo["observacao"]:
        observacao = f"{titulo['observacao']}\n{observacao}"
    return db.execute(
        "INSERT INTO titulo (tipo, descricao, pessoa, valor, vencimento, competencia,"
        " conta_id, centro_custo_id, observacao, multa_pct, juros_mes_pct,"
        " conta_pagamento_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (titulo["tipo"], f"{titulo['descricao']} (o que faltou)", titulo["pessoa"], valor,
         vencimento, titulo["competencia"], titulo["conta_id"], titulo["centro_custo_id"],
         observacao, titulo["multa_pct"], titulo["juros_mes_pct"],
         titulo["conta_pagamento_id"]))


def _partidas_pagamento(titulo: db.sqlite3.Row, valor_pago: float,
                        conta_caixa_id: int) -> list[Partida]:
    """Monta o pagamento separando principal, juros embutidos e encargos de atraso.

    Regras:
      * o principal vai para a categoria do título (ou amortiza a dívida);
      * juros embutidos (parcela de empréstimo) vão para despesa financeira;
      * encargos já provisionados baixam a obrigação em Contas a Pagar;
      * encargos pagos além do provisionado viram despesa financeira na hora;
      * provisão maior do que o efetivamente pago é estornada.
    """
    principal_total = round(float(titulo["valor"]) - float(titulo["juros_embutido"] or 0), 2)
    juros_embutido = round(float(titulo["juros_embutido"] or 0), 2)
    provisionado = round(float(titulo["encargos_lancados"] or 0), 2)

    pago_no_titulo = min(valor_pago, float(titulo["valor"]))
    encargos_pagos = round(max(0.0, valor_pago - float(titulo["valor"])), 2)

    # Reparte o que foi pago entre principal e juros embutidos, proporcionalmente.
    if juros_embutido > CENTAVO and float(titulo["valor"]) > CENTAVO:
        proporcao = pago_no_titulo / float(titulo["valor"])
        juros_pagos = round(juros_embutido * proporcao, 2)
    else:
        juros_pagos = 0.0
    principal_pago = round(pago_no_titulo - juros_pagos, 2)

    conta_encargos = _conta_por_codigo(CONTA_ENCARGOS)
    partidas: list[Partida] = []
    if principal_pago > CENTAVO:
        partidas.append(Partida(titulo["conta_id"], "D", principal_pago))
    if juros_pagos > CENTAVO:
        partidas.append(Partida(conta_encargos, "D", juros_pagos))
    if provisionado > CENTAVO:
        partidas.append(Partida(_conta_por_codigo(CONTA_PROVISAO), "D", provisionado))

    extra = round(encargos_pagos - provisionado, 2)
    if extra > CENTAVO:
        partidas.append(Partida(conta_encargos, "D", extra))
    elif extra < -CENTAVO:
        partidas.append(Partida(conta_encargos, "C", abs(extra)))

    partidas.append(Partida(conta_caixa_id, "C", round(valor_pago, 2)))
    if principal_total < 0:  # segurança: juros embutidos maiores que o valor
        raise RegraNegocioError("Os juros embutidos não podem superar o valor da parcela.")
    return partidas


MARCA_SALDO_PARCIAL = "Saldo do pagamento parcial da conta nº {id}"


def estornar_titulo(titulo_id: int) -> dict:
    """Marca como não paga: a conta volta a ficar em aberto e o dinheiro volta.

    Se o pagamento foi parcial e gerou a conta "(o que faltou)", ela é removida
    junto — senão a dívida ficaria em dobro. Se essa sobra já foi paga, é
    preciso desfazer aquele pagamento primeiro.
    """
    titulo = db.query_one("SELECT * FROM titulo WHERE id = ?", (titulo_id,))
    if titulo is None or titulo["status"] != "QUITADO":
        raise RegraNegocioError("Esta conta não está paga.")

    # O " —" logo após o número evita que a conta 1 ache a sobra da conta 12.
    marca = f"%{MARCA_SALDO_PARCIAL.format(id=titulo_id)} —%"
    sobras = db.query("SELECT * FROM titulo WHERE observacao LIKE ? AND status <> 'CANCELADO'",
                      (marca,))
    if any(s["status"] == "QUITADO" for s in sobras):
        raise RegraNegocioError(
            "O que faltou deste pagamento já foi pago em outra conta."
            " Marque aquela como não paga primeiro.")

    with db.transaction() as conn:
        conn.execute(
            "UPDATE titulo SET status='ABERTO', liquidado_em=NULL, valor_liquidado=NULL,"
            " lancamento_id=NULL WHERE id=?",
            (titulo_id,),
        )
        if titulo["lancamento_id"]:
            conn.execute("DELETE FROM lancamento WHERE id = ?", (titulo["lancamento_id"],))
        for sobra in sobras:
            conn.execute("DELETE FROM titulo WHERE id = ?", (sobra["id"],))
    # Pagamento feito com cartão, ou de uma fatura: as faturas se reajustam.
    fechar_faturas()
    return {"sobras_removidas": len(sobras)}


def cancelar_titulo(titulo_id: int) -> None:
    titulo = db.query_one("SELECT status FROM titulo WHERE id = ?", (titulo_id,))
    if titulo is None:
        raise RegraNegocioError("Título não encontrado.")
    if titulo["status"] == "QUITADO":
        raise RegraNegocioError("Estorne a baixa antes de cancelar.")
    estornar_provisao(titulo_id)
    db.execute("UPDATE titulo SET status='CANCELADO' WHERE id = ?", (titulo_id,))


def excluir_titulo(titulo_id: int) -> None:
    titulo = db.query_one("SELECT status FROM titulo WHERE id = ?", (titulo_id,))
    if titulo and titulo["status"] == "QUITADO":
        raise RegraNegocioError("Estorne a baixa antes de excluir o título.")
    estornar_provisao(titulo_id)
    db.execute("DELETE FROM titulo WHERE id = ?", (titulo_id,))


# --------------------------------------------------------------------------- #
# Relatórios
# --------------------------------------------------------------------------- #
def balancete(desde: str, ate: str, ocultar_zerados: bool = True) -> list[dict]:
    linhas: list[dict] = []
    for conta in listar_contas():
        if conta["aceita_lancamento"]:
            row = db.query_one(
                "SELECT COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor END),0) AS d,"
                "       COALESCE(SUM(CASE WHEN p.tipo='C' THEN p.valor END),0) AS c"
                " FROM partida p JOIN lancamento l ON l.id=p.lancamento_id"
                " WHERE p.conta_id=? AND l.data BETWEEN ? AND ?",
                (conta["id"], desde, ate),
            )
            debito, credito = float(row["d"]), float(row["c"])
            anterior = saldo_conta(conta["id"], ate=_dia_anterior(desde))
        else:
            debito = credito = anterior = 0.0

        saldo = saldo_com_filhos(conta["id"], ate=ate)
        if conta["aceita_lancamento"] and ocultar_zerados and not any(
            (abs(debito) > CENTAVO, abs(credito) > CENTAVO, abs(saldo) > CENTAVO, abs(anterior) > CENTAVO)
        ):
            continue
        linhas.append({
            "codigo": conta["codigo"],
            "nome": conta["nome"],
            "sintetica": not conta["aceita_lancamento"],
            "anterior": round(anterior, 2),
            "debito": round(debito, 2),
            "credito": round(credito, 2),
            "saldo": saldo,
            "natureza": conta["natureza"],
        })
    if ocultar_zerados:
        # Remove sintéticas sem nenhuma analítica visível abaixo delas.
        visiveis = {l["codigo"] for l in linhas if not l["sintetica"]}
        linhas = [
            l for l in linhas
            if not l["sintetica"] or any(v.startswith(l["codigo"] + ".") for v in visiveis)
        ]
    return linhas


def _dia_anterior(iso: str) -> str:
    return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()


def razao(conta_id: int, desde: str, ate: str) -> tuple[float, list[dict]]:
    conta = obter_conta(conta_id)
    if conta is None:
        return 0.0, []
    saldo = saldo_conta(conta_id, ate=_dia_anterior(desde))
    movimentos = db.query(
        "SELECT l.id, l.data, l.historico, l.documento, p.tipo, p.valor"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " WHERE p.conta_id = ? AND l.data BETWEEN ? AND ?"
        " ORDER BY l.data, l.id",
        (conta_id, desde, ate),
    )
    linhas, acumulado = [], saldo
    for m in movimentos:
        delta = m["valor"] if m["tipo"] == conta["natureza"] else -m["valor"]
        acumulado = round(acumulado + delta, 2)
        contrapartida = db.query(
            "SELECT c.codigo, c.nome FROM partida p JOIN conta c ON c.id = p.conta_id"
            " WHERE p.lancamento_id = ? AND p.conta_id <> ?",
            (m["id"], conta_id),
        )
        linhas.append({
            "data": m["data"],
            "lancamento": m["id"],
            "historico": m["historico"],
            "documento": m["documento"],
            "contrapartida": ", ".join(f"{c['codigo']} {c['nome']}" for c in contrapartida),
            "debito": m["valor"] if m["tipo"] == "D" else 0.0,
            "credito": m["valor"] if m["tipo"] == "C" else 0.0,
            "saldo": acumulado,
        })
    return saldo, linhas


def dre(desde: str, ate: str) -> dict:
    def agrupar(tipo: str) -> list[dict]:
        rows = db.query(
            "SELECT c.id, c.codigo, c.nome, c.natureza,"
            " COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END),0) AS liquido"
            " FROM conta c JOIN partida p ON p.conta_id = c.id"
            " JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE c.tipo = ? AND l.data BETWEEN ? AND ?"
            " GROUP BY c.id ORDER BY c.codigo",
            (tipo, desde, ate),
        )
        saida = []
        for r in rows:
            valor = float(r["liquido"]) if r["natureza"] == "D" else -float(r["liquido"])
            if abs(valor) > CENTAVO:
                saida.append({"codigo": r["codigo"], "nome": r["nome"], "valor": round(valor, 2)})
        return saida

    receitas = agrupar("RECEITA")
    despesas = agrupar("DESPESA")
    total_receitas = round(sum(r["valor"] for r in receitas), 2)
    total_despesas = round(sum(d["valor"] for d in despesas), 2)
    return {
        "receitas": receitas,
        "despesas": despesas,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "resultado": round(total_receitas - total_despesas, 2),
    }


def balanco(ate: str) -> dict:
    def grupo(tipo: str) -> list[dict]:
        saida = []
        for conta in db.query("SELECT * FROM conta WHERE tipo = ? ORDER BY codigo", (tipo,)):
            saldo = saldo_com_filhos(conta["id"], ate=ate)
            if abs(saldo) > CENTAVO:
                saida.append({
                    "codigo": conta["codigo"],
                    "nome": conta["nome"],
                    "sintetica": not conta["aceita_lancamento"],
                    "valor": saldo,
                })
        return saida

    ativo = grupo("ATIVO")
    passivo = grupo("PASSIVO")
    patrimonio = grupo("PATRIMONIO")
    resultado = dre("0001-01-01", ate)["resultado"]

    total_ativo = round(sum(a["valor"] for a in ativo if a["codigo"].count(".") == 0), 2)
    total_passivo = round(sum(p["valor"] for p in passivo if p["codigo"].count(".") == 0), 2)
    total_pl = round(sum(p["valor"] for p in patrimonio if p["codigo"].count(".") == 0) + resultado, 2)
    return {
        "ativo": ativo,
        "passivo": passivo,
        "patrimonio": patrimonio,
        "resultado_exercicio": resultado,
        "total_ativo": total_ativo,
        "total_passivo": total_passivo,
        "total_pl": total_pl,
        "diferenca": round(total_ativo - (total_passivo + total_pl), 2),
    }


def livro_diario(desde: str, ate: str) -> list[dict]:
    lancamentos = db.query(
        "SELECT * FROM lancamento WHERE data BETWEEN ? AND ? ORDER BY data, id", (desde, ate)
    )
    return [
        {
            "id": l["id"],
            "data": l["data"],
            "historico": l["historico"],
            "documento": l["documento"],
            "valor": l["valor"],
            "partidas": [dict(p) for p in partidas_do_lancamento(l["id"])],
        }
        for l in lancamentos
    ]


def fluxo_mensal(meses: int = 12) -> list[dict]:
    """Receitas e despesas por mês, até o mês corrente.

    Parcelas de compras já lançadas para o futuro ficam de fora: aqui o assunto
    é o que já aconteceu.
    """
    rows = db.query(
        "SELECT substr(l.data,1,7) AS mes, c.tipo,"
        " SUM(CASE WHEN p.tipo = c.natureza THEN p.valor ELSE -p.valor END) AS total"
        " FROM partida p JOIN lancamento l ON l.id=p.lancamento_id"
        " JOIN conta c ON c.id=p.conta_id WHERE c.tipo IN ('RECEITA','DESPESA')"
        " AND substr(l.data,1,7) <= ?"
        " GROUP BY mes, c.tipo ORDER BY mes", (mes_atual(),)
    )
    mapa: dict[str, dict] = {}
    for r in rows:
        item = mapa.setdefault(r["mes"], {"mes": r["mes"], "receita": 0.0, "despesa": 0.0})
        chave = "receita" if r["tipo"] == "RECEITA" else "despesa"
        item[chave] = round(float(r["total"] or 0.0), 2)
    serie = sorted(mapa.values(), key=lambda x: x["mes"])[-meses:]
    for item in serie:
        item["saldo"] = round(item["receita"] - item["despesa"], 2)
    return serie


# --------------------------------------------------------------------------- #
# Visão mês a mês
# --------------------------------------------------------------------------- #
def primeiro_mes_registrado() -> str | None:
    row = db.query_one("SELECT MIN(data) AS d FROM lancamento")
    return row["d"][:7] if row and row["d"] else None


def meses_do_historico(maximo: int | None = None) -> list[str]:
    """Todas as competências entre o primeiro registro e o mês atual, sem buracos."""
    inicio = primeiro_mes_registrado()
    if inicio is None:
        return []
    fim = mes_atual()
    if inicio > fim:
        fim = inicio
    meses, atual = [], inicio
    while atual <= fim:
        meses.append(atual)
        atual = _mes_seguinte(atual)
    return meses[-maximo:] if maximo else meses


def _fim_do_mes(competencia: str) -> str:
    ano, mes = (int(p) for p in competencia.split("-"))
    return date(ano, mes, _ultimo_dia(ano, mes)).isoformat()


def resumo_mensal(meses: list[str]) -> list[dict]:
    """Entrou, saiu, sobrou, acumulado e dinheiro em conta no fim de cada mês."""
    if not meses:
        return []

    movimento = {m: {"receita": 0.0, "despesa": 0.0} for m in meses}
    for row in db.query(
            "SELECT substr(l.data,1,7) AS mes, c.tipo,"
            " SUM(CASE WHEN p.tipo = c.natureza THEN p.valor ELSE -p.valor END) AS total"
            " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
            " JOIN conta c ON c.id = p.conta_id"
            " WHERE c.tipo IN ('RECEITA','DESPESA') AND substr(l.data,1,7) BETWEEN ? AND ?"
            " GROUP BY mes, c.tipo", (meses[0], meses[-1])):
        if row["mes"] in movimento:
            chave = "receita" if row["tipo"] == "RECEITA" else "despesa"
            movimento[row["mes"]][chave] = round(float(row["total"] or 0.0), 2)

    # Variação do dinheiro em contas (disponível) por mês, para acumular o saldo.
    variacao = {m: 0.0 for m in meses}
    saldo_antes = 0.0
    for row in db.query(
            "SELECT substr(l.data,1,7) AS mes,"
            " SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END) AS total"
            " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
            " JOIN conta c ON c.id = p.conta_id"
            " WHERE c.tipo='ATIVO' AND c.eh_carteira = 1"
            " GROUP BY mes"):
        valor = round(float(row["total"] or 0.0), 2)
        if row["mes"] in variacao:
            variacao[row["mes"]] = valor
        elif row["mes"] < meses[0]:
            saldo_antes += valor

    linhas, acumulado, saldo = [], 0.0, saldo_antes
    for mes in meses:
        receita = movimento[mes]["receita"]
        despesa = movimento[mes]["despesa"]
        sobrou = round(receita - despesa, 2)
        acumulado = round(acumulado + sobrou, 2)
        saldo = round(saldo + variacao[mes], 2)
        linhas.append({
            "mes": mes,
            "nome": mes_nome(mes),
            "receita": receita,
            "despesa": despesa,
            "sobrou": sobrou,
            "acumulado": acumulado,
            "saldo_contas": saldo,
        })
    return linhas


def matriz_categorias(meses: list[str], tipo: str = "DESPESA") -> list[dict]:
    """Uma linha por categoria com o valor de cada mês, mais total e média."""
    if not meses:
        return []
    valores: dict[int, dict] = {}
    for row in db.query(
            "SELECT c.id, c.nome, substr(l.data,1,7) AS mes,"
            " SUM(CASE WHEN p.tipo = c.natureza THEN p.valor ELSE -p.valor END) AS total"
            " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
            " JOIN conta c ON c.id = p.conta_id"
            " WHERE c.tipo = ? AND substr(l.data,1,7) BETWEEN ? AND ?"
            " GROUP BY c.id, mes", (tipo, meses[0], meses[-1])):
        item = valores.setdefault(row["id"], {"nome": row["nome"],
                                              "meses": {m: 0.0 for m in meses}})
        if row["mes"] in item["meses"]:
            item["meses"][row["mes"]] = round(float(row["total"] or 0.0), 2)

    linhas = []
    for item in valores.values():
        total = round(sum(item["meses"].values()), 2)
        if abs(total) < CENTAVO:
            continue
        movimentados = [v for v in item["meses"].values() if abs(v) > CENTAVO]
        item["total"] = total
        item["media"] = round(total / len(movimentados), 2) if movimentados else 0.0
        ultimo = item["meses"][meses[-1]]
        anterior = item["meses"][meses[-2]] if len(meses) > 1 else 0.0
        item["variacao"] = round(ultimo - anterior, 2)
        linhas.append(item)
    return sorted(linhas, key=lambda x: x["total"], reverse=True)


def despesas_por_categoria(desde: str, ate: str, limite: int = 10) -> list[dict]:
    rows = db.query(
        "SELECT c.nome, SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END) AS total"
        " FROM partida p JOIN lancamento l ON l.id=p.lancamento_id"
        " JOIN conta c ON c.id=p.conta_id"
        " WHERE c.tipo='DESPESA' AND l.data BETWEEN ? AND ?"
        " GROUP BY c.id HAVING total > 0 ORDER BY total DESC LIMIT ?",
        (desde, ate, limite),
    )
    return [{"nome": r["nome"], "total": round(float(r["total"]), 2)} for r in rows]


# --------------------------------------------------------------------------- #
# Orçamento por categoria
# --------------------------------------------------------------------------- #
def definir_orcamento(conta_id: int, valor: float, competencia: str = "") -> None:
    """Teto de gasto de uma categoria. Sem competência, vale para todos os meses."""
    if valor < 0:
        raise RegraNegocioError("O valor do orçamento não pode ser negativo.")
    if valor == 0:
        db.execute("DELETE FROM orcamento WHERE conta_id = ? AND competencia = ?",
                   (conta_id, competencia))
        return
    db.execute(
        "INSERT INTO orcamento (conta_id, competencia, valor) VALUES (?,?,?)"
        " ON CONFLICT(conta_id, competencia) DO UPDATE SET valor = excluded.valor",
        (conta_id, competencia, round(valor, 2)))


def teto_da_categoria(conta_id: int, competencia: str) -> tuple[float, bool]:
    """Devolve (valor, se_e_ajuste_do_mes)."""
    especifico = db.query_one(
        "SELECT valor FROM orcamento WHERE conta_id = ? AND competencia = ?",
        (conta_id, competencia))
    if especifico:
        return round(float(especifico["valor"]), 2), True
    padrao = db.query_one("SELECT valor FROM orcamento WHERE conta_id = ? AND competencia = ''",
                          (conta_id,))
    return (round(float(padrao["valor"]), 2), False) if padrao else (0.0, False)


DIAS_MINIMOS_PARA_RITMO = 5     # antes disso o mês é curto demais para extrapolar

# O orçamento se guia pelo mês passado: é o retrato mais próximo da vida de
# agora. Olhar meio ano para trás trazia valores de uma realidade que já mudou.
MESES_BASE_ORCAMENTO = 1


def _historico_da_categoria(conta_id: int, ate_competencia: str,
                            meses: int = MESES_BASE_ORCAMENTO) -> dict:
    """Quanto a categoria costuma consumir, olhando os meses fechados.

    Devolve média, mediana e quantas vezes o teto foi estourado. A mediana é o
    número honesto: um mês atípico (a viagem, o conserto do carro) puxa a média
    para cima e faria o orçamento inteiro mentir.
    """
    anteriores = [m for m in meses_do_historico() if m < ate_competencia][-meses:]
    valores, estouros = [], 0
    for competencia in anteriores:
        ano, mes = (int(p) for p in competencia.split("-"))
        row = db.query_one(
            "SELECT COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END),0) AS t"
            " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ? AND l.data BETWEEN ? AND ?",
            (conta_id, f"{competencia}-01",
             date(ano, mes, _ultimo_dia(ano, mes)).isoformat()))
        gasto = round(float(row["t"]), 2)
        valores.append(gasto)
        teto_do_mes, _ = teto_da_categoria(conta_id, competencia)
        if teto_do_mes > 0 and gasto > teto_do_mes + CENTAVO:
            estouros += 1

    usados = [v for v in valores if v > CENTAVO]
    if usados:
        ordenados = sorted(usados)
        meio = len(ordenados) // 2
        mediana = (ordenados[meio] if len(ordenados) % 2
                   else round((ordenados[meio - 1] + ordenados[meio]) / 2, 2))
        media = round(sum(usados) / len(usados), 2)
    else:
        mediana = media = 0.0
    # Média contando os meses sem gasto: é a única que pode ser somada entre
    # categorias sem inflar o total. Gasto que acontece de vez em quando não
    # pode entrar na projeção como se fosse todo mês.
    esperado = round(sum(valores) / len(valores), 2) if valores else 0.0
    return {"media": media, "mediana": round(mediana, 2), "esperado": esperado,
            "meses": len(valores), "meses_com_gasto": len(usados), "estouros": estouros}


def _comprometido_do_mes(inicio: str, fim: str) -> dict[int, float]:
    """O que já está contratado no mês e ainda não foi pago, por categoria.

    Conta fixa, boleto e parcela em aberto são gasto certo: deixá-los de fora
    fazia o "ainda posso gastar" prometer um dinheiro que já tem dono.
    """
    return {row["conta_id"]: round(float(row["total"]), 2) for row in db.query(
        "SELECT t.conta_id, SUM(t.valor) AS total FROM titulo t"
        " JOIN conta c ON c.id = t.conta_id"
        " WHERE t.tipo = 'PAGAR' AND t.status = 'ABERTO' AND c.tipo = 'DESPESA'"
        "   AND t.vencimento BETWEEN ? AND ? GROUP BY t.conta_id", (inicio, fim))}


def orcamento_do_mes(competencia: str | None = None,
                     incluir_sem_teto: bool = True) -> list[dict]:
    """Previsto × gasto × comprometido de cada categoria de despesa no mês."""
    competencia = competencia or mes_atual()
    inicio = f"{competencia}-01"
    ano, mes = (int(p) for p in competencia.split("-"))
    fim = date(ano, mes, _ultimo_dia(ano, mes)).isoformat()

    hoje = date.today()
    dias_no_mes = _ultimo_dia(ano, mes)
    if hoje.strftime("%Y-%m") == competencia:
        dias_corridos, dias_restantes = hoje.day, dias_no_mes - hoje.day
    elif hoje.strftime("%Y-%m") > competencia:
        dias_corridos, dias_restantes = dias_no_mes, 0
    else:
        dias_corridos, dias_restantes = 0, dias_no_mes

    gastos = {row["id"]: round(float(row["total"]), 2) for row in db.query(
        "SELECT c.id, SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END) AS total"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " JOIN conta c ON c.id = p.conta_id"
        " WHERE c.tipo='DESPESA' AND l.data BETWEEN ? AND ? GROUP BY c.id", (inicio, fim))}
    # O que veio de baixa de conta a pagar é gasto certo, não ritmo do dia a dia.
    fixos_pagos = {row["id"]: round(float(row["total"]), 2) for row in db.query(
        "SELECT c.id, SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END) AS total"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " JOIN conta c ON c.id = p.conta_id"
        " WHERE c.tipo='DESPESA' AND l.origem = 'BAIXA' AND l.data BETWEEN ? AND ?"
        " GROUP BY c.id", (inicio, fim))}
    comprometidos = _comprometido_do_mes(inicio, fim)

    linhas = []
    for conta in db.query("SELECT * FROM conta WHERE tipo='DESPESA' AND aceita_lancamento=1"
                          " AND ativo=1 ORDER BY codigo"):
        teto, ajustado = teto_da_categoria(conta["id"], competencia)
        gasto = gastos.get(conta["id"], 0.0)
        comprometido = comprometidos.get(conta["id"], 0.0)
        if teto <= 0 and gasto <= CENTAVO and comprometido <= CENTAVO:
            continue
        if teto <= 0 and not incluir_sem_teto:
            continue

        historico = _historico_da_categoria(conta["id"], competencia)
        variavel = round(max(gasto - fixos_pagos.get(conta["id"], 0.0), 0.0), 2)

        # Projeção = o que já saiu + o que está contratado + a estimativa do que
        # ainda se gasta no dia a dia. Mês que nem começou não tem ritmo nenhum:
        # ali vale só o que já está agendado, senão a conta vira ficção.
        if dias_restantes <= 0 or dias_corridos <= 0:
            estimado = 0.0
        elif dias_corridos >= DIAS_MINIMOS_PARA_RITMO and variavel > CENTAVO:
            estimado = round(variavel / dias_corridos * dias_restantes, 2)
        else:
            # Começo de mês: o histórico esperado da categoria, proporcional ao
            # que falta — já descontando o que ela consumiu até aqui.
            esperado = max(historico["esperado"] - variavel, 0.0)
            estimado = round(esperado * dias_restantes / dias_no_mes, 2)

        projecao = round(gasto + comprometido + estimado, 2)
        restante = round(teto - gasto, 2) if teto > 0 else 0.0
        livre = round(teto - gasto - comprometido, 2) if teto > 0 else 0.0
        linhas.append({
            "conta_id": conta["id"],
            "codigo": conta["codigo"],
            "nome": conta["nome"],
            "teto": teto,
            "ajuste_do_mes": ajustado,
            "gasto": gasto,
            "comprometido": comprometido,
            "restante": restante,
            "livre": livre,
            "percentual": round(gasto / teto * 100, 1) if teto > 0 else 0.0,
            "percentual_com_comprometido": (round((gasto + comprometido) / teto * 100, 1)
                                            if teto > 0 else 0.0),
            "projecao": projecao,
            "media_historica": historico["media"],
            "mediana_historica": historico["mediana"],
            "meses_historico": historico["meses_com_gasto"],
            "estouros_anteriores": historico["estouros"],
            "estourou": teto > 0 and gasto > teto + CENTAVO,
            "risco": teto > 0 and not gasto > teto and projecao > teto + CENTAVO,
            "por_dia_restante": (round(livre / dias_restantes, 2)
                                 if teto > 0 and dias_restantes > 0 and livre > 0 else 0.0),
        })
    return sorted(linhas, key=lambda x: (-x["teto"], -x["gasto"]))


def renda_do_mes(competencia: str | None = None) -> dict:
    """O que entra no mês: o que já caiu mais o que ainda está previsto.

    É a âncora do orçamento — planejar sem saber quanto entra é adivinhação.
    """
    competencia = competencia or mes_atual()
    ano, mes = (int(p) for p in competencia.split("-"))
    inicio = f"{competencia}-01"
    fim = date(ano, mes, _ultimo_dia(ano, mes)).isoformat()

    recebido = db.query_one(
        "SELECT COALESCE(SUM(CASE WHEN p.tipo='C' THEN p.valor ELSE -p.valor END),0) AS t"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " JOIN conta c ON c.id = p.conta_id"
        " WHERE c.tipo = 'RECEITA' AND l.data BETWEEN ? AND ?", (inicio, fim))["t"]
    a_receber = db.query_one(
        "SELECT COALESCE(SUM(valor),0) AS t FROM titulo WHERE tipo = 'RECEBER'"
        " AND status = 'ABERTO' AND vencimento BETWEEN ? AND ?", (inicio, fim))["t"]
    recebido, a_receber = round(float(recebido), 2), round(float(a_receber), 2)
    return {"recebido": recebido, "a_receber": a_receber,
            "total": round(recebido + a_receber, 2)}


def resumo_orcamento(competencia: str | None = None) -> dict:
    competencia = competencia or mes_atual()
    linhas = orcamento_do_mes(competencia)
    com_teto = [l for l in linhas if l["teto"] > 0]
    previsto = round(sum(l["teto"] for l in com_teto), 2)
    gasto_com_teto = round(sum(l["gasto"] for l in com_teto), 2)
    gasto_total = round(sum(l["gasto"] for l in linhas), 2)
    comprometido = round(sum(l["comprometido"] for l in linhas), 2)
    projecao = round(sum(l["projecao"] for l in linhas), 2)
    renda = renda_do_mes(competencia)

    return {
        "previsto": previsto,
        "gasto": gasto_com_teto,
        "gasto_total": gasto_total,
        "comprometido": comprometido,
        "sem_teto": round(gasto_total - gasto_com_teto, 2),
        "restante": round(previsto - gasto_com_teto, 2),
        # O que ainda dá para gastar depois de descontar o que já tem dono.
        "livre": round(previsto - gasto_com_teto - sum(l["comprometido"] for l in com_teto), 2),
        "percentual": round(gasto_com_teto / previsto * 100, 1) if previsto else 0.0,
        "projecao": projecao,
        "renda": renda,
        # Quanto do que entra no mês já está planejado para sair.
        "percentual_da_renda": (round(previsto / renda["total"] * 100, 1)
                                if renda["total"] > CENTAVO else 0.0),
        "sobra_prevista": round(renda["total"] - projecao, 2),
        # O número que importa para segurar o gasto: o que ainda dá para gastar
        # sem fechar o mês no vermelho, já descontado o que tem dono.
        "limite_ate_o_fim": round(max(renda["total"] - gasto_total - comprometido, 0.0), 2),
        "estouradas": [l for l in linhas if l["estourou"]],
        "em_risco": [l for l in linhas if l["risco"]],
        "sem_teto_relevantes": [l for l in linhas if l["teto"] <= 0
                                and l["gasto"] + l["comprometido"] > CENTAVO],
        "categorias": linhas,
    }


def plano_sugerido(competencia: str | None = None, meses: int = MESES_BASE_ORCAMENTO,
                   folga_pct: float = 10.0) -> dict:
    """Propõe quanto gastar em cada categoria para o mês caber na renda.

    A base é o **mês anterior**: o retrato mais próximo de como você vive agora.
    O que já está contratado (conta fixa, boleto lançado) não entra na conta de
    corte — ele é piso, não escolha.

    Quando nem o mínimo cabe na renda, o plano corta os variáveis na mesma
    proporção e avisa que o buraco é estrutural.
    """
    competencia = competencia or mes_atual()
    ano, mes = (int(p) for p in competencia.split("-"))
    inicio, fim = f"{competencia}-01", date(ano, mes, _ultimo_dia(ano, mes)).isoformat()
    renda = renda_do_mes(competencia)["total"]
    comprometidos = _comprometido_do_mes(inicio, fim)

    anteriores = [m for m in meses_do_historico() if m < competencia][-meses:]
    linhas = []
    for conta in db.query("SELECT * FROM conta WHERE tipo='DESPESA' AND aceita_lancamento=1"
                          " AND ativo=1 ORDER BY codigo"):
        gastos = []
        for anterior in anteriores:
            ano_a, mes_a = (int(p) for p in anterior.split("-"))
            row = db.query_one(
                "SELECT COALESCE(SUM(CASE WHEN p.tipo='D' THEN p.valor ELSE -p.valor END),0)"
                " AS t FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
                " WHERE p.conta_id = ? AND l.data BETWEEN ? AND ?",
                (conta["id"], f"{anterior}-01",
                 date(ano_a, mes_a, _ultimo_dia(ano_a, mes_a)).isoformat()))
            gastos.append(round(float(row["t"]), 2))

        com_gasto = [g for g in gastos if g > CENTAVO]
        fixo = comprometidos.get(conta["id"], 0.0)
        if not com_gasto and fixo <= CENTAVO:
            continue
        minimo = min(com_gasto) if com_gasto else 0.0
        tipico = (round(sum(com_gasto) / len(com_gasto), 2) if com_gasto else 0.0)
        linhas.append({
            "conta_id": conta["id"],
            "nome": conta["nome"],
            "fixo": fixo,
            "minimo": round(minimo, 2),
            "tipico": tipico,
            # O que dá para cortar é só a parte variável acima do contratado.
            "variavel": round(max(minimo - fixo, 0.0), 2),
            "teto_atual": teto_da_categoria(conta["id"], competencia)[0],
        })

    total_fixo = round(sum(l["fixo"] for l in linhas), 2)
    total_variavel = round(sum(l["variavel"] for l in linhas), 2)
    # Sobra desejada: uma folga da renda que não deveria ser gasta.
    alvo_gasto = round(max(renda * (1 - folga_pct / 100), 0.0), 2) if renda > CENTAVO else 0.0
    disponivel_variavel = round(max(alvo_gasto - total_fixo, 0.0), 2)

    if renda <= CENTAVO or total_variavel <= CENTAVO:
        fator = 1.0
    elif total_variavel > disponivel_variavel:
        fator = round(disponivel_variavel / total_variavel, 4)      # nem o mínimo cabe
    else:
        fator = 1.0

    for linha in linhas:
        sugerido = round(linha["fixo"] + linha["variavel"] * fator, 2)
        linha["sugerido"] = sugerido
        linha["percentual_renda"] = (round(sugerido / renda * 100, 1)
                                     if renda > CENTAVO else 0.0)
        linha["corte"] = round(linha["teto_atual"] - sugerido, 2) if linha["teto_atual"] else 0.0

    linhas.sort(key=lambda l: -l["sugerido"])
    total_sugerido = round(sum(l["sugerido"] for l in linhas), 2)
    return {
        "competencia": competencia,
        "renda": renda,
        "categorias": linhas,
        "total_fixo": total_fixo,
        "total_sugerido": total_sugerido,
        "sobra": round(renda - total_sugerido, 2),
        "percentual_da_renda": (round(total_sugerido / renda * 100, 1)
                                if renda > CENTAVO else 0.0),
        "aperta": fator < 1.0,          # nem gastando o mínimo histórico cabe
        "fator": fator,
    }


def aplicar_plano_sugerido(competencia: str | None = None, so_este_mes: bool = False,
                           meses: int = MESES_BASE_ORCAMENTO) -> int:
    """Grava os tetos do plano. Sem ``so_este_mes``, valem para todos os meses."""
    plano = plano_sugerido(competencia, meses)
    alvo = (competencia or mes_atual()) if so_este_mes else ""
    for linha in plano["categorias"]:
        definir_orcamento(linha["conta_id"], linha["sugerido"], alvo)
    return len(plano["categorias"])


def sugerir_orcamento(conta_id: int, meses: int = MESES_BASE_ORCAMENTO,
                      metodo: str = "mediana") -> float:
    """Teto sugerido para a categoria, a partir do mês anterior.

    Com mais de um mês de base, a mediana é quem manda: a média sozinha é
    distorcida por um mês atípico.
    """
    historico = _historico_da_categoria(conta_id, mes_atual(), meses)
    valor = historico["media"] if metodo == "media" else historico["mediana"]
    return round(max(valor, 0.0), 2)


# --------------------------------------------------------------------------- #
# Metas de poupança
# --------------------------------------------------------------------------- #
def salvar_meta(meta_id: int | None, nome: str, valor_alvo: float, data_alvo: str | None,
                conta_id: int | None, observacao: str = "") -> int:
    nome = nome.strip()
    if not nome:
        raise RegraNegocioError("Dê um nome para o objetivo (ex.: Viagem, Reserva de emergência).")
    if valor_alvo <= 0:
        raise RegraNegocioError("O valor do objetivo deve ser maior que zero.")
    if meta_id:
        db.execute("UPDATE meta SET nome=?, valor_alvo=?, data_alvo=?, conta_id=?, observacao=?"
                   " WHERE id=?",
                   (nome, valor_alvo, data_alvo, conta_id, observacao, meta_id))
        return meta_id
    base = saldo_conta(conta_id) if conta_id else 0.0
    return db.execute(
        "INSERT INTO meta (nome, valor_alvo, data_alvo, conta_id, valor_base, observacao,"
        " criada_em) VALUES (?,?,?,?,?,?,?)",
        (nome, valor_alvo, data_alvo, conta_id, base, observacao,
         datetime.now().isoformat(timespec="seconds")))


def listar_metas() -> list[dict]:
    hoje = date.today()
    saida = []
    for meta in db.query("SELECT * FROM meta ORDER BY concluida, data_alvo IS NULL, data_alvo"):
        if meta["conta_id"]:
            guardado = round(saldo_conta(meta["conta_id"]) - float(meta["valor_base"]), 2)
        else:
            guardado = 0.0
        guardado = max(guardado, 0.0)
        alvo = float(meta["valor_alvo"])
        falta = round(max(alvo - guardado, 0.0), 2)
        meses_restantes = 0
        if meta["data_alvo"]:
            alvo_data = date.fromisoformat(meta["data_alvo"])
            meses_restantes = max((alvo_data.year - hoje.year) * 12
                                  + alvo_data.month - hoje.month, 0)
        saida.append({
            "id": meta["id"],
            "nome": meta["nome"],
            "valor_alvo": alvo,
            "data_alvo": meta["data_alvo"],
            "conta_id": meta["conta_id"],
            "guardado": guardado,
            "falta": falta,
            "percentual": round(guardado / alvo * 100, 1) if alvo else 0.0,
            "concluida": bool(meta["concluida"]) or falta <= CENTAVO,
            "meses_restantes": meses_restantes,
            "por_mes": round(falta / meses_restantes, 2) if meses_restantes else falta,
            "atrasada": bool(meta["data_alvo"] and date.fromisoformat(meta["data_alvo"]) < hoje
                             and falta > CENTAVO),
        })
    return saida


def excluir_meta(meta_id: int) -> None:
    db.execute("DELETE FROM meta WHERE id = ?", (meta_id,))


# --------------------------------------------------------------------------- #
# Compras parceladas no cartão
# --------------------------------------------------------------------------- #
def criar_compra_parcelada(
    descricao: str,
    cartao_id: int,
    categoria_id: int,
    valor_total: float,
    parcelas: int,
    primeira_competencia: str,
    data_compra: str | None = None,
    centro_custo_id: int | None = None,
) -> int:
    """Distribui a compra pelas próximas faturas, uma parcela por mês."""
    descricao = descricao.strip()
    if not descricao:
        raise RegraNegocioError("Descreva a compra (ex.: Geladeira nova).")
    if valor_total <= 0:
        raise RegraNegocioError("O valor da compra deve ser maior que zero.")
    if parcelas < 1:
        raise RegraNegocioError("Informe em quantas vezes a compra foi feita.")
    cartao = obter_conta(cartao_id)
    if cartao is None or cartao["tipo"] != "PASSIVO":
        raise RegraNegocioError("Escolha o cartão de crédito usado na compra.")

    data_compra = data_compra or hoje_iso()
    valor_parcela = round(valor_total / parcelas, 2)
    compra_id = db.execute(
        "INSERT INTO compra_parcelada (descricao, cartao_id, categoria_id, valor_total,"
        " parcelas, valor_parcela, primeira, data_compra, centro_custo_id, criada_em)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (descricao, cartao_id, categoria_id, valor_total, parcelas, valor_parcela,
         primeira_competencia, data_compra, centro_custo_id,
         datetime.now().isoformat(timespec="seconds")))

    base = date.fromisoformat(f"{primeira_competencia}-01")
    dia_compra = date.fromisoformat(data_compra).day
    acumulado = 0.0
    for numero in range(1, parcelas + 1):
        # A última parcela absorve os centavos da divisão.
        valor = (round(valor_total - acumulado, 2) if numero == parcelas else valor_parcela)
        acumulado = round(acumulado + valor, 2)
        mes = somar_meses(base, numero - 1)
        data = _data_no_mes(mes, dia_compra)
        lancamento_id = salvar_lancamento(
            None, data.isoformat(),
            f"{descricao} ({numero}/{parcelas})",
            [Partida(categoria_id, "D", valor), Partida(cartao_id, "C", valor)],
            documento=f"PARC-{compra_id}", centro_custo_id=centro_custo_id, origem="PARCELA")
        db.execute("UPDATE lancamento SET compra_id = ? WHERE id = ?",
                   (compra_id, lancamento_id))
    return compra_id


def listar_compras_parceladas(apenas_ativas: bool = True) -> list[dict]:
    hoje = hoje_iso()
    saida = []
    for compra in db.query(
            "SELECT cp.*, ca.nome AS cartao, cat.nome AS categoria FROM compra_parcelada cp"
            " JOIN conta ca ON ca.id = cp.cartao_id JOIN conta cat ON cat.id = cp.categoria_id"
            " ORDER BY cp.data_compra DESC"):
        pagas = db.query_one(
            "SELECT COUNT(*) AS c, COALESCE(SUM(valor),0) AS t FROM lancamento"
            " WHERE compra_id = ? AND data <= ?", (compra["id"], hoje))
        falta = round(float(compra["valor_total"]) - float(pagas["t"]), 2)
        if apenas_ativas and falta <= CENTAVO:
            continue
        saida.append({
            "id": compra["id"],
            "descricao": compra["descricao"],
            "cartao": compra["cartao"],
            "categoria": compra["categoria"],
            "valor_total": float(compra["valor_total"]),
            "parcelas": int(compra["parcelas"]),
            "valor_parcela": float(compra["valor_parcela"]),
            "lancadas": int(pagas["c"]),
            "falta": max(falta, 0.0),
            "data_compra": compra["data_compra"],
        })
    return saida


def excluir_compra_parcelada(compra_id: int) -> int:
    """Remove as parcelas ainda não lançadas (futuras) e, se não sobrar nenhuma, a compra."""
    hoje = hoje_iso()
    with db.transaction() as conn:
        cursor = conn.execute("DELETE FROM lancamento WHERE compra_id = ? AND data > ?",
                              (compra_id, hoje))
        removidas = cursor.rowcount
        restantes = conn.execute("SELECT COUNT(*) AS c FROM lancamento WHERE compra_id = ?",
                                 (compra_id,)).fetchone()["c"]
        if not restantes:
            conn.execute("DELETE FROM compra_parcelada WHERE id = ?", (compra_id,))
    return removidas


def ajustar_compra_parcelada(compra_id: int, novo_total: float) -> int:
    """Muda o valor de uma compra parcelada preservando o que já foi faturado.

    As parcelas que já entraram numa fatura fechada não são tocadas — elas são
    história. O que sobra do novo total é dividido entre as parcelas seguintes.
    Devolve quantas parcelas foram recalculadas.
    """
    compra = db.query_one("SELECT * FROM compra_parcelada WHERE id = ?", (compra_id,))
    if compra is None:
        raise RegraNegocioError("Compra parcelada não encontrada.")
    if novo_total <= 0:
        raise RegraNegocioError("O novo valor total deve ser maior que zero.")

    corte = _ultimo_fechamento(compra["cartao_id"])
    lancamentos = db.query(
        "SELECT * FROM lancamento WHERE compra_id = ? ORDER BY data, id", (compra_id,))
    faturadas = [l for l in lancamentos if l["data"] <= corte]
    futuras = [l for l in lancamentos if l["data"] > corte]
    if not futuras:
        raise RegraNegocioError(
            "Todas as parcelas já entraram em faturas fechadas: não há o que alterar.")

    ja_cobrado = round(sum(float(l["valor"]) for l in faturadas), 2)
    restante = round(novo_total - ja_cobrado, 2)
    if restante <= 0:
        raise RegraNegocioError(
            f"As parcelas já faturadas somam {moeda(ja_cobrado)} — o novo total precisa"
            " ser maior que isso.")

    nova_parcela = round(restante / len(futuras), 2)
    acumulado = 0.0
    with db.transaction() as conn:
        for indice, lancamento in enumerate(futuras, start=1):
            valor = (round(restante - acumulado, 2) if indice == len(futuras)
                     else nova_parcela)
            acumulado = round(acumulado + valor, 2)
            conn.execute("UPDATE lancamento SET valor = ? WHERE id = ?",
                         (valor, lancamento["id"]))
            conn.execute("UPDATE partida SET valor = ? WHERE lancamento_id = ?",
                         (valor, lancamento["id"]))
        conn.execute("UPDATE compra_parcelada SET valor_total = ?, valor_parcela = ?"
                     " WHERE id = ?", (novo_total, nova_parcela, compra_id))
    return len(futuras)


def _ultimo_fechamento(cartao_id: int) -> str:
    """Data da última fatura fechada — o que veio antes dela é intocável."""
    row = db.query_one("SELECT MAX(fechamento) AS f FROM fatura WHERE conta_id = ? AND fechada = 1",
                       (cartao_id,))
    return row["f"] if row and row["f"] else "1900-01-01"


def previsao_faturas(cartao_id: int, meses: int = 6) -> list[dict]:
    """As próximas faturas, com o que já está agendado para cair em cada uma.

    Junta as parcelas de compras já lançadas e as contas fixas que são pagas
    por este cartão. Serve para enxergar o mês em que o cartão aperta.
    """
    cartao = obter_conta(cartao_id)
    if cartao is None:
        raise RegraNegocioError("Cartão não encontrado.")
    dia_fechamento = int(cartao["dia_fechamento"] or 0)
    dia_vencimento = int(cartao["dia_vencimento"] or dia_fechamento or 0)

    hoje = date.today()
    corte = _ultimo_fechamento(cartao_id)
    saida = []
    for indice in range(meses):
        referencia = somar_meses(hoje, indice)
        competencia = referencia.strftime("%Y-%m")
        if dia_fechamento:
            fechamento = _data_no_mes(referencia, dia_fechamento)
            inicio = (date.fromisoformat(corte) + timedelta(days=1)).isoformat() \
                if indice == 0 else _data_no_mes(somar_meses(referencia, -1),
                                                 dia_fechamento).isoformat()
            base_venc = (fechamento if dia_vencimento > fechamento.day
                         else somar_meses(fechamento, 1))
            vencimento = _data_no_mes(base_venc, dia_vencimento).isoformat()
        else:   # sem ciclo definido: usa o mês cheio
            fechamento = _fim_do_mes_data(referencia)
            inicio = f"{competencia}-01"
            vencimento = fechamento.isoformat()
        if fechamento.isoformat() <= corte:
            continue

        parcelas = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) AS t FROM partida p"
            " JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ? AND p.tipo='C' AND l.compra_id IS NOT NULL"
            " AND l.data BETWEEN ? AND ?",
            (cartao_id, inicio, fechamento.isoformat()))["t"]
        avulsos = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) AS t FROM partida p"
            " JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ? AND p.tipo='C' AND l.compra_id IS NULL"
            " AND l.data BETWEEN ? AND ?",
            (cartao_id, inicio, fechamento.isoformat()))["t"]
        fixas = db.query_one(
            "SELECT COALESCE(SUM(valor),0) AS t FROM titulo"
            " WHERE conta_pagamento_id = ? AND status = 'ABERTO'"
            " AND vencimento BETWEEN ? AND ?",
            (cartao_id, inicio, fechamento.isoformat()))["t"]

        anterior = saldo_conta(cartao_id) if indice == 0 else 0.0
        parcelas, avulsos, fixas = (round(float(parcelas), 2), round(float(avulsos), 2),
                                    round(float(fixas), 2))
        saida.append({
            "mes": competencia,
            "nome": mes_nome(competencia),
            "fechamento": fechamento.isoformat(),
            "vencimento": vencimento,
            "saldo_atual": round(anterior, 2),
            "parcelas": parcelas,
            "outras_compras": avulsos,
            "contas_fixas": fixas,
            "previsto": round(anterior + parcelas + avulsos + fixas, 2),
        })
    return saida


def _fim_do_mes_data(referencia: date) -> date:
    return date(referencia.year, referencia.month,
                _ultimo_dia(referencia.year, referencia.month))


def comprometido_por_mes(cartao_id: int, meses: int = 6) -> list[dict]:
    """Quanto das próximas faturas já está tomado por parcelas."""
    hoje = date.today()
    saida = []
    for indice in range(meses):
        competencia = somar_meses(hoje, indice).strftime("%Y-%m")
        ano, mes = (int(p) for p in competencia.split("-"))
        row = db.query_one(
            "SELECT COALESCE(SUM(p.valor),0) AS t FROM partida p"
            " JOIN lancamento l ON l.id = p.lancamento_id"
            " WHERE p.conta_id = ? AND p.tipo='C' AND l.compra_id IS NOT NULL"
            " AND l.data BETWEEN ? AND ?",
            (cartao_id, f"{competencia}-01", date(ano, mes, _ultimo_dia(ano, mes)).isoformat()))
        saida.append({"mes": competencia, "nome": mes_nome(competencia),
                      "parcelas": round(float(row["t"]), 2)})
    return saida


def limite_do_cartao(conta_id: int) -> dict:
    """Limite, quanto já foi usado e quanto ainda dá para gastar.

    Cartão com limite garantido (o banco segura uma aplicação sua como garantia)
    não tem limite fixo: ele vale o que estiver aplicado na conta dada em
    garantia — se a aplicação render, o limite sobe junto.
    """
    conta = obter_conta(conta_id)
    garantia = obter_conta(conta["conta_garantia_id"]) if conta["conta_garantia_id"] else None
    if garantia is not None:
        limite = round(saldo_conta(garantia["id"]), 2)
    else:
        limite = round(float(conta["limite"] or 0), 2)
    usado = max(saldo_conta(conta_id), 0.0)
    return {"limite": limite, "usado": usado,
            "disponivel": round(limite - usado, 2) if limite else 0.0,
            "percentual": round(usado / limite * 100, 1) if limite else 0.0,
            "garantia_id": garantia["id"] if garantia is not None else None,
            "garantia_nome": garantia["nome"] if garantia is not None else ""}


def definir_garantia_cartao(cartao_id: int, conta_garantia_id: int | None) -> None:
    """Amarra (ou desamarra) a aplicação que garante o limite do cartão."""
    cartao = obter_conta(cartao_id)
    if cartao is None or cartao["tipo"] != "PASSIVO":
        raise RegraNegocioError("A garantia só vale para cartão de crédito.")
    if conta_garantia_id is not None:
        garantia = obter_conta(conta_garantia_id)
        if garantia is None or garantia["tipo"] != "ATIVO":
            raise RegraNegocioError("Escolha a aplicação que ficou em garantia.")
        if garantia["id"] == cartao["id"]:
            raise RegraNegocioError("Um cartão não pode garantir a si mesmo.")
    db.execute("UPDATE conta SET conta_garantia_id = ? WHERE id = ?",
               (conta_garantia_id, cartao_id))


def definir_conta_da_fatura(cartao_id: int, conta_pagamento_id: int | None) -> None:
    """De qual conta sai o dinheiro que paga a fatura deste cartão.

    Vale para as próximas faturas e também para as que já estão em aberto.
    """
    cartao = obter_conta(cartao_id)
    if cartao is None or cartao["tipo"] != "PASSIVO":
        raise RegraNegocioError("Escolha um cartão de crédito.")
    if conta_pagamento_id is not None:
        conta = obter_conta(conta_pagamento_id)
        if conta is None or conta["tipo"] != "ATIVO":
            raise RegraNegocioError("A fatura precisa ser paga por uma conta de dinheiro.")
    with db.transaction() as conn:
        conn.execute("UPDATE conta SET conta_pagamento_id = ? WHERE id = ?",
                     (conta_pagamento_id, cartao_id))
        conn.execute(
            "UPDATE titulo SET conta_pagamento_id = ? WHERE status = 'ABERTO'"
            " AND id IN (SELECT titulo_id FROM fatura WHERE conta_id = ?)",
            (conta_pagamento_id, cartao_id))


def definir_dados_do_cartao(conta_id: int, limite: float | None = None,
                            validade: str | None = None) -> None:
    """Grava o limite combinado e a validade impressa no cartão."""
    if obter_conta(conta_id) is None:
        raise RegraNegocioError("Cartão não encontrado.")
    if limite is not None:
        if limite < 0:
            raise RegraNegocioError("O limite não pode ser negativo.")
        db.execute("UPDATE conta SET limite = ? WHERE id = ?", (round(limite, 2), conta_id))
    if validade is not None:
        validade = validade.strip()
        if validade and not _validade_valida(validade):
            raise RegraNegocioError("Escreva a validade como MM/AAAA (ex.: 07/2030).")
        db.execute("UPDATE conta SET validade = ? WHERE id = ?", (validade, conta_id))


def _validade_valida(texto: str) -> bool:
    partes = texto.split("/")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        return False
    mes, ano = int(partes[0]), int(partes[1])
    return 1 <= mes <= 12 and 2000 <= ano <= 2100


def cartao_vencido(validade: str, referencia: str | None = None) -> bool:
    """A validade impressa já passou?"""
    if not validade or not _validade_valida(validade):
        return False
    mes, ano = (int(p) for p in validade.split("/"))
    hoje = date.fromisoformat(referencia or hoje_iso())
    return (ano, mes) < (hoje.year, hoje.month)


def listar_cartoes() -> list[dict]:
    """Todos os cartões — de crédito e pré-pagos — com limite, fatura e validade."""
    saida = []
    for conta in listar_carteiras():
        rotulo = (conta["observacao"] or "").lower()
        # Cartão de crédito é a dívida com ciclo de fatura — empréstimo e
        # financiamento também são passivos, mas não entram nesta tela.
        credito = conta["tipo"] == "PASSIVO" and (
            "cartão" in rotulo or conta["dia_fechamento"] or conta["conta_garantia_id"]
            or conta["codigo"] == CODIGO_CARTAO_CREDITO)
        pre_pago = "pré-pago" in rotulo or conta["codigo"] == CODIGO_PRE_PAGO
        if not credito and not pre_pago:
            continue
        # As contas genéricas do plano padrão só aparecem depois de configuradas
        # ou usadas — senão a lista nasce com cartões que ninguém cadastrou.
        if (abs(saldo_conta(conta["id"])) < CENTAVO
                and not conta["dia_fechamento"] and not float(conta["limite"] or 0)
                and not conta["validade"] and not conta["conta_garantia_id"]
                and not db.query_one("SELECT 1 FROM partida WHERE conta_id = ? LIMIT 1",
                                     (conta["id"],))):
            continue

        limite = limite_do_cartao(conta["id"]) if credito else {}
        aberta = None
        if credito:
            aberta = db.query_one(
                "SELECT f.*, t.vencimento, t.valor, t.status FROM fatura f"
                " JOIN titulo t ON t.id = f.titulo_id"
                " WHERE f.conta_id = ? AND t.status = 'ABERTO'"
                " ORDER BY t.vencimento LIMIT 1", (conta["id"],))

        saida.append({
            "id": conta["id"],
            "nome": conta["nome"],
            "instituicao": conta["instituicao"] or "",
            "credito": credito,
            "tipo_texto": ("Pré-pago" if not credito
                           else "Saldo em garantia" if conta["conta_garantia_id"]
                           else "Crédito"),
            "saldo": round(saldo_conta(conta["id"]), 2),
            "limite": limite.get("limite", 0.0),
            "usado": limite.get("usado", 0.0),
            "disponivel": limite.get("disponivel", 0.0),
            "percentual": limite.get("percentual", 0.0),
            "garantia_id": limite.get("garantia_id"),
            "garantia_nome": limite.get("garantia_nome", ""),
            "dia_fechamento": conta["dia_fechamento"],
            "dia_vencimento": conta["dia_vencimento"],
            "juros_rotativo": float(conta["juros_rotativo"] or 0),
            "validade": conta["validade"] or "",
            "vencido": cartao_vencido(conta["validade"] or ""),
            "fatura_aberta": round(float(aberta["valor"]), 2) if aberta else 0.0,
            "fatura_vence": aberta["vencimento"] if aberta else None,
            "fatura_titulo_id": aberta["titulo_id"] if aberta else None,
            "gasto_desde_fechamento": _gasto_do_ciclo(conta) if credito else 0.0,
        })
    return saida


def _gasto_do_ciclo(cartao: db.sqlite3.Row) -> float:
    """Compras feitas depois do último fechamento — a fatura que ainda vai fechar."""
    ultima = db.query_one("SELECT MAX(fechamento) AS f FROM fatura WHERE conta_id = ? AND fechada = 1",
                          (cartao["id"],))
    inicio = (date.fromisoformat(ultima["f"]) + timedelta(days=1)).isoformat() \
        if ultima and ultima["f"] else "1900-01-01"
    row = db.query_one(
        "SELECT COALESCE(SUM(CASE WHEN p.tipo='C' THEN p.valor ELSE -p.valor END),0) AS t"
        " FROM partida p JOIN lancamento l ON l.id = p.lancamento_id"
        " WHERE p.conta_id = ? AND l.data >= ?", (cartao["id"], inicio))
    return round(max(float(row["t"]), 0.0), 2)


def resumo_cartoes() -> dict:
    cartoes = listar_cartoes()
    credito = [c for c in cartoes if c["credito"]]
    return {
        "cartoes": cartoes,
        "quantidade": len(cartoes),
        "limite_total": round(sum(c["limite"] for c in credito), 2),
        "usado_total": round(sum(c["usado"] for c in credito), 2),
        "livre_total": round(sum(c["disponivel"] for c in credito), 2),
        "fatura_aberta": round(sum(c["fatura_aberta"] for c in credito), 2),
        "saldo_pre_pago": round(sum(c["saldo"] for c in cartoes if not c["credito"]), 2),
        "vencidos": [c for c in cartoes if c["vencido"]],
    }


# --------------------------------------------------------------------------- #
# Previsão de saldo
# --------------------------------------------------------------------------- #
def previsao_saldo(dias: int = 90) -> dict:
    """Projeta o dinheiro disponível dia a dia somando o que já está agendado.

    Considera: saldo de hoje das carteiras, contas a pagar e a receber em aberto,
    contas fixas ainda não geradas e parcelas de compras já lançadas no futuro.
    """
    hoje = date.today()
    fim = hoje + timedelta(days=dias)
    saldo = total_disponivel()["tem"]

    eventos: dict[str, list[dict]] = {}

    def agendar(data_iso: str, descricao: str, valor: float, tipo: str) -> None:
        if not hoje.isoformat() < data_iso <= fim.isoformat():
            return
        eventos.setdefault(data_iso, []).append(
            {"descricao": descricao, "valor": valor, "tipo": tipo})

    for titulo in db.query(
            "SELECT * FROM titulo WHERE status='ABERTO' AND vencimento <= ?", (fim.isoformat(),)):
        encargos = encargos_do_titulo(titulo)
        valor = encargos["valor_atualizado"]
        data = max(titulo["vencimento"], hoje.isoformat())
        if titulo["tipo"] == "PAGAR":
            agendar(data, titulo["descricao"], -valor, "conta")
        else:
            agendar(data, titulo["descricao"], valor, "recebimento")

    # Parcelas de cartão não entram direto: elas aumentam a dívida do cartão e
    # saem do bolso quando a fatura vence — momento já coberto pelos títulos acima.

    linhas, menor, menor_data = [], saldo, hoje.isoformat()
    atual = hoje
    while atual <= fim:
        chave = atual.isoformat()
        do_dia = eventos.get(chave, [])
        saldo = round(saldo + sum(e["valor"] for e in do_dia), 2)
        if saldo < menor:
            menor, menor_data = saldo, chave
        if do_dia or atual == hoje or atual == fim:
            linhas.append({"data": chave, "saldo": saldo, "eventos": do_dia})
        atual += timedelta(days=1)

    return {
        "hoje": total_disponivel()["tem"],
        "final": saldo,
        "menor_saldo": menor,
        "menor_data": menor_data,
        "negativa": menor < 0,
        "linhas": linhas,
    }


def previsao_por_conta(ate: str | None = None) -> dict:
    """Projeta o saldo de cada conta de dinheiro até a data informada.

    Cada título é descontado da conta em que ele foi marcado para sair — o que
    sai do C6 não some do Nubank. Títulos sem conta definida ficam separados,
    porque não dá para saber de onde vai sair o dinheiro.
    """
    ate = ate or ultimo_dia_mes()
    hoje = hoje_iso()

    contas = []
    por_conta: dict[int, dict] = {}
    for conta in listar_carteiras():
        if grupo_da_conta(conta) != "disponivel":
            continue
        linha = {
            "id": conta["id"],
            "nome": conta["nome"],
            "saldo_hoje": saldo_conta(conta["id"], ate=hoje),
            "a_pagar": 0.0,
            "a_receber": 0.0,
        }
        contas.append(linha)
        por_conta[conta["id"]] = linha

    sem_conta = {"a_pagar": 0.0, "a_receber": 0.0}
    for titulo in db.query(
            "SELECT * FROM titulo WHERE status='ABERTO' AND vencimento <= ?", (ate,)):
        encargos = encargos_do_titulo(titulo)
        valor = encargos["valor_atualizado"]
        destino = por_conta.get(titulo["conta_pagamento_id"])
        if destino is None:
            # Conta não escolhida, ou escolhida uma que não é dinheiro (cartão,
            # crédito de loja): não mexe no dinheiro disponível.
            if titulo["conta_pagamento_id"] is None:
                sem_conta["a_pagar" if titulo["tipo"] == "PAGAR" else "a_receber"] += valor
            continue
        destino["a_pagar" if titulo["tipo"] == "PAGAR" else "a_receber"] += valor

    for linha in contas:
        linha["a_pagar"] = round(linha["a_pagar"], 2)
        linha["a_receber"] = round(linha["a_receber"], 2)
        linha["previsto"] = round(linha["saldo_hoje"] + linha["a_receber"] - linha["a_pagar"], 2)
        linha["negativa"] = linha["previsto"] < -CENTAVO
    contas.sort(key=lambda c: -c["previsto"])

    return {
        "ate": ate,
        "contas": contas,
        "saldo_hoje": round(sum(c["saldo_hoje"] for c in contas), 2),
        "previsto": round(sum(c["previsto"] for c in contas), 2),
        "a_pagar": round(sum(c["a_pagar"] for c in contas), 2),
        "a_receber": round(sum(c["a_receber"] for c in contas), 2),
        "sem_conta_pagar": round(sem_conta["a_pagar"], 2),
        "sem_conta_receber": round(sem_conta["a_receber"], 2),
        "contas_negativas": [c for c in contas if c["negativa"]],
    }


def previsao_mensal(meses: int = 6) -> list[dict]:
    """Resumo mês a mês do que já está agendado para o futuro."""
    hoje = date.today()
    saldo = total_disponivel()["tem"]
    saida = []
    for indice in range(meses):
        referencia = somar_meses(hoje, indice)
        competencia = referencia.strftime("%Y-%m")
        ano, mes = referencia.year, referencia.month
        inicio = max(hoje.isoformat(), f"{competencia}-01")
        fim = date(ano, mes, _ultimo_dia(ano, mes)).isoformat()

        row = db.query_one(
            "SELECT COALESCE(SUM(CASE WHEN tipo='PAGAR' THEN valor ELSE 0 END),0) AS pagar,"
            " COALESCE(SUM(CASE WHEN tipo='RECEBER' THEN valor ELSE 0 END),0) AS receber"
            " FROM titulo WHERE status='ABERTO' AND vencimento BETWEEN ? AND ?", (inicio, fim))
        pagar = round(float(row["pagar"]), 2)
        receber = round(float(row["receber"]), 2)
        saldo = round(saldo + receber - pagar, 2)
        saida.append({"mes": competencia, "nome": mes_nome(competencia),
                      "pagar": pagar, "receber": receber,
                      "resultado": round(receber - pagar, 2), "saldo_projetado": saldo})
    return saida


# --------------------------------------------------------------------------- #
# Painel
# --------------------------------------------------------------------------- #
def resumo_dashboard() -> dict:
    inicio, fim = primeiro_dia_mes(), ultimo_dia_mes()
    hoje = hoje_iso()
    # O painel fala do mês corrente: tudo o que vence até o fim dele, incluindo
    # o que já está atrasado. Somar "30 dias corridos" trazia contas do mês seguinte.
    limite = fim

    carteiras = total_disponivel(hoje)
    disponivel = carteiras["tem"]

    mes = dre(inicio, fim)
    bal = balanco(hoje)

    def somar(tipo: str, **filtros: str) -> float:
        clausulas = ["tipo = ?", "status = 'ABERTO'"]
        params: list = [tipo]
        if "ate" in filtros:
            clausulas.append("vencimento <= ?")
            params.append(filtros["ate"])
        if "desde" in filtros:
            clausulas.append("vencimento >= ?")
            params.append(filtros["desde"])
        row = db.query_one(
            f"SELECT COALESCE(SUM(valor),0) AS t FROM titulo WHERE {' AND '.join(clausulas)}",
            tuple(params),
        )
        return round(float(row["t"]), 2)

    anterior_ref = date.fromisoformat(inicio) - timedelta(days=1)
    mes_anterior = dre(primeiro_dia_mes(anterior_ref), ultimo_dia_mes(anterior_ref))

    def variacao(atual: float, passado: float) -> float | None:
        if abs(passado) < CENTAVO:
            return None
        return round((atual - passado) / abs(passado) * 100, 1)

    orcamento = resumo_orcamento()
    metas = listar_metas()
    metas_abertas = [m for m in metas if not m["concluida"]]

    # Detalhe conta a conta, para o painel mostrar de onde vem cada saldo.
    contas_detalhe: list[dict] = []
    for conta in listar_carteiras():
        saldo = saldo_conta(conta["id"], ate=hoje)
        grupo = grupo_da_conta(conta)
        if abs(saldo) < CENTAVO:
            # Conta zerada só aparece se tiver sido usada alguma vez.
            usada = db.query_one(
                "SELECT 1 AS x FROM partida WHERE conta_id = ? LIMIT 1", (conta["id"],))
            if not usada:
                continue
        contas_detalhe.append({
            "id": conta["id"],
            "nome": conta["nome"],
            "instituicao": conta["instituicao"] or "",
            "tipo": conta["observacao"] or "",
            "grupo": grupo,
            "saldo": round(saldo, 2),
        })
    contas_detalhe.sort(key=lambda c: (c["grupo"] != "disponivel", -c["saldo"]))

    dividas = listar_dividas()
    investimentos = resumo_investimentos()
    previsao = previsao_por_conta(fim)
    # O saldo previsto de cada conta entra na própria linha da conta.
    previstos = {c["id"]: c for c in previsao["contas"]}
    for linha in contas_detalhe:
        projecao = previstos.get(linha["id"])
        linha["previsto"] = projecao["previsto"] if projecao else None
        linha["a_pagar"] = projecao["a_pagar"] if projecao else 0.0

    return {
        "disponivel": round(disponivel, 2),
        "investido": carteiras["investido"],
        "outros_saldos": carteiras["outros"],
        "divida_cartoes": carteiras["deve"],
        "contas": contas_detalhe,
        "dividas": dividas,
        "total_dividas": round(sum(d["saldo"] for d in dividas), 2),
        "investimentos": investimentos,
        "metas": metas,
        "previsao": previsao,
        "saldo_previsto_fim_mes": previsao["previsto"],
        "orcamento_restante": orcamento["restante"],
        "receitas_mes_anterior": mes_anterior["total_receitas"],
        "despesas_mes_anterior": mes_anterior["total_despesas"],
        "resultado_mes_anterior": mes_anterior["resultado"],
        "var_receitas": variacao(mes["total_receitas"], mes_anterior["total_receitas"]),
        "var_despesas": variacao(mes["total_despesas"], mes_anterior["total_despesas"]),
        "var_resultado": variacao(mes["resultado"], mes_anterior["resultado"]),
        "orcamento_previsto": orcamento["previsto"],
        "orcamento_gasto": orcamento["gasto"],
        "orcamento_percentual": orcamento["percentual"],
        "categorias_estouradas": len(orcamento["estouradas"]),
        "metas_abertas": len(metas_abertas),
        "receitas_mes": mes["total_receitas"],
        "despesas_mes": mes["total_despesas"],
        "resultado_mes": mes["resultado"],
        "a_pagar_30": somar("PAGAR", ate=limite),
        "a_receber_30": somar("RECEBER", ate=limite),
        "vencidos_pagar": somar("PAGAR", ate=_dia_anterior(hoje)),
        "vencidos_receber": somar("RECEBER", ate=_dia_anterior(hoje)),
        "patrimonio_liquido": bal["total_pl"],
        "total_ativo": bal["total_ativo"],
        "total_passivo": bal["total_passivo"],
        "qtd_lancamentos": int(db.query_one("SELECT COUNT(*) AS c FROM lancamento")["c"]),
    }


def proximos_vencimentos(dias: int = 30, limite: int = 15) -> list[db.sqlite3.Row]:
    fim = (date.today() + timedelta(days=dias)).isoformat()
    return db.query(
        "SELECT t.*, cp.nome AS conta_pagamento_nome FROM titulo t"
        " LEFT JOIN conta cp ON cp.id = t.conta_pagamento_id"
        " WHERE t.status='ABERTO' AND t.vencimento <= ?"
        " ORDER BY t.vencimento LIMIT ?",
        (fim, limite),
    )

