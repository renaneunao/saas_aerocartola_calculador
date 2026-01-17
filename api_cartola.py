import requests
import logging
import time
from datetime import datetime
from config import API_URL_STATUS

logger = logging.getLogger(__name__)

# Variáveis globais para cache da temporada
_TEMPORADA_CACHE = None
_TEMPORADA_CACHE_TIMESTAMP = None
_CACHE_DURATION = 3600  # 1 hora em segundos

def fetch_status_data():
    """Obtém o status do mercado (não requer autenticação)."""
    try:
        response = requests.get(API_URL_STATUS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar a API Cartola (status): {e}")
        return None

def get_temporada_atual() -> int:
    """
    Retorna a temporada atual buscando da API de status do Cartola.
    Usa cache de 1 hora para evitar múltiplas requisições.
    Fallback para ano atual caso a API falhe.
    """
    global _TEMPORADA_CACHE, _TEMPORADA_CACHE_TIMESTAMP
    
    # Verificar cache
    current_time = time.time()
    if _TEMPORADA_CACHE is not None and _TEMPORADA_CACHE_TIMESTAMP is not None:
        if current_time - _TEMPORADA_CACHE_TIMESTAMP < _CACHE_DURATION:
            return _TEMPORADA_CACHE
    
    # Buscar da API
    try:
        status_data = fetch_status_data()
        
        if status_data and 'temporada' in status_data:
            temporada = int(status_data['temporada'])
            # Atualizar cache
            _TEMPORADA_CACHE = temporada
            _TEMPORADA_CACHE_TIMESTAMP = current_time
            logger.info(f"Temporada atual obtida da API: {temporada}")
            return temporada
    except Exception as e:
        logger.error(f"Erro ao buscar temporada da API: {e}. Usando fallback (ano atual)")
    
    # Fallback: usar ano atual
    ano_atual = datetime.now().year
    logger.info(f"Usando ano atual como temporada (fallback): {ano_atual}")
    return ano_atual
