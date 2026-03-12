# Contributing to AgentFlow

Thank you for your interest in contributing to AgentFlow! This guide will help you set up your development environment and understand our development workflow.

## Development Environment Setup

We offer two development environments. **Docker is recommended** for the most consistent and hassle-free experience.

### Option 1: Docker Development (Recommended)

Docker provides a consistent, isolated environment with all dependencies pre-configured. No need to install Node.js, Python, or nginx on your local machine.

#### Prerequisites

- Docker Desktop or Docker Engine




   ```bash
   # Copy example configuration
   cp config.example.yaml config.yaml

   # Set your API keys
   export OPENAI_API_KEY="your-key-here"
   # or edit config.yaml directly
   ```


   ```bash
   make docker-init
   ```
   ```
   This will:
   - Build Docker images

   - Install backend dependencies (uv)
   ```bash
   make docker-start
   ```
   ```bash

   ```
   `make docker-start` reads `config.yaml` and starts `provisioner` only for provisioner/Kubernetes sandbox mode.


   - Frontend changes are automatically reloaded
   - Backend changes trigger automatic restart
   - LangGraph server supports hot-reload


   - Web Interface: http://localhost:2026

```bash
# Build the custom k3s image (with pre-cached sandbox image)
make docker-init
# Start Docker services (mode-aware, localhost:2026)
make docker-start
# Stop Docker development services
make docker-stop
# View Docker development logs
make docker-logs
# View Docker gateway logs
make docker-logs-gateway
# View Docker langgraph logs
make docker-logs-langgraph
```

# View Docker gateway logs

```
Host Machine
  ↓
Docker Compose (agent-flow-dev)
  ├→ nginx (port 2026) ← Reverse proxy
  ├→ api (port 8001) ← Gateway API with hot-reload
  ├→ langgraph (port 2024) ← LangGraph server with hot-reload
  └→ provisioner (optional, port 8002) ← Started only in provisioner/K8s sandbox mode
```

  ├→ api (port 8001) ← Gateway API with hot-reload
   ├→ langgraph (port 2024) ← LangGraph server with hot-reload
   └→ provisioner (optional, port 8002) ← Started only in provisioner/K8s sandbox mode
```

**Benefits of Docker Development**:
- ✅ Consistent environment across different machines

- ✅ Isolated dependencies and services

- ✅ Hot-reload for all services





```bash
make check
```


```bash
make check



- Node.js 22+

- uv (Python package manager)
   ```bash
   make install
   ```

1. **Configure the application** (same as Docker setup above)
   ```bash
   make dev
   ```

   ```

3. **Run development server** (starts all services with nginx):

   make dev



   - Web Interface: http://localhost:2026
   ```bash
   # Terminal 1: Start LangGraph Server (port 2024)
   cd backend
   make dev

   # Terminal 2: Start Gateway API (port 8001)
   cd backend
   make gateway
   ```

   make dev
   ```bash
   nginx -c $(pwd)/docker/nginx/nginx.local.conf -g 'daemon off;'
   ```


   # Terminal 3: Start Frontend (port 3000)

   pnpm dev


2. **Start nginx**:
   ```bash
   make nginx
   # or directly: nginx -c $(pwd)/docker/nginx/nginx.local.conf -g 'daemon off;'
   ```

3. **Access the application**:



```
Agent-flow/
├── config.example.yaml      # Configuration template
├── extensions_config.example.json  # MCP and Skills configuration template
├── Makefile                 # Build and development commands
├── scripts/
│   └── docker.sh           # Docker management script
├── docker/
│   ├── docker-compose-dev.yaml  # Docker Compose configuration
│   └── nginx/
│       ├── nginx.conf      # Nginx config for Docker
│       └── nginx.local.conf # Nginx config for local dev
├── backend/                 # Backend application
│   ├── src/
│   │   ├── gateway/        # Gateway API (port 8001)
│   │   ├── agents/         # LangGraph agents (port 2024)
│   │   ├── mcp/            # Model Context Protocol integration
│   │   ├── skills/         # Skills system
│   │   └── sandbox/        # Sandbox execution
│   ├── docs/               # Backend documentation
│   └── Makefile            # Backend commands
└── skills/                 # Agent skills
    ├── public/             # Public skills
    └── custom/             # Custom skills
```

│   │   ├── gateway/        # Gateway API (port 8001)

```
Browser
  ↓
Nginx (port 2026) ← Unified entry point
  ├→ Gateway API (port 8001) ← /api/models, /api/mcp, /api/skills, /api/threads/*/artifacts
  └→ LangGraph Server (port 2024) ← /api/langgraph/* (agent interactions)
```

    ├── public/             # Public skills

```
   ```bash
   git checkout -b feature/your-feature-name
   ```

Browser

Nginx (port 2026) ← Unified entry point

  ├→ Gateway API (port 8001) ← /api/models, /api/mcp, /api/skills, /api/threads/*/artifacts
   ```bash
   git add .
   git commit -m "feat: description of your changes"
   ```

1. **Create a feature branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Make your changes** with hot-reload enabled

```bash
# Backend tests
cd backend
uv run pytest
```

   ```

5. **Push and create a Pull Request**:

   git push origin feature/your-feature-name
   ```

## Testing

```bash

cd backend


# Frontend tests
cd frontend

```

### PR Regression Checks

Every pull request runs the backend regression workflow at [.github/workflows/backend-unit-tests.yml](.github/workflows/backend-unit-tests.yml), including:

- `tests/test_provisioner_kubeconfig.py`


