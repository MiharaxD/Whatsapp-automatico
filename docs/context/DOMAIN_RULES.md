# Regras do fluxo

- Status únicos: Não contatado, Aguardando resposta, Agendado, Ligar e Finalizado.
- Sugerir horário não reserva. Várias pessoas podem receber a mesma sugestão; o primeiro aceite confirmado ocupa o horário. Um segundo aceite precisa receber novo horário.
- Primeira sugestão: primeiro horário futuro disponível, em ordem cronológica. Recusa: próximo disponível estritamente depois da sugestão anterior.
- Confirmar é uma operação atômica: ocupa horário, salva agendamento e muda status para Agendado.
- Copiar mensagem e abrir WhatsApp não alteram último contato. “Mensagem enviada” registra data/hora; contatos sem agendamento entram em Aguardando resposta.
- Sem resposta: pessoas em Aguardando resposta cujo último contato ultrapassou o prazo configurado. Nenhum envio automático.
- Marcar para ligar muda status para Ligar. “Não atendeu” mantém a fila e registra a tentativa. “Ligação concluída” encerra o contato em Finalizado; se houve aceite, usar Agendado/confirmar.
- Cancelar agendamento libera o horário; finalizar atendimento conserva a data e a reserva como registro. Excluir pessoa também libera sua reserva, com aviso na interface.
- Importar não sobrescreve pessoas existentes. Duplicidade é nome + telefone normalizados; pessoas diferentes podem compartilhar telefone.
