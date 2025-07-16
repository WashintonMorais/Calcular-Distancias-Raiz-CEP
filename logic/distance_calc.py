# logic/distance_calc.py
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import haversine
from .cep_service import get_info_from_cep
from .logger import get_logger

logger = get_logger(__name__)

def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_str):
    """
    Contém a lógica de busca detalhada, usando o método do "Ponto Mais Central"
    para garantir a precisão da localização de cada bairro.
    """
    yield f"data: {json.dumps({'tipo':'log','msg':f'Iniciando varredura de alta precisão para a raiz {raiz_str}...'})}\n\n"
    
    # Usando a amostragem espaçada que se provou eficaz
    ceps_para_consultar = [f"{raiz_str}{d+i:03d}" for d in range(0, 1000, 10) for i in [0, 1, 4, 7]]
    total_ceps = len(ceps_para_consultar)
    resultados_brutos = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        f_to_cep = {executor.submit(get_info_from_cep, c): c for c in ceps_para_consultar}
        
        for i, future in enumerate(as_completed(f_to_cep)):
            cep_c = f_to_cep[future]
            res_c = future.result()
            
            if res_c and res_c[0] is not None:
                lat, lon, bairro = res_c
                dist = round(haversine(lat_partida, lon_partida, lat, lon), 2)
                resultados_brutos.append({'cep': cep_c, 'bairro': bairro, 'distancia': dist, 'lat': lat, 'lon': lon})
            
            if (i+1) % 50 == 0:
                yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Verificados {i+1}/{total_ceps} CEPs...'})}\n\n"
    
    resultados_finais = []
    if resultados_brutos:
        bairros_temp = {}
        for res in resultados_brutos:
            bairro = res['bairro'].strip() if res.get('bairro') else 'Bairro não identificado'
            if bairro not in bairros_temp:
                bairros_temp[bairro] = []
            bairros_temp[bairro].append(res)
        
        for bairro, pontos in bairros_temp.items():
            if not pontos: continue

            pontos_confiaveis = pontos
            if len(pontos) > 2:
                lat_centro_preliminar = statistics.mean(p['lat'] for p in pontos)
                lon_centro_preliminar = statistics.mean(p['lon'] for p in pontos)
                pontos_confiaveis = [p for p in pontos if haversine(p['lat'], p['lon'], lat_centro_preliminar, lon_centro_preliminar) < 3]
                if not pontos_confiaveis:
                    pontos_confiaveis = pontos

            if not pontos_confiaveis: continue

            lat_centro_bairro = statistics.mean(p['lat'] for p in pontos_confiaveis)
            lon_centro_bairro = statistics.mean(p['lon'] for p in pontos_confiaveis)
            
            ponto_referencia = min(pontos_confiaveis, key=lambda p: haversine(p['lat'], p['lon'], lat_centro_bairro, lon_centro_bairro))
            
            distancia_final = round(haversine(lat_partida, lon_partida, ponto_referencia['lat'], ponto_referencia['lon']), 2)

            resultados_finais.append({
                'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': bairro,
                'distancia': distancia_final, 'tempo': round(distancia_final * 2, 1),
                'ceps_consultados': len(pontos_confiaveis), 'lat': ponto_referencia['lat'],
                'lon': ponto_referencia['lon'], 'cep_referencia': ponto_referencia['cep']
            })

        if resultados_finais:
            media_geral = round(statistics.mean(r['distancia'] for r in resultados_brutos), 2)
            resultados_finais.insert(0, {
                'tipo_linha': 'resumo_raiz', 'raiz': raiz_str, 'bairro': 'MÉDIA GERAL DA RAIZ',
                'distancia': media_geral, 'tempo': round(media_geral * 2, 1),
                'ceps_consultados': len(resultados_brutos), 'lat': None, 'lon': None, 'cep_referencia': None
            })
    
    if not resultados_finais:
        resultados_finais.append({
            'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUM CEP VÁLIDO ENCONTRADO',
            'distancia': '-', 'tempo': '-', 'ceps_consultados': 0,
            'lat': None, 'lon': None, 'cep_referencia': None
        })
    
    return sorted(resultados_finais, key=lambda x: (
        x['tipo_linha'] != 'resumo_raiz',
        x.get('distancia', 9999)
    ))

def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_str):
    """Cálculo rápido por centroide."""
    yield f"data: {json.dumps({'tipo':'log', 'msg':f'Iniciando consulta rápida para a raiz {raiz_str}...'})}\n\n"
    
    ceps_para_amostra = [f"{raiz_str}{i:03d}" for i in range(0, 1000, 100)]
    coordenadas = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i, resultado in enumerate(executor.map(get_info_from_cep, ceps_para_amostra)):
            if resultado and resultado[0] is not None:
                coordenadas.append((resultado[0], resultado[1]))
            if (i+1) % 2 == 0:
                yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Processadas {i+1}/{len(ceps_para_amostra)} amostras...'})}\n\n"
    
    if coordenadas:
        lat_media = statistics.mean(c[0] for c in coordenadas)
        lon_media = statistics.mean(c[1] for c in coordenadas)
        distancia = round(haversine(lat_partida, lon_partida, lat_media, lon_media), 2)
        
        # --- ALTERAÇÃO AQUI: Ajuste no texto do 'bairro' para incluir a raiz ---
        descricao_bairro = f"Centro da Raiz {raiz_str} ({len(coordenadas)} amostras)"
        
        resultado_final = [{
            'tipo_linha': 'bairro', 
            'raiz': raiz_str,
            'bairro': descricao_bairro, # Usando a nova descrição
            'distancia': distancia, 
            'tempo': round(distancia * 2, 1), 
            'ceps_consultados': len(coordenadas), 
            'lat': lat_media, 
            'lon': lon_media, 
            'cep_referencia': 'N/A'
        }]
    else:
        resultado_final = [{
            'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUMA AMOSTRA ENCONTRADA',
            'distancia': '-', 'tempo': '-', 'ceps_consultados': 0,
            'lat': None, 'lon': None, 'cep_referencia': None
        }]
    
    return resultado_final