# app.py

from flask import Flask, render_template, request, Response
import json
from logic.logger import get_logger
from logic.cep_service import get_info_from_cep
from logic.distance_calc import _calcular_por_varredura_detalhada, _calcular_por_centroide_rapido

app = Flask(__name__)
logger = get_logger(__name__)

def calcular_distancias_stream(cep_partida, raiz_inicial, raiz_atual, tipo_consulta):
    """Função orquestradora que vive no app para controlar o fluxo."""
    logger.info(f"Iniciando busca para CEP de partida: {cep_partida}")
    lat_partida, lon_partida, bairro_partida = get_info_from_cep(cep_partida)
    
    if not lat_partida:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'CEP de partida {cep_partida} não encontrado.'})}\n\n"
        return

    if raiz_atual == raiz_inicial:
        yield f"data: {json.dumps({'tipo': 'partida_info', 'bairro': bairro_partida, 'cep': cep_partida, 'lat': lat_partida, 'lon': lon_partida})}\n\n"

    calculo_gen = _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_atual) if tipo_consulta == 'rapida' else _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_atual)

    resultados_finais = []
    try:
        # Consome o gerador para enviar logs e obter o resultado final
        while True:
            item = next(calculo_gen)
            # Se o item for uma lista, é o resultado final, não um log
            if isinstance(item, list):
                resultados_finais = item
                break
            yield item # Envia o log para o frontend
    except StopIteration as e:
        # Captura o valor retornado pelo gerador
        resultados_finais = e.value if e.value is not None else []
    
    yield f"data: {json.dumps({'tipo': 'fim', 'resultados': resultados_finais})}\n\n"

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
        return Response("data: {\"tipo\": \"erro\", \"msg\": \"Parâmetros ausentes.\"}\n\n", mimetype='text/event-stream')

    return Response(calcular_distancias_stream(cep_partida, raiz_inicial, raiz_atual, tipo_consulta), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)