"""Janela de ajuda escrita em linguagem simples."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.config import APP_NAME, APP_VERSION, DB_PATH
from app.ui.theme import CORES, FONTE
from app.ui.widgets import centralizar

TOPICOS: list[tuple[str, str]] = [
    ("O que este sistema faz",
     "Ele guarda tudo o que você recebe e tudo o que você gasta, mostra quanto sobra\n"
     "no fim do mês e avisa sobre as contas que estão para vencer.\n\n"
     "Todas as informações ficam salvas no seu próprio computador. Nada vai para a\n"
     "internet."),

    ("Por onde começar",
     "1. Vá em 'Minhas Contas' e cadastre cada lugar onde você guarda dinheiro:\n"
     "   cada banco, a carteira, o cartão pré-pago, o vale, o cartão de crédito.\n"
     "   Ao cadastrar, informe quanto há hoje em cada um.\n\n"
     "2. A partir daí, registre suas entradas e saídas do dia a dia em\n"
     "   'Entradas e Saídas'.\n\n"
     "3. Cadastre em 'Contas a Pagar e Receber' os boletos que ainda vão vencer."),

    ("Várias contas: banco, carteira, pré-pago",
     "Cada conta é cadastrada separadamente e tem saldo próprio. Na tela\n"
     "'Minhas Contas' você vê, lado a lado, quanto há em cada uma, quanto entrou e\n"
     "quanto saiu no período, e quando foi o último uso.\n\n"
     "Tipos disponíveis:\n"
     "  • Conta corrente, poupança e investimento\n"
     "  • Dinheiro em espécie e carteira digital (Pix, PicPay, Mercado Pago)\n"
     "  • Cartão pré-pago e vale alimentação/refeição\n"
     "  • Cartão de crédito\n\n"
     "Clique duas vezes em uma conta para ver o extrato dela, com o saldo passo a\n"
     "passo e como ele evoluiu nos últimos meses.\n\n"
     "'Acertar saldo' compara o saldo do sistema com o do seu extrato e lança\n"
     "somente a diferença, sem apagar nada do que você já registrou."),

    ("Cartão pré-pago, vale e cartão de crédito",
     "Pré-pago e vale (você coloca dinheiro antes de usar):\n"
     "  • Recarregar → 'Transferir', da sua conta para o cartão.\n"
     "  • Gastar → registre uma saída escolhendo o cartão em\n"
     "    'De onde saiu o dinheiro'. O saldo do cartão diminui.\n\n"
     "Cartão de crédito (você paga a fatura depois):\n"
     "  • Comprar → registre a saída escolhendo o cartão. A dívida aumenta.\n"
     "  • Pagar a fatura → 'Transferir', da conta corrente para o cartão.\n"
     "    A dívida diminui.\n\n"
     "Na tela 'Minhas Contas', o cartão de crédito aparece como dívida, e a linha\n"
     "'Sobra de verdade' mostra o que você tem menos o que ainda vai pagar."),

    ("Registrar uma saída (gasto)",
     "Clique em 'Entradas e Saídas' e depois em 'Registrar'.\n\n"
     "Escolha 'Gastei dinheiro' e preencha:\n"
     "  • Com o quê você gastou  → ex.: Supermercado\n"
     "  • De onde saiu o dinheiro → ex.: Conta Corrente\n"
     "  • Quanto e em que dia\n\n"
     "O sistema faz sozinho toda a parte contábil."),

    ("Registrar uma entrada (recebimento)",
     "Mesma tela, opção 'Recebi dinheiro':\n\n"
     "  • De onde veio        → ex.: Salário\n"
     "  • Onde o dinheiro caiu → ex.: Conta Corrente\n"
     "  • Quanto e em que dia"),

    ("Transferir entre suas contas",
     "Use a opção 'Transferi entre minhas contas' quando o dinheiro apenas mudar\n"
     "de lugar — por exemplo, da conta corrente para a poupança.\n\n"
     "Isso não é ganho nem gasto: seu total continua o mesmo."),

    ("Contas a pagar e a receber",
     "Cadastre aqui os boletos e promessas de pagamento antes de eles acontecerem.\n"
     "O sistema mostra o que está próximo do vencimento e o que já está atrasado.\n\n"
     "Quando pagar ou receber de fato, selecione a conta e clique em\n"
     "'Marcar como pago/recebido'. O gasto ou a entrada é registrado automaticamente."),

    ("Contas fixas (todo mês a mesma coisa)",
     "Aluguel, luz, internet, mensalidade: cadastre uma vez e o sistema lança os\n"
     "próximos 12 meses sozinho.\n\n"
     "Em 'Contas a Pagar e Receber' → 'Cadastrar conta', marque a opção\n"
     "'É uma conta fixa: repete todo mês'. Deixe o prazo em 0 para não ter fim.\n\n"
     "Quando o valor subir, abra o mês em que o novo preço começou e corrija.\n"
     "O sistema aplica o novo valor naquele mês e em todos os seguintes que ainda\n"
     "não foram pagos — os meses já pagos ficam como estavam.\n\n"
     "O botão 'Contas fixas' mostra todas elas, permite mudar o valor a partir de\n"
     "um mês escolhido, pausar ou encerrar."),

    ("Ver mês a mês",
     "Em qualquer tela com período, use as setas ◀ e ▶ ao lado de 'Mostrar' para\n"
     "andar de um mês para o outro.\n\n"
     "Em 'Relatórios', as duas primeiras abas percorrem todo o seu histórico:\n\n"
     "  • Mês a mês → um mês por linha, desde o seu primeiro registro, com o que\n"
     "    entrou, o que saiu, quanto sobrou e quanto havia em conta no fim do mês.\n\n"
     "  • Categorias mês a mês → cada categoria em uma linha e cada mês em uma\n"
     "    coluna, com total, média e quanto mudou no último mês. É aqui que se vê\n"
     "    o que subiu ao longo do tempo."),

    ("Importar o extrato do banco (sem digitar tudo)",
     "No site ou app do seu banco, baixe o extrato no formato OFX (às vezes chamado\n"
     "de 'Money' ou 'arquivo para gerenciador financeiro'). Também serve um CSV.\n\n"
     "Em 'Entradas e Saídas' → 'Importar extrato': escolha o arquivo, diga de qual\n"
     "conta ele é e confira. O sistema já sugere a categoria de cada linha, olhando\n"
     "o que você lançou antes e o nome dos estabelecimentos.\n\n"
     "Quando você corrige uma categoria, ele aprende: da próxima vez que aquela loja\n"
     "aparecer, já vem certa.\n\n"
     "Importar o mesmo arquivo duas vezes não duplica nada — o que já entrou é\n"
     "reconhecido e ignorado."),

    ("Orçamento: quanto posso gastar",
     "Na tela 'Orçamento' você define um teto mensal para cada categoria.\n\n"
     "O botão 'Sugerir pela média' preenche tudo de uma vez, usando o que você\n"
     "gastou nos últimos 3 meses — depois é só ajustar.\n\n"
     "Durante o mês, a tela mostra quanto já foi, quanto ainda pode gastar e quanto\n"
     "dá por dia até o fim do mês. A coluna 'Ritmo do mês' avisa antes: se você\n"
     "continuar gastando nesse ritmo, vai estourar.\n\n"
     "O teto vale para todos os meses. Se um mês for atípico (férias, Natal), você\n"
     "pode ajustar só aquele mês, sem mexer nos demais."),

    ("Objetivos de poupança",
     "Em 'Orçamento' → 'Meus objetivos': dê um nome, quanto quer juntar, até quando\n"
     "e em qual conta o dinheiro fica guardado.\n\n"
     "O progresso conta o que entrar naquela conta a partir da criação do objetivo,\n"
     "e o sistema calcula quanto você precisa guardar por mês para chegar lá."),

    ("Compra parcelada no cartão",
     "Comprou em 10x? Em 'Minhas Contas' → 'Compras parceladas' → 'Nova compra\n"
     "parcelada'. Informe o valor total e o número de vezes.\n\n"
     "O sistema distribui uma parcela por mês nas próximas faturas, em vez de jogar\n"
     "tudo em um mês só. Assim cada mês mostra o gasto real daquele mês.\n\n"
     "A mesma tela mostra quanto das próximas faturas já está comprometido com\n"
     "parcelas — útil antes de assumir uma nova compra."),

    ("Previsão: vou ficar no vermelho?",
     "Em 'Relatórios' → 'Previsão de saldo'. O sistema soma o dinheiro que você tem\n"
     "hoje com tudo que já está agendado (contas a pagar, a receber, contas fixas e\n"
     "parcelas) e mostra como o saldo caminha dia a dia.\n\n"
     "Se em algum dia o saldo ficar negativo, ele avisa a data e o valor — dá tempo\n"
     "de se organizar antes."),

    ("Se eu atrasar uma conta, o que acontece?",
     "A conta atrasada não some nem muda de data: ela continua na lista, marcada em\n"
     "vermelho como 'Atrasada há N dias', e continua somando no total a pagar. Ela\n"
     "não é 'jogada' para o mês seguinte — fica no mês em que venceu.\n\n"
     "Se você definiu multa e juros para ela, o sistema calcula quanto ela custa hoje\n"
     "e mostra na coluna 'Com juros hoje'. Uma vez por mês, esses encargos são\n"
     "lançados de verdade como despesa de juros e multas.\n\n"
     "Ao marcar como paga, o valor já vem preenchido com os juros incluídos — você\n"
     "pode alterar para o valor que realmente pagou. O principal vai para a categoria\n"
     "da conta e os juros ficam separados, em 'Juros e Multas'.\n\n"
     "Contas fixas: se você não pagar agosto, setembro é criado do mesmo jeito. Você\n"
     "fica com as duas em aberto — nada é perdido de vista."),

    ("Fatura do cartão de crédito",
     "Ao cadastrar o cartão em 'Minhas Contas', informe o dia de fechamento, o dia de\n"
     "vencimento e os juros do rotativo.\n\n"
     "Na data de fechamento o sistema gera a fatura como uma conta a pagar, com o\n"
     "valor total devido naquele dia.\n\n"
     "Se você pagar só uma parte, o restante continua na dívida do cartão e entra na\n"
     "fatura do mês seguinte, junto com as novas compras e com os juros do rotativo\n"
     "sobre o que ficou sem pagar. É exatamente como o banco faz.\n\n"
     "O botão 'Faturas do cartão' mostra o histórico: quanto veio do mês anterior,\n"
     "quanto você comprou, quanto pagou e quanto de juros foi cobrado."),

    ("Empréstimos e financiamentos",
     "Em 'Contas a Pagar e Receber' → 'Empréstimos', cadastre o valor que você pegou,\n"
     "os juros ao mês e em quantas vezes vai pagar.\n\n"
     "O sistema calcula a parcela, cria todas elas em Contas a Pagar e monta a tabela\n"
     "de amortização: quanto de cada parcela é juro e quanto abate a dívida.\n\n"
     "A cada parcela paga, o saldo devedor diminui sozinho. Em 'Ver parcelas' você\n"
     "acompanha quanto ainda falta quitar depois de cada uma."),

    ("Corrigir ou apagar um registro",
     "Cada registro só pode ser alterado ou apagado na mesma tela onde foi criado:\n\n"
     "  • Entrada ou saída digitada por você → tela 'Entradas e Saídas'\n"
     "  • Boleto ou promessa de pagamento    → tela 'Contas a Pagar e Receber'\n\n"
     "Um gasto que nasceu do pagamento de um boleto não pode ser apagado na tela de\n"
     "Entradas e Saídas. Volte ao boleto e clique em 'Desfazer pagamento'."),

    ("Guardar o comprovante de um registro",
     "Na tela 'Entradas e Saídas', escolha a linha e clique em 'Comprovantes'.\n"
     "Dá para anexar a nota, o boleto ou o recibo — PDF, foto ou planilha.\n\n"
     "A coluna 'Comprovante' mostra quantos arquivos cada registro tem.\n\n"
     "Atenção: os arquivos ficam na pasta 'comprovantes', dentro da pasta de dados.\n"
     "A cópia de segurança guarda o banco de dados, não os anexos — quando copiar\n"
     "seus dados para outro lugar, inclua essa pasta também."),

    ("Fechar um mês (e por que isso importa)",
     "Fechar um mês é dizer que ele já virou relatório: nada mais entra, sai ou muda\n"
     "de valor dentro dele.\n\n"
     "Serve para o balanço de um mês passado continuar o mesmo se você olhar de novo\n"
     "daqui a um ano. Sem isso, uma correção feita hoje em um gasto do ano passado\n"
     "muda em silêncio um resultado que você já tinha dado por certo.\n\n"
     "Em 'Ajustes', seção 'Fechamento de competência', escolha o mês e clique em\n"
     "'Fechar competência'. Só meses que já terminaram podem ser fechados, um a um.\n"
     "Se precisar mexer em algo depois, clique em 'Reabrir o último mês fechado'."),

    ("Trilha de alterações: o que mudou e quando",
     "Toda correção e toda exclusão de um registro guardam como ele era antes.\n\n"
     "Em 'Ajustes', clique em 'Ver trilha de alterações'. Cada linha mostra a data da\n"
     "mudança, o que houve, a descrição e o valor de então, e as contas que o\n"
     "registro usava naquele momento.\n\n"
     "É a resposta para 'esse valor mudou depois que eu lancei?'."),

    ("Entender os relatórios",
     "  • Ano a ano         → o retrato de cada ano e se as coisas melhoraram\n"
     "  • Resumo por conta  → quanto entrou e saiu em cada conta no período\n"
     "  • Extrato da conta  → todos os movimentos de uma conta, em ordem de data\n"
     "  • Receitas e Despesas → o que você ganhou, o que gastou e quanto sobrou\n"
     "  • Meu patrimônio    → tudo o que você tem, tudo o que deve e a diferença\n"
     "  • Histórico completo → a lista de todos os registros, um por um\n"
     "  • Previsão de saldo → como fica o seu dinheiro até o último compromisso\n\n"
     "Todos abrem já com o histórico inteiro, do primeiro registro até hoje."),

    ("Deixar o sistema aberto perto do relógio",
     "Ao minimizar ou fechar a janela, o programa continua funcionando no canto da\n"
     "tela, ao lado do relógio. Clique no ícone para abrir de novo.\n\n"
     "Isso pode ser desligado em 'Ajustes'."),

    ("Não perder seus dados",
     "O sistema salva uma cópia de segurança sozinho toda vez que você o fecha.\n"
     "Você também pode salvar uma cópia quando quiser, em 'Ajustes'.\n\n"
     "Se algo der errado, é possível voltar a uma cópia anterior na mesma tela."),

    ("Atalhos do teclado",
     "  Ctrl + N   registrar uma entrada ou saída\n"
     "  F5         atualizar as informações da tela\n"
     "  F1         abrir esta ajuda\n\n"
     "Nos campos de data: a tecla + avança um dia, - volta um dia e H marca hoje."),
]


class JanelaAjuda(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.transient(master)
        self.title("Como usar o sistema")
        self.configure(bg=CORES["fundo"])

        topo = tk.Frame(self, bg=CORES["superficie"], padx=24, pady=18)
        topo.pack(fill="x")
        tk.Label(topo, text="Como usar o sistema", bg=CORES["superficie"],
                 fg=CORES["texto"], font=(FONTE, 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(topo, text="Escolha um assunto na lista ao lado.", bg=CORES["superficie"],
                 fg=CORES["texto_suave"], font=(FONTE, 10), anchor="w").pack(fill="x")

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill="both", expand=True)

        self.lista = tk.Listbox(corpo, width=34, font=(FONTE, 10), relief="solid",
                                borderwidth=1, activestyle="none", highlightthickness=0,
                                bg=CORES["superficie"], fg=CORES["texto"],
                                selectbackground=CORES["primaria"], selectforeground="#ffffff")
        for titulo, _ in TOPICOS:
            self.lista.insert("end", f"  {titulo}")
        self.lista.pack(side="left", fill="y")
        self.lista.bind("<<ListboxSelect>>", lambda _e: self._mostrar())

        quadro = ttk.Frame(corpo, style="Superficie.TFrame", padding=18)
        quadro.configure(relief="solid", borderwidth=1)
        quadro.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.lbl_titulo = ttk.Label(quadro, style="SecaoSuperficie.TLabel")
        self.lbl_titulo.pack(anchor="w", pady=(0, 10))
        # Altura fixa + rolagem: sem isso o Text pede as 24 linhas padrão e a
        # janela nasce mais alta que a área útil de telas de 768px.
        area_texto = ttk.Frame(quadro, style="Superficie.TFrame")
        area_texto.pack(fill="both", expand=True)
        self.txt = tk.Text(area_texto, wrap="word", font=(FONTE, 11), relief="flat",
                           bg=CORES["superficie"], fg=CORES["texto"], spacing1=2, spacing3=4,
                           padx=2, cursor="arrow", height=15, width=60)
        rolagem = ttk.Scrollbar(area_texto, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=rolagem.set)
        self.txt.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

        rodape = ttk.Frame(self, padding=(16, 0, 16, 16))
        rodape.pack(fill="x")
        ttk.Label(rodape, text=f"{APP_NAME} — versão {APP_VERSION}\nSeus dados: {DB_PATH}",
                  style="Dica.TLabel", justify="left").pack(side="left")
        ttk.Button(rodape, text="Fechar", style="Primario.TButton",
                   command=self.destroy).pack(side="right")

        self.lista.selection_set(0)
        self._mostrar()
        centralizar(self, 940, 640)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _mostrar(self) -> None:
        selecao = self.lista.curselection()
        indice = selecao[0] if selecao else 0
        titulo, texto = TOPICOS[indice]
        self.lbl_titulo.configure(text=titulo)
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", texto)
        self.txt.configure(state="disabled")
