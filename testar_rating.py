#!/usr/bin/env python3
"""
Script para testar o sistema de rating (ELO)
"""
import logging
import sys
from database import get_db_connection, close_db_connection
from api_cartola import fetch_status_data
from calculo_rating import calcular_ratings_historicos, calcular_rating_recente
from calculo_peso_jogo_rating import calculate_peso_jogo_for_profile_rating
from mostrar_rankings import mostrar_ranking_peso_jogo
from config import PERFIS_PESO_JOGO

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def testar_ratings():
    """Testa o cálculo de ratings"""
    logger.info("=" * 80)
    logger.info("TESTE: Sistema de Rating (ELO)")
    logger.info("=" * 80)
    
    status_data = fetch_status_data()
    if not status_data:
        logger.error("Erro ao obter dados de status do Cartola.")
        return False
    
    rodada_atual = status_data.get('rodada_atual')
    if not rodada_atual:
        logger.error("Rodada atual não encontrada.")
        return False
    
    logger.info(f"Rodada atual: {rodada_atual}")
    
    conn = get_db_connection()
    if not conn:
        logger.error("Erro ao conectar ao banco de dados.")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Calcular ratings históricos
        logger.info("\nCalculando ratings históricos...")
        ratings = calcular_ratings_historicos(cursor, rodada_atual)
        
        # Ordenar por rating
        ratings_ordenados = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
        
        logger.info(f"\nRatings Atuais (Top 10):")
        logger.info(f"{'Pos':<5} {'Clube ID':<10} {'Rating':<10}")
        logger.info("-" * 30)
        
        for idx, (clube_id, rating) in enumerate(ratings_ordenados[:10], 1):
            logger.info(f"{idx:<5} {clube_id:<10} {rating:>9.2f}")
        
        logger.info(f"\nTotal de times: {len(ratings)}")
        
        # Testar rating recente para um time específico
        if ratings_ordenados:
            clube_teste = ratings_ordenados[0][0]
            logger.info(f"\nTestando rating recente para clube {clube_teste}:")
            logger.info(f"  Rating histórico: {ratings[clube_teste]:.2f}")
            
            for ultimas_partidas in [2, 4, 7, 10]:
                rating_recente_casa = calcular_rating_recente(
                    cursor, clube_teste, rodada_atual, ultimas_partidas,
                    como_mandante=True, ratings_historicos=ratings
                )
                rating_recente_fora = calcular_rating_recente(
                    cursor, clube_teste, rodada_atual, ultimas_partidas,
                    como_mandante=False, ratings_historicos=ratings
                )
                logger.info(f"  Últimas {ultimas_partidas} partidas - Casa: {rating_recente_casa:.2f}, Fora: {rating_recente_fora:.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao calcular ratings: {e}", exc_info=True)
        return False
    finally:
        close_db_connection(conn)

def testar_calculo_rating():
    """Testa o cálculo de peso do jogo usando rating"""
    logger.info("\n" + "=" * 80)
    logger.info("TESTE: Cálculo de Peso do Jogo usando Rating")
    logger.info("=" * 80)
    
    status_data = fetch_status_data()
    if not status_data:
        logger.error("Erro ao obter dados de status do Cartola.")
        return False
    
    rodada_atual = status_data.get('rodada_atual')
    if not rodada_atual:
        logger.error("Rodada atual não encontrada.")
        return False
    
    logger.info(f"Rodada atual: {rodada_atual}")
    
    conn = get_db_connection()
    if not conn:
        logger.error("Erro ao conectar ao banco de dados.")
        return False
    
    try:
        # Encontrar um perfil baseado em rating
        perfil_rating = None
        for perfil in PERFIS_PESO_JOGO:
            if perfil.get('metodo') == 'rating':
                perfil_rating = perfil
                break
        
        if not perfil_rating:
            logger.error("Nenhum perfil baseado em rating encontrado no config.")
            return False
        
        logger.info(f"\nTestando perfil {perfil_rating['id']}: {perfil_rating['descricao']}")
        
        cache_setores = {}
        calculate_peso_jogo_for_profile_rating(
            conn, rodada_atual, perfil_rating,
            usar_provaveis_cartola=False,
            cache_setores=cache_setores
        )
        
        mostrar_ranking_peso_jogo(conn, rodada_atual, perfil_rating['id'])
        
        logger.info("\n" + "=" * 80)
        logger.info("[OK] Teste concluído com sucesso!")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"Erro no teste: {e}", exc_info=True)
        return False
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    logger.info("Iniciando testes do sistema de rating...\n")
    
    # Testar ratings primeiro
    sucesso_ratings = testar_ratings()
    
    if sucesso_ratings:
        # Testar cálculo usando rating
        sucesso_calculo = testar_calculo_rating()
        sys.exit(0 if sucesso_calculo else 1)
    else:
        sys.exit(1)

