.PHONY: help install lint format test clean run streamlit db-init docker-up docker-down

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help:
	@echo "$(GREEN)Velmo 2.0 - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup & Installation:$(NC)"
	@echo "  make install          Install dependencies (uv sync)"
	@echo "  make docker-up        Start Docker services (PostgreSQL + Redis)"
	@echo "  make docker-down      Stop Docker services"
	@echo "  make db-init          Initialize database schema"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make streamlit        Run Streamlit chat app (http://localhost:8501)"
	@echo "  make test             Run pytest tests"
	@echo "  make lint             Run ruff linter"
	@echo "  make format           Format code with black"
	@echo "  make clean            Remove Python cache files"
	@echo ""
	@echo "$(YELLOW)Full Setup (one command):$(NC)"
	@echo "  make setup            install + docker-up + db-init"
	@echo ""

install:
	@echo "$(GREEN)Installing dependencies with uv...$(NC)"
	UV_LINK_MODE=copy uv sync

docker-up:
	@echo "$(GREEN)Starting Docker services (PostgreSQL + Redis)...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services running$(NC)"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Redis: localhost:6379"

docker-down:
	@echo "$(YELLOW)Stopping Docker services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

db-init:
	@echo "$(GREEN)Initializing database schema...$(NC)"
	uv run python -c "from velmo.memory import get_db; db = get_db(); db.init_db(); print('$(GREEN)✓ Database initialized$(NC)')"

streamlit:
	@echo "$(GREEN)Starting Streamlit chat app...$(NC)"
	@echo "$(YELLOW)Opening browser at http://localhost:8501$(NC)"
	uv run streamlit run apps/streamlit/app_streamlit.py

test:
	@echo "$(GREEN)Running tests...$(NC)"
	uv run pytest tests/ -v --tb=short

test-watch:
	@echo "$(GREEN)Running tests in watch mode...$(NC)"
	uv run pytest-watch tests/

lint:
	@echo "$(GREEN)Running ruff linter...$(NC)"
	uv run ruff check .

format:
	@echo "$(GREEN)Formatting code with black...$(NC)"
	uv run black src tests scripts apps
	@echo "$(GREEN)Fixing lint issues with ruff...$(NC)"
	uv run ruff check . --fix

clean:
	@echo "$(YELLOW)Cleaning Python cache files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

setup: install docker-up db-init
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ Velmo 2.0 setup complete!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Start the Streamlit app:"
	@echo "     $(GREEN)make streamlit$(NC)"
	@echo ""
	@echo "  2. Or run tests:"
	@echo "     $(GREEN)make test$(NC)"
	@echo ""
	@echo "  3. Visit http://localhost:8501 to chat with Velmo 🤖"
	@echo ""

# Development shortcuts
dev: streamlit

run-tests: test

check: lint test
	@echo "$(GREEN)✓ All checks passed$(NC)"

# Memory operations
eval-memory:
	@echo "$(GREEN)Running memory evaluation...$(NC)"
	uv run python scripts/eval_memory.py

eval-guardrails:
	@echo "$(GREEN)Running guardrails evaluation...$(NC)"
	uv run python scripts/eval_guardrails.py

# Status commands
status:
	@echo "$(GREEN)Repository Status:$(NC)"
	@echo ""
	git status
	@echo ""
	@echo "$(GREEN)Docker Status:$(NC)"
	docker-compose ps || echo "Docker services not running"
	@echo ""
	@echo "$(GREEN)Recent Commits:$(NC)"
	git log --oneline -5

