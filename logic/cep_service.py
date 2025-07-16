# logic/cep_service.py
import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from .geocoding import get_precise_coord # Reutilizamos esta função
from .logger import get_logger

logger = get_logger(__name__)
HEADERS = {'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal)'}

# --- Funções Especialistas para cada API ---

def _query_address_api(url_template, cep):
    """Tenta obter dados de endereço de uma API."""
    try:
        res = requests.get(url_template.format(cep=cep), headers=HEADERS, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if not data.get('erro') and data.get('bairro'):
                return {'bairro': data.get('bairro'), 'localidade': data.get('localidade'), 'uf': data.get('uf')}
    except requests.RequestException:
        return None
    return None

def _query_coords_api(url_template, cep):
    """Tenta obter coordenadas de uma API."""
    try:
        res = requests.get(url_template.format(cep=cep), headers=HEADERS, timeout=3)
        if res.status_code == 200:
            data = res.json()
            lat, lon = None, None
            # Lógica para BrasilAPI
            if 'location' in data and data['location']['coordinates']:
                lat = data['location']['coordinates'].get('latitude')
                lon = data['location']['coordinates'].get('longitude')
            # Lógica para AwesomeAPI
            elif 'lat' in data and 'lng' in data:
                lat = data.get('lat')
                lon = data.get('lng')
            
            if lat and lon:
                return {'lat': float(lat), 'lon': float(lon)}
    except requests.RequestException:
        return None
    return None

def _average_coords(coord_list):
    """Calcula a média de uma lista de coordenadas."""
    if not coord_list: return None
    avg_lat = statistics.mean([c['lat'] for c in coord_list])
    avg_lon = statistics.mean([c['lon'] for c in coord_list])
    return {'lat': avg_lat, 'lon': avg_lon}

# --- Função Principal Orquestradora ---

def get_info_from_cep(cep):
    """
    Orquestra a busca de CEP usando um funil de enriquecimento de dados
    com múltiplas fontes em paralelo para velocidade e robustez.
    """
    cep_limpo = cep.replace('-', '')
    
    # ETAPA 1: Obter endereço base em paralelo
    address_apis = {
        "https://opencep.com/v1/{cep}": "OpenCEP",
        "https://viacep.com.br/ws/{cep}/json/": "ViaCEP"
    }
    endereco_base = None
    with ThreadPoolExecutor(max_workers=len(address_apis)) as executor:
        futures = [executor.submit(_query_address_api, url, cep_limpo) for url in address_apis]
        for future in as_completed(futures):
            result = future.result()
            if result:
                endereco_base = result
                executor.shutdown(wait=False, cancel_futures=True) # Encontrou, cancela os outros
                break
    
    if not endereco_base:
        logger.error(f"Não foi possível obter endereço base para o CEP {cep_limpo}.")
        return None, None, None

    # ETAPA 2: Obter coordenadas em paralelo
    coords_apis = {
        "https://brasilapi.com.br/api/cep/v2/{cep}": "BrasilAPI",
        "https://cep.awesomeapi.com.br/json/{cep}": "AwesomeAPI"
    }
    coordenadas_encontradas = []
    with ThreadPoolExecutor(max_workers=len(coords_apis)) as executor:
        futures = [executor.submit(_query_coords_api, url, cep_limpo) for url in coords_apis]
        for future in as_completed(futures):
            result = future.result()
            if result:
                coordenadas_encontradas.append(result)
    
    coordenadas_finais = _average_coords(coordenadas_encontradas)
    
    # Se a Etapa 2 funcionou, combina os resultados e retorna
    if coordenadas_finais:
        logger.info(f"CEP {cep_limpo}: Coordenadas encontradas e calculada a média de {len(coordenadas_encontradas)} fontes.")
        return coordenadas_finais['lat'], coordenadas_finais['lon'], endereco_base['bairro']

    # ETAPA 3: Fallback de geocodificação se a Etapa 2 falhar
    logger.warning(f"CEP {cep_limpo}: Nenhuma coordenada encontrada nas APIs diretas. Usando fallback de geocodificação.")
    lat, lon = get_precise_coord(cep, endereco_base)
    if lat and lon:
        return lat, lon, endereco_base['bairro']

    logger.error(f"Falha completa em obter coordenadas para o CEP {cep_limpo}.")
    return None, None, None