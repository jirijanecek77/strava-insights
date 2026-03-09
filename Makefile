COMPOSE = docker compose

.PHONY: build up down test logs

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
