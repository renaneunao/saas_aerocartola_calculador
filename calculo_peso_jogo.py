import logging
import math
from psycopg2.extras import execute_values
from database import get_db_connection
from config import PERFIS_PESO_JOGO

logger = logging.getLogger(__name__)

def calculate_player_composite_score_inline(media, jogos, preco):
    """Calcula score composto usando dados já obtidos (sem query ao banco)
    
    Removido: custo_beneficio e peso_score (não devem influenciar o cálculo)
    """
    media = max(media or 1.0, 1.0)
    jogos = max(jogos or 0, 0)
    
    media_score = min(media / 10.0, 1.0)
    consistencia_score = min(jogos / 20.0, 1.0)
    
    # Apenas média e consistência (sem custo_beneficio e peso_score)
    composite_score = (
        0.7 * media_score +
        0.3 * consistencia_score
    )
    
    return composite_score

def calculate_team_sector_analysis(cursor, clube_id, posicoes, usar_provaveis_cartola=False):
    """Calcula análise detalhada do setor do time"""
    
    if usar_provaveis_cartola:
        cursor.execute('''
            SELECT a.atleta_id, a.media_num, a.jogos_num, a.preco_num
            FROM acf_atletas a
            JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
            WHERE a.clube_id = %s AND a.posicao_id = ANY(%s) AND p.status = 'provavel'
            ORDER BY a.media_num DESC
        ''', (clube_id, posicoes))
    else:
        cursor.execute('''
            SELECT a.atleta_id, a.media_num, a.jogos_num, a.preco_num
            FROM acf_atletas a
            WHERE a.clube_id = %s AND a.posicao_id = ANY(%s) AND a.status_id = 7
            ORDER BY a.media_num DESC
        ''', (clube_id, posicoes))
    
    jogadores = cursor.fetchall()
    
    if not jogadores:
        return {
            'score_final': 1.0,
            'num_jogadores': 0
        }
    
    # Calcular scores diretamente com dados já obtidos (sem queries adicionais)
    scores_individuais = []
    for atleta_id, media, jogos, preco in jogadores:
        score = calculate_player_composite_score_inline(media, jogos, preco)
        scores_individuais.append(score)
    
    num_titulares = min(len(scores_individuais), 3 if posicoes[0] in [1, 2, 3] else 5)
    score_titulares = sum(scores_individuais[:num_titulares]) / num_titulares if num_titulares > 0 else 1.0
    
    if len(scores_individuais) > num_titulares:
        score_profundidade = sum(scores_individuais[num_titulares:]) / len(scores_individuais[num_titulares:])
    else:
        score_profundidade = score_titulares * 0.8
    
    if len(scores_individuais) > 1:
        import statistics
        desvio_padrao = statistics.stdev(scores_individuais)
        score_consistencia = max(0.1, 1.0 - (desvio_padrao / 2.0))
    else:
        score_consistencia = 1.0
    
    # Removido: custo_beneficio (não deve influenciar o cálculo)
    # Apenas titulares, profundidade e consistência
    score_final = max(0.1, (
        0.6 * score_titulares +
        0.25 * score_profundidade +
        0.15 * score_consistencia
    ))
    
    return {
        'score_final': score_final,
        'num_jogadores': len(jogadores)
    }

def calculate_peso_jogo_for_profile(conn, rodada_atual, perfil, usar_provaveis_cartola=False, cache_setores=None):
    """Calcula peso do jogo para um perfil específico
    
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
        
        logger.info(f"Calculando peso do jogo - Perfil {perfil_id} ({ultimas_partidas} ultimas partidas) - {len(partidas)} partidas")
        
        updates = []  # (clube_id, peso)
        
        for idx, partida in enumerate(partidas, 1):
            partida_id, casa_id, casa_nome, visitante_id, visitante_nome = partida
            if idx % 5 == 0 or idx == len(partidas):
                logger.info(f"  Processando partida {idx}/{len(partidas)}: {casa_nome} vs {visitante_nome}")
            
            # Calcular histórico da casa como mandante (otimizado: sem subquery)
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s
                AND placar_oficial_mandante IS NOT NULL AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (casa_id, rodada_atual - 1, ultimas_partidas))
            partidas_casa = cursor.fetchall()
            
            vitorias_casa = empates_casa = derrotas_casa = 0
            for placar_mandante, placar_visitante in partidas_casa:
                if placar_mandante is None or placar_visitante is None:
                    continue
                if placar_mandante > placar_visitante:
                    vitorias_casa += 1
                elif placar_mandante == placar_visitante:
                    empates_casa += 1
                else:
                    derrotas_casa += 1
            
            total_partidas_casa = vitorias_casa + empates_casa + derrotas_casa
            pontos_conquistados_casa = vitorias_casa * 3 + empates_casa
            pontos_possiveis_casa = total_partidas_casa * 3
            aproveitamento_casa = pontos_conquistados_casa / pontos_possiveis_casa if pontos_possiveis_casa > 0 else 0
            
            gols_feitos_casa = sum(p[0] for p in partidas_casa if p[0] is not None)
            gols_sofridos_casa = sum(p[1] for p in partidas_casa if p[1] is not None)
            
            media_gols_feitos_casa = gols_feitos_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            media_gols_sofridos_casa = gols_sofridos_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            saldo_gols_casa = gols_feitos_casa - gols_sofridos_casa
            
            # Reduzido agressividade: aproveitamento de 3.4 para 2.5, saldo de 0.15 para 0.10
            indice_base_casa = 0.1 + (aproveitamento_casa * 2.5)
            fator_saldo_casa = 1.0 + (saldo_gols_casa * 0.10)
            indice_casa = indice_base_casa * fator_saldo_casa
            
            # Calcular histórico do visitante como visitante (otimizado)
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s
                AND placar_oficial_mandante IS NOT NULL AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (visitante_id, rodada_atual - 1, ultimas_partidas))
            partidas_visitante = cursor.fetchall()
            
            vitorias_visitante = empates_visitante = derrotas_visitante = 0
            for placar_mandante, placar_visitante in partidas_visitante:
                if placar_mandante is None or placar_visitante is None:
                    continue
                if placar_visitante > placar_mandante:
                    vitorias_visitante += 1
                elif placar_visitante == placar_mandante:
                    empates_visitante += 1
                else:
                    derrotas_visitante += 1
            
            total_partidas_visitante = vitorias_visitante + empates_visitante + derrotas_visitante
            pontos_conquistados_visitante = vitorias_visitante * 3 + empates_visitante
            pontos_possiveis_visitante = total_partidas_visitante * 3
            aproveitamento_visitante = pontos_conquistados_visitante / pontos_possiveis_visitante if pontos_possiveis_visitante > 0 else 0
            
            gols_feitos_visitante = sum(p[1] for p in partidas_visitante if p[1] is not None)
            gols_sofridos_visitante = sum(p[0] for p in partidas_visitante if p[0] is not None)
            
            media_gols_feitos_visitante = gols_feitos_visitante / total_partidas_visitante if total_partidas_visitante > 0 else 0
            media_gols_sofridos_visitante = gols_sofridos_visitante / total_partidas_visitante if total_partidas_visitante > 0 else 0
            saldo_gols_visitante = gols_feitos_visitante - gols_sofridos_visitante
            
            # Reduzido agressividade: aproveitamento de 3.4 para 2.5, saldo de 0.15 para 0.10
            indice_base_visitante = 0.1 + (aproveitamento_visitante * 2.5)
            fator_saldo_visitante = 1.0 + (saldo_gols_visitante * 0.10)
            indice_visitante = indice_base_visitante * fator_saldo_visitante
            
            potencial_ataque_casa = media_gols_feitos_casa
            defesa_visitante = media_gols_sofridos_visitante
            indice_ataque_casa = potencial_ataque_casa * (defesa_visitante + 0.1)
            
            potencial_ataque_visitante = media_gols_feitos_visitante
            defesa_casa = media_gols_sofridos_casa
            indice_ataque_visitante = potencial_ataque_visitante * (defesa_casa + 0.1)
            
            fator_base_casa = max(0.1, min(2.0, indice_ataque_casa / 2.0))
            fator_base_visitante = max(0.1, min(2.0, indice_ataque_visitante / 2.0))
            
            # Reduzido agressividade: saldo de gols de 0.20 para 0.12
            fator_saldo_gols_casa = 1.0 + (saldo_gols_casa * 0.12)
            fator_saldo_gols_visitante = 1.0 + (saldo_gols_visitante * 0.12)
            
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
                    # Usar do cache
                    analises['casa'][sector] = {'score_final': cache_setores[pos_key_casa]}
                
                if pos_key_visitante not in cache_setores:
                    analises['visitante'][sector] = calculate_team_sector_analysis(
                        cursor, visitante_id, posicoes, usar_provaveis_cartola
                    )
                    cache_setores[pos_key_visitante] = analises['visitante'][sector]['score_final']
                else:
                    # Usar do cache
                    analises['visitante'][sector] = {'score_final': cache_setores[pos_key_visitante]}
            
            ratio_ata = math.pow(analises['casa']['ata']['score_final'] / analises['visitante']['ata']['score_final'], 1/3)
            ratio_mei = math.pow(analises['casa']['mei']['score_final'] / analises['visitante']['mei']['score_final'], 1/3)
            ratio_def = math.pow(analises['casa']['def']['score_final'] / analises['visitante']['def']['score_final'], 1/3)
            
            peso_jogo_casa = (ratio_ata + ratio_mei + ratio_def) * indice_casa_normalizado
            peso_jogo_visitante = ((1/ratio_ata) + (1/ratio_mei) + (1/ratio_def)) * indice_visitante_normalizado
            
            peso_casa_ajustado = peso_jogo_casa * indice_casa * fator_gols_casa
            peso_fora_ajustado = peso_jogo_visitante * indice_visitante * fator_gols_visitante
            
            # Removido limite de 10.0 para permitir mais diferenciação entre times
            # O limite estava causando valores idênticos quando havia poucos jogos
            # peso_casa_ajustado = min(peso_casa_ajustado, 10.0)
            # peso_fora_ajustado = min(peso_fora_ajustado, 10.0)
            
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
            logger.info(f"  Perfil {perfil_id} de peso do jogo salvo: {len(updates)} clubes")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao calcular peso do jogo para perfil {perfil_id}: {e}", exc_info=True)
    finally:
        cursor.close()

