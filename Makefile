.PHONY: help build up down logs migrate seed test test-backend test-frontend dev-backend dev-frontend lint format

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build all docker images
	docker compose build

up: ## Start full stack (postgres + backend + frontend)
	docker compose up --build -d

down: ## Stop the stack
	docker compose down

logs: ## Tail logs
	docker compose logs -f

migrate: ## Run alembic migrations
	docker compose exec backend alembic upgrade head

seed: ## Seed development data (dev only)
	docker compose exec backend python -m app.scripts.seed_dev

test: ## Run all tests
	docker compose exec backend pytest -q
	docker compose exec frontend npm test -- --run

test-backend: ## Backend tests
	docker compose exec backend pytest -q

test-frontend: ## Frontend tests
	docker compose exec frontend npm test -- --run

dev-backend: ## Run backend locally (needs postgres)
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run frontend locally
	cd frontend && npm run dev

lint: ## Lint both projects
	cd backend && ruff check app tests
	cd frontend && npm run lint

format: ## Format both projects
	cd backend && ruff format app tests
	cd frontend && npm run format