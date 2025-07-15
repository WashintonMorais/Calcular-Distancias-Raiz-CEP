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
    raiz_atual = request.args.get('raiz_atual', '').strip() 
    tipo_consulta = request.args.get('tipo_consulta', 'detalhada')
    
    if not all([cep_partida, raiz_inicial, raiz_atual, tipo_consulta]):
        return Response("data: {\"tipo\": \"erro\", \"msg\": \"Parâmetros ausentes na requisição.\"}\n\n", mimetype='text/event-stream')

    def generate():
        try:
            yield from calcular_distancias_stream(cep_partida, raiz_inicial, raiz_atual, tipo_consulta)
        except Exception as e:
            app.logger.error(f"ERRO CRÍTICO NO STREAM para a raiz {raiz_atual}: {e}", exc_info=True)
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro no servidor ao processar a raiz {raiz_atual}.'})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)