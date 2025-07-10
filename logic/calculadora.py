# logic/calculadora.py

import requests
from math import radians, cos, sin, asin, sqrt
from itertools import cycle
import csv
import os
import json
import logging # Importar o módulo de logging

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ... (código de haversine e APIS continua o mesmo) ...
def haversine(lat1, lon1, lat2, lon2):
    R = 6371; dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)); return R * c

APIS = [
    "https://cep.awesomeapi.com.br/json/{cep}", "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://opencep.com/v1/{cep}", "https://viacep.com.br/ws/{cep}/json/",
]
api_cycle = cycle(APIS)


def get_coord_from_cep(cep):
    for _ in range(len(APIS)):
        api_url = next(api_cycle).format(cep=cep)
        try:
            res = requests.get(api_url, timeout=10)
            res.raise_for_status() # Garante que status de erro (4xx, 5xx) virem exceções
            data = res.json()
            
            # Verifica se não é uma resposta de erro da API (ex: ViaCEP com 'erro: true')
            if data.get('erro'):
                continue
            
            lat = float(data.get('lat') or data.get('latitude') or 0)
            lon = float(data.get('lng') or data.get('longitude') or 0)
            
            if lat != 0 and lon != 0:
                bairro = data.get('bairro') or data.get('district') or data.get('neighborhood', 'N/A')
                return lat, lon, bairro
        except requests.exceptions.RequestException as e:
            # Usa logging.error para registrar a falha de forma segura
            logging.error(f"Falha ao consultar API {api_url}. Erro: {e}")
            continue
        except (ValueError, KeyError) as e:
            logging.error(f"Erro ao processar JSON da API {api_url}. Erro: {e}")
            continue
            
    return None, None, None

# ... (função `calcular_distancias_stream` continua a mesma) ...
def calcular_distancias_stream(cep_partida, raiz_inicio, raiz_fim):
    print("--- EXECUTANDO A VERSÃO NOVA DO CÓDIGO ---")
    resultados = []
    ceps_sucesso = 0
    ceps_falha = 0

    lat1, lon1, _ = get_coord_from_cep(cep_partida)
    if not lat1 or not lon1:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro: CEP de partida inválido ou não encontrado.'})}\n\n"
        return

    # --- MUDANÇA 1: ATUALIZAR O TOTAL DE CEPS PARA O CÁLCULO DO PROGRESSO ---
    # Agora consultamos 100 dezenas * 3 ceps por dezena = 300 ceps por raiz
    total_raizes = (int(raiz_fim) - int(raiz_inicio) + 1)
    total_ceps = total_raizes * 300
    ceps_processados = 0

    for raiz in range(int(raiz_inicio), int(raiz_fim) + 1):
        raiz_str = str(raiz)
        bairros_temp = {}

        # --- MUDANÇA 2: SUBSTITUIR O LOOP DE 1000 POR UM LOOP ANINHADO ---
        # Loop externo: Itera pelas dezenas (0, 10, 20, ..., 990)
        for dezena_inicio in range(0, 1000, 10):
            # Loop interno: Pega apenas os 3 primeiros da dezena
            for i in range(3):
                ceps_processados += 1
                sufixo_cep = dezena_inicio + i
                
                # Formata o CEP final com 8 dígitos
                cep = f"{raiz_str}{str(sufixo_cep).zfill(3)}"
                
                lat2, lon2, bairro = get_coord_from_cep(cep)
                
                if lat2 and lon2:
                    ceps_sucesso += 1
                    distancia = round(haversine(lat1, lon1, lat2, lon2), 2)
                    log_msg = f"[OK] {cep} → Bairro: {bairro} | Distância: {distancia} km"
                    
                    if bairro not in bairros_temp:
                        bairros_temp[bairro] = {'distancias': [], 'ceps': []}
                    bairros_temp[bairro]['distancias'].append(distancia)
                    bairros_temp[bairro]['ceps'].append(cep)
                else:
                    ceps_falha += 1
                    log_msg = f"[ERRO] {cep} → Não foi possível obter localização"

                # O cálculo do progresso e o yield continuam os mesmos
                progresso = round((ceps_processados / total_ceps) * 100, 2)
                update = {'tipo': 'log', 'msg': log_msg, 'progresso': progresso}
                yield f"data: {json.dumps(update)}\n\n"

        # A consolidação dos resultados no final de cada raiz continua a mesma
        for bairro, info in bairros_temp.items():
            media = round(sum(info['distancias']) / len(info['distancias']), 2)
            tempo = round(media * 2, 1)
            resultados.append({
                'raiz': raiz_str, 'bairro': bairro, 'distancia': media,
                'tempo': tempo, 'ceps': ", ".join(info['ceps'])
            })
    
    # O salvamento do CSV e o envio final continuam os mesmos
    os.makedirs("resultados", exist_ok=True)
    with open("resultados/resultado.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Raiz de CEP", "Bairro", "Distância (km)", "Tempo Estimado (min)", "CEPs Consultados"])
        for r in resultados:
            writer.writerow([r['raiz'], r['bairro'], r['distancia'], r['tempo'], r['ceps']])

    final_data = {'tipo': 'fim', 'resultados': resultados, 'download_link': '/baixar_csv'}
    yield f"data: {json.dumps(final_data)}\n\n"