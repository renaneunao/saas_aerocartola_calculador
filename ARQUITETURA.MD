# Documentação de Arquitetura - Produto Cartola FC

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Análise da Proposta Original](#análise-da-proposta-original)
3. [Arquitetura Recomendada](#arquitetura-recomendada)
4. [Componentes do Sistema](#componentes-do-sistema)
5. [Fluxo de Dados](#fluxo-de-dados)
6. [Decisões de Design](#decisões-de-design)
7. [Melhorias Implementadas](#melhorias-implementadas)
8. [Plano de Implementação](#plano-de-implementação)
9. [Considerações Técnicas](#considerações-técnicas)

---

## 🎯 Visão Geral

### Objetivo
Transformar a aplicação atual de cálculo de escalação do Cartola FC em um produto SaaS multi-tenant, onde cada usuário pode:
- Escolher perfis personalizados de peso do jogo e peso do SG
- Configurar pesos específicos por posição
- Obter escalações personalizadas baseadas em suas preferências
- Gerenciar múltiplos times

### Problema Atual
- **Cálculos centralizados**: Todos os usuários usam os mesmos parâmetros (peso do jogo, pesos por posição)
- **Sem personalização**: Não há flexibilidade para diferentes estratégias
- **Escalação única**: Todos os times recebem escalações idênticas

---

## 🔍 Análise da Proposta Original

### ✅ Pontos Positivos
1. **Separação de responsabilidades**: Containers separados para cada função
2. **Múltiplos perfis**: 10 perfis de peso do jogo oferecem opções aos usuários
3. **Personalização de pesos**: Permitir edição local dos pesos por posição

### ✅ Análise da Abordagem Correta

#### **Por que calcular rankings no navegador faz sentido**

**Pesos por posição são muitos e variam muito:**
- **Goleiro**: 6 fatores (FATOR_MEDIA, FATOR_FF, FATOR_FD, FATOR_SG, FATOR_PESO_JOGO, FATOR_GOL_ADVERSARIO)
- **Zagueiro**: ~8 fatores
- **Lateral**: ~8 fatores  
- **Meia**: 9 fatores
- **Atacante**: 9 fatores (FATOR_MEDIA, FATOR_DS, FATOR_FF, FATOR_FS, FATOR_FD, FATOR_G, FATOR_A, FATOR_ESCALACAO, FATOR_PESO_JOGO)
- **Técnico**: ~6 fatores

**Combinatória impossível de pré-calcular:**
- Se cada fator pode ter 100 valores possíveis (0.1 a 10.0 com incrementos de 0.1)
- Para 9 fatores: 100^9 = 10^18 combinações possíveis
-Quando cada usuário personaliza, não há como pré-calcular tudo

**Por que funciona no navegador:**
- ✅ Cálculo de UMA posição por vez é leve (~100-200 atletas)
- ✅ Usuário calcula apenas quando precisa (on-demand)
- ✅ Não precisa pré-calcular combinações infinitas
- ✅ Resposta imediata na UI
- ✅ Dados necessários são pequenos (estatísticas dos atletas da posição + pesos do jogo/SG do perfil escolhido)

**O que deve ser calculado no backend (pesado):**
- ✅ Peso do jogo: Processa todas as partidas, todos os clubes → 10 perfis
- ✅ Peso do SG: Processa todas as partidas, todos os clubes → 10 perfis
- Esses são pesados e dependem apenas do parâmetro "últimas_partidas"
- Solução: Backend calcula e armazena no Redis/PostgreSQL

---

## 🏗️ Arquitetura Recomendada

### Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        CAMADA WEB (Frontend)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   React/     │  │  Seleção de  │  │   Edição de  │          │
│  │   Vue.js     │  │   Perfis     │  │    Pesos     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ REST API / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (Nginx/Traefik)                   │
│                    Rate Limiting, Auth, Load Balance             │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  API Service │    │ Calc Service │    │  Auth Service│
│  (FastAPI/   │    │  (Python)    │    │  (Node.js/   │
│   Flask)     │    │              │    │โม  Python)    │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Data Fetcher│    │  Calc Engine │    │   PostgreSQL │
│  (Python)    │    │  (Python)    │    │   Database   │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Componentes Principais

#### 1. **Data Fetcher Service** (Container 1)
**Responsabilidade**: Coletar dados da API do Cartola FC

**Funcionalidades:**
- Fetch periódico de dados da API Cartola (a cada 5 minutos)
- Atualização de: atletas, clubes, partidas, prováveis
- Armazenamento em PostgreSQL
- Gerenciamento de rate limits
- Retry logic para falhas de API

**Tecnologias:**
- Python (FastAPI/Flask)
- APScheduler ou Celery para agendamento
- PostgreSQL client (psycopg2)

**Dados armazenados:**
- `atletas` (dados brutos de todos os atletas)
- `clubes`
- `partidas`
- `provaveis_cartola`
- `rodadas`

---

#### 2. **Calculation Engine Service** (Container 2)
**Responsabilidade**: Calcular pesos do jogo e peso do SG para múltiplos perfis

**Funcionalidades:**
- Calcular peso do jogo para 10 perfis diferentes (variando `ultimas_partidas`)
- Calcular peso do SG para 10 perfis diferentes (variando `ultimas_partidas`, **INDEPENDENTE** de peso_jogo)
- Armazenar resultados pré-calculados
- Invalidar cache quando novos dados chegarem

**Tecnologias:**
- Python (mesma lógica atual, mas otimizada)
- PostgreSQL para armazenar resultados
- Redis para cache temporário

**Relação entre peso_jogo e peso_sg:**
- ✅ **São INDEPENDENTES**: Cada um calcula seus valores baseado apenas em `ultimas_partidas`
- ✅ **Cálculos necessários**: 10 (peso_jogo) + 10 (peso_sg) = **20 cálculos**
- ✅ **Combinações possíveis**: 10 × 10 = **100 combinações** para o usuário escolher
- ✅ **Armazenamento**: Calcular 20 perfis, usuário combina na seleção

**Estrutura de dados:**
```sql
CREATE TABLE peso_jogo_perfis (
    id SERIAL PRIMARY KEY,
    perfil_id INTEGER NOT NULL,  -- 1 a 10
    rodada_atual INTEGER NOT NULL,
    clube_id INTEGER NOT NULL,
    peso_jogo REAL NOT NULL,
    ultimas_partidas INTEGER NOT NULL,  -- parâmetro do perfil
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(perfil_id, rodada_atual, clube_id)
);

CREATE TABLE peso_sg_perfis (
    id SERIAL PRIMARY KEY,
    perfil_id INTEGER NOT NULL,  -- 1 a 10
    rodada_atual INTEGER NOT NULL,
    clube_id INTEGER NOT NULL,
    peso_sg REAL NOT NULL,
    ultimas_partidas INTEGER NOT NULL,  -- parâmetro do perfil (ex: 3, 5, 7, 10...)
    -- NOTA: Não há referência a peso_jogo porque são independentes
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(perfil_id, rodada_atual, clube_id)
);
```

**Perfis sugeridos:**
| Perfil | Últimas Partidas | Descrição |
|--------|------------------|-----------|
| 1 | 3 | Muito recente (form recente) |
| 2 | 5 | Recente (padrão atual) |
| 3 | 7 | Médio |
| 4 | 10 | Mais histórico |
| 5 | 3 com peso crescente | Recente com peso crescente |
| 6 | 5 com peso decrescente | Histórico com peso crescente |
| 7 | 8 | Longo prazo |
| 8 | 10 com média móvel | Longo com suavização |
| 9 | 5 (apenas casa) | Foco em jogos em casa |
| 10 | 5 (apenas fora) | Foco em jogos fora |

---

#### 3. **API Service** (Container 3 - Backend Principal)
**Responsabilidade**: Servir dados necessários para cálculos no frontend

**Funcionalidades:**
- Autenticação e autorização
- Gerenciamento de usuários e times
- Fornecer dados brutos de atletas (para cálculo no frontend)
- Fornecer pesos do jogo e peso do SG (dos perfis pré-calculados)
- Armazenar rankings calculados pelos usuários (JSON)
- Cálculo de escalação personalizada (no backend, usando ranking já calculado)
- Gerenciamento de perfis de usuário

**Tecnologias:**
- FastAPI (Python) - alta performance, async
- JWT para autenticação
- SQLAlchemy para ORM
- Redis para cache de dados (pesos, atletas)

**Endpoints principais:**
```
POST   /api/auth/login
POST   /api/auth/register
GET    /api/user/profile
PUT    /api/user/profile

GET    /api/atletas?posicao_id={id}&rodada={r}  # Dados dos atletas (filtrado por posição)
GET    /api/perfis/peso-jogo/{perfil_id}       # Peso do jogo de todos os clubes (perfil específico)
GET    /api/perfis/peso-sg/{perfil_id}         # Peso do SG de todos os clubes (perfil específico)
GET    /api/perfis/peso-jogo                   # Lista perfis disponíveis

POST   /api/rankings/salvar                    # Salvar ranking calculado pelo frontend (JSON)
GET    /api/rankings/{ranking_id}              # Obter ranking salvo pelo usuário

POST   /api/escalacao/calcular                 # Calcular escalação (usa ranking já calculado)
POST   /api/escalacao/enviar                   # Enviar escalação para Cartola

GET    /api/times                              # Lista times do usuário
POST   /api/times                              # Criar novo time
PUT    /api/times/{time_id}                    # Atualizar time
DELETE /api/times/{time_id}                    # Deletar time
```

---

#### 4. **Frontend** (Container 4 - Web Application)
**Responsabilidade**: Interface do usuário

**Funcionalidades:**
- Seleção de perfis de peso do jogo e peso do SG
- Edição de pesos por posição (UI intuitiva)
- Visualização de rankings em tempo real
- Cálculo e preview de escalações
- Gerenciamento de múltiplos times
- Envio de escalações para Cartola FC

**Tecnologias:**
- React ou Vue.js
- TypeScript
- Zustand ou Redux para estado global
- React Query ou SWR para cache de dados
- WebSocket para atualizações em tempo real

**Fluxo de uso:**
1. Usuário faz login
2. Seleciona/cria um time
3. Escolhe perfil de peso do jogo (1-10)
4. Escolhe perfil de peso do SG (1-10)
5. Para cada posição:
   - Edita pesos (opcional)
   - Clica "Calcular" → Frontend calcula ranking imediatamente
   - Opcionalmente salva o ranking
6. Clica em "Calcular Escalação"
7. Backend usa rankings já calculados (ou calcula se necessário)
8. Backend calcula escalação
9. Frontend mostra preview
10. Usuário confirma e envia para Cartola

---

## 🔄 Fluxo de Dados

### Fluxo Completo

```
1. DATA FETCHER (a cada 5 min)
   └─> Busca API Cartola
   └─> Salva em PostgreSQL (atletas, partidas, etc.)

2. CALCULATION ENGINE (após novo fetch)
   └─> Detecta novos dados
   └─> Calcula peso_jogo para 10 perfis (independente)
   └─> Calcula peso_sg para 10 perfis (independente)
   └─> Total: 20 cálculos, gerando 100 combinações possíveis
   └─> Salva em PostgreSQL (peso_jogo_perfis e peso_sg_perfis)

3. USUÁRIO NO FRONTEND
   └─> Seleciona perfil peso_jogo (ex: perfil 3)
   └─> Seleciona perfil peso_sg (ex: perfil 2)
   └─> Edita pesos por posição (ex: goleiro)
   └─> Clica "Calcular Ranking" para uma posição

4. FRONTEND (JavaScript)
   └─> GET /api/atletas?posicao_id=1 (goleiros) + rodada_atual
   └─> GET /api/perfis/peso-jogo/3 (pesos do jogo do perfil 3)
   └─> GET /api/perfis/peso-sg/2 (pesos do SG do perfil 2)
   └─> Calcula ranking da posição no navegador usando lógica JavaScript
   └─> Exibe resultado imediatamente
   └─> Opcional: POST /api/rankings/salvar (salva ranking calculado em JSON)

5. USUÁRIO CALCULA OUTRAS POSIÇÕES
   └─> Repete processo para outras posições (zagueiro, lateral, etc.)
   └─> Frontend pode calcular todas as posições ou apenas as necessárias

6. USUÁRIO PEDE ESCALAÇÃO
   └─> POST /api/escalacao/calcular
   └─> Backend usa rankings já calculados (salvos pelo usuário) ou calcula no momento
   └─> Busca patrimônio do time do usuário
   └─> Executa algoritmo de escalação
   └─> Retorna escalação proposta

7. USUÁRIO CONFIRMA
   └─> POST /api/escalacao/enviar
   └─> API Service envia para Cartola FC
   └─> Retorna sucesso/erro
```

---

## 💡 Decisões de Design

### 1. **Cálculo de Rankings: Frontend vs Backend**

**Decisão**: **Cálculo de Rankings no Frontend (uma posição por vez)**

**Justificativa:**
- ✅ **Combinatória impossível**: Com 6-9 fatores por posição e personalização infinita, pré-calcular todas combinações é inviável
- ✅ **Leve por posição**: Calcular ranking de 100-200 atletas de uma posição é rápido no navegador (< 1 segundo)
- ✅ **Resposta imediata**: Usuário vê resultado instantaneamente ao mudar pesos
- ✅ **Flexibilidade total**: Usuário pode experimentar diferentes pesos sem limitar servidor
- ✅ **Dados pequenos**: Apenas estatísticas dos atletas da posição + pesos do jogo/SG dos perfis escolhidos (~100KB)

**O que fica no Backend (pesado):**
- ✅ Peso do jogo: Calcula para 10 perfis, armazena em Redis/PostgreSQL
- ✅ Peso do SG: Calcula para 10 perfis, armazena em Redis/PostgreSQL
- ✅ Escalação: Algoritmo complexo com combinações (fica no backend)
- ✅ Persistência: Salva rankings calculados pelo usuário (JSON no banco)

**Arquitetura Híbrida:**
- Backend: Calcula e cacheia peso_jogo e peso_sg (10 perfis cada)
- Frontend: Calcula rankings personalizados on-demand (uma posição por vez)
- Backend: Usa rankings calculados pelo frontend para fazer escalação

### 2. **Cache de Dados**

**Estratégia**: Cache de dados brutos e pesos pré-calculados

**Cache no Redis:**
1. **Peso do Jogo** (TTL: até nova rodada)
   - Chave: `peso_jogo:perfil_{id}:rodada_{r}:clube_{c}`
   - Valor: peso_jogo do clube
   - Calculado pelo Calculation Engine

2. **Peso do SG** (TTL: até nova rodada)
   - Chave: `peso_sg:perfil_{id}:rodada_{r}:clube_{c}`
   - Valor: peso_sg do clube
   - Calculado pelo Calculation Engine

3. **Dados de Atletas** (TTL: 5 minutos)
   - Chave: `atletas:posicao_{id}:rodada_{r}`
   - Valor: JSON com estatísticas dos atletas da posição
   - Invalidado quando novos dados chegarem

**Cache no PostgreSQL:**
- Rankings salvos pelos usuários (JSONB)
- Persistente até usuário deletar ou recalcular

**Invalidação:**
- Peso do jogo/SG: Quando nova rodada começar
- Dados de atletas: A cada 5 minutos ou quando novos dados chegarem

### 3. **Personalização de Pesos**

**Estrutura de dados:**
```json
{
  "perfil_peso_jogo": 3,
  "perfil_peso_sg": 2,
  "pesos_posicao": {
    "goleiro": {
      "FATOR_MEDIA": 1.0,
      "FATOR_FF": 0.7,
      "FATOR_FD": 0.9,
      "FATOR_PESO_JOGO": 9.5
    },
    "zagueiro": {
      "FATOR_MEDIA": 2.5,
      "FATOR_DS": 3.6,
      ...
    },
    ...
  }
}
```

**Armazenamento:**
- **Configurações de pesos**: No banco (`user_configurations` table)
- **Rascunhos**: No frontend (localStorage) para edição temporária
- **Rankings calculados**: No banco (`user_rankings` table, JSONB) quando usuário salvar
- **Versionamento**: Permitir salvar múltiplas configurações ("Estratégia A", "Estratégia B", etc.)

**Estrutura de armazenamento de ranking:**
```sql
CREATE TABLE user_rankings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    configuration_id INTEGER REFERENCES user_configurations(id),
    posicao_id INTEGER NOT NULL,
    rodada_atual INTEGER NOT NULL,
    ranking_data JSONB NOT NULL,  -- [{atleta_id, apelido, pontuacao_total, ...}, ...]
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4. **Escalabilidade**

**Desafios:**
- 1000+ usuários simultâneos solicitando dados da API
- Escalação ainda é pesada (combinações complexas)

**Soluções:**
1. **Rate Limiting** (para API)
   - Máximo 100 requisições/minuto por usuário
   - Prevenir abuso
   - Usar Redis para contadores

2. **Cache de Dados**
   - Peso do jogo/SG: Cache no Redis (pré-calculados)
   - Dados de atletas: Cache no Redis (5 minutos)
   - Reduz carga no banco

3. **Queue System para Escalação**
   - Escalação pode ser pesada (combinações)
   - Usuários premium: cálculo imediato
   - Usuários gratuitos: fila de baixa prioridade (opcional)

4. **Cálculo no Frontend**
   - Rankings calculados no navegador distribuem a carga
   - Cada usuário usa seu próprio CPU
   - Servidor apenas fornece dados, não processa

---

## 🚀 Melhorias Implementadas (vs Proposta Original)

### 1. **Cálculo Híbrido** ✅
- **Proposta original**: Calcular rankings no navegador
- **Nossa solução**: Rankings no frontend (on-demand), peso_jogo/SG no backend (cache)
- **Benefício**: Flexibilidade total + performance otimizada

### 2. **Sistema de Cache para Pesos** ✅
- **Proposta original**: Não mencionado
- **Nossa solução**: Redis cache para peso_jogo e peso_sg (10 perfis cada)
- **Benefício**: Frontend busca apenas os dados necessários, resposta rápida

### 3. **API RESTful** ✅
- **Proposta original**: Frontend direto no banco (implicito)
- **Nossa solução**: API REST bem definida
- **Benefício**: Separação de responsabilidades, segurança

### 4. **Armazenamento de Rankings Calculados** ✅
- **Proposta original**: Não mencionado
- **Nossa solução**: Salvar rankings calculados no frontend como JSON no banco
- **Benefício**: Usuário pode reutilizar rankings salvos, histórico de estratégias

### 5. **Versionamento de Configurações** ✅
- **Proposta original**: Edição local apenas
- **Nossa solução**: Salvar múltiplas configurações
- **Benefício**: Usuário pode testar diferentes estratégias

### 6. **WebSocket para Updates** ✅
- **Proposta original**: Não mencionado
- **Nossa solução**: WebSocket para notificações em tempo real
- **Benefício**: UX melhor, dados sempre atualizados

### 7. **Preview Interativo** ✅
- **Proposta original**: Apenas cálculo final
- **Nossa solução**: Preview com ajustes em tempo real
- **Benefício**: Usuário pode experimentar antes de calcular

---

## 📋 Plano de Implementação

### Fase 1: Fundação (Semanas 1-2)
- [ ] Configurar infraestrutura (Docker, PostgreSQL, Redis)
- [ ] Implementar Data Fetcher Service
- [ ] Migrar código atual para estrutura de containers
- [ ] Criar schema do banco para perfis

### Fase 2: Calculation Engine (Semanas 3-4)
- [ ] Implementar cálculo de 10 perfis de peso_jogo
- [ ] Implementar cálculo de 10 perfis de peso_sg
- [ ] Otimizar cálculos para batch processing
- [ ] Sistema de invalidação de cache

### Fase 3: API Service (Semanas 5-7)
- [ ] Implementar autenticação (JWT)
- [ ] Criar endpoints de rankings personalizados
- [ ] Implementar sistema de cache
- [ ] Endpoints de escalação personalizada
- [ ] Integração com Cartola FC API

### Fase 4: Frontend (Semanas 8-10)
- [ ] Setup React/Vue.js
- [ ] Páginas de login/registro
- [ ] Dashboard do usuário
- [ ] Seleção de perfis
- [ ] Editor de pesos por posição
- [ ] Visualização de rankings
- [ ] Preview e envio de escalação

### Fase 5: Otimização (Semanas 11-12)
- [ ] Implementar queue system
- [ ] Otimizar queries de banco
- [ ] Testes de carga
- [ ] Monitoramento e logging
- [ ] Documentação de API

### Fase 6: Deploy e Produção (Semanas 13-14)
- [ ] Configurar CI/CD
- [ ] Deploy em produção (AWS/GCP/Azure)
- [ ] Configurar monitoramento (Sentry, DataDog)
- [ ] Testes end-to-end
- [ ] Treinamento de usuários beta

---

## 🔧 Considerações Técnicas

### Banco de Dados

**Schema adicional necessário:**

```sql
-- Tabela de usuários
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de configurações de usuário
CREATE TABLE user_configurations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(255) NOT NULL,  -- "Estratégia Conservadora", etc.
    perfil_peso_jogo INTEGER NOT NULL,
    perfil_peso_sg INTEGER NOT NULL,
    pesos_posicao JSONB NOT NULL,  -- JSON com pesos por posição
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de times do usuário
CREATE TABLE user_teams (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    nome VARCHAR(255) NOT NULL,
    access_token VARCHAR(500) NOT NULL,  -- criptografado
    configuration_id INTEGER REFERENCES user_configurations(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de rankings calculados pelos usuários
CREATE TABLE user_rankings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    configuration_id INTEGER REFERENCES user_configurations(id),
    posicao_id INTEGER NOT NULL,  -- 1=goleiro, 2=lateral, 3=zagueiro, 4=meia, 5=atacante, 6=técnico
    rodada_atual INTEGER NOT NULL,
    ranking_data JSONB NOT NULL,  -- [{atleta_id, apelido, clube_id, pontuacao_total, ...}, ...]
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_rankings ON user_rankings(user_id, configuration_id, posicao_id, rodada_atual)
);

-- Índices para performance
CREATE INDEX idx_peso_jogo_perfis ON peso_jogo_perfis(perfil_id, rodada_atual, clube_id);
CREATE INDEX idx_peso_sg_perfis ON peso_sg_perfis(perfil_id, rodada_atual, clube_id);
CREATE INDEX idx_user_configurations ON user_configurations(user_id);
```

### Segurança

**Medidas necessárias:**
1. **Criptografia de tokens**
   - Armazenar `access_token` do Cartola criptografado
   - Usar AES-256-GCM

2. **Rate Limiting**
   - Por usuário: 10 cálculos/minuto
   - Por IP: 100 requisições/minuto
   - Usar Redis para contadores

3. **Autenticação**
   - JWT com refresh tokens
   - Expiração de 15 minutos (access), 7 dias (refresh)

4. **Validação de dados**
   - Validar todos os inputs
   - Sanitizar queries SQL (usar ORM/parametrização)

5. **HTTPS obrigatório**
   - SSL/TLS em todas as conexões
   - HSTS headers

### Performance

**Otimizações:**
1. **Connection Pooling**
   - PostgreSQL: 20 conexões por serviço
   - Redis: pool de 10 conexões

2. **Query Optimization**
   - Índices em todas as foreign keys
   - Índices em colunas de busca frequente
   - Usar EXPLAIN ANALYZE regularmente

3. **Caching Strategy**
   - Peso do jogo/SG: Até nova rodada (pré-calculados)
   - Dados de atletas: 5 minutos (Redis)
   - Rankings: Salvos pelo usuário (PostgreSQL, JSONB)

4. **Async Processing**
   - Cálculos pesados em background
   - WebSocket para notificações

### Monitoramento

**Métricas importantes:**
- Latência de API (p50, p95, p99)
- Taxa de erro
- Uso de CPU/memória por container
- Queries lentas do banco
- Cache hit rate
- Número de cálculos por hora

**Ferramentas sugeridas:**
- **Logging**: ELK Stack ou Loki
- **Métricas**: Prometheus + Grafana
- **APM**: Sentry ou DataDog
- **Uptime**: Pingdom ou UptimeRobot

---

## 📊 Estimativas de Recursos

### Infraestrutura Mínima (MVP)
- **PostgreSQL**: 2 vCPU, 4GB RAM, 50GB SSD
- **Redis**: 1 vCPU, 2GB RAM
- **API Service**: 2 vCPU, 4GB RAM (2 instâncias)
- **Calc Engine**: 2 vCPU, 4GB RAM
- **Data Fetcher**: 1 vCPU, 2GB RAM
- **Frontend**: CDN ou 1 vCPU, 2GB RAM

**Total estimado**: ~$150-200/mês (AWS/GCP)

### Escala (1000 usuários ativos)
- **PostgreSQL**: 4 vCPU, 16GB RAM, 200GB SSD (read replicas)
- **Redis**: Cluster 3 nodes, 8GB RAM cada
- **API Service**: 4 vCPU, 8GB RAM (4-6 instâncias, auto-scaling)
- **Calc Engine**: 4 vCPU, 8GB RAM (2 instâncias)
- **Data Fetcher**: 2 vCPU, 4GB RAM

**Total estimado**: ~$500-800/mês

---

## 🎯 Próximos Passos

1. **Validar arquitetura** com equipe/stakeholders
2. **Criar POC** (Proof of Concept) com 1 perfil funcionando
3. **Testar performance** com dados reais
4. **Refinar** baseado em feedback
5. **Implementar** seguindo fadamente o plano acima

---

## 📚 Referências e Notas

- **Stack atual**: Python, PostgreSQL, Flask/FastAPI
- **API Cartola**: https://api.cartolafc.globo.com
- **Rate Limit Cartola**: ~10 req/segundo (estimado)

---

**Versão**: 1.0  
**Data**: 2024  
**Autor**: Documentação técnica da arquitetura

