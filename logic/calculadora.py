import requests
import json
import logging
import random
from math import radians, cos, sin, asin, sqrt
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from flask import request

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lista completa de APIs para o fallback (Plano C)
APIS_COMPLETA = [
    "https://viacep.com.br/ws/{cep}/json/", "https://brasilapi.com.br/api/cep/v2/{cep}",
    "https://nominatim.openstreetmap.org/search?postalcode={cep}&country=Brasil&format=json",
    "https://opencep.com/v1/{cep}", "https://cep.awesomeapi.com.br/json/{cep}",
]
# APIs para a Etapa 1 da busca de alta precisão
APIS_ENDERECO = [
    "https://brasilapi.com.br/api/cep/v2/{cep}", "https://viacep.com.br/ws/{cep}/json/",
]

def haversine(lat1, lon1, lat2, lon2):
    R=6371; dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c=2*asin(sqrt(a)); return R*c

def get_coord_fallback(cep):
    """Plano C: A busca original, mais permissiva, que consulta todas as APIs."""
    headers={'User-Agent':'CalculadoraDistancia/1.0(Projeto Pessoal)'}
    for api_url_template in random.sample(APIS_COMPLETA, len(APIS_COMPLETA)):
        url_final=api_url_template.format(cep=cep.replace('-',''))
        try:
            res=requests.get(url_final,headers=headers,timeout=10); res.raise_for_status(); data=res.json()
            lat,lon,bairro=None,None,'N/A'
            if isinstance(data,list)and data:
                r=data[0]; lat,lon=r.get('lat'),r.get('lon'); parts=r.get('display_name','').split(','); bairro=parts[1].strip()if len(parts)>2 else'N/A'
            elif isinstance(data,dict):
                if data.get('erro'):continue
                lat=data.get('lat')or data.get('latitude')or(data.get('location')and data['location']['coordinates'].get('latitude'))
                lon=data.get('lng')or data.get('longitude')or(data.get('location')and data['location']['coordinates'].get('longitude'))
                bairro=data.get('bairro')or data.get('district')or data.get('neighborhood','N/A')
            if lat is not None and lon is not None:return float(lat),float(lon),bairro
        except Exception:continue
    return None,None,None

def get_precise_coord(cep, endereco_info):
    """Etapa 2 da busca de alta precisão (Nominatim)."""
    headers={'User-Agent':'CalculadoraDistancia/1.0(Projeto Pessoal)'}
    logradouro=endereco_info.get('logradouro'); bairro=endereco_info.get('bairro'); localidade=endereco_info.get('localidade'); uf=endereco_info.get('uf')
    full_address=", ".join(filter(None,[logradouro,bairro,localidade,uf,cep]))
    query_string=quote(full_address)
    url=f"https://nominatim.openstreetmap.org/search?q={query_string}&format=jsonv2&countrycodes=br"
    try:
        res=requests.get(url,headers=headers,timeout=10); res.raise_for_status(); data=res.json()
        if data and isinstance(data,list): return float(data[0]['lat']),float(data[0]['lon'])
    except Exception as e:
        logging.warning(f"Nominatim falhou para a busca '{full_address}'. Erro: {e}")
    return None,None

def get_info_from_cep(cep):
    """Função principal que orquestra a busca com múltiplos fallbacks."""
    headers={'User-Agent':'CalculadoraDistancia/1.0(Projeto Pessoal)'}
    endereco_info = {}; fallback_coords = None
    
    # Etapa 1: Busca o endereço e tenta coletar coordenadas de fallback
    for api_url_template in APIS_ENDERECO:
        url_final = api_url_template.format(cep=cep.replace('-', ''))
        try:
            res = requests.get(url_final, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if not data.get('erro'):
                    if not endereco_info.get('localidade'):
                        endereco_info = {'logradouro':data.get('logradouro')or data.get('street'),'bairro':data.get('bairro')or data.get('neighborhood'),'localidade':data.get('localidade')or data.get('city'),'uf':data.get('uf')or data.get('state')}
                    if not fallback_coords:
                        if data.get('location') and data['location'].get('coordinates'):
                            lat_fb,lon_fb = data['location']['coordinates'].get('latitude'),data['location']['coordinates'].get('longitude')
                        else:
                            lat_fb,lon_fb = data.get('lat')or data.get('latitude'),data.get('lng')or data.get('longitude')
                        if lat_fb and lon_fb: fallback_coords = (float(lat_fb),float(lon_fb))
            if endereco_info and fallback_coords: break
        except Exception: continue
    
    # Se a Etapa 1 funcionou e obteve um endereço, tenta a Etapa 2 (busca precisa)
    if endereco_info.get('localidade'):
        lat_precisa, lon_precisa = get_precise_coord(cep, endereco_info)
        bairro_final = endereco_info.get('bairro') or 'N/A'
        if lat_precisa and lon_precisa: # Plano A bem-sucedido
            return lat_precisa, lon_precisa, bairro_final
        if fallback_coords: # Plano B bem-sucedido
            logging.warning(f"Usando coordenadas de fallback para o CEP {cep}.")
            return fallback_coords[0], fallback_coords[1], bairro_final
    
    # Plano C: Se tudo acima falhou, usa o método de busca antigo e abrangente
    logging.warning(f"Usando método de busca abrangente (Plano C) para o CEP {cep}.")
    return get_coord_fallback(cep)


# --- As demais funções não precisam de nenhuma alteração ---
def _calcular_por_varredura_detalhada(lat_partida, lon_partida, raiz_str):
    resultados_finais=[]; yield f"data: {json.dumps({'tipo':'log','msg':f'Iniciando varredura precisa para a raiz {raiz_str}...'})}\n\n"
    ceps_para_consultar=[f"{raiz_str}{d+i:03d}"for d in range(0,1000,10)for i in range(3)]
    resultados_da_raiz=[]
    with ThreadPoolExecutor(max_workers=10)as executor:
        f_to_cep={executor.submit(get_info_from_cep,c):c for c in ceps_para_consultar}
        for i,future in enumerate(as_completed(f_to_cep)):
            cep_c=f_to_cep[future]; res_c=future.result()
            if res_c and res_c[0]is not None:
                lat,lon,bairro=res_c; dist=round(haversine(lat_partida,lon_partida,lat,lon),2)
                resultados_da_raiz.append({'cep':cep_c,'bairro':bairro,'distancia':dist,'lat':lat,'lon':lon})
            if(i+1)%10==0:yield f"data: {json.dumps({'tipo':'log','msg':f'Verificados {i+1}/{len(ceps_para_consultar)} CEPs...'})}\n\n"
    if resultados_da_raiz:
        media_geral=round(sum(r['distancia']for r in resultados_da_raiz)/len(resultados_da_raiz),2)
        resultados_finais.append({'tipo_linha':'resumo_raiz','raiz':raiz_str,'bairro':'MÉDIA GERAL DA RAIZ','distancia':media_geral,'tempo':round(media_geral*2,1),'ceps_consultados':len(resultados_da_raiz),'lat':None,'lon':None,'cep_referencia':None})
        bairros_temp={}
        for r in resultados_da_raiz:
            b=r['bairro']if r['bairro']and r['bairro'].strip()else'Bairro não identificado'
            if b not in bairros_temp:bairros_temp[b]=[]
            bairros_temp[b].append(r)
        for b,d_b in sorted(bairros_temp.items()):
            p_m_p=min(d_b,key=lambda p:p['distancia'])
            resultados_finais.append({'tipo_linha':'bairro','raiz':raiz_str,'bairro':f"{b}",'distancia':p_m_p['distancia'],'tempo':round(p_m_p['distancia']*2,1),'ceps_consultados':len(d_b),'lat':p_m_p['lat'],'lon':p_m_p['lon'],'cep_referencia':p_m_p['cep']})
    else:
        resultados_finais.append({'tipo_linha':'erro_raiz','raiz':raiz_str,'bairro':'NENHUM CEP VÁLIDO ENCONTRADO','distancia':'-','tempo':'-','ceps_consultados':0,'lat':None,'lon':None,'cep_referencia':None})
    return resultados_finais

def calcular_distancias_stream(cep_partida,raiz_inicial,raiz_atual,tipo_consulta):
    get_coord_func=get_info_from_cep
    lat_partida,lon_partida,bairro_partida=get_coord_func(cep_partida)
    if not lat_partida:yield f"data: {json.dumps({'tipo':'erro','msg':f'CEP de partida {cep_partida} não encontrado.'})}\n\n";return
    if raiz_atual==raiz_inicial:yield f"data: {json.dumps({'tipo':'partida_info','bairro':bairro_partida,'cep':cep_partida,'lat':lat_partida,'lon':lon_partida})}\n\n"
    if tipo_consulta=='rapida':
        # A consulta rápida é otimizada para velocidade, mantendo a busca mais simples
        get_coord_func_rapida = get_coord_fallback
        ceps_amostra=[f"{raiz_atual}{i:03d}"for i in range(0,1000,100)];coords_encontradas=[]
        with ThreadPoolExecutor(max_workers=10)as executor:
            for r in executor.map(get_coord_func_rapida,ceps_amostra):
                if r and r[0]is not None:coords_encontradas.append(r)
        if coords_encontradas:
            lat_m=sum(c[0]for c in coords_encontradas)/len(coords_encontradas);lon_m=sum(c[1]for c in coords_encontradas)/len(coords_encontradas)
            dist=round(haversine(lat_partida,lon_partida,lat_m,lon_m),2)
            resultados_finais=[{'tipo_linha':'bairro','raiz':raiz_atual,'bairro':f'Centro da Raiz ({len(coords_encontradas)} amostras)','distancia':dist,'tempo':round(dist*2,1),'ceps_consultados':len(coords_encontradas),'lat':lat_m,'lon':lon_m,'cep_referencia':'N/A'}]
        else:
            resultados_finais=[{'tipo_linha':'erro_raiz','raiz':raiz_atual,'bairro':'NENHUMA AMOSTRA ENCONTRADA','distancia':'-','tempo':'-','ceps_consultados':0,'lat':None,'lon':None,'cep_referencia':None}]
    else:
        gen=_calcular_por_varredura_detalhada(lat_partida,lon_partida,raiz_atual)
        try:resultados_finais=yield from gen
        except StopIteration as e:resultados_finais=e.value
    yield f"data: {json.dumps({'tipo':'fim','resultados':resultados_finais})}\n\n"