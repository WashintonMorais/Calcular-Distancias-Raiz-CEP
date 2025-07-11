# logic/calculadora.py

import requests
import json
import csv
import os
import time
import logging
from math import radians, cos, sin, asin, sqrt, fsum
import random
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)); return R * c

APIS = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json",
    "https://opencep.com/v1/{cep}",
    "https://cep.awesomeapi.com.br/json/{cep}",
]

def get_coord_from_cep(cep):
    headers = {'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal)'}
    apis_embaralhadas = random.sample(APIS, len(APIS))

    for api_url_template in apis_embaralhadas:
        url_final = api_url_template.format(cep=cep.replace('-', ''))
        try:
            res = requests.get(url_final, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            lat, lon, bairro = None, None, 'N/A'

            if isinstance(data, list) and data:
                r = data[0]
                lat = r.get('lat')
                lon = r.get('lon')
                parts = r.get('display_name', '').split(','); bairro = parts[1].strip() if len(parts) > 2 else 'N/A'
            elif isinstance(data, dict):
                if data.get('erro'): continue
                lat = data.get('lat') or data.get('latitude')
                lon = data.get('lng') or data.get('longitude')
                bairro = data.get('bairro') or data.get('district') or data.get('neighborhood', 'N/A')

            # --- VALIDAÇÃO MAIS RIGOROSA ---
            # Só retorna se lat e lon forem encontrados e puderem ser convertidos para float
            if lat is not None and lon is not None:
                return float(lat), float(lon), bairro
                
        except Exception as e:
            logging.error(f"Falha na API {url_final}. Erro: {e}")
            time.sleep(0.5)
            continue
            
    return None, None, None

def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final):
    resultados = []
    total_raizes = (int(raiz_final) - int(raiz_inicial) + 1)
    raizes_processadas = 0

    for raiz in range(int(raiz_inicial), int(raiz_final) + 1):
        raiz_str = str(raiz)
        coordenadas_encontradas = []
        
        yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Buscando amostras para a raiz {raiz_str} em paralelo...', 'progresso': (raizes_processadas / total_raizes) * 100})}\n\n"
        
        ceps_para_amostra = [f"{raiz_str}{str(i).zfill(3)}" for i in range(0, 1000, 100)]
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            for resultado in executor.map(get_coord_from_cep, ceps_para_amostra):
                # --- DUPLA CAMADA DE PROTEÇÃO ---
                # Garante que o resultado e suas coordenadas não são nulos antes de usar
                if resultado and resultado[0] is not None and resultado[1] is not None:
                    lat, lon, _ = resultado
                    coordenadas_encontradas.append((lat, lon))
        
        raizes_processadas += 1

        if coordenadas_encontradas:
            lat_media = fsum(c[0] for c in coordenadas_encontradas) / len(coordenadas_encontradas)
            lon_media = fsum(c[1] for c in coordenadas_encontradas) / len(coordenadas_encontradas)
            distancia = round(haversine(lat_partida, lon_partida, lat_media, lon_media), 2)
            log_msg = f"[OK] Raiz {raiz_str} → Centro geográfico encontrado. Distância: {distancia} km"
            resultados.append({'raiz': raiz_str, 'bairro': f'Centro da Raiz ({len(coordenadas_encontradas)} amostras)', 'distancia': distancia, 'tempo': round(distancia * 2, 1), 'ceps_consultados': len(coordenadas_encontradas)})
        else:
            log_msg = f"[ERRO] Raiz {raiz_str} → Nenhuma amostra de CEP encontrada."
        
        yield f"data: {json.dumps({'tipo': 'log', 'msg': log_msg, 'progresso': round((raizes_processadas / total_raizes) * 100, 2)})}\n\n"
    
    return resultados

# ... (O resto do arquivo, incluindo _calcular_por_varredura_detalhada e calcular_distancias_stream, continua o mesmo) ...
def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_inicial, raiz_final):
    resultados_finais = []
    total_raizes = (int(raiz_final) - int(raiz_inicial) + 1)
    total_ceps_a_consultar = total_raizes * 300
    ceps_processados = 0

    for raiz in range(int(raiz_inicial), int(raiz_final) + 1):
        raiz_str = str(raiz)
        bairros_temp = {}
        distancia_total_raiz, ceps_sucesso_raiz = 0, 0

        for dezena_inicio in range(0, 1000, 10):
            for i in range(3):
                ceps_processados += 1
                cep = f"{raiz_str}{str(dezena_inicio + i).zfill(3)}"
                resultado_cep = get_coord_from_cep(cep)
                
                if resultado_cep:
                    lat, lon, bairro = resultado_cep
                    distancia = round(haversine(lat_partida, lon_partida, lat, lon), 2)
                    log_msg = f"[OK] {cep} → Bairro: {bairro} | Distância: {distancia} km"
                    distancia_total_raiz += distancia
                    ceps_sucesso_raiz += 1
                    if bairro not in bairros_temp: bairros_temp[bairro] = {'distancias': []}
                    bairros_temp[bairro]['distancias'].append(distancia)
                else:
                    log_msg = f"[ERRO] {cep} → Localização não encontrada"
                
                yield f"data: {json.dumps({'tipo': 'log', 'msg': log_msg, 'progresso': round((ceps_processados / total_ceps_a_consultar) * 100, 2)})}\n\n"

        if ceps_sucesso_raiz > 0:
            media_geral = round(distancia_total_raiz / ceps_sucesso_raiz, 2)
            resultados_finais.append({'tipo_linha': 'resumo_raiz', 'raiz': raiz_str, 'bairro': 'MÉDIA GERAL DA RAIZ', 'distancia': media_geral, 'tempo': round(media_geral * 2, 1), 'ceps_consultados': ceps_sucesso_raiz})

        for bairro, info in bairros_temp.items():
            media_bairro = round(sum(info['distancias']) / len(info['distancias']), 2)
            resultados_finais.append({'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': bairro, 'distancia': media_bairro, 'tempo': round(media_bairro * 2, 1), 'ceps_consultados': len(info['distancias'])})
    
    return resultados_finais

def calcular_distancias_stream(cep_partida_input, raiz_inicial_input, raiz_final_input, tipo_consulta):
    cep_partida = cep_partida_input.strip()
    raiz_inicial = raiz_inicial_input.strip()
    raiz_final = raiz_final_input.strip()

    if len(cep_partida) != 8:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: O CEP de Partida ({cep_partida}) deve ter exatamente 8 dígitos.'})}\n\n"; return
    if len(raiz_inicial) != 5:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: A Raiz Inicial ({raiz_inicial}) deve ter 5 dígitos.'})}\n\n"; return
    if len(raiz_final) != 5:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: A Raiz Final ({raiz_final}) deve ter 5 dígitos.'})}\n\n"; return
    
    lat_partida, lon_partida, _ = get_coord_from_cep(cep_partida)
    if not lat_partida or not lon_partida:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: CEP de partida {cep_partida} inválido ou não encontrado.'})}\n\n"; return

    resultados_finais = []
    try:
        if tipo_consulta == 'rapida':
            gen = _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final)
        else:
            gen = _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_inicial, raiz_final)
        
        while True:
            yield next(gen)
    except StopIteration as e:
        resultados_finais = e.value
    
    os.makedirs("resultados", exist_ok=True)
    with open("resultados/resultado.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Raiz", "Bairro/Descrição", "Distância(km)", "Tempo(min)", "CEPs/Amostras"])
        if resultados_finais:
            for r in resultados_finais:
                writer.writerow([r.get('raiz'), r.get('bairro'), r.get('distancia'), r.get('tempo'), r.get('ceps_consultados')])
    yield f"data: {json.dumps({'tipo': 'fim', 'resultados': resultados_finais, 'download_link': '/baixar_csv'})}\n\n"