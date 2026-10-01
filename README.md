# Agenda de contatos

Ferramenta pessoal para organizar contatos do Cadastro Único, sugerir horários e preparar mensagens. Funciona neste computador, sem login e sem servidor externo.

## Abrir

No Windows, dê dois cliques em **Abrir agenda.bat**. O navegador abre a agenda automaticamente. Mantenha a janela do programa aberta durante o uso; para encerrar, pressione Ctrl+C nessa janela. Os dados ficam salvos.

É necessário Python 3.10 ou superior. Nesta máquina, Python 3.14.7 está disponível. Não precisa instalar bibliotecas adicionais. Em outros sistemas, execute `python app.py` na pasta do projeto.

O inicializador procura o Python instalado e o executa pelo caminho completo. Também busca instalações padrão do Windows caso os atalhos `python`/`py` não funcionem; não precisa reinstalar só porque esses atalhos falharam.

Se a porta estiver ocupada, feche a outra instância ou execute `python app.py --port 8766`.

## Uso diário

1. Em **Agenda**, adicione a data e os horários disponíveis, um por linha.
2. Em **Pessoas**, adicione alguém ou importe uma planilha.
3. Abra a pessoa e clique em **Sugerir próximo horário**.
4. Use **Enviar no WhatsApp** ou **Copiar mensagem**. Você pode editar o texto preparado antes de abrir/copiar; essa edição vale apenas para a mensagem atual, enquanto o painel permanecer aberto.
5. Revise e envie no WhatsApp. Depois clique em **Mensagem enviada** para registrar o contato.
6. Se a pessoa não puder, clique em **Não pode nesse horário · Próximo horário**.
7. Se aceitar, clique em **Confirmar agendamento**. O horário fica reservado e a mensagem de confirmação aparece.

O WhatsApp abre por um [link oficial de conversa com texto preenchido](https://faq.whatsapp.com/5913398998672934/?locale=pt_BR). Dependendo do navegador e das preferências do computador, ele pode oferecer WhatsApp Web ou o aplicativo. A agenda não envia mensagens, não lê respostas e não registra um envio apenas por abrir a conversa.

Em **Pessoas**, a área **Sem resposta** destaca quem está aguardando há mais tempo que o prazo configurado. Use **Marcar para ligar** para incluir a pessoa em **Ligações**. **Não atendeu** registra a tentativa e mantém a pessoa na fila; **Ligação concluída** finaliza o contato. Se houve aceite de um horário, use **Agendado** para conferir e confirmar a reserva.

Em **Configurações**, ajuste o prazo de 1 a 30 dias e os três modelos de mensagem. Variáveis disponíveis: `{{nome}}`, `{{data}}`, `{{horario}}`.

## Planilhas

- Formatos: CSV ou XLSX, até 8 MB e 10.000 linhas. Em XLSX, apenas a primeira aba.
- Primeira linha com **Nome**, **Telefone** e, opcionalmente, **Observação**. CSV aceita vírgula, ponto e vírgula ou tabulação; UTF-8 ou Windows-1252.
- Telefones brasileiros: DDD + número. Para outro país, use `+código do país`. Salve telefones como texto no Excel para conservar a formatação. Fórmulas não são executadas nem importadas como contatos.
- A prévia informa linhas inválidas e duplicadas antes de salvar. Duplicidade significa o mesmo nome e telefone; pessoas diferentes podem compartilhar telefone. Nada existente é sobrescrito.
- O modelo CSV pode ser baixado na tela de importação. Substitua a linha de exemplo pelos contatos reais.

## Horários e dados

Uma sugestão ainda está disponível para outras pessoas. Somente confirmar ocupa o horário. Se outra pessoa já o reservou, será preciso sugerir o próximo. Horários passados não são sugeridos.

**Cancelar agendamento** libera o horário e remove a sugestão. **Finalizar atendimento** preserva a data e a reserva como registro. Excluir uma pessoa libera sua reserva. Horários reservados só podem ser excluídos depois do cancelamento.

O banco fica em `data/agenda.sqlite3`. Para fazer uma cópia, encerre o programa e copie a pasta **data** inteira. Para restaurar, com o programa fechado, substitua essa pasta pela cópia. Não apague essa pasta ao atualizar os arquivos do programa. Os contatos e observações são dados pessoais: mantenha a pasta e as cópias em um local protegido no seu computador.

## Validação de desenvolvimento

Execute `python -m unittest discover -s tests -v`. Os testes usam bancos temporários e não alteram os contatos reais. Para uma sessão isolada: `python app.py --no-browser --port 8766 --database .test-data/agenda.sqlite3`.

A memória operacional do projeto fica em `AGENTS.md` e `docs/context/`; consulte cada documento apenas quando seu tema for necessário.
# Whatsapp-automatico
