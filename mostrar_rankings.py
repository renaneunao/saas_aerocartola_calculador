"""Funções para exibir rankings de peso do jogo e peso do SG"""
import logging
from database import get_db_connection

logger = logging.getLogger(__name__)

def mostrar_ranking_peso_jogo(conn, rodada_atual, perfil_id):
    """Exibe ranking de peso do jogo para um perfil específico"""
    cursor = conn.cursor()
    
    try:
        # Buscar dados com informações das partidas
        cursor.execute('''
            SELECT 
                pj.perfil_id,
                pj.clube_id,
                c.nome_fantasia as clube_nome,
                pj.peso_jogo,
                p.clube_casa_id,
                p.clube_visitante_id,
                c1.nome_fantasia as casa_nome,
                c2.nome_fantasia as visitante_nome
            FROM acp_peso_jogo_perfis pj
            JOIN clubes c ON pj.clube_id = c.id
            JOIN partidas p ON (
                (p.clube_casa_id = pj.clube_id OR p.clube_visitante_id = pj.clube_id)
                AND p.rodada_id = %s AND p.valida = TRUE
            )
            JOIN clubes c1 ON p.clube_casa_id = c1.id
            JOIN clubes c2 ON p.clube_visitante_id = c2.id
            WHERE pj.perfil_id = %s AND pj.rodada_atual = %s
            ORDER BY pj.peso_jogo DESC
        ''', (rodada_atual, perfil_id, rodada_atual))
        
        resultados = cursor.fetchall()
        
        if not resultados:
            logger.warning(f"  Nenhum resultado encontrado para perfil {perfil_id}")
            return
        
        # Organizar por partida
        partidas_dict = {}
        for row in resultados:
            perfil_id_db, clube_id, clube_nome, peso_jogo, casa_id, visitante_id, casa_nome, visitante_nome = row
            
            # Determinar adversário
            if clube_id == casa_id:
                adversario_nome = visitante_nome
            else:
                adversario_nome = casa_nome
            
            chave_partida = tuple(sorted([casa_id, visitante_id]))
            if chave_partida not in partidas_dict:
                partidas_dict[chave_partida] = {
                    'casa_id': casa_id,
                    'visitante_id': visitante_id,
                    'casa_nome': casa_nome,
                    'visitante_nome': visitante_nome,
                    'pesos': {}
                }
            
            partidas_dict[chave_partida]['pesos'][clube_id] = {
                'nome': clube_nome,
                'peso': peso_jogo
            }
        
        # Exibir ranking
        logger.info(f"\n{'='*100}")
        logger.info(f"RANKING PESO DO JOGO - PERFIL {perfil_id} - Rodada {rodada_atual}")
        logger.info(f"{'='*100}")
        logger.info(f"{'Pos':<5} {'Time':<25} {'Adversario':<25} {'Peso Jogo':<12}")
        logger.info(f"{'-'*100}")
        
        # Criar lista de times ordenados por peso
        todos_pesos = []
        for chave, partida in partidas_dict.items():
            for clube_id, dados in partida['pesos'].items():
                if clube_id == partida['casa_id']:
                    adversario = partida['visitante_nome']
                else:
                    adversario = partida['casa_nome']
                
                todos_pesos.append({
                    'time': dados['nome'],
                    'adversario': adversario,
                    'peso': dados['peso']
                })
        
        todos_pesos.sort(key=lambda x: x['peso'], reverse=True)
        
        for idx, item in enumerate(todos_pesos, 1):
            logger.info(f"{idx:<5} {item['time']:<25} {item['adversario']:<25} {item['peso']:>10.4f}")
        
        logger.info(f"{'-'*100}\n")
        
    except Exception as e:
        logger.error(f"Erro ao exibir ranking de peso do jogo: {e}", exc_info=True)
    finally:
        cursor.close()

def mostrar_ranking_peso_sg(conn, rodada_atual, perfil_id):
    """Exibe ranking de peso do SG para um perfil específico"""
    cursor = conn.cursor()
    
    try:
        # Buscar dados com informações das partidas
        cursor.execute('''
            SELECT 
                ps.perfil_id,
                ps.clube_id,
                c.nome_fantasia as clube_nome,
                ps.peso_sg,
                p.clube_casa_id,
                p.clube_visitante_id,
                c1.nome_fantasia as casa_nome,
                c2.nome_fantasia as visitante_nome
            FROM acp_peso_sg_perfis ps
            JOIN clubes c ON ps.clube_id = c.id
            JOIN partidas p ON (
                (p.clube_casa_id = ps.clube_id OR p.clube_visitante_id = ps.clube_id)
                AND p.rodada_id = %s AND p.valida = TRUE
            )
            JOIN clubes c1 ON p.clube_casa_id = c1.id
            JOIN clubes c2 ON p.clube_visitante_id = c2.id
            WHERE ps.perfil_id = %s AND ps.rodada_atual = %s
            ORDER BY ps.peso_sg DESC
        ''', (rodada_atual, perfil_id, rodada_atual))
        
        resultados = cursor.fetchall()
        
        if not resultados:
            logger.warning(f"  Nenhum resultado encontrado para perfil {perfil_id}")
            return
        
        # Organizar por partida
        partidas_dict = {}
        for row in resultados:
            perfil_id_db, clube_id, clube_nome, peso_sg, casa_id, visitante_id, casa_nome, visitante_nome = row
            
            # Determinar adversário
            if clube_id == casa_id:
                adversario_nome = visitante_nome
            else:
                adversario_nome = casa_nome
            
            chave_partida = tuple(sorted([casa_id, visitante_id]))
            if chave_partida not in partidas_dict:
                partidas_dict[chave_partida] = {
                    'casa_id': casa_id,
                    'visitante_id': visitante_id,
                    'casa_nome': casa_nome,
                    'visitante_nome': visitante_nome,
                    'pesos': {}
                }
            
            partidas_dict[chave_partida]['pesos'][clube_id] = {
                'nome': clube_nome,
                'peso': peso_sg
            }
        
        # Exibir ranking
        logger.info(f"\n{'='*100}")
        logger.info(f"RANKING PESO DO SG - PERFIL {perfil_id} - Rodada {rodada_atual}")
        logger.info(f"{'='*100}")
        logger.info(f"{'Pos':<5} {'Time':<25} {'Adversario':<25} {'Peso SG':<12}")
        logger.info(f"{'-'*100}")
        
        # Criar lista de times ordenados por peso
        todos_pesos = []
        for chave, partida in partidas_dict.items():
            for clube_id, dados in partida['pesos'].items():
                if clube_id == partida['casa_id']:
                    adversario = partida['visitante_nome']
                else:
                    adversario = partida['casa_nome']
                
                todos_pesos.append({
                    'time': dados['nome'],
                    'adversario': adversario,
                    'peso': dados['peso']
                })
        
        todos_pesos.sort(key=lambda x: x['peso'], reverse=True)
        
        for idx, item in enumerate(todos_pesos, 1):
            logger.info(f"{idx:<5} {item['time']:<25} {item['adversario']:<25} {item['peso']:>10.4f}")
        
        logger.info(f"{'-'*100}\n")
        
    except Exception as e:
        logger.error(f"Erro ao exibir ranking de peso do SG: {e}", exc_info=True)
    finally:
        cursor.close()

