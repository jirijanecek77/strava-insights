COMPOSE = docker compose
PROD_COMPOSE = docker compose --env-file .env.production -f docker-compose.prod.yml

.PHONY: build up down test logs build-prod up-prod down-prod logs-prod

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

test:
	$(COMPOSE) run --rm backend pytest
	$(COMPOSE) run --rm worker pytest
	$(COMPOSE) run --rm frontend npm run test -- --run

logs:
	$(COMPOSE) logs -f

build-prod:
	$(PROD_COMPOSE) build

up-prod:
	$(PROD_COMPOSE) up -d

down-prod:
	$(PROD_COMPOSE) down --remove-orphans

logs-prod:
	$(PROD_COMPOSE) logs -f
