import requests
import json
import csv
import os
import time
import logging
from math import radians, cos, sin, asin, sqrt, fsum
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÃO INICIAL ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lista de APIs para consulta de CEP, garantindo redundância
APIS = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json",
    "https://opencep.com/v1/{cep}",
    "https://cep.awesomeapi.com.br/json/{cep}",
]

# --- FUNÇÕES CORE ---

def haversine(lat1, lon1, lat2, lon2):
    """Calcula a distância em km entre duas coordenadas geográficas."""
    R = 6371  # Raio da Terra em km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def get_coord_from_cep(cep):
    """
    Busca as coordenadas (latitude, longitude) e o bairro de um CEP
    utilizando múltiplas APIs de forma resiliente.
    """
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
                lat, lon = r.get('lat'), r.get('lon')
                parts = r.get('display_name', '').split(',')
                bairro = parts[1].strip() if len(parts) > 2 else 'N/A'
            elif isinstance(data, dict):
                if data.get('erro'): continue
                lat = data.get('lat') or data.get('latitude')
                lon = data.get('lng') or data.get('longitude')
                bairro = data.get('bairro') or data.get('district') or data.get('neighborhood', 'N/A')

            if lat is not None and lon is not None:
                return float(lat), float(lon), bairro
                
        except Exception as e:
            logging.error(f"Falha na API {url_final} para o CEP {cep}. Erro: {e}")
            time.sleep(0.25)  # Pequeno delay antes de tentar a próxima API
            continue
            
    return None, None, None

def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final):
    """Calcula a distância com base no centro geográfico de amostras de CEPs de uma raiz."""
    resultados_finais = []
    total_raizes = int(raiz_final) - int(raiz_inicial) + 1
    raizes_processadas = 0

    for raiz in range(int(raiz_inicial), int(raiz_final) + 1):
        raiz_str = str(raiz)
        raizes_processadas += 1
        progresso = round((raizes_processadas / total_raizes) * 100, 2)
        yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Buscando amostras para a raiz {raiz_str}...', 'progresso': progresso})}\n\n"
        
        ceps_para_amostra = [f"{raiz_str}{str(i).zfill(3)}" for i in range(0, 1000, 100)]
        coordenadas_encontradas = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_cep = {executor.submit(get_coord_from_cep, cep): cep for cep in ceps_para_amostra}
            for future in as_completed(future_to_cep):
                resultado = future.result()
                if resultado and resultado[0] is not None and resultado[1] is not None:
                    coordenadas_encontradas.append((resultado[0], resultado[1]))
        
        if coordenadas_encontradas:
            lat_media = fsum(c[0] for c in coordenadas_encontradas) / len(coordenadas_encontradas)
            lon_media = fsum(c[1] for c in coordenadas_encontradas) / len(coordenadas_encontradas)
            distancia = round(haversine(lat_partida, lon_partida, lat_media, lon_media), 2)
            log_msg = f"[OK] Raiz {raiz_str} → Centro geográfico encontrado. Distância: {distancia} km"
            resultados_finais.append({'raiz': raiz_str, 'bairro': f'Centro da Raiz ({len(coordenadas_encontradas)} amostras)', 'distancia': distancia, 'tempo': round(distancia * 1.5, 1), 'ceps_consultados': len(coordenadas_encontradas)})
        else:
            log_msg = f"[ERRO] Raiz {raiz_str} → Nenhuma amostra de CEP encontrada."
        
        yield f"data: {json.dumps({'tipo': 'log', 'msg': log_msg, 'progresso': progresso})}\n\n"
    
    return resultados_finais

def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_inicial, raiz_final):
    """
    [REATORADO PARA ALTA PERFORMANCE]
    Calcula a distância para múltiplas amostras de CEPs, agrupando por bairro.
    Utiliza processamento concorrente para acelerar as consultas.
    """
    resultados_finais = []
    total_raizes = int(raiz_final) - int(raiz_inicial) + 1
    total_ceps_a_consultar = total_raizes * 300  # 3 amostras por dezena
    ceps_processados = 0

    for idx, raiz in enumerate(range(int(raiz_inicial), int(raiz_final) + 1)):
        raiz_str = str(raiz)
        yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Iniciando varredura detalhada para a raiz {raiz_str}...', 'progresso': round((ceps_processados / total_ceps_a_consultar) * 100, 2)})}\n\n"

        ceps_para_consultar = [f"{raiz_str}{str(dezena_inicio + i).zfill(3)}" for dezena_inicio in range(0, 1000, 10) for i in range(3)]
        
        resultados_da_raiz = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_cep = {executor.submit(get_coord_from_cep, cep): cep for cep in ceps_para_consultar}

            for future in as_completed(future_to_cep):
                cep = future_to_cep[future]
                resultado_cep = future.result()
                ceps_processados += 1
                progresso = round((ceps_processados / total_ceps_a_consultar) * 100, 2)

                if resultado_cep and resultado_cep[0] is not None:
                    lat, lon, bairro = resultado_cep
                    distancia = round(haversine(lat_partida, lon_partida, lat, lon), 2)
                    log_msg = f"[OK] {cep} → Bairro: {bairro} | Distância: {distancia} km"
                    resultados_da_raiz.append({'bairro': bairro, 'distancia': distancia})
                else:
                    log_msg = f"[ERRO] {cep} → Localização não encontrada"
                
                yield f"data: {json.dumps({'tipo': 'log', 'msg': log_msg, 'progresso': progresso})}\n\n"

        # --- Consolidação dos resultados da raiz ---
        if resultados_da_raiz:
            bairros_temp = {}
            distancia_total_raiz = sum(r['distancia'] for r in resultados_da_raiz)
            media_geral = round(distancia_total_raiz / len(resultados_da_raiz), 2)
            
            # Adiciona a linha de resumo da raiz
            resultados_finais.append({'tipo_linha': 'resumo_raiz', 'raiz': raiz_str, 'bairro': 'MÉDIA GERAL DA RAIZ', 'distancia': media_geral, 'tempo': round(media_geral * 1.5, 1), 'ceps_consultados': len(resultados_da_raiz)})

            # Agrupa por bairro para calcular médias específicas
            for res in resultados_da_raiz:
                bairro = res['bairro']
                if bairro not in bairros_temp:
                    bairros_temp[bairro] = {'distancias': []}
                bairros_temp[bairro]['distancias'].append(res['distancia'])

            # Adiciona as linhas de cada bairro
            for bairro, info in sorted(bairros_temp.items()):
                media_bairro = round(sum(info['distancias']) / len(info['distancias']), 2)
                resultados_finais.append({'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': bairro, 'distancia': media_bairro, 'tempo': round(media_bairro * 1.5, 1), 'ceps_consultados': len(info['distancias'])})
        else:
             yield f"data: {json.dumps({'tipo': 'log', 'msg': f'[AVISO] Nenhum CEP encontrado para a raiz {raiz_str}.', 'progresso': progresso})}\n\n"

    return resultados_finais

def calcular_distancias_stream(cep_partida_input, raiz_inicial_input, raiz_final_input, tipo_consulta):
    """Função principal que orquestra o cálculo e gera o stream de eventos."""
    cep_partida = cep_partida_input.strip()
    raiz_inicial = raiz_inicial_input.strip()
    raiz_final = raiz_final_input.strip()

    # --- VALIDAÇÃO DE ENTRADA ROBUSTA ---
    if not cep_partida.isdigit() or len(cep_partida) != 8:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro: O CEP de Partida deve conter exatamente 8 dígitos numéricos.'})}\n\n"; return
    if not raiz_inicial.isdigit() or len(raiz_inicial) != 5:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro: A Raiz Inicial deve conter exatamente 5 dígitos numéricos.'})}\n\n"; return
    if not raiz_final.isdigit() or len(raiz_final) != 5:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro: A Raiz Final deve conter exatamente 5 dígitos numéricos.'})}\n\n"; return
    if int(raiz_inicial) > int(raiz_final):
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro: A Raiz Inicial não pode ser maior que a Raiz Final.'})}\n\n"; return
    
    yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Buscando coordenadas para o CEP de partida {cep_partida}...'})}\n\n"
    lat_partida, lon_partida, bairro_partida = get_coord_from_cep(cep_partida)
    if not lat_partida or not lon_partida:
        yield f"data: {json.dumps({'tipo': 'erro', 'msg': f'Erro: CEP de partida {cep_partida} inválido ou não encontrado.'})}\n\n"; return
    yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Partida de {bairro_partida} ({cep_partida}) definida.'})}\n\n"

    resultados_finais = []
    try:
        if tipo_consulta == 'rapida':
            gen = _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_inicial, raiz_final)
        else:
            gen = _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_inicial, raiz_final)
        
        # Consome o gerador para obter os logs e o progresso
        yield from gen
        # A StopIteration é capturada para obter o valor de retorno do gerador
    except StopIteration as e:
        resultados_finais = e.value
    
    # Salva os resultados em um arquivo CSV
    os.makedirs("resultados", exist_ok=True)
    caminho_csv = "resultados/resultado.csv"
    with open(caminho_csv, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Raiz", "Bairro/Descricao", "Distancia_Media(km)", "Tempo_Estimado(min)", "CEPs_Amostras_Encontradas"])
        if resultados_finais:
            for r in resultados_finais:
                writer.writerow([r.get('raiz'), r.get('bairro'), r.get('distancia'), r.get('tempo'), r.get('ceps_consultados')])

    yield f"data: {json.dumps({'tipo': 'fim', 'resultados': resultados_finais, 'download_link': '/baixar_csv'})}\n\n"