# Define la base del comando para reusarla
COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

# .PHONY evita conflictos si tienes carpetas con estos mismos nombres
.PHONY: up down logs restart

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