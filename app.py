from flask import Flask, render_template, request, send_file, Response
from logic.calculadora import calcular_distancias_stream
import os
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-calculo')
def stream_calculo():
    cep_partida = request.args.get('cep_partida', '')
    raiz_inicial = request.args.get('raiz_inicial', '')
    raiz_final = request.args.get('raiz_final', '')
    tipo_consulta = request.args.get('tipo_consulta', 'detalhada')
    
    def generate():
        try:
            yield from calcular_distancias_stream(cep_partida, raiz_inicial, raiz_final, tipo_consulta)
        except Exception as e:
            app.logger.error(f"ERRO CRÍTICO NO STREAM: {e}", exc_info=True)
            error_message = {'tipo': 'erro', 'msg': 'Ocorreu um erro inesperado no servidor.'}
            yield f"data: {json.dumps(error_message)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/baixar_csv')
def baixar_csv():
    caminho_csv = 'resultados/resultado.csv'
    return send_file(caminho_csv, as_attachment=True, download_name='distancias_calculadas.csv')

if __name__ == '__main__':
    os.makedirs('resultados', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)