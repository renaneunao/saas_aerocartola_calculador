"""
Versão ajustada do cálculo de peso do jogo que considera a força dos adversários
usando a tabela de classificação
"""
import logging
import math
from psycopg2.extras import execute_values
from database import get_db_connection
from config import PERFIS_PESO_JOGO
from calculo_tabela import (
    calcular_tabela_classificacao,
    calcular_forca_media_adversarios,
    ajustar_aproveitamento_por_forca_adversarios,
    ajustar_saldo_gols_por_forca_adversarios,
    calcular_peso_resultado_por_forca_adversario
)
from calculo_peso_jogo import calculate_player_composite_score_inline, calculate_team_sector_analysis

logger = logging.getLogger(__name__)

def calculate_peso_jogo_for_profile_ajustado(conn, rodada_atual, perfil, usar_provaveis_cartola=False, cache_setores=None):
    """Calcula peso do jogo para um perfil específico, ajustado pela força dos adversários
    
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
    
    # Usar cache compartilhado se fornecido, senão criar novo
    if cache_setores is None:
        cache_setores = {}
    
    try:
        # Calcular tabela de classificação uma vez para toda a rodada
        logger.info(f"Calculando tabela de classificação para rodada {rodada_atual}")
        tabela_classificacao = calcular_tabela_classificacao(cursor, rodada_atual)
        
        # Obter partidas da rodada atual
        cursor.execute('''
            SELECT p.partida_id, p.clube_casa_id, c1.nome_fantasia AS casa_nome, 
                   p.clube_visitante_id, c2.nome_fantasia AS visitante_nome
            FROM acf_partidas p
            JOIN acf_clubes c1 ON p.clube_casa_id = c1.id
            JOIN acf_clubes c2 ON p.clube_visitante_id = c2.id
            WHERE p.rodada_id = %s AND p.valida = TRUE
        ''', (rodada_atual,))
        partidas = cursor.fetchall()
        
        if not partidas:
            logger.warning(f"Nenhuma partida encontrada para rodada {rodada_atual}")
            return
        
        logger.info(f"Calculando peso do jogo (AJUSTADO) - Perfil {perfil_id} ({ultimas_partidas} ultimas partidas) - {len(partidas)} partidas")
        
        updates = []  # (clube_id, peso)
        
        for idx, partida in enumerate(partidas, 1):
            partida_id, casa_id, casa_nome, visitante_id, visitante_nome = partida
            if idx % 5 == 0 or idx == len(partidas):
                logger.info(f"  Processando partida {idx}/{len(partidas)}: {casa_nome} vs {visitante_nome}")
            
            # Buscar últimas partidas da casa como mandante com informações dos adversários
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante, clube_visitante_id
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s
                AND placar_oficial_mandante IS NOT NULL AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (casa_id, rodada_atual - 1, ultimas_partidas))
            partidas_casa = cursor.fetchall()
            
            # Calcular aproveitamento e saldo considerando força dos adversários
            pontos_ponderados_casa = 0.0
            pontos_possiveis_ponderados_casa = 0.0
            gols_feitos_casa = 0
            gols_sofridos_casa = 0
            
            for placar_mandante, placar_visitante, adversario_id in partidas_casa:
                if placar_mandante is None or placar_visitante is None:
                    continue
                
                # Obter força do adversário
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                
                # Determinar resultado
                if placar_mandante > placar_visitante:
                    resultado = 'vitoria'
                    pontos_base = 3
                elif placar_mandante == placar_visitante:
                    resultado = 'empate'
                    pontos_base = 1
                else:
                    resultado = 'derrota'
                    pontos_base = 0
                
                # Calcular peso do resultado baseado na força do adversário
                peso_resultado = calcular_peso_resultado_por_forca_adversario(resultado, forca_adversario)
                
                # Pontos ponderados
                pontos_ponderados_casa += pontos_base * peso_resultado
                pontos_possiveis_ponderados_casa += 3.0 * peso_resultado  # Máximo possível ponderado
                
                gols_feitos_casa += placar_mandante
                gols_sofridos_casa += placar_visitante
            
            total_partidas_casa = len(partidas_casa)
            aproveitamento_casa = pontos_ponderados_casa / pontos_possiveis_ponderados_casa if pontos_possiveis_ponderados_casa > 0 else 0
            
            # Ajustar aproveitamento pela força média dos adversários
            forca_media_adversarios_casa = calcular_forca_media_adversarios(
                cursor, casa_id, rodada_atual, ultimas_partidas, 
                como_mandante=True, tabela_classificacao=tabela_classificacao
            )
            aproveitamento_casa_ajustado = ajustar_aproveitamento_por_forca_adversarios(
                aproveitamento_casa, forca_media_adversarios_casa
            )
            
            media_gols_feitos_casa = gols_feitos_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            media_gols_sofridos_casa = gols_sofridos_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            saldo_gols_casa = gols_feitos_casa - gols_sofridos_casa
            
            # Ajustar saldo de gols pela força dos adversários
            saldo_gols_casa_ajustado = ajustar_saldo_gols_por_forca_adversarios(
                saldo_gols_casa, forca_media_adversarios_casa
            )
            
            # Calcular índices ajustados
            indice_base_casa = 0.1 + (aproveitamento_casa_ajustado * 2.5)
            fator_saldo_casa = 1.0 + (saldo_gols_casa_ajustado * 0.10)
            indice_casa = indice_base_casa * fator_saldo_casa
            
            # Buscar últimas partidas do visitante como visitante com informações dos adversários
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante, clube_casa_id
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s
                AND placar_oficial_mandante IS NOT NULL AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (visitante_id, rodada_atual - 1, ultimas_partidas))
            partidas_visitante = cursor.fetchall()
            
            # Calcular aproveitamento e saldo considerando força dos adversários
            pontos_ponderados_visitante = 0.0
            pontos_possiveis_ponderados_visitante = 0.0
            gols_feitos_visitante = 0
            gols_sofridos_visitante = 0
            
            for placar_mandante, placar_visitante, adversario_id in partidas_visitante:
                if placar_mandante is None or placar_visitante is None:
                    continue
                
                # Obter força do adversário
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                
                # Determinar resultado (do ponto de vista do visitante)
                if placar_visitante > placar_mandante:
                    resultado = 'vitoria'
                    pontos_base = 3
                elif placar_visitante == placar_mandante:
                    resultado = 'empate'
                    pontos_base = 1
                else:
                    resultado = 'derrota'
                    pontos_base = 0
                
                # Calcular peso do resultado baseado na força do adversário
                peso_resultado = calcular_peso_resultado_por_forca_adversario(resultado, forca_adversario)
                
                # Pontos ponderados
                pontos_ponderados_visitante += pontos_base * peso_resultado
                pontos_possiveis_ponderados_visitante += 3.0 * peso_resultado
                
                gols_feitos_visitante += placar_visitante
                gols_sofridos_visitante += placar_mandante
            
            total_partidas_visitante = len(partidas_visitante)
            aproveitamento_visitante = pontos_ponderados_visitante / pontos_possiveis_ponderados_visitante if pontos_possiveis_ponderados_visitante > 0 else 0
            
            # Ajustar aproveitamento pela força média dos adversários
            forca_media_adversarios_visitante = calcular_forca_media_adversarios(
                cursor, visitante_id, rodada_atual, ultimas_partidas,
                como_mandante=False, tabela_classificacao=tabela_classificacao
            )
            aproveitamento_visitante_ajustado = ajustar_aproveitamento_por_forca_adversarios(
                aproveitamento_visitante, forca_media_adversarios_visitante
            )
            
            media_gols_feitos_visitante = gols_feitos_visitante / total_partidas_visitante if total_partidas_visitante > 0 else 0
            media_gols_sofridos_visitante = gols_sofridos_visitante / total_partidas_visitante if total_partidas_visitante > 0 else 0
            saldo_gols_visitante = gols_feitos_visitante - gols_sofridos_visitante
            
            # Ajustar saldo de gols pela força dos adversários
            saldo_gols_visitante_ajustado = ajustar_saldo_gols_por_forca_adversarios(
                saldo_gols_visitante, forca_media_adversarios_visitante
            )
            
            # Calcular índices ajustados
            indice_base_visitante = 0.1 + (aproveitamento_visitante_ajustado * 2.5)
            fator_saldo_visitante = 1.0 + (saldo_gols_visitante_ajustado * 0.10)
            indice_visitante = indice_base_visitante * fator_saldo_visitante
            
            # Resto do cálculo permanece igual (análise de setores, etc.)
            potencial_ataque_casa = media_gols_feitos_casa
            defesa_visitante = media_gols_sofridos_visitante
            indice_ataque_casa = potencial_ataque_casa * (defesa_visitante + 0.1)
            
            potencial_ataque_visitante = media_gols_feitos_visitante
            defesa_casa = media_gols_sofridos_casa
            indice_ataque_visitante = potencial_ataque_visitante * (defesa_casa + 0.1)
            
            fator_base_casa = max(0.1, min(2.0, indice_ataque_casa / 2.0))
            fator_base_visitante = max(0.1, min(2.0, indice_ataque_visitante / 2.0))
            
            fator_saldo_gols_casa = 1.0 + (saldo_gols_casa_ajustado * 0.12)
            fator_saldo_gols_visitante = 1.0 + (saldo_gols_visitante_ajustado * 0.12)
            
            fator_gols_casa = fator_base_casa * fator_saldo_gols_casa
            fator_gols_visitante = fator_base_visitante * fator_saldo_gols_visitante
            
            soma_indices = indice_casa + indice_visitante
            indice_casa_normalizado = indice_casa / soma_indices if soma_indices > 0 else 0.5
            indice_visitante_normalizado = indice_visitante / soma_indices if soma_indices > 0 else 0.5
            
            # Analisar setores dos times (usar cache se disponível)
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
            
            ratio_ata = math.pow(analises['casa']['ata']['score_final'] / analises['visitante']['ata']['score_final'], 1/3)
            ratio_mei = math.pow(analises['casa']['mei']['score_final'] / analises['visitante']['mei']['score_final'], 1/3)
            ratio_def = math.pow(analises['casa']['def']['score_final'] / analises['visitante']['def']['score_final'], 1/3)
            
            peso_jogo_casa = (ratio_ata + ratio_mei + ratio_def) * indice_casa_normalizado
            peso_jogo_visitante = ((1/ratio_ata) + (1/ratio_mei) + (1/ratio_def)) * indice_visitante_normalizado
            
            peso_casa_ajustado = peso_jogo_casa * indice_casa * fator_gols_casa
            peso_fora_ajustado = peso_jogo_visitante * indice_visitante * fator_gols_visitante
            
            # Usar expoente configurado no perfil (1/4 para brando, 1/3 para agressivo)
            expoente = perfil.get('expoente', 1/4)  # Default: brando se não especificado
            diff = peso_casa_ajustado - peso_fora_ajustado
            peso_final = (diff ** expoente) if diff >= 0 else -((-diff) ** expoente)
            
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
            logger.info(f"  Perfil {perfil_id} de peso do jogo (AJUSTADO) salvo: {len(updates)} clubes")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao calcular peso do jogo (AJUSTADO) para perfil {perfil_id}: {e}", exc_info=True)
    finally:
        cursor.close()

