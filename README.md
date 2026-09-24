# Minhas Contas — Sistema Contábil Pessoal

Aplicação desktop para Windows de controle financeiro pessoal. Por dentro trabalha com
**partidas dobradas** e guarda tudo em **SQLite**; por fora fala a língua do dia a dia
("gastei", "recebi", "transferi"). Fica aberta na **bandeja do sistema**, ao lado do relógio.

> **Tudo fica no seu computador.** Não há nuvem, login ou envio de dados para a internet.
> O banco de dados é um arquivo em `%LOCALAPPDATA%\SistemaContabil\contabil.db`.

## Baixar e usar

1. Baixe o `SistemaContabil.exe` na página de
   [Releases](https://github.com/Allysonubius/sistema-gerenciamento-contabil-pessoal/releases).
2. Execute. Não precisa instalar nada: é um arquivo único, sem dependências externas.
3. O Windows pode mostrar o aviso "SmartScreen" por ser um programa sem assinatura digital
   paga — clique em *Mais informações* → *Executar assim mesmo*.
4. Na primeira abertura o sistema cria o banco de dados e o plano de contas padrão
   (67 categorias). Em **Ajustes** dá para ligar a abertura junto com o Windows e as
   cópias de segurança automáticas.

O [Manual do Sistema (PDF)](Manual_do_Sistema.pdf) explica cada tela em linguagem simples.

## Rodar a partir do código

Requer **Python 3.11+** no Windows (o Tkinter vem junto com o instalador oficial).

```bash
git clone https://github.com/Allysonubius/sistema-gerenciamento-contabil-pessoal.git
cd sistema-gerenciamento-contabil-pessoal
python -m pip install -r requirements.txt
python main.py
```

### Gerar o executável

```powershell
.\build.ps1                # roda os testes e empacota com PyInstaller
.\build.ps1 -Portable      # o banco fica na pasta do .exe, não em %LOCALAPPDATA%
.\build.ps1 -PularTestes   # compila sem rodar a suíte
```

O resultado é `dist\SistemaContabil.exe`. O build **falha de propósito** se algum teste
quebrar: regra de negócio com defeito não chega ao executável.

### Testes

```bash
python -m pytest -q
```

São 183 testes sobre as regras que não podem quebrar: partidas dobradas, saldos, contas a
pagar, contas fixas, cartões, faturas, dívidas, previsão, orçamento, conferência e backup.
Cada teste roda num banco temporário próprio — os seus dados nunca são tocados.

## Privacidade e o que não está aqui

Este repositório contém **apenas o código**. Ficam de fora, pelo `.gitignore`:

| O quê | Onde fica de verdade |
|-------|----------------------|
| Banco de dados (`contabil.db`) | `%LOCALAPPDATA%\SistemaContabil\` |
| Cópias de segurança | `%LOCALAPPDATA%\SistemaContabil\backups\` (e a pasta de nuvem escolhida) |
| Extratos baixados do banco (`.ofx`, `.pdf`) | pasta local do usuário, nunca versionada |
| Registro de erros (`app.log`) | `%LOCALAPPDATA%\SistemaContabil\` |

## Telas

| Tela | O que faz |
|------|-----------|
| **Início** | Dinheiro disponível, o que sobrou no mês, entradas, saídas, contas a vencer, gráfico de 12 meses e maiores gastos. |
| **Entradas e Saídas** | Lista de tudo que entrou e saiu, com filtros de período, tipo, texto e conta. |
| **Minhas Contas** | Cada banco, carteira, cartão pré-pago, vale ou cartão de crédito com saldo próprio, movimento do período, extrato individual, transferência e acerto de saldo. |
| **Contas a Pagar** | Boletos e promessas de pagamento; ao marcar como pago, o movimento é registrado sozinho. Também abriga contas fixas e empréstimos. |
| **Orçamento** | Teto mensal por categoria, com consumo, ritmo e projeção; e os objetivos de poupança. |
| **Contas e Categorias** | Contas de dinheiro (banco, carteira, cartão) e categorias de ganho/gasto — 67 já vêm prontas. |
| **Relatórios** | Mês a mês, Categorias mês a mês, Resumo por conta (balancete), Extrato (razão), Ganhos e gastos (DRE), Meu patrimônio (balanço) e Histórico completo (diário). |
| **Ajustes** | Preferências, cópias de segurança, restauração, exportação e conferência dos dados. |

Não há barra de menu no topo: toda a navegação está no menu lateral, e as ações de cada
tela ficam no cabeçalho dela.

## Registrar um movimento

O botão **Registrar** abre um formulário guiado com cinco situações:

| Aba | O que preenche | Lançamento gerado |
|-----|----------------|-------------------|
| Gastei dinheiro | categoria do gasto + conta usada | débito na despesa, crédito na conta |
| Recebi dinheiro | origem + conta que recebeu | débito na conta, crédito na receita |
| Transferi entre contas | conta de origem + conta de destino | débito no destino, crédito na origem |
| Saldo inicial | conta + valor que já existe nela | contrapartida em Patrimônio Inicial |
| Modo contábil | débitos e créditos manuais (N partidas) | conforme informado |

## Instância única

Abrir o programa quando ele já está rodando **não cria uma segunda janela**: a existente
é trazida para a frente — inclusive quando está minimizada na bandeja — e a nova encerra.
A detecção usa um mutex nomeado do Windows; o pedido de exibição trafega por um arquivo
de sinal em `%LOCALAPPDATA%\SistemaContabil\`, lido pela janela a cada 800 ms. Não há
sockets envolvidos, então o firewall nunca é acionado.

## Contas de dinheiro (Minhas Contas)

Cada lugar onde o dinheiro fica é uma conta própria, com saldo e extrato individuais.
Tipos disponíveis no cadastro:

| Tipo | Natureza | Como funciona |
|------|----------|---------------|
| Conta corrente, poupança, investimento | Ativo | saldo disponível |
| Dinheiro em espécie, carteira digital | Ativo | saldo disponível |
| **Cartão pré-pago**, **vale alimentação/refeição** | Ativo | você carrega antes de usar: recarga é transferência, gasto é saída |
| Cartão de crédito | Passivo | gasto aumenta a dívida; pagar a fatura é transferência da conta para o cartão |

O totalizador mostra **você tem**, **deve em cartões** e **sobra de verdade** (a diferença).
"Acertar saldo" compara com o extrato real e lança **somente a diferença**, sem apagar
nada. O extrato de cada conta traz o saldo passo a passo e a evolução dos últimos meses.

Internamente, a coluna `conta.eh_carteira` marca quais contas entram nessa visão e no
cálculo do dinheiro disponível — contas a receber, por exemplo, ficam de fora.

## Contas fixas (recorrência mensal)

Ao cadastrar uma conta a pagar/receber, marque **"É uma conta fixa: repete todo mês"**.
Informe o prazo em meses ou deixe `0` para não ter fim. O sistema:

- gera automaticamente os títulos dos próximos 12 meses (`gerar_titulos_recorrentes`,
  idempotente — roda a cada abertura da tela sem duplicar nada);
- mantém a janela sempre à frente conforme os meses passam.

**Reajuste:** quando o valor mudar, corrija o mês em que o novo preço começou (ou use
"Contas fixas → Mudar o valor", escolhendo o mês). O novo valor vale **daquele mês em
diante**, em todos os meses ainda em aberto. Meses já pagos nunca são alterados — o
histórico permanece fiel ao que foi realmente pago.

**Encerrar** desativa a regra e remove apenas os meses futuros ainda em aberto; o que já
foi pago fica no histórico.

## Visão mês a mês

- Setas **◀ ▶** ao lado do seletor de período andam de um mês para o outro (em períodos
  que não são um mês inteiro, deslizam a janela pelo mesmo número de dias).
- **Relatórios → Mês a mês**: um mês por linha, desde o primeiro registro, com entrou,
  saiu, sobrou, acumulado e o dinheiro em conta no fim de cada mês, mais as médias.
- **Relatórios → Categorias mês a mês**: uma categoria por linha e um mês por coluna,
  com total, média e variação do último mês. Alterna entre gastos e ganhos e entre
  6, 12, 24 meses ou todo o histórico.

Essas duas abas percorrem todo o histórico e ignoram o seletor de período.

## Orçamento e objetivos

Cada categoria de despesa pode ter um **teto mensal** (`orcamento`). O teto vale para todos
os meses; um mês atípico pode receber um **ajuste pontual** sem alterar os demais.
"Sugerir pela média" preenche os tetos com a média dos últimos 3 meses.

A tela mostra, por categoria: quanto já foi gasto, quanto ainda pode, **quanto dá por dia
até o fim do mês** e o **ritmo** — a projeção do gasto no mês mantido o ritmo atual, que
avisa do estouro antes de ele acontecer.

**Objetivos** (`meta`) acompanham quanto já foi guardado em uma conta desde a criação da
meta e quanto falta por mês para chegar ao alvo na data desejada.

## Importar extrato do banco

`Entradas e Saídas → Importar extrato` lê **OFX/QFX** (o formato que todo banco brasileiro
exporta) e **CSV** em qualquer ordem de colunas, detectando separador, formato de data e
valores no padrão brasileiro.

Cada linha recebe uma sugestão de categoria, nesta ordem: regra aprendida → histórico de
lançamentos parecidos → nome da categoria → padrão. A comparação ignora acentos e exige
palavra inteira (senão "posto" casaria com "imposto"). Ao corrigir uma categoria, o sistema
**aprende** (`regra_categoria`) e acerta na próxima vez.

Reimportar o mesmo arquivo não duplica nada: cada item guarda seu identificador de origem
(`lancamento.id_extrato`, com índice único).

## Compra parcelada no cartão

`Minhas Contas → Compras parceladas`: informe o total e o número de vezes, e o sistema
distribui **uma parcela por mês** nas próximas faturas — cada mês mostra o gasto real
daquele mês, em vez de tudo em um só. A tela mostra quanto das faturas futuras já está
comprometido. Cancelar remove só as parcelas ainda não vencidas.

## Previsão de saldo

`Relatórios → Previsão de saldo` projeta o dinheiro disponível dia a dia somando o saldo de
hoje com contas a pagar/receber, contas fixas e parcelas já agendadas — e aponta **em que
data o saldo fica mais baixo**, avisando se ficaria negativo. Há também o resumo mês a mês.

## Atraso, multa e juros

Uma conta não paga **não muda de data nem é transferida para o mês seguinte**: continua
no mês em que venceu, marcada como "Atrasada há N dias", e segue somando nos totais.

Cada conta a pagar tem **multa (% fixo, cobrada uma vez)** e **juros (% ao mês,
proporcionais aos dias)** — os padrões ficam em Ajustes e podem ser mudados conta a conta.
A coluna "Com juros hoje" mostra o valor atualizado.

**Uma vez por mês**, no fechamento do mês anterior, os encargos das contas atrasadas são
lançados de verdade: débito em `5.7.01 Juros e Multas` e crédito em `2.1.02 Contas a Pagar`
(a obrigação reconhecida). Ao pagar, a provisão é baixada e o que exceder vira despesa
financeira na hora; se você pagar menos do que o provisionado, a diferença é estornada.
Cancelar ou apagar a conta também estorna a provisão — o balanço nunca fica com resíduo.

## Fatura do cartão de crédito

Cada cartão pode ter **dia de fechamento**, **dia de vencimento** e **juros do rotativo**.
Na data de fechamento o sistema gera a fatura como uma conta a pagar, com o total devido
naquele dia.

Pagando parcialmente, **o restante continua na dívida do cartão e entra na fatura
seguinte**, junto com as novas compras e com o rotativo sobre o que ficou sem pagar —
como o banco faz. A janela "Faturas do cartão" mostra, por mês: quanto veio do mês
anterior, quanto você comprou, quanto pagou, os juros cobrados e o total.

## Empréstimos e financiamentos

Cadastre o valor pego, os juros ao mês e o número de parcelas: o sistema monta a **tabela
Price**, cria todas as parcelas em Contas a Pagar e mantém uma conta de dívida própria.
Cada parcela é lançada separando **juros** (despesa financeira) de **amortização** (abate
da dívida), de modo que o saldo devedor cai sozinho a cada pagamento. "Ver parcelas"
mostra o plano completo, com quanto ainda falta quitar depois de cada uma.

## Regra de alteração dos registros

Um registro só pode ser corrigido ou apagado **na tela em que foi criado**:

- movimento digitado por você → tela **Entradas e Saídas**;
- boleto ou promessa de pagamento → tela **Contas a Pagar**.

O movimento gerado pelo pagamento de um boleto **não** pode ser apagado nem alterado em
Entradas e Saídas — a única forma de desfazê-lo é **Desfazer pagamento** na tela do boleto,
o que remove o movimento e devolve a conta para "em aberto". Não existe nenhuma função de
apagar movimentos em massa.

## Executar a partir do código

```bash
python -m pip install -r requirements.txt
```

```bash
python main.py
```

## Gerar o executável

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

O arquivo final é `dist\SistemaContabil.exe` — arquivo único, sem console e sem
necessidade de Python instalado na máquina de destino.

Versão portátil (dados na mesma pasta do `.exe`):

```bash
powershell -ExecutionPolicy Bypass -File build.ps1 -Portable
```

## Onde os dados ficam

| Item | Caminho |
|------|---------|
| Banco de dados | `%LOCALAPPDATA%\SistemaContabil\contabil.db` |
| Cópias de segurança | `%LOCALAPPDATA%\SistemaContabil\backups\` |
| Exportações | `%LOCALAPPDATA%\SistemaContabil\exportacoes\` |
| Log | `%LOCALAPPDATA%\SistemaContabil\app.log` |

No modo portátil, tudo vai para `dados\` ao lado do executável.

## Atalhos

| Atalho | Ação |
|--------|------|
| `Ctrl+N` | Registrar entrada ou saída |
| `F5` | Atualizar a tela atual |
| `F1` | Abrir a ajuda |

Nos campos de data: `+` avança um dia, `-` volta um dia, `H` marca hoje.

## Estrutura do projeto

```
sistemacontabil/
├── main.py                  ponto de entrada e tratamento global de erros
├── build.ps1                geração do .exe (PyInstaller)
├── requirements.txt
└── app/
    ├── config.py            caminhos, versão e diretórios de dados
    ├── db.py                SQLite: esquema, migração, carga inicial, backup
    ├── services.py          regras de negócio, tradução dos lançamentos e relatórios
    ├── instancia.py         garante uma única janela aberta
    ├── importacao.py        leitura de OFX/CSV e sugestão de categoria
    ├── tray.py              ícone da bandeja (pystray)
    └── ui/
        ├── theme.py         paleta e estilos ttk
        ├── widgets.py       cabeçalho, cartões, tabelas, gráfico, campos
        ├── main_window.py   janela principal, menu lateral e bandeja
        ├── ajuda.py         manual em linguagem simples (F1)
        ├── carteiras.py     Minhas Contas: saldo, extrato, faturas, parcelamentos
        ├── orcamento.py     tetos por categoria e objetivos de poupança
        ├── importar.py      janela de importação de extrato
        ├── dashboard.py
        ├── lancamentos.py
        ├── financeiro.py
        ├── plano_contas.py
        ├── relatorios.py
        └── configuracoes.py
```

## Modelo de dados

`conta` (plano de contas hierárquico) · `centro_custo` · `lancamento` ·
`partida` (débitos e créditos) · `titulo` (a pagar/receber) ·
`recorrencia` (contas fixas, referenciada por `titulo.recorrencia_id`) · `fatura` ·
`emprestimo` + `emprestimo_parcela` · `orcamento` · `meta` · `compra_parcelada` ·
`regra_categoria` · `divida_quitacao` (histórico das dívidas encerradas) · `configuracao`.
`conta.eh_carteira` e `conta.instituicao` sustentam a tela Minhas Contas;
`conta.dia_fechamento` / `dia_vencimento` / `juros_rotativo`, o ciclo do cartão;
`titulo.multa_pct` / `juros_mes_pct` / `encargos_lancados` / `encargos_ate`, os encargos de
atraso; `titulo.juros_embutido`, a parte de juros de cada parcela de empréstimo.
Chaves estrangeiras ativas, modo WAL e versionamento por `PRAGMA user_version`.
A coluna `lancamento.origem` distingue o que foi digitado (`MANUAL`) do que nasceu de
uma baixa de título (`BAIXA`) — é ela que sustenta a regra de alteração acima.
`titulo.pagamento_automatico` marca as contas em débito automático, baixadas sozinhas no
vencimento; `lancamento.conferido`, o que já foi conferido (automático por padrão).

## Dívidas: pagar não é o mesmo que corrigir

Três ações diferentes, de propósito:

| Ação | O que faz | Sai dinheiro? |
|------|-----------|---------------|
| **Pagar uma parte** | abate o saldo devedor pelo valor pago | sim, da conta escolhida |
| **Alterar valor da dívida** | corrige quanto você deve (juros, correção, renegociação) | não |
| **Quitar dívida** | encerra, zera e guarda no histórico de dívidas quitadas | sim, ou "perdoada" |

Por isso o cartão "Já pago dessas dívidas" conta **só o que saiu de uma conta sua** —
correção de valor não entra. O botão **Extrato** mostra, movimento a movimento, o que foi
pagamento e o que foi ajuste, com o saldo depois de cada um.

## Licença

[GNU GPL v3](LICENSE) — você pode usar, estudar, modificar e redistribuir, desde que
trabalhos derivados mantenham a mesma licença e o código-fonte permaneça disponível.
