include .env
export

# Define la base del comando para reusarla
COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

# .PHONY evita conflictos si tienes carpetas con estos mismos nombres
.PHONY: up down logs restart psql migrate revision

psql:
	$(COMPOSE) exec -it postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)
migrate:
	$(COMPOSE) exec backend alembic upgrade head

# uso: make revision m="create candles table"
revision:
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"
# Levantar el proyecto
up:
	$(COMPOSE) up -d

# Apagar el proyecto
down:
	$(COMPOSE) down

# Ver los logs en tiempo real
logs:
	$(COMPOSE) logs -f

# Reiniciar todo
restart: down up