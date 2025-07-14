from flask import Flask, render_template, request, send_file, Response
from logic.calculadora import calcular_distancias_stream
import os
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    """Renderiza a página inicial da aplicação."""
    return render_template('index.html')

@app.route('/stream-calculo')
def stream_calculo():
    """
    Endpoint que inicia o cálculo e transmite os resultados em tempo real
    usando Server-Sent Events (SSE).
    """
    # Coleta os parâmetros da requisição GET
    cep_partida = request.args.get('cep_partida', '')
    raiz_inicial = request.args.get('raiz_inicial', '')
    raiz_final = request.args.get('raiz_final', '')
    tipo_consulta = request.args.get('tipo_consulta', 'detalhada')
    
    def generate():
        """Função geradora que produz o fluxo de eventos."""
        try:
            # Delega a geração do stream para a função de lógica de negócio
            yield from calcular_distancias_stream(cep_partida, raiz_inicial, raiz_final, tipo_consulta)
        except Exception as e:
            # Captura exceções críticas e informa o cliente
            app.logger.error(f"ERRO CRÍTICO NO STREAM: {e}", exc_info=True)
            error_message = {'tipo': 'erro', 'msg': 'Ocorreu um erro inesperado no servidor. Verifique os logs.'}
            yield f"data: {json.dumps(error_message)}\n\n"

    # Retorna uma Resposta HTTP com o mimetype correto para SSE
    return Response(generate(), mimetype='text/event-stream')

@app.route('/baixar_csv')
def baixar_csv():
    """Endpoint para permitir o download do arquivo CSV com os resultados."""
    caminho_csv = 'resultados/resultado.csv'
    if os.path.exists(caminho_csv):
        return send_file(caminho_csv, as_attachment=True, download_name='distancias_calculadas.csv')
    return "Arquivo não encontrado.", 404

if __name__ == '__main__':
    # Garante que o diretório de resultados exista ao iniciar
    os.makedirs('resultados', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)