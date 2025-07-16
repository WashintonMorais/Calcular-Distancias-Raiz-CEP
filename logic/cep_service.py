# logic/cep_service.py
import requests
import random
from .geocoding import get_precise_coord, reverse_geocode_and_validate
from .logger import get_logger

logger = get_logger(__name__)

# Mantemos a sua lista de APIs de fallback
APIS_FALLBACK = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://opencep.com/v1/{cep}",
]

HEADERS = {'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal)'}


def get_info_from_cep(cep):
    """
    Busca informações do CEP usando a estratégia de intercalação (par/ímpar)
    e com um sistema de fallback em caso de falha.
    """
    cep_limpo = cep.replace('-', '')
    if not cep_limpo or not cep_limpo[-1].isdigit():
        return None, None, None

    resultado = None
    
    # Tenta a API primária de acordo com a estratégia par/ímpar
    try:
        if int(cep_limpo[-1]) % 2 == 0:
            # CEP PAR: Tenta BrasilAPI primeiro
            url = f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}"
            res = requests.get(url, headers=HEADERS, timeout=4)
            if res.status_code == 200:
                data = res.json()
                if data.get('location') and data.get('location').get('coordinates'):
                    coords = data['location']['coordinates']
                    lat, lon = coords.get('latitude'), coords.get('longitude')
                    bairro = data.get('neighborhood') or data.get('bairro')
                    if lat and lon and bairro:
                        resultado = (float(lat), float(lon), bairro)
        else:
            # CEP ÍMPAR: Tenta AwesomeAPI primeiro
            url = f"https://cep.awesomeapi.com.br/json/{cep_limpo}"
            res = requests.get(url, headers=HEADERS, timeout=4)
            if res.status_code == 200:
                data = res.json()
                lat, lon = data.get('lat'), data.get('lng')
                bairro = data.get('district')
                if lat and lon and bairro:
                    resultado = (float(lat), float(lon), bairro)
    except requests.RequestException as e:
        logger.warning(f"API primária falhou para {cep}: {e}")

    # Se a primeira tentativa deu certo, retorna o resultado
    if resultado:
        return resultado

    # Se a primeira tentativa falhou, usa as APIs de fallback
    logger.warning(f"CEP {cep_limpo}: Falha na API primária. Tentando fallbacks...")
    for api_url in APIS_FALLBACK:
        try:
            url = api_url.format(cep=cep_limpo)
            res = requests.get(url, headers=HEADERS, timeout=4)
            if res.status_code == 200:
                data = res.json()
                if not data.get('erro') and data.get('bairro') and data.get('localidade'):
                    # Encontrou um endereço, agora tenta geocodificar
                    lat_geo, lon_geo = get_precise_coord(cep, data)
                    if lat_geo and lon_geo:
                        logger.info(f"Sucesso no fallback para {cep} com {api_url.split('/')[2]}")
                        return lat_geo, lon_geo, data.get('bairro')
        except requests.RequestException:
            continue
            
    logger.error(f"Falha completa em todas as fontes para o CEP {cep_limpo}.")
    return None, None, None