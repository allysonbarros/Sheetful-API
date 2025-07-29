# Makefile para Sheetful API
# Comandos comuns para desenvolvimento e manutenção

.PHONY: help install dev test lint format clean run docker-build docker-run

# Configuração padrão
PYTHON = python3
PIP = pip
VENV = .venv
APP_MODULE = main:app

help: ## Mostra esta ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependências
	$(PIP) install -r requirements.txt

install-dev: ## Instala dependências de desenvolvimento
	$(PIP) install -r requirements.txt
	$(PIP) install pre-commit
	pre-commit install

venv: ## Cria ambiente virtual
	$(PYTHON) -m venv $(VENV)
	@echo "Ative o ambiente virtual com: source $(VENV)/bin/activate"

dev: ## Executa aplicação em modo desenvolvimento
	$(PYTHON) main.py

run: ## Executa aplicação
	uvicorn $(APP_MODULE) --host 0.0.0.0 --port 8000

test: ## Executa testes
	pytest

test-cov: ## Executa testes com cobertura
	pytest --cov=app --cov-report=html --cov-report=term

lint: ## Verifica código com linters
	flake8 app/ main.py server.py dev_utils.py
	mypy app/ main.py server.py dev_utils.py

format: ## Formata código
	black app/ main.py server.py dev_utils.py
	isort app/ main.py server.py dev_utils.py

format-check: ## Verifica formatação
	black --check app/ main.py server.py dev_utils.py
	isort --check-only app/ main.py server.py dev_utils.py

validate: ## Valida configuração do ambiente
	$(PYTHON) dev_utils.py validate

clean: ## Remove arquivos temporários
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/

docker-build: ## Constrói imagem Docker
	docker build -t sheetful-api .

docker-run: ## Executa container Docker
	docker run -p 8000:8000 --env-file .env sheetful-api

docker-compose-up: ## Executa com docker-compose
	docker-compose up -d

docker-compose-down: ## Para containers docker-compose
	docker-compose down

logs: ## Mostra logs da aplicação
	tail -f logs/django.log

setup: venv install ## Configuração inicial completa
	@echo "Configuração concluída!"
	@echo "1. Ative o ambiente virtual: source $(VENV)/bin/activate"
	@echo "2. Configure o arquivo .env"
	@echo "3. Execute: make dev"

# Comandos para CI/CD
ci-test: install test lint format-check ## Pipeline de CI/CD

# Comandos de utilidade
docs: ## Abre documentação da API
	@echo "Documentação disponível em:"
	@echo "- Swagger UI: http://localhost:8000/docs"
	@echo "- ReDoc: http://localhost:8000/redoc"

health: ## Verifica saúde da aplicação
	curl -f http://localhost:8000/health || echo "Aplicação não está rodando"
