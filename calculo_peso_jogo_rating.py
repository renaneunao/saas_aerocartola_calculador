"""
Cálculo de peso do jogo baseado em sistema de rating (ELO)
Usa a diferença de rating entre os times para determinar o peso
"""
import logging
import math
from psycopg2.extras import execute_values
from database import get_db_connection
from calculo_rating import (
    calcular_ratings_historicos,
    calcular_rating_recente,
    calcular_diferenca_rating_peso
)
from calculo_peso_jogo import calculate_team_sector_analysis
from api_cartola import get_temporada_atual

logger = logging.getLogger(__name__)

def calculate_peso_jogo_for_profile_rating(conn, rodada_atual, perfil, usar_provaveis_cartola=False, cache_setores=None):
    """Calcula peso do jogo baseado em ratings (ELO) para um perfil específico
    
    Args:
        conn: Conexão com banco
        rodada_atual: Rodada atual
        perfil: Dicionário com id, ultimas_partidas, descricao
        usar_provaveis_cartola: Se deve usar prováveis do Cartola
        cache_setores: Cache compartilhado de análises de setores {(clube_id, tuple(posicoes)): score_final}
    """
    cursor = conn.cursor()
    perfil_id = perfil['id']
    ultimas_partidas = perfil['ultimas_partidas']
    temporada_atual = get_temporada_atual()
    
    # Usar cache compartilhado se fornecido, senão criar novo
    if cache_setores is None:
        cache_setores = {}
    
    try:
        # Calcular ratings históricos uma vez para toda a rodada
        logger.info(f"Calculando ratings históricos até rodada {rodada_atual - 1} da temporada {temporada_atual}")
        ratings_historicos = calcular_ratings_historicos(cursor, rodada_atual, temporada_atual)
        
        # Obter partidas da rodada atual
        cursor.execute('''
            SELECT p.partida_id, p.clube_casa_id, c1.nome_fantasia AS casa_nome, 
                   p.clube_visitante_id, c2.nome_fantasia AS visitante_nome
            FROM acf_partidas p
            JOIN acf_clubes c1 ON p.clube_casa_id = c1.id
            JOIN acf_clubes c2 ON p.clube_visitante_id = c2.id
            WHERE p.rodada_id = %s AND p.temporada = %s AND p.valida = TRUE
        ''', (rodada_atual, temporada_atual))
        partidas = cursor.fetchall()
        
        if not partidas:
            logger.warning(f"Nenhuma partida encontrada para rodada {rodada_atual}")
            return
        
        logger.info(f"Calculando peso do jogo (RATING) - Perfil {perfil_id} ({ultimas_partidas} ultimas partidas) - {len(partidas)} partidas")
        
        updates = []  # (clube_id, peso)
        
        for idx, partida in enumerate(partidas, 1):
            partida_id, casa_id, casa_nome, visitante_id, visitante_nome = partida
            if idx % 5 == 0 or idx == len(partidas):
                logger.info(f"  Processando partida {idx}/{len(partidas)}: {casa_nome} vs {visitante_nome}")
            
            # Calcular rating recente da casa (como mandante)
            rating_casa = calcular_rating_recente(
                cursor, casa_id, rodada_atual, temporada_atual, ultimas_partidas,
                como_mandante=True, ratings_historicos=ratings_historicos
            )
            
            # Calcular rating recente do visitante (como visitante)
            rating_visitante = calcular_rating_recente(
                cursor, visitante_id, rodada_atual, temporada_atual, ultimas_partidas,
                como_mandante=False, ratings_historicos=ratings_historicos
            )
            
            # Calcular peso baseado na diferença de rating
            peso_base_rating = calcular_diferenca_rating_peso(rating_casa, rating_visitante)
            
            # Opcional: Ajustar com análise de setores (para manter alguma consistência com o método original)
            # Mas com peso menor, já que o rating já captura muito da força dos times
            sectors = {'ata': [5], 'mei': [4], 'def': [1, 2, 3]}
            analises = {'casa': {}, 'visitante': {}}
            
            for sector, posicoes in sectors.items():
                pos_key_casa = (casa_id, tuple(posicoes))
                pos_key_visitante = (visitante_id, tuple(posicoes))
                
                if pos_key_casa not in cache_setores:
                    analises['casa'][sector] = calculate_team_sector_analysis(
                        cursor, casa_id, posicoes, usar_provaveis_cartola
                    )
                    cache_setores[pos_key_casa] = analises['casa'][sector]['score_final']
                else:
                    analises['casa'][sector] = {'score_final': cache_setores[pos_key_casa]}
                
                if pos_key_visitante not in cache_setores:
                    analises['visitante'][sector] = calculate_team_sector_analysis(
                        cursor, visitante_id, posicoes, usar_provaveis_cartola
                    )
                    cache_setores[pos_key_visitante] = analises['visitante'][sector]['score_final']
                else:
                    analises['visitante'][sector] = {'score_final': cache_setores[pos_key_visitante]}
            
            # Calcular fator de ajuste baseado em setores (peso menor, apenas como refinamento)
            ratio_ata = math.pow(analises['casa']['ata']['score_final'] / analises['visitante']['ata']['score_final'], 1/3)
            ratio_mei = math.pow(analises['casa']['mei']['score_final'] / analises['visitante']['mei']['score_final'], 1/3)
            ratio_def = math.pow(analises['casa']['def']['score_final'] / analises['visitante']['def']['score_final'], 1/3)
            
            # Média dos ratios (ajuste fino)
            fator_setores = ((ratio_ata + ratio_mei + ratio_def) / 3.0) - 1.0  # Centralizar em 0
            fator_setores = fator_setores * 0.3  # Reduzir impacto (20% do ajuste, menos que antes)
            
            # Peso final: rating + ajuste fino de setores
            # O peso base do rating já é calculado e deve ser o principal
            peso_final = peso_base_rating + fator_setores
            
            # Para rating, usar expoente menos agressivo para manter valores maiores
            # Usar expoente 2/3 (menos redução) para manter valores mais altos
            # Isso mantém os valores mais próximos da escala original do rating
            expoente = 2/3  # Sempre usar 2/3 para rating (menos agressivo que 1/2)
            
            # Aplicar expoente para suavizar diferenças
            if peso_final >= 0:
                peso_final = peso_final ** expoente
            else:
                peso_final = -((-peso_final) ** expoente)
            
            updates.append((casa_id, float(peso_final)))
            updates.append((visitante_id, float(-peso_final)))
        
        # Salvar no banco de dados na tabela de perfis
        if updates:
            # Primeiro, deletar registros antigos do perfil para esta rodada
            cursor.execute('''
                DELETE FROM acp_peso_jogo_perfis 
                WHERE perfil_id = %s AND rodada_atual = %s
            ''', (perfil_id, rodada_atual))
            
            # Inserir novos valores
            insert_data = [
                (perfil_id, rodada_atual, clube_id, peso, ultimas_partidas)
                for clube_id, peso in updates
            ]
            
            execute_values(
                cursor,
                '''
                INSERT INTO acp_peso_jogo_perfis (perfil_id, rodada_atual, clube_id, peso_jogo, ultimas_partidas)
                VALUES %s
                ON CONFLICT (perfil_id, rodada_atual, clube_id) 
                DO UPDATE SET peso_jogo = EXCLUDED.peso_jogo, created_at = NOW()
                ''',
                insert_data,
                template=None,
                page_size=1000
            )
            
            conn.commit()
            logger.info(f"  Perfil {perfil_id} de peso do jogo (RATING) salvo: {len(updates)} clubes")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao calcular peso do jogo (RATING) para perfil {perfil_id}: {e}", exc_info=True)
    finally:
        cursor.close()

