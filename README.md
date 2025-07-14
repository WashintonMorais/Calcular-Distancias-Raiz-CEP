Painel de Distância por Raiz de CEP
1. Visão Geral
A Calculadora de Distâncias por Raiz de CEP é uma aplicação web desenvolvida em Python com o framework Flask. Seu objetivo é calcular a distância geodésica (usando a fórmula de Haversine) entre um CEP de partida e uma ou múltiplas "raízes" de CEP de destino (os 5 primeiros dígitos de um CEP).

A ferramenta foi projetada para lidar com tarefas longas e computacionalmente intensas de forma estável, especialmente em ambientes de nuvem como a Vercel. A arquitetura utiliza um modelo de orquestração pelo cliente, onde o navegador gerencia o fluxo de trabalho, solicitando ao servidor o processamento de uma raiz de CEP por vez. Isso garante que a aplicação não sofra com timeouts do servidor, fornecendo ao usuário atualizações de progresso em tempo real através de uma interface reativa.

2. Principais Funcionalidades
Cálculo de Distância em Dois Modos:

Consulta Detalhada: Uma varredura otimizada que consulta os 3 primeiros CEPs de cada dezena dentro de uma raiz (ex: 000, 001, 002; 010, 011, 012...). Os resultados são agrupados por bairro, com o cálculo da distância média para cada um, fornecendo um mapa detalhado da distribuição geográfica daquela raiz.

Consulta Rápida: Um método de amostragem que calcula o centro geográfico (centroide) de uma raiz de CEP a partir de 10 amostras e retorna uma única distância média, ideal para análises rápidas.

Arquitetura Resiliente a Timeouts: O frontend gerencia uma fila de raízes de CEP a serem processadas. Ele faz requisições sequenciais e curtas ao backend para cada raiz, evitando que a conexão seja interrompida por limites de tempo do servidor.

Interface Reativa em Tempo Real: Utiliza Server-Sent Events (SSE) para enviar atualizações do progresso do backend para o frontend. O usuário acompanha o processo através de uma barra de progresso (que avança a cada raiz concluída) e um log de execução detalhado.

Geração de Relatórios no Cliente: Após a conclusão dos cálculos, o usuário pode baixar um relatório completo em formato .csv. Este arquivo é gerado dinamicamente no navegador (client-side) a partir dos dados recebidos, uma abordagem moderna e compatível com qualquer plataforma de hospedagem.

Consulta Robusta a APIs: Para obter as coordenadas, a aplicação utiliza um sistema de embaralhamento e tentativa entre múltiplas APIs públicas de CEP, aumentando drasticamente a resiliência e a taxa de sucesso caso uma delas esteja fora do ar.

3. Tecnologias Utilizadas
Backend
Linguagem: Python 3

Framework Web: Flask

Bibliotecas Python:

requests: Para fazer as chamadas HTTP para as APIs de CEP externas.

concurrent.futures: Para realizar as consultas de CEP em paralelo, otimizando drasticamente o tempo de resposta.

random: Para embaralhar a lista de APIs a cada consulta.

Frontend
Estrutura: HTML5

Estilização: Tailwind CSS (para um design moderno e responsivo)

Interatividade: JavaScript (Vanilla) para:

Gerenciar o envio do formulário e a validação dos dados.

Orquestrar o fluxo de trabalho, criando uma fila de raízes e fazendo requisições sequenciais ao backend.

Estabelecer e gerenciar conexões EventSource (SSE) para cada requisição.

Atualizar dinamicamente o DOM com o progresso, logs e a tabela de resultados.

Gerar e iniciar o download do arquivo .csv no navegador.

APIs Externas Consultadas
ViaCEP: https://viacep.com.br/ws/{cep}/json/

BrasilAPI: https://brasilapi.com.br/api/cep/v2/{cep}

OpenCEP: https://opencep.com/v1/{cep}

AwesomeAPI: https://cep.awesomeapi.com.br/json/{cep}

Nominatim (OpenStreetMap): https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json

Plataforma de Deploy
Vercel: Plataforma de nuvem otimizada para "Serverless Functions", cujas limitações de tempo de execução inspiraram a arquitetura de orquestração pelo cliente.

4. Como Funciona
A arquitetura do projeto é dividida em três componentes principais que trabalham em harmonia:

A. Frontend (templates/index.html) - O Gerente
O usuário preenche o formulário. Ao clicar em "Calcular", o JavaScript:

Cria uma fila de tarefas com todas as raízes de CEP a serem consultadas (ex: ['37410', '37411', '37412']).

Inicia uma função de processamento em loop, que pega a primeira raiz da fila.

Abre uma conexão EventSource com a rota /stream-calculo, enviando os dados para processar apenas aquela raiz.

Ouve as mensagens do servidor (log, fim, erro) e atualiza a interface.

Quando recebe a mensagem fim para a raiz atual, ele fecha a conexão, adiciona os resultados à tabela, e chama a si mesmo para processar a próxima raiz da fila.

O ciclo se repete até a fila ficar vazia.

B. Servidor Flask (app.py) - O Trabalhador Focado
É a ponte que executa tarefas específicas a pedido do frontend.

@app.route('/'): Renderiza a página principal.

@app.route('/stream-calculo'): Endpoint otimizado que recebe dados para processar uma única raiz de CEP. Ele chama a lógica de cálculo, mantém a conexão aberta para enviar logs de progresso (via yield), e envia um resultado final quando termina a tarefa daquela raiz.

C. Lógica Principal (logic/calculadora.py) - O Cérebro
Contém as funções que fazem o trabalho pesado.

calcular_distancias_stream: Orquestra o cálculo para uma única raiz, chamando a função de consulta apropriada.

_calcular_por_varredura_detalhada e _calcular_por_centroide_rapido: Funções "geradoras" que executam as consultas em paralelo usando ThreadPoolExecutor e enviam (yield) atualizações de progresso.

get_coord_from_cep: Consulta as 5 APIs externas de forma resiliente.

5. Como Executar o Projeto Localmente
1. Clone o Repositório:

Bash

git clone https://github.com/WashintonMorais/Calcular-Distancias-Raiz-CEP.git
2. Navegue até a Pasta:

Bash

cd Calcular-Distancias-Raiz-CEP
3. (Recomendado) Crie e Ative um Ambiente Virtual:

Bash

# Criar
python -m venv venv

# Ativar no Windows (Git Bash)
source venv/Scripts/activate

# Ativar no macOS / Linux
source venv/bin/activate
4. Instale as Dependências:

Bash

pip install -r requirements.txt
5. Execute o Servidor Flask (Escolha um método):

Método 1 (Simples e Direto):

Bash

python app.py
Método 2 (Oficial do Flask):

No macOS/Linux:

Bash

export FLASK_APP=app.py
export FLASK_DEBUG=1
flask run
No Windows (CMD):

Bash

set FLASK_APP=app.py
set FLASK_DEBUG=1
flask run
6. Acesse http://127.0.0.1:5000 no seu navegador.