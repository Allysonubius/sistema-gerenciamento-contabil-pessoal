"""Monta uma base FICTÍCIA para demonstração/gravação.

Pessoa inventada: Ana Paula Ribeiro, analista, salário mensal fixo.

Só roda pelo código-fonte. O executável distribuído não carrega este arquivo e
não tem como chegar nesta base: quem usa o programa instalado vê sempre os
próprios dados, em `%LOCALAPPDATA%\\SistemaContabil`.

Uso:
    python demo\\popular_demo.py           # recria a base do zero
"""
from __future__ import annotations

import os
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEMO_DIR = Path(os.environ.get("DEMO_DIR", RAIZ / "demo"))

if getattr(sys, "frozen", False):                       # pragma: no cover
    raise SystemExit("A demonstração não roda pelo executável — use o código-fonte.")

# Trava de segurança: a demonstração nunca pode apontar para a pasta de dados
# real do usuário.
real = Path(os.environ.get("LOCALAPPDATA", "")) / "SistemaContabil"
if (DEMO_DIR / "SistemaContabil").resolve() == real.resolve():
    raise SystemExit("DEMO_DIR aponta para a pasta de dados real. Escolha outra.")

# O app guarda tudo em %LOCALAPPDATA%\SistemaContabil: apontando a variável para
# a pasta da demonstração, o banco real fica intocado.
DEMO_DIR.mkdir(parents=True, exist_ok=True)
if (DEMO_DIR / "SistemaContabil").exists():
    shutil.rmtree(DEMO_DIR / "SistemaContabil")
os.environ["LOCALAPPDATA"] = str(DEMO_DIR)
sys.path.insert(0, str(RAIZ))

from app import db, services                                    # noqa: E402
from app.services import Partida                                # noqa: E402

random.seed(7)          # a demonstração precisa sair igual toda vez
HOJE = date.today()
MES = HOJE.strftime("%Y-%m")


def mes_menos(n: int) -> str:
    """n positivo volta no tempo; n negativo avança."""
    indice = (HOJE.year * 12 + HOJE.month - 1) - n
    return f"{indice // 12}-{indice % 12 + 1:02d}"


def dia(competencia: str, d: int) -> str:
    ano, mes = (int(p) for p in competencia.split("-"))
    ultimo = services._ultimo_dia(ano, mes)
    return date(ano, mes, min(d, ultimo)).isoformat()


def cat(codigo: str) -> int:
    return services._conta_por_codigo(codigo)


def gasto(data_iso: str, descricao: str, categoria: str, valor: float, conta: int) -> int:
    return services.salvar_lancamento(
        None, data_iso, descricao,
        [Partida(cat(categoria), "D", valor), Partida(conta, "C", valor)])


def receita(data_iso: str, descricao: str, categoria: str, valor: float, conta: int) -> int:
    return services.salvar_lancamento(
        None, data_iso, descricao,
        [Partida(conta, "D", valor), Partida(cat(categoria), "C", valor)])


def main() -> None:
    db.get_connection()
    db.set_config("empresa", "Ana Paula Ribeiro")
    # Marca lida pelo programa para exibir a tarja "DEMONSTRAÇÃO".
    from app.config import DEMO_FLAG
    DEMO_FLAG.write_text("base ficticia para demonstracao\n", encoding="utf-8")

    # ------------------------------------------------------------------ #
    # 1. Contas de dinheiro
    # ------------------------------------------------------------------ #
    inicio = dia(mes_menos(11), 1)
    banco = services.criar_carteira("Banco Azul", "Conta corrente", "Banco Azul",
                                    2400.00, inicio)
    carteira = services.criar_carteira("Carteira", "Dinheiro em espécie", "", 180.00, inicio)
    poupanca = services.criar_carteira("Poupança", "Poupança", "Banco Azul", 2500.00, inicio)
    vale = services.criar_carteira("Vale Refeição",
                                   "Cartão pré-pago (você carrega antes de usar)",
                                   "Ticket", 260.00, inicio)
    services.definir_conta_dinheiro(poupanca, True)

    # Investimentos: um CDB que serve de garantia do cartão e um fundo.
    cdb = services.criar_carteira("CDB Garantido", "Investimento", "Banco Azul",
                                  3000.00, inicio, conta_origem_id=banco)
    fundo = services.criar_carteira("Tesouro Selic", "Investimento", "Corretora XP",
                                    4000.00, inicio, conta_origem_id=banco)
    for n in range(10, 0, -1):
        services.registrar_rendimento(cdb, round(random.uniform(18, 26), 2),
                                      dia(mes_menos(n), 1))
        services.registrar_rendimento(fundo, round(random.uniform(30, 44), 2),
                                      dia(mes_menos(n), 1))

    # ------------------------------------------------------------------ #
    # 2. Cartões
    # ------------------------------------------------------------------ #
    cartao = services.criar_carteira("Cartão Azul",
                                     "Cartão de crédito (você paga a fatura depois)",
                                     "Banco Azul")
    services.configurar_cartao(cartao, dia_fechamento=20, dia_vencimento=28,
                               juros_rotativo=12.0)
    services.definir_conta_da_fatura(cartao, banco)
    services.definir_dados_do_cartao(cartao, limite=4500.0, validade="09/2030")

    garantido = services.criar_carteira("Cartão Garantido",
                                        "Cartão de crédito (você paga a fatura depois)",
                                        "Banco Azul")
    services.configurar_cartao(garantido, dia_fechamento=15, dia_vencimento=15,
                               juros_rotativo=14.0)
    services.definir_conta_da_fatura(garantido, banco)
    services.definir_garantia_cartao(garantido, cdb)      # limite vem do CDB
    services.definir_dados_do_cartao(garantido, validade="03/2029")

    # ------------------------------------------------------------------ #
    # 3. Um ano de vida financeira
    # ------------------------------------------------------------------ #
    mercados = ["Supermercado Dia a Dia", "Hortifruti do Bairro", "Atacadão Central"]
    restaurantes = ["Almoço no trabalho", "Delivery de pizza", "Café da tarde"]
    for n in range(11, 0, -1):
        competencia = mes_menos(n)
        receita(dia(competencia, 5), "Salário", "4.1.01", 5200.00, banco)
        if n % 3 == 0:
            receita(dia(competencia, 18), "Freelance de design", "4.1.02",
                    round(random.uniform(700, 1200), 2), banco)

        gasto(dia(competencia, 10), "Aluguel do apartamento", "5.1.01", 1450.00, banco)
        gasto(dia(competencia, 12), "Conta de luz", "5.1.02",
              round(random.uniform(90, 160), 2), banco)
        gasto(dia(competencia, 12), "Conta de água", "5.1.03",
              round(random.uniform(45, 70), 2), banco)
        gasto(dia(competencia, 15), "Internet fibra", "5.1.04", 119.90, banco)
        gasto(dia(competencia, 8), "Plano de saúde", "5.4.01", 389.00, banco)
        for semana in (3, 11, 19, 26):
            gasto(dia(competencia, semana), random.choice(mercados), "5.2.01",
                  round(random.uniform(180, 420), 2), banco)
        # O vale é carregado todo mês pela empresa e gasto no almoço.
        services.salvar_lancamento(
            None, dia(competencia, 1), "Recarga do vale refeição",
            [Partida(vale, "D", 420.00), Partida(cat("4.1.01"), "C", 420.00)])
        for d in (2, 5, 8, 12, 16, 19, 23, 26):
            gasto(dia(competencia, d), random.choice(restaurantes), "5.2.02",
                  round(random.uniform(32, 58), 2), vale)
        gasto(dia(competencia, 7), "Combustível", "5.3.01",
              round(random.uniform(180, 260), 2), banco)
        gasto(dia(competencia, 16), "Aplicativo de transporte", "5.3.03",
              round(random.uniform(30, 90), 2), carteira)
        gasto(dia(competencia, 9), "Assinaturas de streaming", "5.6.01", 39.90, cartao)
        gasto(dia(competencia, 13), "Curso de inglês", "5.5.01", 320.00, banco)
        gasto(dia(competencia, 17), "Academia", "5.9.01", 89.90, banco)
        gasto(dia(competencia, 20), "Compras do dia a dia", "5.9.01",
              round(random.uniform(220, 480), 2), banco)
        if n % 4 == 0:
            gasto(dia(competencia, 22), "Farmácia", "5.4.02",
                  round(random.uniform(60, 180), 2), banco)
            gasto(dia(competencia, 24), "Roupas", "5.6.03",
                  round(random.uniform(120, 320), 2), cartao)
        # Sobra do mês vai para a poupança.
        services.salvar_lancamento(
            None, dia(competencia, 28), "Guardando a sobra do mês",
            [Partida(poupanca, "D", 200.00), Partida(banco, "C", 200.00)])

    # Mês atual, até hoje.
    receita(dia(MES, 5), "Salário", "4.1.01", 5200.00, banco)
    gasto(dia(MES, 3), "Supermercado Dia a Dia", "5.2.01", 318.47, banco)
    services.salvar_lancamento(
        None, dia(MES, 1), "Recarga do vale refeição",
        [Partida(vale, "D", 420.00), Partida(cat("4.1.01"), "C", 420.00)])
    for d, valor in ((2, 38.50), (5, 44.90), (6, 42.90), (9, 51.20), (12, 39.80)):
        gasto(dia(MES, d), "Almoço no trabalho", "5.2.02", valor, vale)
    gasto(dia(MES, 7), "Combustível", "5.3.01", 210.00, banco)
    gasto(dia(MES, 9), "Assinaturas de streaming", "5.6.01", 39.90, cartao)
    gasto(dia(MES, 11), "Aplicativo de transporte", "5.3.03", 38.50, carteira)

    # ------------------------------------------------------------------ #
    # 4. Compras no cartão: avulsas e parceladas
    # ------------------------------------------------------------------ #
    services.criar_compra_parcelada("Notebook novo", cartao, cat("5.5.02"), 3600.00, 6,
                                    mes_menos(2), dia(mes_menos(2), 14))
    services.criar_compra_parcelada("Passagem aérea", cartao, cat("5.6.02"), 1440.00, 4,
                                    mes_menos(1), dia(mes_menos(1), 8))
    services.registrar_compra_cartao(cartao, cat("5.2.02"), 96.70, dia(MES, 4),
                                     "Jantar de aniversário")
    services.registrar_compra_cartao(cartao, cat("5.6.03"), 249.90, dia(MES, 8),
                                     "Tênis de corrida")
    # Depois do fechamento (dia 15): cai na fatura atual, ainda aberta.
    services.registrar_compra_cartao(garantido, cat("5.2.01"), 187.35, dia(MES, 18),
                                     "Compras do mês")
    services.fechar_faturas()

    # A fatura fechada do mês passado foi paga.
    for fatura in services.listar_faturas(cartao):
        if fatura["fechada"] and fatura["titulo_id"]:
            titulo = services.obter_titulo(fatura["titulo_id"])
            if titulo and titulo["status"] == "ABERTO" and titulo["vencimento"] < HOJE.isoformat():
                services.baixar_titulo(titulo["id"], titulo["vencimento"],
                                       float(titulo["valor"]), banco)

    # ------------------------------------------------------------------ #
    # 5. Contas fixas (uma delas em débito automático)
    # ------------------------------------------------------------------ #
    services.criar_conta_fixa("PAGAR", "Aluguel do apartamento", "Imobiliária Central",
                              1450.00, dia(MES, 10), cat("5.1.01"),
                              conta_pagamento_id=banco, pagamento_automatico=True)
    services.criar_conta_fixa("PAGAR", "Internet fibra", "NetFibra", 119.90,
                              dia(MES, 15), cat("5.1.04"), conta_pagamento_id=banco,
                              pagamento_automatico=True)
    services.criar_conta_fixa("PAGAR", "Plano de saúde", "Saúde Mais", 389.00,
                              dia(MES, 8), cat("5.4.01"), conta_pagamento_id=banco)
    services.criar_conta_fixa("PAGAR", "Academia", "Corpo em Forma", 89.90,
                              dia(MES, 12), cat("5.9.01"), conta_pagamento_id=banco)
    services.criar_conta_fixa("RECEBER", "Aluguel da garagem", "Vizinho do 302", 250.00,
                              dia(MES, 20), cat("4.1.03"), conta_pagamento_id=banco)

    # ------------------------------------------------------------------ #
    # 6. Contas a pagar e receber de todos os tipos
    # ------------------------------------------------------------------ #
    # Atrasada do mês passado.
    services.salvar_titulo(None, "PAGAR", "Consulta odontológica", "Clínica Sorriso",
                           240.00, dia(mes_menos(1), 25), cat("5.4.03"), None,
                           conta_pagamento_id=banco, multa_pct=2.0, juros_mes_pct=1.0)
    # Vence hoje.
    services.salvar_titulo(None, "PAGAR", "IPVA — parcela 3", "Detran", 312.45,
                           HOJE.isoformat(), cat("5.8.01"), None, conta_pagamento_id=banco)
    # Futuras.
    services.salvar_titulo(None, "PAGAR", "Curso de inglês", "Escola Falar Bem", 320.00,
                           dia(MES, 25), cat("5.5.01"), None, conta_pagamento_id=banco)
    services.salvar_titulo(None, "PAGAR", "Presente de casamento", "", 180.00,
                           dia(mes_menos(-1), 5), cat("5.9.01"), None,
                           conta_pagamento_id=carteira)
    # A receber.
    services.salvar_titulo(None, "RECEBER", "Freelance — site da padaria", "Padaria Pão Novo",
                           800.00, dia(MES, 18), cat("4.1.02"), None,
                           conta_pagamento_id=banco)
    # Paga pela metade: o que faltou virou outra conta.
    acordo = services.salvar_titulo(None, "PAGAR", "Conserto da geladeira", "Assistência Fria",
                                    600.00, dia(MES, 2), cat("5.1.05"), None,
                                    conta_pagamento_id=banco)
    services.baixar_titulo(acordo, dia(MES, 2), 350.00, banco, saldo_em_aberto=True,
                           vencimento_do_saldo=dia(MES, 22))
    # Já paga, para aparecer no filtro "Já pagas".
    paga = services.salvar_titulo(None, "PAGAR", "Seguro do celular", "Protege Já", 34.90,
                                  dia(MES, 6), cat("5.9.01"), None, conta_pagamento_id=banco)
    services.baixar_titulo(paga, dia(MES, 6), 34.90, banco)

    # ------------------------------------------------------------------ #
    # 7. Dívidas e empréstimos
    # ------------------------------------------------------------------ #
    services.criar_emprestimo("Empréstimo pessoal", "Banco Azul", 8000.00, 1.89, 12,
                              mes_menos(3), 15, conta_recebimento_id=banco,
                              data_contratacao=dia(mes_menos(4), 20))
    conserto = services.criar_divida("Conserto do carro", "Oficina do Zé", 1200.00,
                                     dia(mes_menos(2), 10))
    services.pagar_divida(conserto, 300.00, banco, dia(mes_menos(1), 10))
    services.alterar_valor_divida(conserto, 950.00, dia(MES, 1))   # o dono revisou o valor

    celular = services.criar_divida("Celular parcelado", "Loja Tech", 900.00,
                                    dia(mes_menos(6), 5))
    services.pagar_divida(celular, 600.00, banco, dia(mes_menos(3), 5))
    services.quitar_divida(celular, "PAGAMENTO", banco, dia(mes_menos(1), 5),
                           observacao="Últimas parcelas pagas de uma vez")

    # Parcelas do empréstimo que já venceram foram pagas.
    for titulo in services.listar_titulos(tipo="PAGAR", status="ABERTO"):
        if titulo["de_emprestimo"] and titulo["vencimento"] < dia(MES, 1):
            services.baixar_titulo(titulo["id"], titulo["vencimento"],
                                   float(titulo["valor"]), banco)

    # ------------------------------------------------------------------ #
    # 8. Orçamento e objetivos
    # ------------------------------------------------------------------ #
    for codigo, teto in (("5.2.01", 1400.00), ("5.2.02", 350.00), ("5.3.01", 260.00),
                         ("5.6.01", 60.00), ("5.6.03", 250.00), ("5.4.02", 150.00),
                         ("5.3.03", 120.00)):
        services.definir_orcamento(cat(codigo), teto)
    services.salvar_meta(None, "Viagem para a praia", 6000.00,
                         dia(mes_menos(-8), 15), poupanca,
                         "Passagem, hospedagem e passeios")
    services.salvar_meta(None, "Reserva de emergência", 15000.00, None, poupanca,
                         "Seis meses de despesas")

    # ------------------------------------------------------------------ #
    services.gerar_titulos_recorrentes()
    services.fechar_faturas()
    services.conferir_automatico()

    totais = services.total_disponivel()
    print("Base de demonstração criada em:", DEMO_DIR / "SistemaContabil")
    print("  dinheiro hoje: ", services.moeda(totais["tem"]))
    print("  investido:     ", services.moeda(totais["investido"]))
    print("  deve:          ", services.moeda(totais["deve"]))
    print("  lançamentos:   ", len(services.listar_lancamentos(limite=100000)))
    print("  contas a pagar em aberto:",
          len(services.listar_titulos(tipo="PAGAR", status="ABERTO")))
    print("  dívidas:       ", len(services.listar_dividas()))
    db.fechar()


if __name__ == "__main__":
    main()
