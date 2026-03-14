# Makefile — управление AI Assistant на сервере
# Использование: make <target>
# Требует: systemd, npm (для miniapp)

.PHONY: help deploy restart stop start logs status build-miniapp health

# Путь к проекту
PROJECT_DIR := /root/ai-assistant

help: ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build-miniapp: ## Собрать и задеплоить Mini App
	@echo "→ Сборка Mini App..."
	cd $(PROJECT_DIR)/miniapp && npm run deploy
	@echo "✓ Mini App задеплоен в /var/www/jarvis/"

deploy: ## Полный деплой: pull + pip + miniapp + restart
	@echo "→ git pull..."
	cd $(PROJECT_DIR) && git pull
	@echo "→ pip install..."
	cd $(PROJECT_DIR) && venv/bin/pip install -q -r requirements.txt
	@echo "→ Сборка Mini App..."
	$(MAKE) build-miniapp
	@echo "→ Перезапуск сервисов..."
	$(MAKE) restart
	@echo "✓ Деплой завершён"

restart: ## Перезапустить API и бота
	systemctl restart ai-api ai-bot
	@echo "✓ Перезапущено: ai-api, ai-bot"

stop: ## Остановить оба сервиса
	systemctl stop ai-api ai-bot
	@echo "✓ Остановлено"

start: ## Запустить оба сервиса
	systemctl start ai-api ai-bot
	@echo "✓ Запущено"

logs: ## Показать live-логи обоих сервисов
	journalctl -f -u ai-api -u ai-bot -n 100

logs-api: ## Логи только API
	journalctl -f -u ai-api -n 100

logs-bot: ## Логи только бота
	journalctl -f -u ai-bot -n 100

status: ## Статус сервисов
	@echo "=== ai-api ==="
	@systemctl status ai-api --no-pager -l || true
	@echo ""
	@echo "=== ai-bot ==="
	@systemctl status ai-bot --no-pager -l || true

health: ## Проверить health-check API
	@curl -s http://localhost:8000/api/health | python3 -m json.tool || echo "API недоступен"
