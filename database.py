import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)

def get_db_connection():
    """Conecta ao banco de dados PostgreSQL"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def close_db_connection(conn):
    """Fecha a conexão com o banco de dados"""
    if conn:
        try:
            conn.close()
        except psycopg2.Error as e:
            logger.error(f"Erro ao fechar conexão: {e}")

def init_tables(conn):
    """Cria as tabelas necessárias para armazenar os perfis"""
    cursor = conn.cursor()
    
    try:
        # Tabela de perfis de peso do jogo
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acp_peso_jogo_perfis (
                id SERIAL PRIMARY KEY,
                perfil_id INTEGER NOT NULL,
                rodada_atual INTEGER NOT NULL,
                clube_id INTEGER NOT NULL,
                peso_jogo REAL NOT NULL,
                ultimas_partidas INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(perfil_id, rodada_atual, clube_id)
            );
        ''')
        
        # Tabela de perfis de peso do SG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS acp_peso_sg_perfis (
                id SERIAL PRIMARY KEY,
                perfil_id INTEGER NOT NULL,
                rodada_atual INTEGER NOT NULL,
                clube_id INTEGER NOT NULL,
                peso_sg REAL NOT NULL,
                ultimas_partidas INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(perfil_id, rodada_atual, clube_id)
            );
        ''')
        
        # Índices para performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_acp_peso_jogo_perfis 
            ON acp_peso_jogo_perfis(perfil_id, rodada_atual, clube_id);
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_acp_peso_sg_perfis 
            ON acp_peso_sg_perfis(perfil_id, rodada_atual, clube_id);
        ''')
        
        conn.commit()
        logger.info("Tabelas inicializadas com sucesso")
        return True
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Erro ao criar tabelas: {e}")
        return False
    finally:
        cursor.close()

