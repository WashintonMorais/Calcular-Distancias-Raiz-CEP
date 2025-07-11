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

# --- LISTA DE APIS ATUALIZADA COM A NOMINATIM ---
APIS = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json", # <- NOVA
    "https://opencep.com/v1/{cep}",
    "https://cep.awesomeapi.com.br/json/{cep}",
]
api_cycle = cycle(APIS)

def get_coord_from_cep(cep):
    # --- CABEÇALHO OBRIGATÓRIO PARA A NOMINATIM ---
    headers = {
        'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal - washinton.morais@email.com)'
    }
    # (É uma boa prática usar um email de contato real no User-Agent)

    for _ in range(len(APIS)):
        api_url = next(api_cycle)
        
        # Formata a URL (remove o hífen do CEP para a maioria das APIs)
        formatted_cep = cep.replace('-', '')
        url_final = api_url.format(cep=formatted_cep)
        
        try:
            # Adiciona o cabeçalho 'headers' à requisição
            res = requests.get(url_final, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()

            # --- LÓGICA DE EXTRAÇÃO ATUALIZADA ---
            lat, lon, bairro = 0, 0, 'N/A'

            # Se a resposta for uma lista (caso da Nominatim)
            if isinstance(data, list) and data:
                primeiro_resultado = data[0]
                lat = float(primeiro_resultado.get('lat') or 0)
                lon = float(primeiro_resultado.get('lon') or 0)
                # Tenta pegar um nome de bairro/distrito do display_name
                display_parts = primeiro_resultado.get('display_name', '').split(',')
                if len(display_parts) > 2:
                    bairro = display_parts[1].strip()

            # Se for um dicionário (outras APIs)
            elif isinstance(data, dict):
                if data.get('erro'): continue
                lat = float(data.get('lat') or data.get('latitude') or 0)
                lon = float(data.get('lng') or data.get('longitude') or 0)
                bairro = data.get('bairro') or data.get('district') or data.get('neighborhood', 'N/A')

            if lat != 0 and lon != 0:
                return lat, lon, bairro
            
        except Exception as e:
            logging.error(f"Falha ou erro na API {url_final}. Erro: {e}")
            time.sleep(1) # Adiciona uma pausa de 1 segundo para respeitar limites de API
            continue
            
    return None, None, None

# --- LÓGICA 1: CONSULTA RÁPIDA (CENTRO DA RAIZ) - AGORA EM PARALELO ---
def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final):
    resultados = []
    total_raizes = (int(raiz_final) - int(raiz_inicial) + 1)
    raizes_processadas = 0

    for raiz in range(int(raiz_inicial), int(raiz_final) + 1):
        raiz_str = str(raiz)
        coordenadas_encontradas = []
        
        yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Buscando amostras para a raiz {raiz_str} em paralelo...', 'progresso': (raizes_processadas / total_raizes) * 100})}\n\n"
        
        # Cria a lista de 10 CEPs para amostra
        ceps_para_amostra = [f"{raiz_str}{str(i).zfill(3)}" for i in range(0, 1000, 100)]
        
        # Executa as 10 chamadas de API em threads paralelas
        with ThreadPoolExecutor(max_workers=10) as executor:
            # O `map` aplica a função `get_coord_from_cep` a cada item da lista de CEPs
            for resultado in executor.map(get_coord_from_cep, ceps_para_amostra):
                if resultado:
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

# --- LÓGICA 2: CONSULTA DETALHADA (POR BAIRRO) - SEM ALTERAÇÃO ---
def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_inicial, raiz_final):
    # Esta função continua a mesma, pois suas chamadas já são mais distribuídas
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

# --- FUNÇÃO PRINCIPAL (ROTEADOR) ---
# Esta função foi simplificada para ser mais robusta
def calcular_distancias_stream(cep_partida_input, raiz_inicial_input, raiz_final_input, tipo_consulta):
    cep_partida = cep_partida_input.strip()
    raiz_inicial = raiz_inicial_input.strip()
    raiz_final = raiz_final_input.strip()

    # Validações de entrada
    if len(cep_partida) != 8:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: O CEP de Partida deve ter 8 dígitos.'})}\n\n"; return
    if len(raiz_inicial) != 5:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: A Raiz Inicial deve ter 5 dígitos.'})}\n\n"; return
    if len(raiz_final) != 5:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: A Raiz Final deve ter 5 dígitos.'})}\n\n"; return
    
    lat_partida, lon_partida, _ = get_coord_from_cep(cep_partida)
    if not lat_partida or not lon_partida:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: CEP de partida {cep_partida} inválido ou não encontrado.'})}\n\n"; return

    # Execução e captura de resultados
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
    
    # Finalização
    os.makedirs("resultados", exist_ok=True)
    with open("resultados/resultado.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Raiz", "Bairro/Descrição", "Distância(km)", "Tempo(min)", "CEPs/Amostras"])
        if resultados_finais:
            for r in resultados_finais:
                writer.writerow([r.get('raiz'), r.get('bairro'), r.get('distancia'), r.get('tempo'), r.get('ceps_consultados')])
    yield f"data: {json.dumps({'tipo': 'fim', 'resultados': resultados_finais, 'download_link': '/baixar_csv'})}\n\n"