#!/usr/bin/env python3
"""
Script para testar os cálculos ajustados que consideram a força dos adversários
"""
import logging
import sys
from datetime import datetime
from database import get_db_connection, close_db_connection, init_tables
from api_cartola import fetch_status_data
from calculo_tabela import calcular_tabela_classificacao
from calculo_peso_jogo_ajustado import calculate_peso_jogo_for_profile_ajustado
from calculo_peso_sg_ajustado import calculate_peso_sg_for_profile_ajustado
from mostrar_rankings import mostrar_ranking_peso_jogo, mostrar_ranking_peso_sg
from config import PERFIS_PESO_JOGO, PERFIS_PESO_SG

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def testar_tabela_classificacao():
    """Testa o cálculo da tabela de classificação"""
    logger.info("=" * 80)
    logger.info("TESTE: Cálculo da Tabela de Classificação")
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
        tabela = calcular_tabela_classificacao(cursor, rodada_atual)
        
        logger.info(f"\nTabela de Classificação (Top 10):")
        logger.info(f"{'Pos':<5} {'Clube ID':<10} {'Pontos':<8} {'V':<4} {'E':<4} {'D':<4} {'GP':<5} {'GC':<5} {'SG':<6} {'Aproveit.':<12} {'Força':<8}")
        logger.info("-" * 100)
        
        # Ordenar por posição
        times_ordenados = sorted(tabela.items(), key=lambda x: x[1]['posicao'])
        
        for clube_id, stats in times_ordenados[:10]:
            logger.info(
                f"{stats['posicao']:<5} {clube_id:<10} {stats['pontos']:<8} "
                f"{stats['vitorias']:<4} {stats['empates']:<4} {stats['derrotas']:<4} "
                f"{stats['gols_pro']:<5} {stats['gols_contra']:<5} {stats['saldo_gols']:<6} "
                f"{stats['aproveitamento']*100:>10.2f}% {stats['forca_normalizada']:>7.4f}"
            )
        
        logger.info(f"\nTotal de times na tabela: {len(tabela)}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao calcular tabela: {e}", exc_info=True)
        return False
    finally:
        close_db_connection(conn)

def testar_calculo_ajustado():
    """Testa os cálculos ajustados para um perfil de cada tipo"""
    logger.info("\n" + "=" * 80)
    logger.info("TESTE: Cálculos Ajustados (1 perfil de cada)")
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
        init_tables(conn)
        
        # Testar 1 perfil de peso do jogo
        logger.info(f"\n{'='*80}")
        logger.info("TESTANDO PESO DO JOGO (AJUSTADO) - Perfil 1")
        logger.info(f"{'='*80}\n")
        
        perfil_jogo = PERFIS_PESO_JOGO[0]
        cache_setores = {}
        
        calculate_peso_jogo_for_profile_ajustado(
            conn, rodada_atual, perfil_jogo,
            usar_provaveis_cartola=False,
            cache_setores=cache_setores
        )
        
        mostrar_ranking_peso_jogo(conn, rodada_atual, perfil_jogo['id'])
        
        # Testar 1 perfil de peso do SG
        logger.info(f"\n{'='*80}")
        logger.info("TESTANDO PESO DO SG (AJUSTADO) - Perfil 1")
        logger.info(f"{'='*80}\n")
        
        perfil_sg = PERFIS_PESO_SG[0]
        
        calculate_peso_sg_for_profile_ajustado(
            conn, rodada_atual, perfil_sg,
            usar_provaveis_cartola=False
        )
        
        mostrar_ranking_peso_sg(conn, rodada_atual, perfil_sg['id'])
        
        logger.info("\n" + "=" * 80)
        logger.info("[OK] Testes concluídos com sucesso!")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"Erro nos testes: {e}", exc_info=True)
        return False
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    logger.info("Iniciando testes dos cálculos ajustados...\n")
    
    # Testar tabela primeiro
    sucesso_tabela = testar_tabela_classificacao()
    
    if sucesso_tabela:
        # Testar cálculos ajustados
        sucesso_calculos = testar_calculo_ajustado()
        sys.exit(0 if sucesso_calculos else 1)
    else:
        sys.exit(1)

