import requests
import logging
from config import API_URL_STATUS

logger = logging.getLogger(__name__)

def fetch_status_data():
    """Obtém o status do mercado (não requer autenticação)."""
    try:
        response = requests.get(API_URL_STATUS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar a API Cartola (status): {e}")
        return None

