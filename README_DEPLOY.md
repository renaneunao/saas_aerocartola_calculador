# Deploy - Calculador de Pesos do Jogo e SG

## Pré-requisitos

1. **Secrets do GitHub Actions**:
   - `DOCKERHUB_USERNAME`: Nome de usuário do Docker Hub
   - `DOCKERHUB_ACCESS_TOKEN`: Token de acesso do Docker Hub

2. **Variáveis de Ambiente (.env)**:
   ```
   POSTGRES_HOST=194.163.142.108
   POSTGRES_PORT=5432
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=gYlN0EredxHkxFm9BsftKvJ7
   POSTGRES_DB=cartola_manager
   CALCULATION_INTERVAL_MINUTES=15
   DOCKERHUB_USERNAME=renaneunao  # Opcional, se diferente do padrão
   ```

## Como funciona

1. **GitHub Actions**:
   - Ao fazer push na branch `main` ou `master`, o workflow é acionado
   - Faz build da imagem Docker
   - Faz push para Docker Hub: `{DOCKERHUB_USERNAME}/saas-cartola-calculador:latest`

2. **Docker Compose**:
   - Usa a imagem do Docker Hub (não faz build local)
   - Lê variáveis de ambiente do arquivo `.env`
   - Container roda automaticamente a cada 15 minutos (ou intervalo configurado)

## Deploy

```bash
# 1. Configure o .env com suas credenciais
cp env.example .env
# Edite o .env com suas configurações

# 2. Inicie o serviço
docker-compose up -d

# 3. Ver logs
docker-compose logs -f calculador

# 4. Parar o serviço
docker-compose down
```

## Verificação

O serviço executará:
- **10 perfis de Peso do Jogo** (5 brandos + 5 agressivos)
- **10 perfis de Peso do SG** (5 brandos + 5 agressivos)
- Total: **20 perfis** calculados a cada ciclo
- Tempo estimado: ~3-4 minutos por ciclo
- Intervalo entre ciclos: 15 minutos (após término de cada ciclo)

