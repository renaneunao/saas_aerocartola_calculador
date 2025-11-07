"""
Versão ajustada do cálculo de peso do SG que considera a força dos adversários
usando a tabela de classificação
"""
import logging
from psycopg2.extras import execute_values
from database import get_db_connection
from calculo_tabela import (
    calcular_tabela_classificacao,
    calcular_forca_media_adversarios,
    ajustar_aproveitamento_por_forca_adversarios
)

logger = logging.getLogger(__name__)

def calculate_peso_sg_for_profile_ajustado(conn, rodada_atual, perfil, usar_provaveis_cartola=False):
    """Calcula peso do SG para um perfil específico, ajustado pela força dos adversários"""
    cursor = conn.cursor()
    perfil_id = perfil['id']
    ultimas_partidas = perfil['ultimas_partidas']
    
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
        
        logger.info(f"Calculando peso do SG (AJUSTADO) - Perfil {perfil_id} ({ultimas_partidas} ultimas partidas) - {len(partidas)} partidas")
        
        updates = []  # (clube_id, peso_sg)
        
        for idx, partida in enumerate(partidas, 1):
            partida_id, casa_id, casa_nome, visitante_id, visitante_nome = partida
            if idx % 5 == 0 or idx == len(partidas):
                logger.info(f"  Processando partida {idx}/{len(partidas)}: {casa_nome} vs {visitante_nome}")
            
            # Calcular gols sofridos pela casa como mandante (com informações dos adversários)
            cursor.execute('''
                SELECT placar_oficial_visitante, clube_visitante_id
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s 
                AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (casa_id, rodada_atual - 1, ultimas_partidas))
            gols_sofridos_casa = cursor.fetchall()
            
            total_gols_sofridos_casa = 0
            total_partidas_casa = len(gols_sofridos_casa)
            gols_ponderados_sofridos_casa = 0.0
            peso_total_casa = 0.0
            
            for gols, adversario_id in gols_sofridos_casa:
                total_gols_sofridos_casa += gols
                # Ponderar gols sofridos pela força do adversário
                # Se sofreu gols de time forte, é mais aceitável (peso menor)
                # Se sofreu gols de time fraco, é pior (peso maior)
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                peso = 1.0 + (0.5 - forca_adversario) * 0.3  # Times fortes = peso menor
                gols_ponderados_sofridos_casa += gols * peso
                peso_total_casa += peso
            
            media_gols_sofridos_casa = total_gols_sofridos_casa / total_partidas_casa if total_partidas_casa > 0 else 0
            media_gols_sofridos_casa_ponderada = gols_ponderados_sofridos_casa / peso_total_casa if peso_total_casa > 0 else media_gols_sofridos_casa
            
            # Calcular gols feitos pelo visitante como visitante (com informações dos adversários)
            cursor.execute('''
                SELECT placar_oficial_visitante, clube_casa_id
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s 
                AND placar_oficial_visitante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (visitante_id, rodada_atual - 1, ultimas_partidas))
            gols_feitos_visitante = cursor.fetchall()
            
            total_gols_feitos_visitante = 0
            total_partidas_visitante = len(gols_feitos_visitante)
            gols_ponderados_feitos_visitante = 0.0
            peso_total_visitante_feitos = 0.0
            
            for gols, adversario_id in gols_feitos_visitante:
                total_gols_feitos_visitante += gols
                # Ponderar gols feitos pela força do adversário
                # Se fez gols contra time forte, é melhor (peso maior)
                # Se fez gols contra time fraco, é menos impressionante (peso menor)
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                peso = 1.0 + (forca_adversario - 0.5) * 0.3  # Times fortes = peso maior
                gols_ponderados_feitos_visitante += gols * peso
                peso_total_visitante_feitos += peso
            
            media_gols_feitos_visitante = total_gols_feitos_visitante / total_partidas_visitante if total_partidas_visitante > 0 else 0
            media_gols_feitos_visitante_ponderada = gols_ponderados_feitos_visitante / peso_total_visitante_feitos if peso_total_visitante_feitos > 0 else media_gols_feitos_visitante
            
            # Calcular gols sofridos pelo visitante como visitante (com informações dos adversários)
            cursor.execute('''
                SELECT placar_oficial_mandante, clube_casa_id
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s 
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (visitante_id, rodada_atual - 1, ultimas_partidas))
            gols_sofridos_visitante = cursor.fetchall()
            
            total_gols_sofridos_visitante = 0
            total_partidas_visitante_sofr = len(gols_sofridos_visitante)
            gols_ponderados_sofridos_visitante = 0.0
            peso_total_visitante_sofr = 0.0
            
            for gols, adversario_id in gols_sofridos_visitante:
                total_gols_sofridos_visitante += gols
                # Ponderar gols sofridos pela força do adversário
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                peso = 1.0 + (0.5 - forca_adversario) * 0.3
                gols_ponderados_sofridos_visitante += gols * peso
                peso_total_visitante_sofr += peso
            
            media_gols_sofridos_visitante = total_gols_sofridos_visitante / total_partidas_visitante_sofr if total_partidas_visitante_sofr > 0 else 0
            media_gols_sofridos_visitante_ponderada = gols_ponderados_sofridos_visitante / peso_total_visitante_sofr if peso_total_visitante_sofr > 0 else media_gols_sofridos_visitante
            
            # Calcular gols feitos pela casa como mandante (com informações dos adversários)
            cursor.execute('''
                SELECT placar_oficial_mandante, clube_visitante_id
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s 
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT %s
            ''', (casa_id, rodada_atual - 1, ultimas_partidas))
            gols_feitos_casa = cursor.fetchall()
            
            total_gols_feitos_casa = 0
            total_partidas_casa_feitos = len(gols_feitos_casa)
            gols_ponderados_feitos_casa = 0.0
            peso_total_casa_feitos = 0.0
            
            for gols, adversario_id in gols_feitos_casa:
                total_gols_feitos_casa += gols
                # Ponderar gols feitos pela força do adversário
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                peso = 1.0 + (forca_adversario - 0.5) * 0.3
                gols_ponderados_feitos_casa += gols * peso
                peso_total_casa_feitos += peso
            
            media_gols_feitos_casa = total_gols_feitos_casa / total_partidas_casa_feitos if total_partidas_casa_feitos > 0 else 0
            media_gols_feitos_casa_ponderada = gols_ponderados_feitos_casa / peso_total_casa_feitos if peso_total_casa_feitos > 0 else media_gols_feitos_casa
            
            # Calcular clean sheets (considerando força dos adversários)
            clean_sheets_casa = 0
            clean_sheets_ponderados_casa = 0.0
            for gols, adversario_id in gols_sofridos_casa:
                if gols == 0:
                    clean_sheets_casa += 1
                    # Clean sheet contra time forte vale mais
                    forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                    peso = 1.0 + (forca_adversario - 0.5) * 0.4
                    clean_sheets_ponderados_casa += peso
            
            clean_sheets_visitante = 0
            clean_sheets_ponderados_visitante = 0.0
            for gols, adversario_id in gols_sofridos_visitante:
                if gols == 0:
                    clean_sheets_visitante += 1
                    forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                    peso = 1.0 + (forca_adversario - 0.5) * 0.4
                    clean_sheets_ponderados_visitante += peso
            
            # Calcular aproveitamento recente (últimas 3 partidas) - ajustado
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante, clube_visitante_id
                FROM acf_partidas
                WHERE clube_casa_id = %s AND valida = TRUE AND rodada_id <= %s 
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT 3
            ''', (casa_id, rodada_atual - 1))
            partidas_casa = cursor.fetchall()
            
            cursor.execute('''
                SELECT placar_oficial_mandante, placar_oficial_visitante, clube_casa_id
                FROM acf_partidas
                WHERE clube_visitante_id = %s AND valida = TRUE AND rodada_id <= %s 
                AND placar_oficial_mandante IS NOT NULL
                ORDER BY rodada_id DESC
                LIMIT 3
            ''', (visitante_id, rodada_atual - 1))
            partidas_visitante = cursor.fetchall()
            
            pontos_casa = 0.0
            pontos_ponderados_casa = 0.0
            pontos_possiveis_ponderados_casa = 0.0
            for partida in partidas_casa:
                placar_mandante, placar_visitante, adversario_id = partida
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                peso = 1.0 + (forca_adversario - 0.5) * 0.3
                
                if placar_mandante > placar_visitante:
                    pontos_casa += 3
                    pontos_ponderados_casa += 3 * peso
                elif placar_mandante == placar_visitante:
                    pontos_casa += 1
                    pontos_ponderados_casa += 1 * peso
                pontos_possiveis_ponderados_casa += 3 * peso
            
            pontos_visitante = 0.0
            pontos_ponderados_visitante = 0.0
            pontos_possiveis_ponderados_visitante = 0.0
            for partida in partidas_visitante:
                placar_mandante, placar_visitante, adversario_id = partida
                forca_adversario = tabela_classificacao.get(adversario_id, {}).get('forca_normalizada', 0.5)
                peso = 1.0 + (forca_adversario - 0.5) * 0.3
                
                if placar_visitante > placar_mandante:
                    pontos_visitante += 3
                    pontos_ponderados_visitante += 3 * peso
                elif placar_visitante == placar_mandante:
                    pontos_visitante += 1
                    pontos_ponderados_visitante += 1 * peso
                pontos_possiveis_ponderados_visitante += 3 * peso
            
            aproveitamento_casa = pontos_ponderados_casa / pontos_possiveis_ponderados_casa if pontos_possiveis_ponderados_casa > 0 else 0
            aproveitamento_visitante = pontos_ponderados_visitante / pontos_possiveis_ponderados_visitante if pontos_possiveis_ponderados_visitante > 0 else 0
            
            # Ajustar aproveitamento pela força média dos adversários
            forca_media_adversarios_casa = calcular_forca_media_adversarios(
                cursor, casa_id, rodada_atual, 3, 
                como_mandante=True, tabela_classificacao=tabela_classificacao
            )
            forca_media_adversarios_visitante = calcular_forca_media_adversarios(
                cursor, visitante_id, rodada_atual, 3,
                como_mandante=False, tabela_classificacao=tabela_classificacao
            )
            
            aproveitamento_casa_ajustado = ajustar_aproveitamento_por_forca_adversarios(
                aproveitamento_casa, forca_media_adversarios_casa
            )
            aproveitamento_visitante_ajustado = ajustar_aproveitamento_por_forca_adversarios(
                aproveitamento_visitante, forca_media_adversarios_visitante
            )
            
            # Fatores do SG (usando médias ponderadas)
            fator_clean_sheets_casa = clean_sheets_ponderados_casa / peso_total_casa if peso_total_casa > 0 else (clean_sheets_casa / total_partidas_casa if total_partidas_casa > 0 else 0)
            fator_clean_sheets_visitante = clean_sheets_ponderados_visitante / peso_total_visitante_sofr if peso_total_visitante_sofr > 0 else (clean_sheets_visitante / total_partidas_visitante_sofr if total_partidas_visitante_sofr > 0 else 0)
            
            # Usar médias ponderadas para defesa
            fator_defesa_casa = max(0, 1 - (media_gols_sofridos_casa_ponderada / 3.0))
            fator_defesa_visitante = max(0, 1 - (media_gols_sofridos_visitante_ponderada / 3.0))
            
            # Usar médias ponderadas para ataque adversário
            fator_ataque_adversario_casa = max(0, 1 - (media_gols_feitos_visitante_ponderada / 3.0))
            fator_ataque_adversario_visitante = max(0, 1 - (media_gols_feitos_casa_ponderada / 3.0))
            
            fator_aproveitamento_casa = aproveitamento_casa_ajustado
            fator_aproveitamento_visitante = aproveitamento_visitante_ajustado
            
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
            logger.info(f"  Perfil {perfil_id} de peso do SG (AJUSTADO) salvo: {len(updates_normalizados)} clubes")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao calcular peso do SG (AJUSTADO) para perfil {perfil_id}: {e}", exc_info=True)
    finally:
        cursor.close()

