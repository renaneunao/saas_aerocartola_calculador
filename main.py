import logging
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
from database import get_db_connection, close_db_connection, init_tables
from api_cartola import fetch_status_data
from calculo_peso_jogo import calculate_peso_jogo_for_profile
from calculo_peso_sg import calculate_peso_sg_for_profile
from mostrar_rankings import mostrar_ranking_peso_jogo, mostrar_ranking_peso_sg
from config import PERFIS_PESO_JOGO, PERFIS_PESO_SG, CALCULATION_INTERVAL_MINUTES

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def execute_calculations(scheduler=None):
    """Executa todos os cálculos de peso do jogo e peso do SG para todos os perfis
    
    Após a conclusão, agenda a próxima execução para 15 minutos após o término.
    
    Args:
        scheduler: Instância do scheduler (opcional, para agendar próxima execução)
    """
    logger.info("=" * 80)
    logger.info("Iniciando rotina de cálculos")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # Obter rodada atual
    status_data = fetch_status_data()
    if not status_data:
        logger.error("Erro ao obter dados de status do Cartola. Abortando cálculos.")
        _agendar_proxima_execucao(scheduler, start_time)
        return
    
    rodada_atual = status_data.get('rodada_atual')
    if not rodada_atual:
        logger.error("Rodada atual não encontrada nos dados de status. Abortando cálculos.")
        _agendar_proxima_execucao(scheduler, start_time)
        return
    
    # Verificar se o mercado está aberto
    # status_mercado: 1 = aberto, 2 = fechado, etc.
    status_mercado = status_data.get('status_mercado')
    if status_mercado != 1:
        logger.info(f"Mercado está fechado (status: {status_mercado}). Pulando atualização das tabelas.")
        logger.info("Os cálculos serão retomados quando o mercado abrir novamente.")
        _agendar_proxima_execucao(scheduler, start_time)
        return
    
    logger.info(f"Rodada atual: {rodada_atual}")
    logger.info(f"Mercado está aberto (status: {status_mercado}). Iniciando cálculos...")
    
    # Conectar ao banco
    conn = get_db_connection()
    if not conn:
        logger.error("Erro ao conectar ao banco de dados. Abortando cálculos.")
        _agendar_proxima_execucao(scheduler, start_time)
        return
    
    try:
        # Inicializar tabelas se necessário
        init_tables(conn)
        
        # Cache compartilhado de análises de setores (os dados dos atletas não mudam entre perfis)
        cache_setores_jogo = {}
        
        # Calcular peso do jogo para todos os perfis
        logger.info(f"\n{'='*80}")
        logger.info("CALCULANDO PESO DO JOGO - 10 PERFIS")
        logger.info(f"{'='*80}\n")
        
        for perfil in PERFIS_PESO_JOGO:
            try:
                logger.info(f"Processando perfil {perfil['id']}: {perfil['descricao']}")
                calculate_peso_jogo_for_profile(
                    conn, 
                    rodada_atual, 
                    perfil, 
                    usar_provaveis_cartola=False,
                    cache_setores=cache_setores_jogo
                )
                logger.info(f"[OK] Perfil {perfil['id']} de peso do jogo concluido")
                # Mostrar ranking
                mostrar_ranking_peso_jogo(conn, rodada_atual, perfil['id'])
            except Exception as e:
                logger.error(f"[ERRO] Erro ao processar perfil {perfil['id']} de peso do jogo: {e}", exc_info=True)
        
        # Calcular peso do SG para todos os perfis
        logger.info(f"\n{'='*80}")
        logger.info("CALCULANDO PESO DO SG - 10 PERFIS")
        logger.info(f"{'='*80}\n")
        
        for perfil in PERFIS_PESO_SG:
            try:
                logger.info(f"Processando perfil {perfil['id']}: {perfil['descricao']}")
                calculate_peso_sg_for_profile(
                    conn, 
                    rodada_atual, 
                    perfil, 
                    usar_provaveis_cartola=False
                )
                logger.info(f"[OK] Perfil {perfil['id']} de peso do SG concluido")
                # Mostrar ranking
                mostrar_ranking_peso_sg(conn, rodada_atual, perfil['id'])
            except Exception as e:
                logger.error(f"[ERRO] Erro ao processar perfil {perfil['id']} de peso do SG: {e}", exc_info=True)
        
        elapsed_time = datetime.now() - start_time
        logger.info("=" * 80)
        logger.info(f"Rotina de cálculos concluída em {elapsed_time.total_seconds():.2f} segundos")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Erro geral na rotina de cálculos: {e}", exc_info=True)
    finally:
        close_db_connection(conn)
        # Agendar próxima execução após o término (não importa se deu erro ou sucesso)
        _agendar_proxima_execucao(scheduler, datetime.now())

def _agendar_proxima_execucao(scheduler, fim_execucao_atual):
    """Agenda a próxima execução para 15 minutos após o término da atual"""
    if scheduler is None:
        return
    
    from datetime import timedelta
    
    proxima_execucao = fim_execucao_atual + timedelta(minutes=CALCULATION_INTERVAL_MINUTES)
    
    # Remover job existente se houver
    try:
        scheduler.remove_job('calculo_pesos')
    except:
        pass
    
    # Agendar próxima execução
    scheduler.add_job(
        execute_calculations,
        trigger='date',
        run_date=proxima_execucao,
        args=[scheduler],  # Passar o scheduler para poder agendar a próxima
        id='calculo_pesos',
        name='Cálculo de Pesos do Jogo e SG',
        replace_existing=True
    )
    
    logger.info(f"Próxima execução agendada para: {proxima_execucao.strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Função principal que configura o agendador"""
    logger.info("Iniciando Calculador de Pesos do Jogo e SG")
    logger.info(f"Intervalo entre ciclos: {CALCULATION_INTERVAL_MINUTES} minutos (após término de cada ciclo)")
    
    # Configurar agendador
    scheduler = BlockingScheduler(timezone='America/Sao_Paulo')
    
    # Executar imediatamente na primeira vez
    # A função execute_calculations vai agendar a próxima execução após terminar
    logger.info("Executando cálculos iniciais...")
    execute_calculations(scheduler)
    
    logger.info("Agendador configurado. O serviço executará um novo ciclo {} minutos após o término de cada ciclo anterior.".format(CALCULATION_INTERVAL_MINUTES))
    logger.info("Pressione Ctrl+C para parar o serviço.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Serviço interrompido pelo usuário.")
        scheduler.shutdown()

if __name__ == "__main__":
    main()

