# Makefile — управление AI Assistant (docker-compose стек)
# Использование: make <target>
# Требует: docker compose, npm (для miniapp)

.PHONY: help up down restart restart-bot restart-api restart-scheduler \
        logs logs-bot logs-api logs-scheduler ps \
        migrate migrate-check \
        build-miniapp deploy health

# Путь к проекту
PROJECT_DIR := /root/ai-assistant

help: ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ── Docker Compose ────────────────────────────────────────────────────────────

up: ## Поднять все сервисы (build + detach)
	docker compose up -d --build

down: ## Остановить и удалить контейнеры
	docker compose down

ps: ## Статус контейнеров
	docker compose ps

restart: ## Перезапустить все сервисы
	docker compose restart

restart-bot: ## Перезапустить только бота
	docker compose restart bot

restart-api: ## Перезапустить только API
	docker compose restart api

restart-scheduler: ## Перезапустить только планировщик
	docker compose restart scheduler

# ── Логи ──────────────────────────────────────────────────────────────────────

logs: ## Live-логи всех сервисов
	docker compose logs -f

logs-bot: ## Логи только бота
	docker compose logs -f bot

logs-api: ## Логи только API
	docker compose logs -f api

logs-scheduler: ## Логи планировщика уведомлений
	docker compose logs -f scheduler

# ── Миграции ──────────────────────────────────────────────────────────────────

migrate: ## Применить Alembic миграции
	docker compose run --rm migrator

migrate-check: ## Показать текущую версию миграций
	docker compose run --rm migrator alembic current

# ── Деплой ────────────────────────────────────────────────────────────────────

build-miniapp: ## Собрать и задеплоить Mini App
	@echo "→ Сборка Mini App..."
	cd $(PROJECT_DIR)/miniapp && npm run deploy
	@echo "✓ Mini App задеплоен в /var/www/jarvis/"

deploy: ## Полный деплой: git pull + miniapp + docker up
	@echo "→ git pull..."
	cd $(PROJECT_DIR) && git pull
	@echo "→ Сборка Mini App..."
	$(MAKE) build-miniapp
	@echo "→ Поднимаем сервисы..."
	$(MAKE) up
	@echo "✓ Деплой завершён"

# ── Health ────────────────────────────────────────────────────────────────────

health: ## Проверить health-check API
	@curl -s http://localhost:8000/api/health | python3 -m json.tool || echo "API недоступен"
