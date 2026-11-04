COMPOSE = docker compose --env-file .env.secrets
PROD_COMPOSE = docker compose --env-file .env.production -f docker-compose.prod.yml

.PHONY: build up down deploy test logs build-prod up-prod down-prod logs-prod ai-notes-enqueue ai-notes-run

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

deploy: build up

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

ai-notes-enqueue:
	$(COMPOSE) exec worker python -m app.coaching_cli enqueue-latest --user-id 1 --count 1

ai-notes-run:
	$(COMPOSE) exec worker python -m app.coaching_cli run --user-id 1 --batch-size 1