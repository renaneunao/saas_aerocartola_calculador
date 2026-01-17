"""
Módulo para calcular a tabela de classificação do campeonato
e fornecer funções auxiliares para ajustar estatísticas baseadas na força dos adversários
"""
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

def calcular_tabela_classificacao(cursor, rodada_atual: int, ano: int) -> Dict[int, Dict]:
    """
    Calcula a tabela de classificação até a rodada atual
    
    Retorna um dicionário: {clube_id: {
        'pontos': int,
        'vitorias': int,
        'empates': int,
        'derrotas': int,
        'gols_pro': int,
        'gols_contra': int,
        'saldo_gols': int,
        'aproveitamento': float,
        'posicao': int,  # 1-20
        'forca_normalizada': float  # 0.0-1.0 (1.0 = líder, 0.0 = lanterna)
    }}
    """
    # Buscar todas as partidas válidas até a rodada atual
    cursor.execute('''
        SELECT 
            clube_casa_id,
            clube_visitante_id,
            placar_oficial_mandante,
            placar_oficial_visitante
        FROM acf_partidas
        WHERE valida = TRUE 
        AND rodada_id <= %s
        AND temporada = %s
        AND placar_oficial_mandante IS NOT NULL 
        AND placar_oficial_visitante IS NOT NULL
        ORDER BY rodada_id
    ''', (rodada_atual, ano))
    
    partidas = cursor.fetchall()
    
    # Inicializar estatísticas de todos os times
    tabela = {}
    
    # Primeiro, identificar todos os times que já jogaram
    for casa_id, visitante_id, placar_casa, placar_visitante in partidas:
        if casa_id not in tabela:
            tabela[casa_id] = {
                'pontos': 0,
                'vitorias': 0,
                'empates': 0,
                'derrotas': 0,
                'gols_pro': 0,
                'gols_contra': 0,
                'saldo_gols': 0,
                'jogos': 0
            }
        if visitante_id not in tabela:
            tabela[visitante_id] = {
                'pontos': 0,
                'vitorias': 0,
                'empates': 0,
                'derrotas': 0,
                'gols_pro': 0,
                'gols_contra': 0,
                'saldo_gols': 0,
                'jogos': 0
            }
    
    # Processar partidas
    for casa_id, visitante_id, placar_casa, placar_visitante in partidas:
        # Time da casa
        tabela[casa_id]['jogos'] += 1
        tabela[casa_id]['gols_pro'] += placar_casa
        tabela[casa_id]['gols_contra'] += placar_visitante
        
        # Time visitante
        tabela[visitante_id]['jogos'] += 1
        tabela[visitante_id]['gols_pro'] += placar_visitante
        tabela[visitante_id]['gols_contra'] += placar_casa
        
        # Resultado
        if placar_casa > placar_visitante:
            # Vitória da casa
            tabela[casa_id]['pontos'] += 3
            tabela[casa_id]['vitorias'] += 1
            tabela[visitante_id]['derrotas'] += 1
        elif placar_casa < placar_visitante:
            # Vitória do visitante
            tabela[visitante_id]['pontos'] += 3
            tabela[visitante_id]['vitorias'] += 1
            tabela[casa_id]['derrotas'] += 1
        else:
            # Empate
            tabela[casa_id]['pontos'] += 1
            tabela[casa_id]['empates'] += 1
            tabela[visitante_id]['pontos'] += 1
            tabela[visitante_id]['empates'] += 1
    
    # Calcular saldo de gols e aproveitamento
    for clube_id in tabela:
        stats = tabela[clube_id]
        stats['saldo_gols'] = stats['gols_pro'] - stats['gols_contra']
        pontos_possiveis = stats['jogos'] * 3
        stats['aproveitamento'] = stats['pontos'] / pontos_possiveis if pontos_possiveis > 0 else 0.0
    
    # Ordenar por critérios de classificação (pontos, vitórias, saldo, gols pró)
    times_ordenados = sorted(
        tabela.items(),
        key=lambda x: (
            -x[1]['pontos'],  # Mais pontos primeiro
            -x[1]['vitorias'],  # Mais vitórias
            -x[1]['saldo_gols'],  # Melhor saldo
            -x[1]['gols_pro']  # Mais gols pró
        )
    )
    
    # Adicionar posição e força normalizada
    total_times = len(times_ordenados)
    for posicao, (clube_id, stats) in enumerate(times_ordenados, 1):
        stats['posicao'] = posicao
        # Força normalizada: 1.0 para o líder, 0.0 para o lanterna
        # Usar uma escala que considera posição e aproveitamento
        if total_times > 1:
            # Normalização baseada em posição (invertida)
            forca_posicao = 1.0 - ((posicao - 1) / (total_times - 1))
            # Combinar com aproveitamento (peso 70% posição, 30% aproveitamento)
            stats['forca_normalizada'] = (0.7 * forca_posicao) + (0.3 * stats['aproveitamento'])
        else:
            stats['forca_normalizada'] = 0.5
    
    # Converter para dicionário indexado por clube_id
    resultado = {clube_id: stats for clube_id, stats in times_ordenados}
    
    logger.debug(f"Tabela calculada: {len(resultado)} times até rodada {rodada_atual}")
    
    return resultado


def calcular_forca_media_adversarios(
    cursor, 
    clube_id: int, 
    rodada_atual: int, 
    ano: int,
    ultimas_partidas: int,
    como_mandante: bool = True,
    tabela_classificacao: Optional[Dict[int, Dict]] = None
) -> float:
    """
    Calcula a força média dos adversários enfrentados pelo time nas últimas N partidas
    
    Args:
        cursor: Cursor do banco
        clube_id: ID do clube
        rodada_atual: Rodada atual
        ultimas_partidas: Número de últimas partidas a considerar
        como_mandante: Se True, considera partidas como mandante; se False, como visitante
        tabela_classificacao: Tabela de classificação (se None, será calculada)
    
    Returns:
        Força média normalizada dos adversários (0.0-1.0)
    """
    if tabela_classificacao is None:
        tabela_classificacao = calcular_tabela_classificacao(cursor, rodada_atual, ano)
    
    # Buscar últimas partidas
    if como_mandante:
        cursor.execute('''
            SELECT clube_visitante_id
            FROM acf_partidas
            WHERE clube_casa_id = %s 
            AND valida = TRUE 
            AND rodada_id <= %s
            AND temporada = %s
            AND placar_oficial_mandante IS NOT NULL
            ORDER BY rodada_id DESC
            LIMIT %s
        ''', (clube_id, rodada_atual - 1, ano, ultimas_partidas))
    else:
        cursor.execute('''
            SELECT clube_casa_id
            FROM acf_partidas
            WHERE clube_visitante_id = %s 
            AND valida = TRUE 
            AND rodada_id <= %s
            AND temporada = %s
            AND placar_oficial_visitante IS NOT NULL
            ORDER BY rodada_id DESC
            LIMIT %s
        ''', (clube_id, rodada_atual - 1, ano, ultimas_partidas))
    
    adversarios = cursor.fetchall()
    
    if not adversarios:
        return 0.5  # Força média neutra se não houver partidas
    
    # Calcular força média dos adversários
    forcas = []
    for (adversario_id,) in adversarios:
        if adversario_id in tabela_classificacao:
            forcas.append(tabela_classificacao[adversario_id]['forca_normalizada'])
    
    if not forcas:
        return 0.5
    
    return sum(forcas) / len(forcas)


def ajustar_aproveitamento_por_forca_adversarios(
    aproveitamento: float,
    forca_media_adversarios: float,
    fator_ajuste: float = 0.3
) -> float:
    """
    Ajusta o aproveitamento considerando a força média dos adversários
    
    Se enfrentou adversários fracos (forca_media < 0.5), reduz o aproveitamento
    Se enfrentou adversários fortes (forca_media > 0.5), aumenta o aproveitamento
    
    Args:
        aproveitamento: Aproveitamento original (0.0-1.0)
        forca_media_adversarios: Força média dos adversários (0.0-1.0)
        fator_ajuste: Intensidade do ajuste (0.0-1.0), padrão 0.3
    
    Returns:
        Aproveitamento ajustado (limitado entre 0.0 e 1.0)
    """
    # Diferença da força média em relação ao neutro (0.5)
    diferenca = forca_media_adversarios - 0.5
    
    # Ajuste: se enfrentou times fortes (diferenca > 0), aumenta aproveitamento
    # Se enfrentou times fracos (diferenca < 0), diminui aproveitamento
    ajuste = diferenca * fator_ajuste
    
    aproveitamento_ajustado = aproveitamento + ajuste
    
    # Limitar entre 0.0 e 1.0
    return max(0.0, min(1.0, aproveitamento_ajustado))


def ajustar_saldo_gols_por_forca_adversarios(
    saldo_gols: float,
    forca_media_adversarios: float,
    fator_ajuste: float = 0.2
) -> float:
    """
    Ajusta o saldo de gols considerando a força média dos adversários
    
    Args:
        saldo_gols: Saldo de gols original
        forca_media_adversarios: Força média dos adversários (0.0-1.0)
        fator_ajuste: Intensidade do ajuste, padrão 0.2
    
    Returns:
        Saldo de gols ajustado
    """
    # Se enfrentou times fortes, saldo positivo vale mais
    # Se enfrentou times fracos, saldo positivo vale menos
    diferenca = forca_media_adversarios - 0.5
    
    # Ajuste proporcional ao saldo
    ajuste = saldo_gols * diferenca * fator_ajuste
    
    return saldo_gols + ajuste


def calcular_peso_resultado_por_forca_adversario(
    resultado: str,  # 'vitoria', 'empate', 'derrota'
    forca_adversario: float,
    fator_ajuste: float = 0.4
) -> float:
    """
    Calcula um peso para o resultado baseado na força do adversário
    
    Vitória sobre time forte vale mais que vitória sobre time fraco
    Derrota para time forte vale menos que derrota para time fraco
    
    Args:
        resultado: 'vitoria', 'empate', ou 'derrota'
        forca_adversario: Força do adversário (0.0-1.0)
        fator_ajuste: Intensidade do ajuste, padrão 0.4
    
    Returns:
        Peso do resultado (0.5-1.5 aproximadamente)
    """
    if resultado == 'vitoria':
        # Vitória sobre time forte (forca alta) = peso maior
        # Vitória sobre time fraco (forca baixa) = peso menor
        peso_base = 1.0
        ajuste = (forca_adversario - 0.5) * fator_ajuste
        return peso_base + ajuste
    
    elif resultado == 'empate':
        # Empate com time forte = peso maior
        # Empate com time fraco = peso menor
        peso_base = 1.0
        ajuste = (forca_adversario - 0.5) * fator_ajuste * 0.5  # Ajuste menor para empates
        return peso_base + ajuste
    
    else:  # derrota
        # Derrota para time forte = peso menor (menos penalizante)
        # Derrota para time fraco = peso maior (mais penalizante)
        peso_base = 1.0
        ajuste = (0.5 - forca_adversario) * fator_ajuste  # Invertido
        return peso_base + ajuste

