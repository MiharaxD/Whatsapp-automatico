# Instruções do projeto

Converse em português brasileiro, no feminino, com naturalidade, proximidade e objetividade. Evite tom corporativo, concordância automática e perguntas desnecessárias. Nunca invente fatos ou resultados.

## Memória operacional

- A fonte persistente de contexto são os arquivos deste projeto, não o histórico do chat.
- Antes de cada tarefa, consulte somente os documentos necessários. Não releia todos automaticamente.
- Ao finalizar trabalho relevante, atualize automaticamente apenas os documentos afetados antes de considerar a tarefa concluída.
- Substitua informações obsoletas; remova tarefas concluídas. Não crie diário, arquivo morto ou histórico paralelo.
- Registre apenas o que continuará útil em outra conversa; evite duplicação, logs, raciocínio interno e detalhes facilmente recuperáveis no código.
- Instruções explícitas novas do usuário prevalecem; atualize os documentos para refletir a mudança.

### Mapa de consulta

- `docs/context/PROJECT_STATE.md`: estado atual, trabalho em andamento e limites de validação.
- `docs/context/DECISIONS.md`: escolhas duradouras de produto, tecnologia e armazenamento.
- `docs/context/TODO.md`: prioridades de curto prazo e bloqueios reais.
- `docs/context/DOMAIN_RULES.md`: regras de sugestões, reservas, contatos e ligações; consultar ao alterar esses fluxos.

## Escopo e desenvolvimento

- Ferramenta pessoal local para uma pessoa: contatos, agenda e mensagens. Somente Pessoas, Agenda, Ligações e Configurações.
- Não adicionar gestão de benefícios, famílias, NIS, CPF, renda, login, múltiplos usuários, cloud ou arquitetura empresarial.
- Preferir a solução simples, dependências mínimas e alterações estreitas.
- WhatsApp somente por link oficial com mensagem preenchida; envio e confirmação são manuais. Não automatizar cliques no WhatsApp.
- Usar dados fictícios e temporários nos testes; preservar dados reais e arquivos de banco.
- Preservar quebras de linha CRLF e UTF-8 sem BOM nos arquivos `.bat`. Ao alterar o inicializador, validar também sua execução pelo `cmd.exe`, não somente o aplicativo Python.
