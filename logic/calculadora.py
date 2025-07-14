import requests
import json
import logging
import random
from math import radians, cos, sin, asin, sqrt, fsum
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

APIS = [
    "https://viacep.com.br/ws/{cep}/json/", "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json",
    "https://opencep.com/v1/{cep}", "https://cep.awesomeapi.com.br/json/{cep}",
]

def haversine(lat1, lon1, lat2, lon2):
    R=6371; dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c=2*asin(sqrt(a)); return R*c

def get_coord_from_cep(cep):
    headers={'User-Agent':'CalculadoraDistancia/1.0(Projeto Pessoal)'}
    for api_url_template in random.sample(APIS,len(APIS)):
        url_final=api_url_template.format(cep=cep.replace('-',''))
        try:
            res=requests.get(url_final,headers=headers,timeout=10); res.raise_for_status(); data=res.json()
            lat,lon,bairro=None,None,'N/A'
            if isinstance(data,list)and data:
                r=data[0]; lat,lon=r.get('lat'),r.get('lon'); parts=r.get('display_name','').split(','); bairro=parts[1].strip()if len(parts)>2 else'N/A'
            elif isinstance(data,dict):
                if data.get('erro'):continue
                lat=data.get('lat')or data.get('latitude'); lon=data.get('lng')or data.get('longitude'); bairro=data.get('bairro')or data.get('district')or data.get('neighborhood','N/A')
            if lat is not None and lon is not None:return float(lat),float(lon),bairro
        except Exception:continue
    return None,None,None

def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_str):
    resultados_finais = []
    yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Buscando amostras para a raiz {raiz_str}...'})}\n\n"
    ceps_para_amostra = [f"{raiz_str}{i:03d}" for i in range(0, 1000, 100)]
    coordenadas_encontradas = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for resultado in executor.map(get_coord_from_cep, ceps_para_amostra):
            if resultado and resultado[0] is not None:
                coordenadas_encontradas.append((resultado[0], resultado[1]))
    if coordenadas_encontradas:
        lat_media = fsum(c[0] for c in coordenadas_encontradas) / len(coordenadas_encontradas)
        lon_media = fsum(c[1] for c in coordenadas_encontradas) / len(coordenadas_encontradas)
        distancia = round(haversine(lat_partida, lon_partida, lat_media, lon_media), 2)
        resultados_finais.append({'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': f'Centro da Raiz ({len(coordenadas_encontradas)} amostras)', 'distancia': distancia, 'tempo': round(distancia * 2, 1), 'ceps_consultados': len(coordenadas_encontradas)})
    else:
        resultados_finais.append({'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUMA AMOSTRA ENCONTRADA', 'distancia': '-', 'tempo': '-', 'ceps_consultados': 0})
    return resultados_finais

def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_str):
    resultados_finais = []
    yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Iniciando varredura detalhada para a raiz {raiz_str}...'})}\n\n"
    ceps_para_consultar = [f"{raiz_str}{i:03d}" for i in range(1000)]
    resultados_da_raiz = []
    with ThreadPoolExecutor(max_workers=50) as executor: # Aumentado para mais performance
        f_to_cep = {executor.submit(get_coord_from_cep, cep): cep for cep in ceps_para_consultar}
        for i, future in enumerate(as_completed(f_to_cep)):
            resultado_cep = future.result()
            if resultado_cep and resultado_cep[0] is not None:
                lat, lon, bairro = resultado_cep
                distancia = round(haversine(lat_partida, lon_partida, lat, lon), 2)
                resultados_da_raiz.append({'bairro': bairro, 'distancia': distancia})
            if (i + 1) % 100 == 0:
                yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Verificados {i+1}/{len(ceps_para_consultar)} CEPs para a raiz {raiz_str}...'})}\n\n"

    if resultados_da_raiz:
        distancia_total = sum(r['distancia'] for r in resultados_da_raiz)
        media_geral = round(distancia_total / len(resultados_da_raiz), 2)
        resultados_finais.append({'tipo_linha': 'resumo_raiz', 'raiz': raiz_str, 'bairro': 'MÉDIA GERAL DA RAIZ', 'distancia': media_geral, 'tempo': round(media_geral * 2, 1), 'ceps_consultados': len(resultados_da_raiz)})
        bairros_temp = {}
        for res in resultados_da_raiz:
            bairro = res['bairro'] if (res['bairro'] and res['bairro'].strip()) else 'Bairro não identificado'
            if bairro not in bairros_temp: bairros_temp[bairro] = []
            bairros_temp[bairro].append(res['distancia'])
        for bairro, distancias in sorted(bairros_temp.items()):
            media_bairro = round(sum(distancias) / len(distancias), 2)
            resultados_finais.append({'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': bairro, 'distancia': media_bairro, 'tempo': round(media_bairro * 2, 1), 'ceps_consultados': len(distancias)})
    else:
        resultados_finais.append({'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUM CEP VÁLIDO ENCONTRADO', 'distancia': '-', 'tempo': '-', 'ceps_consultados': 0})
    return resultados_finais

def calcular_distancias_stream(cep_partida, raiz_inicial, raiz_atual, tipo_consulta):
    if not cep_partida.isdigit() or len(cep_partida) != 8:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'CEP de Partida deve ter 8 dígitos.'})}\n\n"; return
    
    # Validação da raiz é feita no frontend, aqui só processamos.
    
    lat_partida, lon_partida, bairro_partida = get_coord_from_cep(cep_partida)
    if not lat_partida:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'CEP de partida {cep_partida} não encontrado.'})}\n\n"; return
    
    # Envia a msg de partida apenas uma vez, quando processa a primeira raiz.
    if raiz_atual == raiz_inicial:
        yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Partida de {bairro_partida or "CEP " + cep_partida} definida.'})}\n\n"

    gen = _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_atual) if tipo_consulta == 'rapida' else _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_atual)
    
    try:
        resultados_finais = yield from gen
    except StopIteration as e:
        resultados_finais = e.value
    
    yield f"data: {json.dumps({'tipo': 'fim', 'resultados': resultados_finais})}\n\n"