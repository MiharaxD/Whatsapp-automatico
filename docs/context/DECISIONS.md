# Decisões

## Aplicação web local sem dependências extras
Decisão: Python com biblioteca padrão, SQLite e interface HTML/CSS/JavaScript; servidor restrito a 127.0.0.1, aberto no navegador.
Motivo: instalação e manutenção pequenas, funcionamento local, sem infraestrutura externa.
Consequências: computador precisa de Python 3.10 ou superior; CSV/XLSX serão lidos localmente. Nenhum serviço remoto guarda os dados.

## Envio revisado pela usuária
Decisão: link oficial `wa.me` com mensagem preenchida; registrar contato apenas por ação explícita “Mensagem enviada”.
Motivo: abrir uma conversa ou copiar texto não comprova envio.
Consequências: sem API, bots ou leitura automática de respostas; a usuária registra retorno e aceite.

## Escopo pessoal estrito
Decisão: quatro abas e somente os cinco status solicitados.
Motivo: reduzir cliques na tarefa diária de uma pessoa.
Consequências: sem gestão cadastral de famílias, benefícios ou identificação civil.

## Inicializador independente dos comandos curtos
Decisão: executar Python por caminho completo validado; localizar executáveis no PATH e buscar também instalações padrão no perfil do Windows.
Motivo: os comandos `python`/`py` falharam no cmd.exe mesmo com Python instalado e acessível por caminho completo. Isso não comprova ausência de Python.
Consequências: não alterar configurações globais do Windows nem exigir reinstalação quando a instalação existente funciona. Preservar CRLF e testar o BAT pelo cmd.exe.
