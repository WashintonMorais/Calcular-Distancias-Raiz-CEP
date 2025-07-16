# logic/distance_calc.py
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import haversine
from .cep_service import get_info_from_cep
from .logger import get_logger

logger = get_logger(__name__)

def _calcular_centroide(pontos):
    """Calcula a latitude e longitude média (centroide) de uma lista de pontos."""
    if not pontos:
        return None, None
    
    lat_media = sum(p['lat'] for p in pontos) / len(pontos)
    lon_media = sum(p['lon'] for p in pontos) / len(pontos)
    return lat_media, lon_media

def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_str):
    """
    Contém a lógica de busca detalhada, com um filtro estatístico de duas etapas
    para remover outliers e garantir a precisão dos dados.
    """
    yield f"data: {json.dumps({'tipo':'log','msg':f'Iniciando varredura de alta precisão para a raiz {raiz_str}...'})}\n\n"
    
    # PASSO 1: Coleta dos dados brutos
    ceps_para_consultar = [f"{raiz_str}{d+i:03d}" for d in range(0, 1000, 10) for i in range(3)]
    total_ceps = len(ceps_para_consultar)
    resultados_brutos = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        f_to_cep = {executor.submit(get_info_from_cep, c): c for c in ceps_para_consultar}
        
        for i, future in enumerate(as_completed(f_to_cep)):
            cep_c = f_to_cep[future]
            res_c = future.result()
            
            if res_c and res_c[0] is not None:
                lat, lon, bairro = res_c
                dist = round(haversine(lat_partida, lon_partida, lat, lon), 2)
                resultados_brutos.append({
                    'cep': cep_c, 'bairro': bairro, 'distancia': dist,
                    'lat': lat, 'lon': lon
                })
            
            if (i+1) % 10 == 0:
                yield f"data: {json.dumps({'tipo': 'log', 'msg': f'Verificados {i+1}/{total_ceps} CEPs...'})}\n\n"
    
    if not resultados_brutos:
        return [{
            'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUM CEP VÁLIDO ENCONTRADO',
            'distancia': '-', 'tempo': '-', 'ceps_consultados': 0, 'lat': None, 'lon': None, 'cep_referencia': None
        }]

    # --- INÍCIO DA LÓGICA DE FILTRAGEM DE DUAS ETAPAS ---

    # PASSO 2.A: Calcular centroide inicial e distâncias
    lat_centro_ingenuo, lon_centro_ingenuo = _calcular_centroide(resultados_brutos)
    distancias_ao_centro = [haversine(p['lat'], p['lon'], lat_centro_ingenuo, lon_centro_ingenuo) for p in resultados_brutos]

    # PASSO 2.B: Identificar outliers estatisticamente
    pontos_preliminares = resultados_brutos
    if len(distancias_ao_centro) > 1:
        media_distancias = statistics.mean(distancias_ao_centro)
        try:
            # stdev precisa de pelo menos 2 pontos
            desvio_padrao_distancias = statistics.stdev(distancias_ao_centro)
        except statistics.StatisticsError:
            desvio_padrao_distancias = 0 # Não há desvio com 1 ponto

        if desvio_padrao_distancias > 0:
            FATOR_DESVIO_PADRAO = 2.0
            limite_distancia = media_distancias + FATOR_DESVIO_PADRAO * desvio_padrao_distancias
            pontos_preliminares = [ponto for ponto, dist in zip(resultados_brutos, distancias_ao_centro) if dist <= limite_distancia]
    
    # PASSO 3: Calcular o centroide robusto
    msg_centroide = f"Calculando centroide robusto com {len(pontos_preliminares)}/{len(resultados_brutos)} amostras."
    yield f"data: {json.dumps({'tipo':'log', 'msg': msg_centroide})}\n\n"
    lat_centroide_robusto, lon_centroide_robusto = _calcular_centroide(pontos_preliminares)

    # PASSO 4: Validação final usando o centroide robusto
    RAIO_MAX_KM = 10.0
    resultados_confiaveis = []
    for ponto in resultados_brutos:
        distancia_final = haversine(ponto['lat'], ponto['lon'], lat_centroide_robusto, lon_centroide_robusto)
        if distancia_final <= RAIO_MAX_KM:
            resultados_confiaveis.append(ponto)
        else:
            msg_outlier = f"Outlier descartado: CEP {ponto['cep']} está a {distancia_final:.1f} km do centro da raiz."
            yield f"data: {json.dumps({'tipo':'log', 'msg': f'⚠️ {msg_outlier}'})}\n\n"

    yield f"data: {json.dumps({'tipo':'log', 'msg': f'Processo final com {len(resultados_confiaveis)} pontos confiáveis.'})}\n\n"
    
    # --- FIM DA LÓGICA DE FILTRAGEM ---

    # O restante do código agora usa a lista 'resultados_confiaveis'
    resultados_finais = []
    if resultados_confiaveis:
        bairros_temp = {}
        for res in resultados_confiaveis:
            bairro = res['bairro'] if res['bairro'] and res['bairro'].strip() else 'Bairro não identificado'
            if bairro not in bairros_temp:
                bairros_temp[bairro] = []
            bairros_temp[bairro].append(res)
        
        for bairro, pontos in bairros_temp.items():
            # A filtragem de pontos dentro do bairro se torna menos crítica, mas ainda é uma boa prática
            if len(pontos) > 2:
                lat_centro_bairro = sum(p['lat'] for p in pontos) / len(pontos)
                lon_centro_bairro = sum(p['lon'] for p in pontos) / len(pontos)
                pontos_bairro_filtrados = [p for p in pontos if haversine(p['lat'], p['lon'], lat_centro_bairro, lon_centro_bairro) < 3]
                if not pontos_bairro_filtrados: pontos_bairro_filtrados = pontos
            else:
                pontos_bairro_filtrados = pontos
            
            ponto_campeao = min(pontos_bairro_filtrados, key=lambda p: p['distancia'])
            resultados_finais.append({
                'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': bairro,
                'distancia': ponto_campeao['distancia'], 'tempo': round(ponto_campeao['distancia'] * 2, 1),
                'ceps_consultados': len(pontos_bairro_filtrados), 'lat': ponto_campeao['lat'],
                'lon': ponto_campeao['lon'], 'cep_referencia': ponto_campeao['cep']
            })

        media_geral = round(sum(r['distancia'] for r in resultados_confiaveis) / len(resultados_confiaveis), 2)
        resultados_finais.insert(0, {
            'tipo_linha': 'resumo_raiz', 'raiz': raiz_str, 'bairro': 'MÉDIA GERAL DA RAIZ',
            'distancia': media_geral, 'tempo': round(media_geral * 2, 1),
            'ceps_consultados': len(resultados_confiaveis), 'lat': None, 'lon': None, 'cep_referencia': None
        })
    
    if not resultados_finais:
        resultados_finais.append({
            'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUM PONTO CONFIÁVEL ENCONTRADO',
            'distancia': '-', 'tempo': '-', 'ceps_consultados': 0, 'lat': None, 'lon': None, 'cep_referencia': None
        })
    
    return sorted(resultados_finais, key=lambda x: (
        x['tipo_linha'] != 'resumo_raiz',
        x.get('distancia', 9999) if isinstance(x.get('distancia'), (int, float)) else 9999
    ))


def _calcular_por_centroide_rapido(lat_partida, lon_partida, raiz_str):
    """Cálculo rápido por centroide. (Não precisa de filtro complexo)."""
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
        lat_media = sum(c[0] for c in coordenadas) / len(coordenadas)
        lon_media = sum(c[1] for c in coordenadas) / len(coordenadas)
        distancia = round(haversine(lat_partida, lon_partida, lat_media, lon_media), 2)
        resultado_final = [{
            'tipo_linha': 'bairro', 'raiz': raiz_str, 'bairro': f'Centro da Raiz ({len(coordenadas)} amostras)',
            'distancia': distancia, 'tempo': round(distancia * 2, 1),
            'ceps_consultados': len(coordenadas), 'lat': lat_media, 'lon': lon_media, 'cep_referencia': 'N/A'
        }]
    else:
        resultado_final = [{
            'tipo_linha': 'erro_raiz', 'raiz': raiz_str, 'bairro': 'NENHUMA AMOSTRA ENCONTRADA',
            'distancia': '-', 'tempo': '-', 'ceps_consultados': 0, 'lat': None, 'lon': None, 'cep_referencia': None
        }]
    
    return resultado_final