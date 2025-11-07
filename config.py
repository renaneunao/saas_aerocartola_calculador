import os
from dotenv import load_dotenv

load_dotenv()

# Configurações do PostgreSQL
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'password'),
    'database': os.getenv('POSTGRES_DB', 'cartola_manager')
}

# Configurações de API
API_URL_STATUS = "https://api.cartola.globo.com/mercado/status"

# Configurações de agendamento
CALCULATION_INTERVAL_MINUTES = int(os.getenv('CALCULATION_INTERVAL_MINUTES', '15'))

# Configurações de perfis
# 10 perfis de peso do jogo: 5 brandos (raiz quarta 1/4) e 5 agressivos (raiz cúbica 1/3)
# Cada grupo usa os mesmos valores de últimas partidas: 2, 4, 7, 10, 12
PERFIS_PESO_JOGO = [
    # Perfis brandos (expoente 1/4 - menos agressivo)
    {'id': 1, 'ultimas_partidas': 2, 'expoente': 1/4, 'descricao': 'Últimos 2 jogos (Brando)'},
    {'id': 2, 'ultimas_partidas': 4, 'expoente': 1/4, 'descricao': 'Últimos 4 jogos (Brando)'},
    {'id': 3, 'ultimas_partidas': 7, 'expoente': 1/4, 'descricao': 'Últimos 7 jogos (Brando)'},
    {'id': 4, 'ultimas_partidas': 10, 'expoente': 1/4, 'descricao': 'Últimos 10 jogos (Brando)'},
    {'id': 5, 'ultimas_partidas': 12, 'expoente': 1/4, 'descricao': 'Últimos 12 jogos (Brando)'},
    
    # Perfis agressivos (expoente 1/3 - mais agressivo)
    {'id': 6, 'ultimas_partidas': 2, 'expoente': 1/3, 'descricao': 'Últimos 2 jogos (Agressivo)'},
    {'id': 7, 'ultimas_partidas': 4, 'expoente': 1/3, 'descricao': 'Últimos 4 jogos (Agressivo)'},
    {'id': 8, 'ultimas_partidas': 7, 'expoente': 1/3, 'descricao': 'Últimos 7 jogos (Agressivo)'},
    {'id': 9, 'ultimas_partidas': 10, 'expoente': 1/3, 'descricao': 'Últimos 10 jogos (Agressivo)'},
    {'id': 10, 'ultimas_partidas': 12, 'expoente': 1/3, 'descricao': 'Últimos 12 jogos (Agressivo)'},
    
    # Perfis baseados em rating (ELO) - 5 perfis com os mesmos números de jogos
    {'id': 11, 'ultimas_partidas': 2, 'expoente': 1/4, 'metodo': 'rating', 'descricao': 'Rating - Últimos 2 jogos'},
    {'id': 12, 'ultimas_partidas': 4, 'expoente': 1/4, 'metodo': 'rating', 'descricao': 'Rating - Últimos 4 jogos'},
    {'id': 13, 'ultimas_partidas': 7, 'expoente': 1/4, 'metodo': 'rating', 'descricao': 'Rating - Últimos 7 jogos'},
    {'id': 14, 'ultimas_partidas': 10, 'expoente': 1/4, 'metodo': 'rating', 'descricao': 'Rating - Últimos 10 jogos'},
    {'id': 15, 'ultimas_partidas': 12, 'expoente': 1/4, 'metodo': 'rating', 'descricao': 'Rating - Últimos 12 jogos'},
]

# 10 perfis de peso do SG: 5 brandos e 5 agressivos
# Cada grupo usa os mesmos valores de últimas partidas: 2, 4, 7, 10, 12
# Brandos: pesos mais equilibrados (distribuição uniforme)
# Agressivos: mais peso em clean sheets e defesa (fatores mais determinantes)
PERFIS_PESO_SG = [
    # Perfis brandos (pesos equilibrados)
    {'id': 1, 'ultimas_partidas': 2, 'agressividade': 'brando', 'descricao': 'Últimos 2 jogos (Brando)'},
    {'id': 2, 'ultimas_partidas': 4, 'agressividade': 'brando', 'descricao': 'Últimos 4 jogos (Brando)'},
    {'id': 3, 'ultimas_partidas': 7, 'agressividade': 'brando', 'descricao': 'Últimos 7 jogos (Brando)'},
    {'id': 4, 'ultimas_partidas': 10, 'agressividade': 'brando', 'descricao': 'Últimos 10 jogos (Brando)'},
    {'id': 5, 'ultimas_partidas': 12, 'agressividade': 'brando', 'descricao': 'Últimos 12 jogos (Brando)'},
    
    # Perfis agressivos (mais peso em clean sheets e defesa)
    {'id': 6, 'ultimas_partidas': 2, 'agressividade': 'agressivo', 'descricao': 'Últimos 2 jogos (Agressivo)'},
    {'id': 7, 'ultimas_partidas': 4, 'agressividade': 'agressivo', 'descricao': 'Últimos 4 jogos (Agressivo)'},
    {'id': 8, 'ultimas_partidas': 7, 'agressividade': 'agressivo', 'descricao': 'Últimos 7 jogos (Agressivo)'},
    {'id': 9, 'ultimas_partidas': 10, 'agressividade': 'agressivo', 'descricao': 'Últimos 10 jogos (Agressivo)'},
    {'id': 10, 'ultimas_partidas': 12, 'agressividade': 'agressivo', 'descricao': 'Últimos 12 jogos (Agressivo)'},
]

