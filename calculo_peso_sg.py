import logging
from psycopg2.extras import execute_values
from psycopg2.extras import execute_values
from database import get_db_connection
from api_cartola import get_temporada_atual

logger = logging.getLogger(__name__)

def calculate_peso_sg_for_profile(conn, rodada_atual, perfil, usar_provaveis_cartola=False):
    """Calcula peso do SG para um perfil específico"""
    cursor = conn.cursor()
    perfil_id = perfil['id']
    ultimas_partidas = perfil['ultimas_partidas']
    temporada_atual = get_temporada_atual()
    
    try:
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
        
        logger.info(f"Calculando peso do SG - Perfil {perfil_id} ({ultimas_partidas} ultimas partidas) - {len(partidas)} partidas")
        
        updates = []  # (clube_id, peso_sg)
        
        for idx, partida in enumerate(partidas, 1):
            partida_id, casa_id, casa_nome, visitante_id, visitante_nome = partida
            if idx % 5 == 0 or idx == len(partidas):
                logger.info(f"  Processando partida {idx}/{len(partidas)}: {casa_nome} vs {visitante_nome}")
            
            # Calcular gols sofridos pela casa como mandante
            query_gols_sofridos_casa = '''
                SELECT placar_oficial_visitante
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s AND temporada = %s
                AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            '''
            params = (casa_id, rodada_atual - 1, temporada_atual, ultimas_partidas)
            
            cursor.execute(query_gols_sofridos_casa, params)
            gols_sofridos_casa = cursor.fetchall()
            total_gols_sofridos_casa = sum(gols[0] for gols in gols_sofridos_casa)
            total_partidas_casa = len(gols_sofridos_casa)
            media_gols_sofridos_casa = total_gols_sofridos_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            
            # Calcular gols feitos pelo visitante como visitante
            query_gols_feitos_visitante = '''
                SELECT placar_oficial_visitante
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s AND temporada = %s
                AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            '''
            params = (visitante_id, rodada_atual - 1, temporada_atual, ultimas_partidas)
            
            cursor.execute(query_gols_feitos_visitante, params)
            gols_feitos_visitante = cursor.fetchall()
            total_gols_feitos_visitante = sum(gols[0] for gols in gols_feitos_visitante)
            total_partidas_visitante = len(gols_feitos_visitante)
            media_gols_feitos_visitante = total_gols_feitos_visitante / total_partidas_visitante if total_partidas_visitante > 0 else 0
            
            # Calcular gols sofridos pelo visitante como visitante
            query_gols_sofridos_visitante = '''
                SELECT placar_oficial_mandante
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s AND temporada = %s
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            '''
            params = (visitante_id, rodada_atual - 1, temporada_atual, ultimas_partidas)
            
            cursor.execute(query_gols_sofridos_visitante, params)
            gols_sofridos_visitante = cursor.fetchall()
            total_gols_sofridos_visitante = sum(gols[0] for gols in gols_sofridos_visitante)
            total_partidas_visitante_sofr = len(gols_sofridos_visitante)
            media_gols_sofridos_visitante = total_gols_sofridos_visitante / total_partidas_visitante_sofr if total_partidas_visitante_sofr > 0 else 0
            
            # Calcular gols feitos pela casa como mandante
            query_gols_feitos_casa = '''
                SELECT placar_oficial_mandante
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s AND temporada = %s
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            '''
            params = (casa_id, rodada_atual - 1, temporada_atual, ultimas_partidas)
            
            cursor.execute(query_gols_feitos_casa, params)
            gols_feitos_casa = cursor.fetchall()
            total_gols_feitos_casa = sum(gols[0] for gols in gols_feitos_casa)
            total_partidas_casa_feitos = len(gols_feitos_casa)
            media_gols_feitos_casa = total_gols_feitos_casa / total_partidas_casa_feitos if total_partidas_casa_feitos > 0 else 0
            
            # Calcular clean sheets
            clean_sheets_casa = sum(1 for gols in gols_sofridos_casa if gols[0] == 0)
            clean_sheets_visitante = sum(1 for gols in gols_sofridos_visitante if gols[0] == 0)
            
            # Calcular aproveitamento recente (últimas 3 partidas)
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s AND temporada = %s
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT 3
            ''', (casa_id, rodada_atual - 1, temporada_atual))
            partidas_casa = cursor.fetchall()
            
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s AND temporada = %s
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT 3
            ''', (visitante_id, rodada_atual - 1, temporada_atual))
            partidas_visitante = cursor.fetchall()
            
            pontos_casa = 0
            for partida in partidas_casa:
                placar_mandante, placar_visitante = partida
                if placar_mandante > placar_visitante:
                    pontos_casa += 3
                elif placar_mandante == placar_visitante:
                    pontos_casa += 1
            
            pontos_visitante = 0
            for partida in partidas_visitante:
                placar_mandante, placar_visitante = partida
                if placar_visitante > placar_mandante:
                    pontos_visitante += 3
                elif placar_visitante == placar_mandante:
                    pontos_visitante += 1
            
            aproveitamento_casa = pontos_casa / (len(partidas_casa) * 3) if partidas_casa else 0
            aproveitamento_visitante = pontos_visitante / (len(partidas_visitante) * 3) if partidas_visitante else 0
            
            # Fatores do SG
            fator_clean_sheets_casa = clean_sheets_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            fator_clean_sheets_visitante = clean_sheets_visitante / total_partidas_visitante_sofr if total_partidas_visitante_sofr > 0 else 0
            
            fator_defesa_casa = max(0, 1 - (media_gols_sofridos_casa / 3.0))
            fator_defesa_visitante = max(0, 1 - (media_gols_sofridos_visitante / 3.0))
            
            fator_ataque_adversario_casa = max(0, 1 - (media_gols_feitos_visitante / 3.0))
            fator_ataque_adversario_visitante = max(0, 1 - (media_gols_feitos_casa / 3.0))
            
            fator_aproveitamento_casa = aproveitamento_casa
            fator_aproveitamento_visitante = aproveitamento_visitante
            
            # Fator de jogadores prováveis (simplificado - pode ser expandido)
            fator_jogadores_casa = 0.5
            fator_jogadores_visitante = 0.5
            
            if usar_provaveis_cartola:
                posicoes_defesa = [1, 2, 3, 6]
                
                cursor.execute('''
                    SELECT AVG(a.media_num) as media_defesa, COUNT(*) as total_jogadores
                    FROM acf_atletas a
                    JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
                    WHERE a.clube_id = %s AND a.posicao_id = ANY(%s) AND p.status = 'provavel'
                ''', (casa_id, posicoes_defesa))
                defesa_casa = cursor.fetchone()
                
                cursor.execute('''
                    SELECT AVG(a.media_num) as media_ataque, COUNT(*) as total_jogadores
                    FROM acf_atletas a
                    JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
                    WHERE a.clube_id = %s AND a.posicao_id IN (4, 5) AND p.status = 'provavel'
                ''', (visitante_id,))
                ataque_visitante = cursor.fetchone()
                
                cursor.execute('''
                    SELECT AVG(a.media_num) as media_defesa, COUNT(*) as total_jogadores
                    FROM acf_atletas a
                    JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
                    WHERE a.clube_id = %s AND a.posicao_id = ANY(%s) AND p.status = 'provavel'
                ''', (visitante_id, posicoes_defesa))
                defesa_visitante = cursor.fetchone()
                
                cursor.execute('''
                    SELECT AVG(a.media_num) as media_ataque, COUNT(*) as total_jogadores
                    FROM acf_atletas a
                    JOIN provaveis_cartola p ON a.atleta_id = p.atleta_id
                    WHERE a.clube_id = %s AND a.posicao_id IN (4, 5) AND p.status = 'provavel'
                ''', (casa_id,))
                ataque_casa = cursor.fetchone()
                
                if defesa_casa and defesa_casa[0] and ataque_visitante and ataque_visitante[0]:
                    fator_jogadores_casa = max(0.1, min(1.0, 
                        (defesa_casa[0] / 10.0) - (ataque_visitante[0] / 10.0) + 0.5
                    ))
                
                if defesa_visitante and defesa_visitante[0] and ataque_casa and ataque_casa[0]:
                    fator_jogadores_visitante = max(0.1, min(1.0, 
                        (defesa_visitante[0] / 10.0) - (ataque_casa[0] / 10.0) + 0.5
                    ))
            
            # SG composto - ajustar pesos conforme agressividade do perfil
            agressividade = perfil.get('agressividade', 'brando')
            
            if agressividade == 'agressivo':
                # Agressivo: mais peso em clean sheets e defesa (fatores mais determinantes)
                peso_clean_sheets = 0.3
                peso_defesa = 0.3
                peso_ataque_adversario = 0.15
                peso_aproveitamento = 0.1
                peso_jogadores = 0.15
            else:
                # Brando: pesos mais equilibrados (distribuição uniforme)
                peso_clean_sheets = 0.2
                peso_defesa = 0.2
                peso_ataque_adversario = 0.2
                peso_aproveitamento = 0.1
                peso_jogadores = 0.3
            
            peso_sg_casa = (
                peso_clean_sheets * fator_clean_sheets_casa +
                peso_defesa * fator_defesa_casa +
                peso_ataque_adversario * fator_ataque_adversario_casa +
                peso_aproveitamento * fator_aproveitamento_casa +
                peso_jogadores * fator_jogadores_casa
            )
            
            peso_sg_visitante = (
                peso_clean_sheets * fator_clean_sheets_visitante +
                peso_defesa * fator_defesa_visitante +
                peso_ataque_adversario * fator_ataque_adversario_visitante +
                peso_aproveitamento * fator_aproveitamento_visitante +
                peso_jogadores * fator_jogadores_visitante
            )
            
            updates.append((casa_id, peso_sg_casa))
            updates.append((visitante_id, peso_sg_visitante))
        
        # Normalizar valores
        if updates:
            sg_values = [peso for _, peso in updates]
            min_sg = min(sg_values)
            max_sg = max(sg_values)
            
            updates_normalizados = []
            for clube_id, peso_sg in updates:
                if max_sg > min_sg:
                    normalized = (peso_sg - min_sg) / (max_sg - min_sg)
                    peso_sg_normalizado = 0.1 + (normalized * 0.9)
                else:
                    peso_sg_normalizado = 0.5
                updates_normalizados.append((clube_id, peso_sg_normalizado))
            
            # Deletar registros antigos do perfil para esta rodada
            cursor.execute('''
                DELETE FROM acp_peso_sg_perfis 
                WHERE perfil_id = %s AND rodada_atual = %s
            ''', (perfil_id, rodada_atual))
            
            # Inserir novos valores
            insert_data = [
                (perfil_id, rodada_atual, clube_id, peso_sg, ultimas_partidas)
                for clube_id, peso_sg in updates_normalizados
            ]
            
            execute_values(
                cursor,
                '''
                INSERT INTO acp_peso_sg_perfis (perfil_id, rodada_atual, clube_id, peso_sg, ultimas_partidas)
                VALUES %s
                ON CONFLICT (perfil_id, rodada_atual, clube_id) 
                DO UPDATE SET peso_sg = EXCLUDED.peso_sg, created_at = NOW()
                ''',
                insert_data,
                template=None,
                page_size=1000
            )
            
            conn.commit()
            logger.info(f"  Perfil {perfil_id} de peso do SG salvo: {len(updates_normalizados)} clubes")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao calcular peso do SG para perfil {perfil_id}: {e}", exc_info=True)
    finally:
        cursor.close()

