# Estado do projeto

## Objetivo atual
Entregar um MVP local e simples para uma pessoa organizar contatos, sugerir horários, preparar mensagens do Cadastro Único e registrar agendamentos e ligações.

## Estado atual
MVP implementado. Aplicação local Python + SQLite, sem pacotes externos. Python 3.14.7 confirmado nesta máquina em 01/10/2026; mínimo suportado 3.10. Inicializador Windows: `Abrir agenda.bat`, com CRLF e UTF-8 sem BOM; `.gitattributes` conserva CRLF ao usar Git. O inicializador usa caminhos completos de executáveis validados e busca instalações locais quando os comandos curtos/atalhos falham. Instruções de uso e cópia dos dados em `README.md`.

## Sistemas principais
Quatro abas: Pessoas (cadastro, edição/exclusão, pesquisa, importação com prévia e pendências); Agenda (horários e reservas); Ligações (tentativas/conclusão/agendamento); Configurações (três modelos e prazo de 1–30 dias).

Fluxo completo: sugerir → abrir/copiar mensagem → registrar envio → sugerir próximo ou confirmar. Reservas transacionais impedem aceitar o mesmo horário para duas pessoas.

Banco de uso: `data/agenda.sqlite3`, criado na primeira abertura. Dados fictícios e captura da interface ficam separados em `.test-data/`, fora do banco real.

## Trabalho em andamento
Nenhuma implementação pendente no escopo autorizado. Memória operacional ativa conforme `AGENTS.md`.

## Problemas conhecidos
Nenhum defeito funcional conhecido. WhatsApp usa link oficial e envio manual; não foi enviada mensagem real. XLSX lê somente a primeira aba e valores literais, sem fórmulas.

Validação: 17 testes do aplicativo aprovados em 30/09/2026 (fluxos, persistência, reserva concorrente, CSV/XLSX, proteção de acesso local). Em 01/10/2026 passaram os 5 testes do inicializador: CRLF/sem BOM, caminhos com espaços, PATH com separadores duplicados, Python fora do PATH e encaminhamento de argumentos.

O BAT original corrigido também iniciou o aplicativo real com banco temporário: página e API HTTP 200, SQLite criado e processos de teste encerrados, sem usar o banco real.

Interface conferida no navegador em desktop: cadastro, sugestão/recusa/confirmação, cópia, envio registrado, importação CSV, ligações, configurações persistidas e Sem resposta. Console sem erros nessa sessão. Não houve teste com planilha real da usuária ou envio real de WhatsApp.

## Próximo passo recomendado
Abrir o inicializador, cadastrar horários e importar a lista real. Para alterações futuras, consultar apenas o contexto pertinente e preservar `data/`.
