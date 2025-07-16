Painel de Distância por Raiz de CEP - Documentação Atualizada
1. Visão Geral
A Calculadora de Distâncias por Raiz de CEP é uma aplicação web desenvolvida em Python com o framework Flask. Seu objetivo é calcular a distância geodésica (usando a fórmula de Haversine) entre um CEP de partida e uma ou múltiplas "raízes" de CEP de destino (os 5 primeiros dígitos de um CEP).

A ferramenta foi projetada para lidar com a instabilidade e a inconsistência de dados de APIs públicas. Sua arquitetura utiliza um modelo de orquestração pelo cliente, onde o navegador gerencia o fluxo de trabalho, solicitando ao servidor o processamento de uma raiz de CEP por vez. Isso garante que a aplicação não sofra com timeouts do servidor, fornecendo ao usuário atualizações de progresso em tempo real através de uma interface reativa.

2. Principais Funcionalidades
Cálculo de Distância em Dois Modos:

Consulta Detalhada (Alta Precisão): Realiza uma amostragem espaçada e inteligente, consultando CEPs com terminações como 0, 1, 4 e 7 em cada dezena para garantir uma cobertura geográfica ampla. A funcionalidade mais poderosa é o uso do método do "Ponto Mais Central": para cada bairro, a aplicação calcula o centro geográfico (centroide) de todas as amostras encontradas e elege o CEP real mais próximo deste centro como o ponto de referência definitivo. Isso neutraliza outliers e garante altíssima precisão na distância final.

Consulta Rápida (Centro da Raiz): Um método de amostragem que calcula o centro geográfico (centroide) de uma raiz de CEP a partir de 10 amostras. O resultado é um único pino no mapa que agora identifica a raiz consultada (ex: "Centro da Raiz 37416"), fornecendo maior clareza ao usuário.

Arquitetura Resiliente a Timeouts: O frontend gerencia uma fila de raízes de CEP, fazendo requisições sequenciais e curtas ao backend para cada raiz. Isso torna a aplicação robusta e compatível com plataformas de nuvem com limites de tempo de execução (ex: Vercel, Heroku).

Consulta de Dados com "Funil de Enriquecimento": Para obter as coordenadas, a aplicação utiliza uma estratégia sofisticada em múltiplas etapas e fontes:

Validação de Endereço: Consulta em paralelo as APIs OpenCEP e ViaCEP para obter um endereço base confiável.

Coleta de Coordenadas: Com um endereço válido, consulta em paralelo as APIs BrasilAPI e AwesomeAPI. As coordenadas obtidas são agregadas e uma média é calculada para aumentar a precisão.

Fallback Inteligente: Se as fontes de coordenadas falham, o sistema recorre a uma geocodificação de precisão (via Nominatim) usando o endereço base validado. Se mesmo o endereço base não for encontrado, ele tenta uma busca direta por coordenadas, garantindo a máxima cobertura possível.

Interface Reativa e Visualização Aprimorada:

Utiliza Server-Sent Events (SSE) para enviar o progresso e logs do backend para o frontend em tempo real.

O mapa de resultados, desenvolvido com Leaflet, agora inclui um controle de tela cheia (fullscreen) para melhor análise e exploração dos dados geográficos.

Geração de Relatórios no Cliente: Após a conclusão, o usuário pode baixar um relatório completo em formato .csv, gerado dinamicamente no navegador.

3. Tecnologias Utilizadas
Backend

Linguagem: Python 3

Framework Web: Flask

Bibliotecas Python:

requests: Para fazer as chamadas HTTP para as APIs de CEP externas.

concurrent.futures: Para realizar as consultas de CEP em paralelo, otimizando o tempo de resposta.

statistics: Para cálculos de média no método do "Ponto Mais Central" e na agregação de coordenadas.

Frontend

Estrutura: HTML5

Estilização: Tailwind CSS

Interatividade: JavaScript (Vanilla)

Mapas: Leaflet.js com o plugin Leaflet.fullscreen

APIs Externas Consultadas (em ordem de preferência e especialidade)

Endereço: OpenCEP, ViaCEP

Coordenadas: BrasilAPI, AwesomeAPI

Geocodificação (Fallback): Nominatim (OpenStreetMap)

4. Como Funciona
A arquitetura do projeto é dividida em três componentes principais:

A. Frontend (templates/index.html) - O Gerente

O JavaScript no lado do cliente cria uma fila de tarefas (raízes de CEP) e requisita o processamento de uma por vez ao servidor através de uma conexão EventSource. Ele gerencia a atualização da interface (logs, progresso, tabela, mapa) e só chama a próxima tarefa quando a anterior é concluída, garantindo que o servidor nunca fique sobrecarregado.

B. Servidor Flask (app.py) - O Trabalhador Focado

Atua como um executor de tarefas. A rota /stream-calculo recebe a requisição para uma única raiz, chama a lógica de cálculo apropriada (detalhada ou rápida), e transmite os resultados e logs de volta para o cliente usando a técnica de yield.

C. Lógica Principal (módulos em logic/) - O Cérebro

logic/cep_service.py: Implementa o "Funil de Enriquecimento de Dados", orquestrando as chamadas paralelas às APIs externas para obter os dados mais confiáveis no menor tempo possível.

logic/distance_calc.py: Contém as duas estratégias de cálculo:

_calcular_por_varredura_detalhada: Realiza a amostragem espaçada e aplica a robusta lógica do "Ponto Mais Central".

_calcular_por_centroide_rapido: Realiza o cálculo rápido para o centro da raiz.

logic/geocoding.py: Módulo auxiliar para a geocodificação de precisão (Fallback).

5. Como Executar o Projeto Localmente
Clone o Repositório:

Bash

git clone https://github.com/WashintonMorais/Calcular-Distancias-Raiz-CEP.git
Navegue até a Pasta:

Bash

cd Calcular-Distancias-Raiz-CEP
(Recomendado) Crie e Ative um Ambiente Virtual:

Bash

# Criar
python -m venv venv

# Ativar no Windows
.\venv\Scripts\activate

# Ativar no macOS / Linux
source venv/bin/activate
Instale as Dependências:

Bash

pip install -r requirements.txt
Execute o Servidor Flask:

Bash

flask run
Se o comando flask não for encontrado, você pode usar python -m flask run.

Acesse http://127.0.0.1:5000 no seu navegador.