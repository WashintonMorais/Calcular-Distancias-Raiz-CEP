import requests
import json
import csv
import os
import time
import logging
from math import radians, cos, sin, asin, sqrt, fsum
from itertools import cycle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)); return R * c

APIS = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://cep.awesomeapi.com.br/json/{cep}",
    "https://opencep.com/v1/{cep}",
]
api_cycle = cycle(APIS)

def get_coord_from_cep(cep):
    for _ in range(len(APIS)):
        api_url = next(api_cycle).format(cep=cep)
        try:
            res = requests.get(api_url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('erro'): continue
            
            lat = float(data.get('lat') or data.get('latitude') or data.get('location', {}).get('coordinates', {}).get('latitude') or 0)
            lon = float(data.get('lng') or data.get('longitude') or data.get('location', {}).get('coordinates', {}).get('longitude') or 0)
            
            if lat != 0 and lon != 0:
                bairro = data.get('bairro') or data.get('district') or data.get('neighborhood', 'N/A')
                return lat, lon, bairro
        except requests.exceptions.RequestException as e:
            logging.error(f"Falha na API {api_url} para CEP {cep}. Erro: {e}")
            time.sleep(0.05)
            continue
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logging.error(f"Erro de JSON/dados na API {api_url} para CEP {cep}. Erro: {e}")
            continue
            
    return None, None, None

def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final):
    resultados = []
    total_raizes = (int(raiz_final) - int(raiz_inicial) + 1)
    raizes_processadas = 0

    for raiz in range(int(raiz_inicial), int(raiz_final) + 1):
        raiz_str = str(raiz)
        coordenadas_encontradas = []
        
        yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Buscando amostras para a raiz {raiz_str}...', 'progresso': (raizes_processadas / total_raizes) * 100})}\n\n"
        for i in range(0, 1000, 100):
            lat, lon, _ = get_coord_from_cep(f"{raiz_str}{str(i).zfill(3)}")
            if lat and lon:
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
                lat, lon, bairro = get_coord_from_cep(cep)
                
                if lat and lon:
                    distancia = round(haversine(lat_partida, lon_partida, lat, lon), 2)
                    log_msg = f"[OK] {cep} → Bairro: {bairro} | Distância: {distancia} km"
                    distancia_total_raiz += distancia
                    ceps_sucesso_raiz += 1
                    if bairro not in bairros_temp: bairros_temp[bairro] = {'distancias': [], 'ceps': []}
                    bairros_temp[bairro]['distancias'].append(distancia)
                else:
                    log_msg = f"[ERRO] {cep} → Localização não encontrada"
                
                yield f"data: {json.dumps({'tipo': 'log', 'msg': log_msg, 'progresso': round((ceps_processados / total_ceps_a_consultar) * 100, 2)})}\n\n"

        if ceps_sucesso_raiz > 0:
            media_geral = round(distancia_total_raiz / ceps_sucesso_raiz, 2)
            resultados_finais.append({'tipo_linha': 'resumo_raiz', 'raiz': raiz_str, 'bairro': 'MÉDIA GERAL DA RAIZ', 'distancia': media_geral, 'tempo': round(media_geral * 2, 1), 'ceps_consultados': ceps_sucesso_raiz})

        for bairro, info in bairros_temp.items():
            media_bairro = round(sum(info['distancias']) / len(info['distancias']), 2)
            resultados_finais.append({'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': bairro, 'distancia': media_bairro, 'tempo': round(media_bairro * 2, 1), 'ceps_consultados': len(info['ceps'])})
    
    return resultados_finais

def calcular_distancias_stream(cep_partida_input, raiz_inicial_input, raiz_final_input, tipo_consulta):
    # 1. VALIDAÇÃO DE ENTRADA REFORÇADA
    cep_partida = cep_partida_input.strip()
    raiz_inicial = raiz_inicial_input.strip()[:5]
    raiz_final = raiz_final_input.strip()[:5]

    if len(cep_partida) != 8:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: O CEP de Partida ({cep_partida}) deve ter exatamente 8 dígitos.'})}\n\n"
        return
    if not (raiz_inicial.isdigit() and raiz_final.isdigit() and cep_partida.isdigit()):
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro: Todos os campos devem conter apenas números.'})}\n\n"
        return

    # 2. BUSCA DAS COORDENADAS DE PARTIDA
    lat_partida, lon_partida, _ = get_coord_from_cep(cep_partida)
    if not lat_partida or not lon_partida:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: CEP de partida {cep_partida} inválido ou não encontrado.'})}\n\n"
        return

    # 3. EXECUÇÃO E CAPTURA DE RESULTADOS
    resultados_finais = []
    # Usamos um 'try' para capturar o valor de retorno do gerador
    try:
        if tipo_consulta == 'rapida':
            gen = _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final)
        else:
            gen = _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_inicial, raiz_final)
        
        # Iteramos sobre o gerador, passando cada 'yield' para o cliente
        while True:
            yield next(gen)
    except StopIteration as e:
        # Quando o gerador termina, capturamos seu valor de retorno
        resultados_finais = e.value
    
    # 4. SALVAMENTO DO CSV E MENSAGEM FINAL
    os.makedirs("resultados", exist_ok=True)
    csv_header = ["Raiz de CEP", "Bairro/Descrição", "Distância (km)", "Tempo Estimado (min)", "CEPs/Amostras"]
    with open("resultados/resultado.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        for r in resultados_finais:
            writer.writerow([r.get('raiz'), r.get('bairro'), r.get('distancia'), r.get('tempo'), r.get('ceps_consultados')])

    yield f"data: {json.dumps({'tipo': 'fim', 'resultados': resultados_finais, 'download_link': '/baixar_csv'})}\n\n"