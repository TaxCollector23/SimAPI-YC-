.DEFAULT_GOAL := help
.PHONY: help install dev run test cov lint format typecheck docker docker-run clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies
	pip install -r requirements.txt

dev: ## Install dev + runtime dependencies and pre-commit hooks
	pip install -r requirements-dev.txt
	pre-commit install || true

run: ## Run the API + dashboard locally
	python launch.py

test: ## Run the test suite
	pytest tests/ -q

cov: ## Run tests with a coverage report
	pytest tests/ --cov=api --cov=core --cov-report=term-missing --cov-report=xml

lint: ## Lint with ruff
	ruff check api core sdk tests

format: ## Auto-format with ruff
	ruff format api core sdk tests

typecheck: ## Static type-check with mypy
	mypy api core

docker: ## Build the production image
	docker build -t simapi:latest .

docker-run: ## Run the container
	docker compose up --build

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov coverage.xml .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
