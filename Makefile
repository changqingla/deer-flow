# AgentFlow -统一开发环境

.PHONY: help config check install dev stop clean docker-init docker-start docker-stop docker-logs docker-logs-gateway docker-logs-langgraph

help:
	@echo "Agent-flow Development Commands:"
	@echo "  make config          - Generate local config files (aborts if config already exists)"
	@echo "  make check           - Check if all required tools are installed"
	@echo "  make install         - Install backend dependencies"
	@echo "  make setup-sandbox   - Pre-pull sandbox container image (recommended)"
	@echo "  make dev             - Start backend services (+ nginx on localhost:2026)"
	@echo "  make stop            - Stop all running services"
	@echo "  make clean           - Clean up processes and temporary files"
	@echo ""
	@echo "Docker Development Commands:"
	@echo "  make docker-init     - Build the custom k3s image (with pre-cached sandbox image)"
	@echo "  make docker-start    - Start Docker services (mode-aware from config.yaml, 0.0.0.0:2026)"
	@echo "  make docker-stop     - Stop Docker development services"
	@echo "  make docker-logs     - View Docker development logs"
	@echo "  make docker-logs-gateway - View Docker gateway logs"
	@echo "  make docker-logs-langgraph - View Docker langgraph logs"

config:
	@if [ -f config.yaml ] || [ -f config.yml ] || [ -f configure.yml ]; then \
		echo "Error: configuration file already exists (config.yaml/config.yml/configure.yml). Aborting."; \
		exit 1; \
	fi
	@cp config.example.yaml config.yaml
	@test -f .env || cp .env.example .env


check:
	@echo "=========================================="
	@echo "  Checking Required Dependencies"
	@echo "=========================================="
	@echo ""
	@FAILED=0; \
	echo "Checking uv..."; \
	if command -v uv >/dev/null 2>&1; then \
		UV_VERSION=$$(uv --version | awk '{print $$2}'); \
		echo "  ✓ uv $$UV_VERSION"; \
	else \
		echo "  ✗ uv not found"; \
		echo "    Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo "    Or visit: https://docs.astral.sh/uv/getting-started/installation/"; \
		FAILED=1; \
	fi; \
	echo ""; \
	echo "Checking nginx..."; \
	if command -v nginx >/dev/null 2>&1; then \
		NGINX_VERSION=$$(nginx -v 2>&1 | awk -F'/' '{print $$2}'); \
		echo "  ✓ nginx $$NGINX_VERSION"; \
	else \
		echo "  ✗ nginx not found"; \
		echo "    macOS:   brew install nginx"; \
		echo "    Ubuntu:  sudo apt install nginx"; \
		echo "    Or visit: https://nginx.org/en/download.html"; \
		FAILED=1; \
	fi; \
	echo ""; \
	if [ $$FAILED -eq 0 ]; then \
		echo "=========================================="; \
		echo "  ✓ All dependencies are installed!"; \
		echo "=========================================="; \
		echo ""; \
		echo "You can now run:"; \
		echo "  make install  - Install project dependencies"; \
		echo "  make dev      - Start development server"; \
	else \
		echo "=========================================="; \
		echo "  ✗ Some dependencies are missing"; \
		echo "=========================================="; \
		echo ""; \
		echo "Please install the missing tools and run 'make check' again."; \
		exit 1; \
	fi

# echo "正在检查nginx...";\
install:
	@echo "Installing backend dependencies..."
	@cd backend && uv sync
	@echo "✓ Backend dependencies installed"
	@echo ""
	@echo "=========================================="
	@echo "  Optional: Pre-pull Sandbox Image"
	@echo "=========================================="
	@echo ""
	@echo "If you plan to use Docker/Container-based sandbox, you can pre-pull the image:"
	@echo "  make setup-sandbox"
	@echo ""

# echo "✓所有依赖项已安装！";\
setup-sandbox:
	@echo "=========================================="
	@echo "  Pre-pulling Sandbox Container Image"
	@echo "=========================================="
	@echo ""
	@IMAGE=$$(grep -A 20 "# sandbox:" config.yaml 2>/dev/null | grep "image:" | awk '{print $$2}' | head -1); \
	if [ -z "$$IMAGE" ]; then \
		IMAGE="enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest"; \
		echo "Using default image: $$IMAGE"; \
	else \
		echo "Using configured image: $$IMAGE"; \
	fi; \
	echo ""; \
	if command -v container >/dev/null 2>&1 && [ "$$(uname)" = "Darwin" ]; then \
		echo "Detected Apple Container on macOS, pulling image..."; \
		container pull "$$IMAGE" || echo "⚠ Apple Container pull failed, will try Docker"; \
	fi; \
	if command -v docker >/dev/null 2>&1; then \
		echo "Pulling image using Docker..."; \
		docker pull "$$IMAGE"; \
		echo ""; \
		echo "✓ Sandbox image pulled successfully"; \
	else \
		echo "✗ Neither Docker nor Apple Container is available"; \
		echo "  Please install Docker: https://docs.docker.com/get-docker/"; \
		exit 1; \
	fi

# 回声
dev:
	@./scripts/start.sh

# 回声
stop:
	@echo "Stopping all services..."
	@-pkill -f "langgraph dev" 2>/dev/null || true
	@-pkill -f "uvicorn src.gateway.app:app" 2>/dev/null || true
	@-nginx -c $(PWD)/docker/nginx/nginx.local.conf -p $(PWD) -s quit 2>/dev/null || true
	@sleep 1
	@-pkill -9 nginx 2>/dev/null || true
	@echo "Cleaning up sandbox containers..."
	@-./scripts/cleanup-containers.sh agent-flow-sandbox 2>/dev/null || true
	@echo "✓ All services stopped"

# if command -v container >/dev/null 2 > & 1 & & ["$ $ (uname)" = "Darwin"]; then\
clean: stop
	@echo "Cleaning up..."
	@-rm -rf logs/*.log 2>/dev/null || true
	@echo "✓ Cleanup complete"

# ==========================================
# 回声
# ==========================================

# echo "Docker✗和Apple Container都不可用";\
docker-init:
	@./scripts/docker.sh init


docker-start:
	@./scripts/docker.sh start


docker-stop:
	@./scripts/docker.sh stop

# @ -pkill -f "langgraph dev" 2 >/dev/null || true
docker-logs:
	@./scripts/docker.sh logs

# @ sleep 1
docker-logs-gateway:
	@./scripts/docker.sh logs --gateway
docker-logs-langgraph:
	@./scripts/docker.sh logs --langgraph
