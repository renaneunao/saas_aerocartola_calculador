# Calculador de Pesos do Jogo e SG - Cartola FC

Este é o Container 2 do sistema SaaS Cartola-Aero, responsável por calcular e armazenar os perfis de peso do jogo e peso do SG.

## Funcionalidades

- Calcula **10 perfis diferentes** de peso do jogo (5 brandos + 5 agressivos)
- Calcula **10 perfis diferentes** de peso do SG (5 brandos + 5 agressivos)
- Executa automaticamente a cada **15 minutos** (após término de cada ciclo)
- Armazena resultados em tabelas PostgreSQL (`peso_jogo_perfis` e `peso_sg_perfis`)
- Total: **20 cálculos** gerando **100 combinações possíveis** para o usuário escolher

## Perfis Disponíveis

### Perfis de Peso do Jogo:

**Brandos (Raiz Quarta - Menos Agressivos):**
1. Perfil 1: Últimos 2 jogos (Brando)
2. Perfil 2: Últimos 4 jogos (Brando)
3. Perfil 3: Últimos 7 jogos (Brando)
4. Perfil 4: Últimos 10 jogos (Brando)
5. Perfil 5: Últimos 12 jogos (Brando)

**Agressivos (Raiz Cúbica - Mais Agressivos):**
6. Perfil 6: Últimos 2 jogos (Agressivo)
7. Perfil 7: Últimos 4 jogos (Agressivo)
8. Perfil 8: Últimos 7 jogos (Agressivo)
9. Perfil 9: Últimos 10 jogos (Agressivo)
10. Perfil 10: Últimos 12 jogos (Agressivo)

### Perfis de Peso do SG:

**Brandos (Pesos Equilibrados):**
1. Perfil 1: Últimos 2 jogos (Brando)
2. Perfil 2: Últimos 4 jogos (Brando)
3. Perfil 3: Últimos 7 jogos (Brando)
4. Perfil 4: Últimos 10 jogos (Brando)
5. Perfil 5: Últimos 12 jogos (Brando)

**Agressivos (Mais Peso em Clean Sheets e Defesa):**
6. Perfil 6: Últimos 2 jogos (Agressivo)
7. Perfil 7: Últimos 4 jogos (Agressivo)
8. Perfil 8: Últimos 7 jogos (Agressivo)
9. Perfil 9: Últimos 10 jogos (Agressivo)
10. Perfil 10: Últimos 12 jogos (Agressivo)

## Estrutura do Projeto

```
.
├── main.py                  # Arquivo principal com agendador
├── config.py                # Configurações e definição de perfis
├── database.py              # Conexão com PostgreSQL
├── api_cartola.py           # API do Cartola FC
├── calculo_peso_jogo.py     # Lógica de cálculo de peso do jogo
├── calculo_peso_sg.py       # Lógica de cálculo de peso do SG
├── requirements.txt         # Dependências Python
├── Dockerfile              # Container Docker
├── docker-compose.yml      # Orquestração de containers
├── .env.example            # Exemplo de variáveis de ambiente
└── README.md               # Este arquivo
```

## Configuração

### 1. Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env` e configure:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```env
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=senha_segura_aqui
POSTGRES_DB=cartola_manager
CALCULATION_INTERVAL_MINUTES=15
```

### 2. Banco de Dados

O serviço criará automaticamente as tabelas necessárias na primeira execução:

- `peso_jogo_perfis`: Armazena os pesos do jogo para cada perfil, rodada e clube
- `peso_sg_perfis`: Armazena os pesos do SG para cada perfil, rodada e clube

## Execução

### Usando Docker Compose (Recomendado)

```bash
docker-compose up -d
```

### Executar localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
export POSTGRES_HOST=localhost
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=sua_senha
export POSTGRES_DB=cartola_manager

# Executar
python main.py
```

## Logs

Os logs são exibidos no console e mostram:
- Rodada atual sendo processada
- Progresso de cada perfil
- Erros e avisos
- Tempo de execução

Para visualizar logs no Docker:

```bash
docker-compose logs -f calculador
```

## Monitoramento

O serviço executa continuamente e:
- Busca a rodada atual da API do Cartola FC
- Calcula todos os 10 perfis de peso do jogo
- Calcula todos os 10 perfis de peso do SG
- Armazena os resultados no PostgreSQL
- Aguarda 15 minutos após o término de cada ciclo antes de iniciar o próximo
- Repete o processo

## Estrutura das Tabelas

### peso_jogo_perfis

```sql
CREATE TABLE peso_jogo_perfis (
    id SERIAL PRIMARY KEY,
    perfil_id INTEGER NOT NULL,
    rodada_atual INTEGER NOT NULL,
    clube_id INTEGER NOT NULL,
    peso_jogo REAL NOT NULL,
    ultimas_partidas INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(perfil_id, rodada_atual, clube_id)
);
```

### peso_sg_perfis

```sql
CREATE TABLE peso_sg_perfis (
    id SERIAL PRIMARY KEY,
    perfil_id INTEGER NOT NULL,
    rodada_atual INTEGER NOT NULL,
    clube_id INTEGER NOT NULL,
    peso_sg REAL NOT NULL,
    ultimas_partidas INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(perfil_id, rodada_atual, clube_id)
);
```

## Notas Importantes

1. **Dependência do Container 1**: Este serviço depende de dados coletados pelo Container 1 (Data Fetcher), que deve estar populando as tabelas `partidas`, `clubes`, `atletas`, etc.

2. **Independência dos Cálculos**: Os cálculos de peso do jogo e peso do SG são **independentes**. Cada um calcula seus valores baseado apenas em `ultimas_partidas` e a estratégia do perfil.

3. **Combinações**: Com 10 perfis de peso do jogo e 10 perfis de peso do SG, temos **100 combinações possíveis** (10 × 10) que o usuário pode escolher no frontend.

4. **Performance**: O serviço otimiza os cálculos em batch e usa índices no banco de dados para rápido acesso.

## Troubleshooting

### Erro de conexão com banco

Verifique se:
- O PostgreSQL está rodando
- As credenciais no `.env` estão corretas
- A rede Docker está configurada corretamente (se usando Docker)

### Nenhuma partida encontrada

Isso pode ocorrer se:
- A rodada ainda não começou
- O Container 1 não coletou os dados ainda
- Há um problema na API do Cartola FC

### Erros de cálculo

Verifique os logs para detalhes. Erros comuns:
- Partidas sem placares válidos (normal no início da rodada)
- Falta de dados históricos para alguns clubes

## Desenvolvimento

Para desenvolvimento local:

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Executar em modo debug
python main.py
```

## Licença

Este projeto faz parte do sistema SaaS Cartola-Aero.

