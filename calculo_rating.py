"""
Módulo para calcular ratings dos times estilo ELO (FIDE)
Todos os times começam com 1000 pontos e o rating é atualizado a cada partida
"""
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Constantes do sistema ELO
RATING_INICIAL = 1000
K_FACTOR = 20  # Fator de ajuste (quanto maior, mais rápido o rating muda)
DIVISOR_ELO = 400  # Divisor padrão do ELO

def calcular_rating_esperado(rating_time: float, rating_adversario: float) -> float:
    """
    Calcula a probabilidade esperada de vitória baseada nos ratings
    
    Args:
        rating_time: Rating do time
        rating_adversario: Rating do adversário
    
    Returns:
        Probabilidade esperada (0.0-1.0)
    """
    diferenca = rating_adversario - rating_time
    return 1.0 / (1.0 + (10 ** (diferenca / DIVISOR_ELO)))


def atualizar_rating(
    rating_atual: float,
    rating_adversario: float,
    resultado: float,  # 1.0 = vitória, 0.5 = empate, 0.0 = derrota
    k_factor: float = K_FACTOR
) -> float:
    """
    Atualiza o rating após uma partida
    
    Args:
        rating_atual: Rating atual do time
        rating_adversario: Rating do adversário
        resultado: 1.0 para vitória, 0.5 para empate, 0.0 para derrota
        k_factor: Fator de ajuste (padrão 20)
    
    Returns:
        Novo rating
    """
    rating_esperado = calcular_rating_esperado(rating_atual, rating_adversario)
    novo_rating = rating_atual + k_factor * (resultado - rating_esperado)
    return novo_rating


def calcular_ratings_historicos(cursor, rodada_atual: int, ano: int) -> Dict[int, float]:
    """
    Calcula os ratings de todos os times considerando todas as partidas até a rodada atual
    
    Processa todas as partidas em ordem cronológica, atualizando os ratings progressivamente
    
    Args:
        cursor: Cursor do banco de dados
        rodada_atual: Rodada atual (calcula até rodada_atual - 1)
        ano: Ano da temporada
    
    Returns:
        Dicionário {clube_id: rating_atual}
    """
    # Buscar todas as partidas válidas até a rodada anterior em ordem cronológica
    cursor.execute('''
        SELECT 
            rodada_id,
            clube_casa_id,
            clube_visitante_id,
            placar_oficial_mandante,
            placar_oficial_visitante
        FROM acf_partidas
        WHERE valida = TRUE 
        AND rodada_id < %s
        AND temporada = %s
        AND placar_oficial_mandante IS NOT NULL  
        AND placar_oficial_visitante IS NOT NULL
        ORDER BY rodada_id, partida_id
    ''', (rodada_atual, ano))
    
    partidas = cursor.fetchall()
    
    # Inicializar ratings de todos os times
    ratings = {}
    
    # Primeiro, identificar todos os times
    cursor.execute('''
        SELECT DISTINCT id FROM acf_clubes
    ''')
    todos_clubes = cursor.fetchall()
    
    for (clube_id,) in todos_clubes:
        ratings[clube_id] = RATING_INICIAL
    
    # Processar partidas em ordem cronológica
    for rodada_id, casa_id, visitante_id, placar_casa, placar_visitante in partidas:
        # Garantir que os times existem no dicionário
        if casa_id not in ratings:
            ratings[casa_id] = RATING_INICIAL
        if visitante_id not in ratings:
            ratings[visitante_id] = RATING_INICIAL
        
        # Obter ratings atuais
        rating_casa = ratings[casa_id]
        rating_visitante = ratings[visitante_id]
        
        # Determinar resultado
        if placar_casa > placar_visitante:
            # Vitória da casa
            resultado_casa = 1.0
            resultado_visitante = 0.0
        elif placar_casa < placar_visitante:
            # Vitória do visitante
            resultado_casa = 0.0
            resultado_visitante = 1.0
        else:
            # Empate
            resultado_casa = 0.5
            resultado_visitante = 0.5
        
        # Atualizar ratings
        ratings[casa_id] = atualizar_rating(rating_casa, rating_visitante, resultado_casa)
        ratings[visitante_id] = atualizar_rating(rating_visitante, rating_casa, resultado_visitante)
    
    logger.info(f"Ratings calculados para {len(ratings)} times até rodada {rodada_atual - 1}")
    
    return ratings


def calcular_rating_recente(
    cursor,
    clube_id: int,
    rodada_atual: int,
    ano: int,
    ultimas_partidas: int,
    como_mandante: bool = True,
    ratings_historicos: Optional[Dict[int, float]] = None
) -> float:
    """
    Calcula o rating do time considerando apenas as últimas N partidas
    
    Para isso, busca as últimas N partidas e recalcula o rating processando apenas essas partidas,
    usando os ratings históricos dos adversários como referência
    
    Args:
        cursor: Cursor do banco
        clube_id: ID do clube
        rodada_atual: Rodada atual
        ano: Ano da temporada
        ultimas_partidas: Número de últimas partidas a considerar
        como_mandante: Se True, considera partidas como mandante; se False, como visitante
        ratings_historicos: Ratings históricos de todos os times (se None, será calculado)
    
    Returns:
        Rating recente do time
    """
    if ratings_historicos is None:
        ratings_historicos = calcular_ratings_historicos(cursor, rodada_atual, ano)
    
    # Buscar últimas N partidas
    if como_mandante:
        cursor.execute('''
            SELECT 
                clube_visitante_id,
                placar_oficial_mandante,
                placar_oficial_visitante,
                rodada_id
            FROM acf_partidas
            WHERE clube_casa_id = %s 
            AND valida = TRUE 
            AND rodada_id < %s
            AND temporada = %s
            AND placar_oficial_mandante IS NOT NULL
            ORDER BY rodada_id DESC
            LIMIT %s
        ''', (clube_id, rodada_atual, ano, ultimas_partidas))
    else:
        cursor.execute('''
            SELECT 
                clube_casa_id,
                placar_oficial_mandante,
                placar_oficial_visitante,
                rodada_id
            FROM acf_partidas
            WHERE clube_visitante_id = %s 
            AND valida = TRUE 
            AND rodada_id < %s
            AND temporada = %s
            AND placar_oficial_visitante IS NOT NULL
            ORDER BY rodada_id DESC
            LIMIT %s
        ''', (clube_id, rodada_atual, ano, ultimas_partidas))
    
    partidas_recentes = cursor.fetchall()
    
    if not partidas_recentes:
        # Se não há partidas, retornar rating histórico
        return ratings_historicos.get(clube_id, RATING_INICIAL)
    
    # Ordenar por rodada (mais antiga primeiro) para processar em ordem cronológica
    partidas_recentes = sorted(partidas_recentes, key=lambda x: x[3])
    
    # Calcular rating base: rating antes da primeira partida recente
    primeira_rodada = partidas_recentes[0][3]
    ratings_antes = calcular_ratings_historicos(cursor, primeira_rodada, ano)
    rating_atual = ratings_antes.get(clube_id, RATING_INICIAL)
    
    # Processar partidas recentes em ordem cronológica
    for partida in partidas_recentes:
        if como_mandante:
            adversario_id, placar_casa, placar_visitante, _ = partida
        else:
            adversario_id, placar_mandante, placar_visitante, _ = partida
            placar_casa = placar_visitante
            placar_visitante = placar_mandante
        
        # Obter rating do adversário no momento da partida
        # Usar rating histórico completo como aproximação (mais simples e eficiente)
        rating_adversario = ratings_historicos.get(adversario_id, RATING_INICIAL)
        
        # Determinar resultado
        if placar_casa > placar_visitante:
            resultado = 1.0
        elif placar_casa < placar_visitante:
            resultado = 0.0
        else:
            resultado = 0.5
        
        # Atualizar rating
        rating_atual = atualizar_rating(rating_atual, rating_adversario, resultado)
    
    return rating_atual


def calcular_diferenca_rating_peso(
    rating_casa: float,
    rating_visitante: float,
    max_peso: float = 5.0
) -> float:
    """
    Calcula o peso do jogo baseado na diferença de rating
    
    Escala a diferença de rating para um range de -max_peso a +max_peso
    Uma diferença de rating de ~200 pontos (muito grande) resulta em peso próximo a max_peso
    
    Args:
        rating_casa: Rating do time da casa
        rating_visitante: Rating do time visitante
        max_peso: Peso máximo (padrão 5.0, significando "impossível perder")
    
    Returns:
        Peso do jogo (escalado para range de -max_peso a +max_peso)
    """
    diferenca = rating_casa - rating_visitante
    
    # Normalizar a diferença: rating varia tipicamente entre 800-1200
    # Diferença máxima esperada: ~200 pontos (time muito forte vs muito fraco)
    # Queremos que diferença de ~150-200 pontos resulte em peso próximo a max_peso (5.0)
    
    # Usar função sigmóide suave (tanh) para mapear diferença para o range desejado
    # tanh(x) vai de -1 a 1, então precisamos ajustar a escala de entrada
    import math
    
    # Ajustar para aumentar a escala: usar divisor menor para que diferenças menores
    # resultem em pesos maiores, mas ainda calculados baseados na diferença real
    # Divisor 60: diferença de 120 pontos ≈ 2.0, tanh(2.0) ≈ 0.96 → peso ≈ 4.8
    # Diferença de 90 pontos ≈ 1.5, tanh(1.5) ≈ 0.9 → peso ≈ 4.5
    # Diferença de 60 pontos ≈ 1.0, tanh(1.0) ≈ 0.76 → peso ≈ 3.8
    diferenca_normalizada = diferenca / 60.0
    
    # Aplicar tanh e escalar para max_peso
    # tanh(2.0) ≈ 0.96, então 140 pontos ≈ 0.96 * 5 = 4.8
    # tanh(1.5) ≈ 0.9, então 105 pontos ≈ 0.9 * 5 = 4.5
    # tanh(1.0) ≈ 0.76, então 70 pontos ≈ 0.76 * 5 = 3.8
    peso = math.tanh(diferenca_normalizada) * max_peso
    
    return peso

