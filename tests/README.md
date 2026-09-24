# Testes

Cobrem as regras que não podem quebrar: partidas dobradas, saldos, contas a
pagar, contas fixas, cartões, previsão, orçamento, conferência e backup.

## Como rodar

```bash
python -m pytest tests -q
```

Para ver o nome de cada teste:

```bash
python -m pytest tests -v
```

Rodando só um arquivo:

```bash
python -m pytest tests/test_pagamento_parcial.py -v
```

## Como funcionam

Cada teste roda em um banco novo, criado numa pasta temporária. A fixture
`sistema` (em `conftest.py`) aponta `LOCALAPPDATA` para essa pasta antes de
importar `app.db`, e confere que o caminho do banco não é o de produção — o
banco real nunca é tocado.

A fixture `contas` monta o cenário mínimo: uma conta corrente com R$ 1.000,
uma carteira em espécie com R$ 100, um cartão de crédito e as categorias de
supermercado e salário.

## O que cada arquivo cobre

| Arquivo | Assunto |
|---|---|
| `test_contabilidade.py` | plano de contas, partidas dobradas, saldos, balanço |
| `test_financeiro.py` | títulos, baixa, estorno, contas fixas, multa e juros |
| `test_pagamento_parcial.py` | pagar menos que o devido e o saldo que sobra |
| `test_cartoes.py` | fatura, rotativo, limite garantido, pré-pago |
| `test_previsao_orcamento.py` | previsão por conta, tetos de gasto, painel |
| `test_conferencia.py` | conciliação com o extrato do banco |
| `test_backup.py` | cópia local, cópia externa e rotação |

## Antes de gerar o executável

Rode a suíte. Se algo ficar vermelho, o `build.ps1` não deve ser executado —
o erro chega ao usuário final.
