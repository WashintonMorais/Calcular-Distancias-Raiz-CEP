# logic/geocoding.py

import requests
from urllib.parse import quote
from logic.logger import get_logger

logger = get_logger(__name__)

HEADERS = {'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal)'}

def get_precise_coord(cep, endereco_info):
    query_params = {
        'street': endereco_info.get('logradouro'),
        'city': endereco_info.get('localidade'),
        'postalcode': cep,
        'country': 'Brasil',
        'format': 'jsonv2'
    }
    query_string = "&".join(f"{key}={quote(str(value))}" for key, value in query_params.items() if value)
    url = f"https://nominatim.openstreetmap.org/search?{query_string}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()
        if data and isinstance(data, list):
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        logger.warning(f"Nominatim falhou para {cep}: {e}")

    return None, None

def reverse_geocode_and_validate(lat, lon, bairro_original, cidade_original):
    if not all([lat, lon, bairro_original, cidade_original]):
        return False

    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=jsonv2"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()

        addr = data.get('address', {})
        bairro_reverso = addr.get('suburb') or addr.get('city_district')
        cidade_reversa = addr.get('city') or addr.get('town') or addr.get('village')

        if cidade_reversa and cidade_original in cidade_reversa:
            if bairro_reverso and bairro_original in bairro_reverso:
                return True
    except Exception as e:
        logger.warning(f"Reverse geocoding falhou para {lat},{lon}: {e}")

    return False