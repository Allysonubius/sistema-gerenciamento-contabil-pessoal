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

## Demonstração com dados fictícios

Para gravar um vídeo, tirar prints ou experimentar sem medo, o repositório traz uma base
inventada (a persona "Ana Paula Ribeiro", com um ano de histórico, cartões, dívidas,
contas fixas e orçamento):

```powershell
python demo\popular_demo.py   # cria a base fictícia em demo\SistemaContabil\
python demo\abrir_demo.py     # abre o programa usando essa base
```

Os dois mundos **não se misturam**:

- a demonstração vive em `demo\SistemaContabil\`, nunca em `%LOCALAPPDATA%`, e os scripts
  se recusam a rodar se a pasta apontada for a de dados reais;
- rodando sobre ela, o programa exibe a tarja **DEMONSTRAÇÃO — dados fictícios** no menu
  lateral e no título da janela;
- **o executável distribuído não tem demonstração alguma**: `demo/` não entra no pacote e
  a marca é ignorada quando o programa roda empacotado. Quem baixa o `.exe` vê sempre, e
  somente, os próprios dados.

O roteiro sugerido de gravação, tela por tela, está em [`demo/ROTEIRO.md`](demo/ROTEIRO.md).

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

São 660 testes sobre as regras que não podem quebrar: partidas dobradas, saldos, contas a
pagar, contas fixas, cartões, faturas, dívidas, previsão, orçamento, conferência, backup,
fechamento de competência e o lembrete dele, trilha de alterações, comprovantes, fluxo de
caixa, poupança, a virada do mês, a senha de abertura, a instalação e a atualização dentro
do programa.
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
| **Salários e Rendas** | Cada fonte de renda que se repete todo mês, com total já recebido, histórico mês a mês (previsto × recebido) e o que fazer ao trocar de emprego: encerrar a fonte antiga no último mês em que entrou e cadastrar a nova. |
| **Orçamento** | Teto mensal por categoria, com consumo, ritmo e projeção; a poupança do mês (meta como fatia do que entrou) e os objetivos de poupança. |
| **Contas e Categorias** | Contas de dinheiro (banco, carteira, cartão) e categorias de ganho/gasto — 67 já vêm prontas. |
| **Relatórios** | Mês a mês, **Ano a ano**, Categorias mês a mês, Resumo por conta (balancete), Extrato (razão), Ganhos e gastos (DRE), Meu patrimônio (balanço), Histórico completo (diário) e Previsão de saldo. |
| **Ajustes** | Preferências, cópias de segurança, restauração, exportação, conferência dos dados, fechamento de competência, trilha de alterações, **senha, instalação e versão**. |

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

O horizonte padrão é **até o último compromisso cadastrado**, não um prazo fixo: projetar
90 dias enquanto há parcelas lançadas para dois anos à frente escondia justamente o que
não está na cabeça de ninguém. Prazos menores (30, 60, 90 dias, 6 meses) continuam
disponíveis no seletor.

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

## O painel fala de dinheiro

Os três cartões do mês — *Entrou*, *Saiu* e *Sobrou* — mostram o **fluxo de caixa**: o que
entrou nas contas, o que saiu delas e a diferença. O número fecha com o saldo, sempre:

```
saldo no começo do mês  +  sobrou  =  dinheiro que você tem hoje
```

Antes esses cartões vinham da DRE (receitas − despesas) e ignoravam o dinheiro que saiu
para **pagar dívida** ou para **virar aplicação** — dava para o painel anunciar que haviam
sobrado R$ 459,48 num mês que terminou com R$ 8,99 na conta. Quando parte das saídas não foi
gasto comum, o próprio cartão diz por quê: *1.916,26 em gastos · 440,00 em dívidas · 115,00
aplicado*.

Transferência entre duas contas de dinheiro não conta como entrada nem como saída: cada
lançamento é medido pelo efeito líquido sobre o conjunto das contas.

O retrato por competência (ganhei mais do que gastei?) continua inteiro em
`Relatórios → Ganhos e gastos` e em `Ano a ano`.

## Acertar um saldo não é ganho nem gasto

Acertar um saldo — de uma dívida ou de uma conta — é dizer que a anotação estava errada.
Nada foi ganho nem gasto. Esses acertos iam para *Despesas Diversas* e *Reembolsos e
Restituições* e se misturavam ao que foi de fato gasto e recebido: uma dívida acertada em
R$ 3.863,71 entrava no mês como se fosse dinheiro recebido, e os acertos miúdos de banco
inchavam o que a pessoa achava ter ganhado.

A contrapartida passou a ser sempre o **Patrimônio Inicial**, a mesma de um saldo
inicial. As migrações v15 (dívidas) e v16 (contas) reclassificam os acertos já gravados e
registram cada um na trilha de alterações, com o estado anterior. No fluxo de caixa eles
aparecem numa caixinha própria, *em acertos*, em vez de se esconderem entre os
recebimentos.

## Instalar no computador

Na primeira vez que o `.exe` baixado é aberto, o programa oferece instalar-se, numa tela
que diz exatamente o que vai acontecer: a **pasta de destino** (editável, com botão para
escolher outra e para voltar à padrão), o tamanho do arquivo, cada **atalho** com o
caminho completo onde será criado, e se o programa deve abrir junto com o Windows.
A pasta escolhida fica lembrada para as próximas atualizações.

A tela avisa enquanto você digita se a pasta já existe, se será criada, ou se é lugar
que exige administrador. A instalação é **só do usuário** e não pede administrador:

- copia o executável para `%LOCALAPPDATA%\Programs\SistemaContabil`;
- cria atalho no menu Iniciar e na área de trabalho;
- cadastra o programa em *Aplicativos instalados* do Windows, com desinstalador.

Os seus dados **não** moram ali: ficam em `%LOCALAPPDATA%\SistemaContabil` e sobrevivem a
instalar, desinstalar e reinstalar. Desinstalar pergunta, em separado, se os registros
também devem ir embora — a resposta padrão é mantê-los.

O **modo portátil** (`portable.flag` ao lado do `.exe`) nunca é convidado a instalar: ali o
programa e os dados andam juntos de propósito.

## Senha de abertura

Na primeira abertura o programa pede para criar uma senha, e a exige nas seguintes.

**O que ela é:** uma tranca na porta. Quem senta no seu computador não abre o programa nem
vê os seus números.

**O que ela não é:** criptografia. O arquivo do banco continua legível por quem tiver
acesso a ele e souber abrir um SQLite. Isso está dito aqui, na tela de criação e em
Ajustes de propósito — uma tranca anunciada como cofre é pior do que nenhuma, porque faz
a pessoa guardar coisas que não guardaria.

**Presa a este computador:** o identificador da máquina (o `MachineGuid` do Windows) entra
na conta que gera o hash. O banco copiado para outro computador não abre com a mesma
senha — e o programa diz exatamente isso, em vez de fingir que a senha está errada.

A senha é guardada como PBKDF2-HMAC-SHA256, 240 mil iterações, com sal sorteado a cada
vez; a comparação é em tempo constante e cada erro aumenta a espera, até meio minuto.

**Esqueceu?** Há um caminho de volta, e ele está à vista: digitar `APAGAR SENHA` remove a
tranca. Esconder essa saída não protegeria nada — quem tem o arquivo já tem os números —
e só criaria o risco de você ficar trancado para fora da sua própria vida financeira.

Quem abre junto com o Windows não é interrompido no boot: a senha só é pedida quando a
janela for chamada de volta do relógio.

## Aviso de versão nova

Uma vez por dia, numa linha separada para não segurar a abertura, o programa pergunta à
API pública de releases do GitHub se saiu versão nova. Sem token, sem cadastro, sem
telemetria: a única coisa que sai daqui é a pergunta "qual é a última versão".

Havendo novidade, **uma janela se abre** contando o que mudou — tarja no alto da tela
é fácil demais de não ver, e ficar numa versão velha sem saber é justamente o que o
aviso existe para evitar. A faixa fica atrás dela, e o ícone perto do relógio avisa
também.

A conferência se repete a cada abertura **e a cada virada de dia**: o programa passa
dias na bandeja, e conferir só na abertura seria conferir uma vez na vida.

### Atualizar não é opcional

Não há *agora não*, *dispensar* nem *não avisar desta versão*: da janela só se sai
instalando a versão nova ou fechando o programa. A conferência diária também deixou de
ter interruptor — desligá-la seria a recusa entrando por outra porta.

Com uma exceção deliberada: quando atualizar é **impossível** — a release sem arquivo,
o download falhando, o programa rodando pelo código-fonte — aparece *Continuar assim
mesmo*. Obrigatoriedade que impede alguém de abrir a própria vida financeira por causa
de uma rede fora do ar não é regra, é armadilha.

### Tudo acontece aqui dentro

*Ver o que mudou* abre uma janela **do próprio programa**, não o navegador. Ela traz a
descrição da versão nova em texto corrido, a data, o tamanho do arquivo e um botão
único: **Baixar e atualizar**. O programa busca o executável, mostra o andamento,
instala por cima e reabre. Os dados ficam onde estavam.

Mandar a pessoa procurar um `.exe` numa página e achar o botão certo é pedir para ela
errar — o programa já sabe o que mudou e onde está o arquivo.

O download vai para um arquivo temporário e só no fim ganha o nome definitivo, e o
tamanho recebido é conferido contra o anunciado: uma queda de conexão deixa lixo, nunca
um executável pela metade.

Mesmo sem novidade o botão continua servindo, para relembrar o que mudou na versão que
está rodando.

### Depois de atualizar

Na primeira abertura de uma versão nova, o programa mostra **o que mudou** numa janela,
sem ser preciso ir procurar. Aparece uma vez só, nunca na primeira abertura da vida —
ali não houve atualização nenhuma, e encher a tela de novidade antes de a pessoa ter
usado o programa seria começar pelo fim.

O programa **não se atualiza sozinho** — e isso é escolha, não falta: saber que a versão
mudou vale mais do que descobrir depois que alguma coisa já está diferente na tela. Quem
clica é sempre o usuário.

Sem internet, nada disso aparece e nada trava.

## Poupança do mês

Guardar o que sobra é não guardar nada: num mês apertado sobra zero e a poupança some. A
meta é uma **fatia do que entrou no próprio mês** — 10% por padrão, ajustável em
`Orçamento → Poupança do mês`. Recebeu menos, a meta encolhe junto, em vez de virar uma
cobrança impossível.

O medidor compara três coisas:

- **entrou** no mês (só recebimento de verdade; acerto de saldo não conta);
- **a meta**, a fatia escolhida desse valor;
- **o que ficou guardado**, que é o dinheiro que foi para as contas de investimento menos
  o que foi resgatado delas — guardar 300 e tirar 250 de volta é ter guardado 50.

O cartão *Poupança deste mês*, no painel, fica verde quando a meta foi batida, amarelo
quando faltou e vermelho quando nada foi guardado, e diz quanto falta. A janela traz
ainda os últimos seis meses, para ver se o hábito se sustenta.

## Mudar a data de uma conta

A conta que não foi paga no dia não deixa de existir: ela passa a vencer noutro dia. Em
**Contas a Pagar**, o botão *Mudar a data* abre uma janela com o vencimento atual, há
quantos dias ele passou, e atalhos para as datas que se escolheria de qualquer jeito —
hoje, daqui a 7 dias, daqui a 15, mesmo dia do mês que vem.

Sendo conta fixa, dá para marcar **"valer também para os próximos meses"**: a conta passa
a vencer nesse dia todo mês e os meses à frente que ainda estão em aberto acompanham.
Mês já pago nunca é tocado — ele é história, e história não se remarca.

A competência **não** muda junto: a conta de outubro paga em novembro continua sendo a
conta de outubro. Dia 31 em mês que não tem 31 cai no último dia que existe.

## Receber menos num mês não é o salário novo

Ao dar baixa numa conta fixa por um valor diferente do previsto, o programa perguntava
se os próximos meses passavam a usar o valor novo — com a caixa do Windows e *Sim* já
escolhido. Um Enter distraído rebaixava o ano inteiro.

Agora a regra é assimétrica, porque a vida é:

- **Entrou (ou saiu) menos:** fica só naquele mês, sem pergunta. Quase nunca é o
  valor novo — é desconto, falta, adiantamento. O aviso diz onde mudar de verdade,
  se for o caso.
- **Entrou (ou saiu) mais:** aí sim pergunta, e a opção *Foi só neste mês* vem
  escolhida. A outra explica exatamente quantos meses mudariam.

As caixas do sistema saíram desse caminho: são janelas da própria ferramenta, com a
opção segura em primeiro lugar e cada escolha dizendo o que faz.

## Fechamento de competência

Fechar um mês é dizer que ele **já virou relatório**: nada mais entra, sai ou muda de valor
dentro dele. É o que garante que o balanço e a DRE de um período passado continuem
reproduzíveis — sem isso, uma correção feita hoje em um gasto do ano passado muda em
silêncio um resultado já dado por certo.

Em `Ajustes → Fechamento de competência` o mês é escolhido e travado. A regra vale para
tudo que mexeria naquele mês:

- registrar, corrigir ou apagar um lançamento com data dentro dele;
- **mover** um lançamento de dentro para fora (ou de fora para dentro);
- pagar um boleto, desfazer um pagamento, quitar ou reabrir uma dívida naquela data;
- corrigir ou remover uma compra de cartão daquele ciclo.

Só meses que já terminaram podem ser fechados, um a um, na ordem. **Reabrir** é possível a
qualquer momento, e o fecho anda um mês para trás por vez. O estado mora em
`configuracao.fechamento_ate`.

### O programa é quem lembra

O fechamento só vale se acontecer, e deixar para quando lembrar é o mesmo que não ter.
Por isso, havendo mês encerrado e ainda aberto, o programa abre uma **janela** — não
uma tarja, que é fácil demais de não ver. Ela diz qual mês é e quantos registros
continuam alteráveis, e fecha ali mesmo: *Fechar <mês>*, *Fechar os N meses* quando há
mais de um, *Depois* (cala por sete dias) e *Não avisar mais*, com interruptor para
religar em Ajustes.

A regra é estrita: **só aparece quando o mês seguinte começa**. Lançar hoje nunca faz o
programa pedir para fechar o mês de hoje, e quem está em dia não é incomodado — fechado
até setembro, outubro só é cobrado quando novembro chegar.

### Categorias que nunca foram usadas

O plano de contas vem pronto, e boa parte dele nunca será usada. Categoria demais no
seletor atrapalha e convida a classificar errado.

*Ajustes → Ver as categorias* abre a lista com a **prova de que cada uma está vazia**:
lançamentos, contas a pagar, contas fixas, tetos, metas, compras parceladas,
subcategorias e regras de importação, tudo contado um a um. Dá para arquivar as
escolhidas ou todas.

Arquivar **desativa, não apaga**: elas somem dos seletores e voltam a qualquer momento
na tela Categorias. Arquivar é uma decisão pequena, mas é uma decisão — a pessoa vê o
que há dentro antes de dizer sim, em vez de confiar na palavra do programa.

## Trilha de alterações

Toda criação, correção e exclusão de um lançamento grava uma linha em
`lancamento_historico` com o estado que ele tinha **antes** daquela mudança — data,
descrição, documento, valor, as partidas em texto e o motivo. Somada à linha atual do
banco, a trilha reconstrói a história inteira do registro.

A tabela não tem chave estrangeira para `lancamento` **de propósito**: a linha precisa
sobreviver à exclusão do registro que ela descreve. O carimbo da última mudança fica em
`lancamento.alterado_em`.

Tudo que apaga um lançamento passa por um único ponto (`_apagar_lancamento`), então os
caminhos indiretos também deixam rastro: desfazer um pagamento, desfazer uma quitação,
cancelar uma compra parcelada, refazer uma fatura. `Ajustes → Ver trilha de alterações`
mostra tudo, com filtro por ação e por texto, e exporta em CSV.

## Comprovantes

Na tela **Entradas e Saídas**, o botão `Comprovantes` anexa nota, boleto ou recibo ao
registro escolhido — PDF, imagem ou planilha, até 10 MB por arquivo. A coluna
*Comprovante* mostra quantos arquivos cada registro tem.

Os arquivos são **copiados** para `comprovantes/<ano>/` dentro da pasta de dados; o banco
guarda somente o cadastro (`lancamento_anexo`), para a cópia diária de segurança não
crescer com PDFs dentro. Em troca, **a cópia de segurança não inclui os anexos**: ao levar
os dados para outro lugar, leve essa pasta também.

## Datas aceitas

Um ano digitado errado (2062 em vez de 2026) entrava sem aviso e estragava silenciosamente
toda a previsão. Agora um lançamento só aceita data entre **1990** e o **fim do décimo ano
à frente** — margem que cobre qualquer financiamento longo e ainda barra o dedo
escorregado.

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
    ├── seguranca.py         senha de abertura, presa a este computador
    ├── instalacao.py        instalar, desinstalar e atalhos do Windows
    ├── atualizacao.py       aviso de versão nova e download (releases do GitHub)
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

`conta` (plano de contas hierárquico) · `centro_custo` (histórico; ver nota abaixo) · `lancamento` ·
`partida` (débitos e créditos) · `titulo` (a pagar/receber) ·
`recorrencia` (contas fixas, referenciada por `titulo.recorrencia_id`) · `fatura` ·
`emprestimo` + `emprestimo_parcela` · `orcamento` · `meta` · `compra_parcelada` ·
`regra_categoria` · `divida_quitacao` (histórico das dívidas encerradas) ·
`lancamento_historico` (trilha de alterações) · `lancamento_anexo` (comprovantes) · `configuracao`.
`conta.eh_carteira` e `conta.instituicao` sustentam a tela Minhas Contas;
`conta.dia_fechamento` / `dia_vencimento` / `juros_rotativo`, o ciclo do cartão;
`titulo.multa_pct` / `juros_mes_pct` / `encargos_lancados` / `encargos_ate`, os encargos de
atraso; `titulo.juros_embutido`, a parte de juros de cada parcela de empréstimo.
Chaves estrangeiras ativas, modo WAL com `synchronous = FULL` e versionamento por
`PRAGMA user_version`.

O `FULL` é deliberado. Com `NORMAL`, o SQLite não espera o disco confirmar a gravação,
e um processo encerrado no meio de um *checkpoint* do WAL deixa o cabeçalho dizendo que
o banco tem mais páginas do que o arquivo realmente tem — e o banco inteiro deixa de
abrir. Aconteceu duas vezes durante o desenvolvimento. Os poucos milissegundos a mais
por gravação não se percebem num programa pessoal; perder o arquivo, sim.

Fechar o banco faz um `wal_checkpoint(TRUNCATE)` explícito antes do `close`, para não
deixar esse trabalho justamente para o instante em que o processo pode morrer. E antes
de trocar o executável numa atualização — o momento mais arriscado da vida do programa
— sai uma cópia forçada, não a do dia.

Se mesmo assim o arquivo não abrir, o programa **oferece voltar para a cópia mais recente
com um clique**, guardando o arquivo danificado ao lado. Mandar alguém renomear arquivos
no Explorador logo depois de um susto é pedir para o estrago virar dois.
A coluna `lancamento.origem` distingue o que foi digitado (`MANUAL`) do que nasceu de
uma baixa de título (`BAIXA`) — é ela que sustenta a regra de alteração acima.
`titulo.pagamento_automatico` marca as contas em débito automático, baixadas sozinhas no
vencimento; `lancamento.conferido`, o que já foi conferido (automático por padrão);
`lancamento.alterado_em`, o carimbo da última mudança.

### Centro de custo

A coluna `lancamento.centro_custo_id` e a tabela `centro_custo` continuam no banco e na
exportação, mas **o campo saiu dos formulários**. Eram três opções herdadas da carga
inicial, sem nenhuma tela para gerenciá-las e sem nenhum relatório que agrupasse por elas:
na prática, um passo a mais em cada registro que não devolvia informação nenhuma. Numa
correção, o valor que já estava gravado é preservado.

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
