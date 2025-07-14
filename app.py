from flask import Flask, render_template, request, Response
from logic.calculadora import calcular_distancias_stream
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-calculo')
def stream_calculo():
    cep_partida = request.args.get('cep_partida', '').strip()
    raiz_inicial = request.args.get('raiz_inicial', '').strip()
    raiz_final = request.args.get('raiz_final', '').strip()
    tipo_consulta = request.args.get('tipo_consulta', 'detalhada')
    
    def generate():
        try:
            yield from calcular_distancias_stream(cep_partida, raiz_inicial, raiz_final, tipo_consulta)
        except Exception as e:
            app.logger.error(f"ERRO CRÍTICO NO STREAM: {e}", exc_info=True)
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro inesperado no servidor.'})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)