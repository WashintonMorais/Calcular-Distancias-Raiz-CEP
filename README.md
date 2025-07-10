# Painel de Distância por CEP

Execute `app.py` e acesse via navegador para usar o painel.

Documentação do Projeto: Calculadora de Distâncias por Raiz de CEP
1. Visão Geral
A "Calculadora de Distâncias por Raiz de CEP" é uma aplicação web desenvolvida em Python com o framework Flask. Seu objetivo principal é calcular a distância geodésica (Haversine) entre um CEP de partida e uma ou múltiplas "raízes" de CEP de destino (os 5 primeiros dígitos de um CEP).

A ferramenta foi projetada para ser eficiente e informativa, fornecendo atualizações de progresso em tempo real para o usuário e oferecendo dois modos de consulta para diferentes necessidades de análise.

2. Principais Funcionalidades
Cálculo de Distância em Dois Modos:

Consulta Detalhada: Uma varredura otimizada que consulta os 3 primeiros CEPs de cada dezena dentro de uma raiz, agrupando os resultados por bairro e calculando a distância média para cada um.

Consulta Rápida: Um método de amostragem que calcula o centro geográfico (centroide) de uma raiz de CEP e retorna uma única distância média, tornando a consulta drasticamente mais rápida.

Interface Reativa: Utiliza Server-Sent Events (SSE) para enviar atualizações do progresso do backend para o frontend em tempo real, sem que a página precise ser recarregada. O usuário acompanha o processo através de uma barra de progresso e um log de execução detalhado.

Geração de Relatórios: Após a conclusão dos cálculos, a aplicação gera um arquivo .csv com os resultados consolidados, que pode ser baixado pelo usuário.

Validação de Entradas: A interface e o backend validam as entradas do usuário para garantir que os CEPs e raízes estejam em um formato válido, prevenindo erros.

Consulta Robusta a APIs: Utiliza um sistema de rodízio entre múltiplas APIs de CEP para aumentar a resiliência e a taxa de sucesso na obtenção de coordenadas geográficas.

3. Tecnologias Utilizadas
Backend
Linguagem: Python 3

Framework Web: Flask (para criar o servidor, gerenciar rotas e renderizar a página)

Bibliotecas Python:

requests: Para fazer as chamadas HTTP para as APIs de CEP externas.

itertools: Usado para criar o ciclo de rodízio entre as APIs.

Frontend
Estrutura: HTML5

Estilização: Tailwind CSS (para um design moderno e responsivo com baixo esforço)

Interatividade: JavaScript (Vanilla, sem frameworks) para:

Controlar o envio do formulário.

Estabelecer e gerenciar a conexão de Server-Sent Events (EventSource).

Atualizar dinamicamente o DOM (a página) com o progresso, logs e resultados finais.

APIs Externas Consultadas
Para obter as coordenadas (latitude e longitude) a partir de um CEP, a aplicação consulta as seguintes APIs públicas em rodízio:

ViaCEP: https://viacep.com.br/ws/{cep}/json/

BrasilAPI: https://brasilapi.com.br/api/cep/v2/{cep}

AwesomeAPI: https://cep.awesomeapi.com.br/json/{cep}

OpenCEP: https://opencep.com/v1/{cep}

Plataforma de Deploy
Vercel: Plataforma de nuvem otimizada para "Serverless Functions", onde o projeto está hospedado.

4. Como Funciona
A arquitetura do projeto é dividida em três componentes principais:

A. Frontend (templates/index.html)
O usuário interage com um formulário onde insere o CEP de partida e o intervalo de raízes de destino. Ele também seleciona o tipo de consulta (Detalhada ou Rápida). Ao clicar em "Calcular", o JavaScript:

Impede o envio tradicional do formulário.

Coleta todos os dados, incluindo o tipo de consulta.

Inicia uma conexão EventSource com a rota /stream-calculo do backend, passando os dados como parâmetros na URL.

Fica "ouvindo" as mensagens enviadas pelo servidor. A cada mensagem recebida, o JavaScript atualiza a barra de progresso, adiciona uma linha ao log ou preenche a tabela de resultados.

B. Servidor Flask (app.py)
É o coração que conecta o frontend à lógica de cálculo.

@app.route('/'): Renderiza a página principal index.html.

@app.route('/stream-calculo'): Esta é a rota mágica. Ela recebe os parâmetros do formulário, incluindo o tipo de consulta. Ela chama a função de cálculo correspondente e retorna um objeto Response com o mimetype='text/event-stream'. Isso mantém a conexão com o navegador aberta, permitindo que o backend envie atualizações contínuas.

@app.route('/baixar_csv'): Serve o arquivo de resultados para download.

C. Lógica Principal (logic/calculadora.py)
É o cérebro da aplicação, onde os cálculos pesados são feitos.

A função principal calcular_distancias_stream atua como um roteador. Baseado no tipo_consulta, ela chama uma de duas funções auxiliares.

_calcular_por_varredura_detalhada: Executa a lógica de consultar os 3 primeiros CEPs de cada dezena, agrupa os resultados por bairro e calcula as médias.

_calcular_por_centroide_rapido: Executa a lógica de amostragem (ex: CEPs terminados em 000, 100, 200...), calcula o ponto geográfico central e retorna um único resultado por raiz.

Ambas as funções são "geradores" (generators). Elas usam a palavra-chave yield para enviar dados de progresso de volta para o app.py assim que são gerados, permitindo o funcionamento em tempo real.

A função get_coord_from_cep é a responsável por consultar as 4 APIs externas em rodízio, tratando falhas e garantindo a maior chance de sucesso.

5. Como Executar o Projeto Localmente
Clone o Repositório: git clone git@github.com:WashintonMorais/alcular-Dist-ncias-por-Raiz-de-CEP.git

Navegue até a Pasta: cd alcular-Dist-ncias-por-Raiz-de-CEP

(Recomendado) Crie um Ambiente Virtual: python -m venv venv e ative-o.

Instale as Dependências: pip install -r requirements.txt

Execute o Servidor Flask:

Bash

export FLASK_APP=app.py
export FLASK_DEBUG=1
flask run
Acesse http://127.0.0.1:5000 no seu navegador.