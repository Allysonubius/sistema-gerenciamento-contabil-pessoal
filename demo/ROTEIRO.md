# Roteiro de gravação — dados fictícios

Persona: **Ana Paula Ribeiro**, analista, salário de R$ 5.200 no dia 5.
Nada aqui é real: a base vive em `demo\SistemaContabil\` e o seu banco de verdade
continua intocado em `%LOCALAPPDATA%\SistemaContabil\`.

| Onde | O que mostrar |
|------|----------------|
| **Início** | Dinheiro disponível, sobra do mês, contas a vencer, gráfico de 12 meses, maiores gastos. Tem 1 ano de histórico. |
| **Entradas e Saídas** | Filtros de período e tipo; abrir **Registrar** e lançar um gasto (a janela fica aberta para o próximo). Note a coluna "Conferido" ausente: conferência automática ligada. |
| **Minhas Contas** | Banco Azul, Carteira, Poupança, Vale Refeição (pré-pago), CDB Garantido e Tesouro Selic. Abrir o **Extrato** do Banco Azul; mostrar "É dinheiro?" e o acerto de saldo. |
| **Meus Cartões** | *Cartão Azul* (crédito, fecha 20 / vence 28) e *Cartão Garantido* (limite vem do CDB). Fatura atual aberta, compras parceladas (Notebook 6x, Passagem 4x), **Nova compra** e **Compras (corrigir / remover)**. |
| **Contas a Pagar** | Uma conta **atrasada** do mês passado (Consulta odontológica, com multa e juros), uma que **vence hoje** (IPVA), o **"(o que faltou)"** do Conserto da geladeira (pagamento parcial), a coluna **Pagamento: Automático** do Aluguel e da Internet, e o rodapé com A pagar / A receber / Diferença / Entrou. Marcar uma conta como paga e usar a barra **Desfazer**. |
| **Contas fixas** | Aluguel, Internet, Plano de saúde, Academia e o aluguel da garagem a receber; mostrar o botão **Débito automático** e o **Mudar o valor** (reajuste vale só daqui pra frente). |
| **Dívidas** | Empréstimo pessoal 12x (3 pagas), Conserto do carro (pago em parte e com o valor corrigido), os cartões. Mostrar **Pagar uma parte** com a prévia "ainda vão faltar", **Alterar valor da dívida** (não é pagamento), **Quitar dívida**, **Extrato** e **Dívidas quitadas** (Celular parcelado). |
| **Orçamento** | Tetos por categoria com consumo, quanto dá por dia e o ritmo; objetivos "Viagem para a praia" e "Reserva de emergência". |
| **Relatórios** | Mês a mês, Categorias mês a mês, Resumo por conta, Extrato, Ganhos e gastos, Meu patrimônio, Histórico completo e Previsão de saldo. |
| **Ajustes** | Abrir junto com o Windows, conferência automática, cópias de segurança e a pasta de nuvem. |

## Como abrir de novo

```powershell
cd D:\git\sistemacontabil
python demo\abrir_demo.py        # abre com os dados fictícios
python demo\popular_demo.py      # recria a base do zero (apaga a anterior)
```
