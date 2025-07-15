# logic/cep_service.py

import requests
import random
from logic.geocoding import get_precise_coord, reverse_geocode_and_validate
from logic.logger import get_logger

logger = get_logger(__name__)

APIS_ENDERECO = [
    "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://viacep.com.br/ws/{cep}/json/"
]

APIS_COMPLETA = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json",
    "https://opencep.com/v1/{cep}",
    "https://cep.awesomeapi.com.br/json/{cep}"
]

HEADERS = {'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal)'}

def get_coord_fallback(cep):
    logger.info(f"Executando fallback para {cep}")
    for api in random.sample(APIS_COMPLETA, len(APIS_COMPLETA)):
        try:
            url = api.format(cep=cep.replace('-', ''))
            res = requests.get(url, headers=HEADERS, timeout=10)
            res.raise_for_status()
            data = res.json()

            if isinstance(data, list) and data:
                r = data[0]
                return float(r['lat']), float(r['lon']), r.get('display_name', 'N/A').split(',')[1].strip()
            elif isinstance(data, dict):
                if data.get('erro'):
                    continue
                lat = data.get('lat') or data.get('latitude') or (data.get('location') and data['location']['coordinates'].get('latitude'))
                lon = data.get('lng') or data.get('longitude') or (data.get('location') and data['location']['coordinates'].get('longitude'))
                bairro = data.get('bairro') or data.get('district') or data.get('neighborhood', 'N/A')
                if lat and lon:
                    return float(lat), float(lon), bairro
        except Exception as e:
            logger.warning(f"Erro no fallback {api}: {e}")
            continue
    logger.error(f"Falha completa no fallback para {cep}")
    return None, None, None

def get_info_from_cep(cep):
    logger.info(f"Consultando informações do CEP {cep}")
    endereco_info = {}
    fallback_coords = None

    for api in APIS_ENDERECO:
        try:
            url = api.format(cep=cep.replace('-', ''))
            res = requests.get(url, headers=HEADERS, timeout=5)
            res.raise_for_status()
            data = res.json()

            if not data.get('erro'):
                endereco_info = {
                    'logradouro': data.get('logradouro') or data.get('street'),
                    'bairro': data.get('bairro') or data.get('neighborhood'),
                    'localidade': data.get('localidade') or data.get('city'),
                    'uf': data.get('uf') or data.get('state')
                }
                if data.get('location') and data['location'].get('coordinates'):
                    coords = data['location']['coordinates']
                    fallback_coords = (float(coords['latitude']), float(coords['longitude']))
                elif data.get('lat') or data.get('latitude'):
                    fallback_coords = (float(data.get('lat') or data.get('latitude')), float(data.get('lng') or data.get('longitude')))
            if endereco_info and fallback_coords:
                break
        except Exception as e:
            logger.warning(f"Erro na API {api}: {e}")
            continue

    if not endereco_info.get('localidade'):
        return get_coord_fallback(cep)

    lat_precisa, lon_precisa = get_precise_coord(cep, endereco_info)
    bairro_final = endereco_info.get('bairro') or 'N/A'

    if lat_precisa and lon_precisa:
        if reverse_geocode_and_validate(lat_precisa, lon_precisa, endereco_info.get('bairro'), endereco_info.get('localidade')):
            return lat_precisa, lon_precisa, bairro_final

    if fallback_coords:
        return fallback_coords[0], fallback_coords[1], bairro_final

    return get_coord_fallback(cep)
