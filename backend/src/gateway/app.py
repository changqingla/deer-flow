import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.app_config import get_app_config
from src.gateway.config import get_gateway_config
from src.gateway.routers import (
    agents,
    artifacts,
    channels,
    mcp,
    memory,
    models,
    skills,
    suggestions,
    uploads,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期处理器。"""

    # 启动时加载配置并校验必要环境变量
    try:
        get_app_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration during gateway startup: {e}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e
    config = get_gateway_config()
    logger.info(f"Starting API Gateway on {config.host}:{config.port}")

    # 注意：这里不初始化 MCP 工具，原因如下：
    # 1. Gateway 本身不直接使用 MCP 工具，工具由 LangGraph Server 中的 Agent 调用
    # 2. Gateway 与 LangGraph Server 是独立进程，缓存也相互独立
    # 模型上下文协议（MCP）工具会在 LangGraph Server 首次需要时延迟初始化

    # 若配置了 IM 渠道，则启动渠道服务
    try:
        from src.channels.service import start_channel_service

        channel_service = await start_channel_service()
        logger.info("Channel service started: %s", channel_service.get_status())
    except Exception:
        logger.exception("No IM channels configured or channel service failed to start")

    yield

    # 关闭时停止渠道服务
    try:
        from src.channels.service import stop_channel_service

        await stop_channel_service()
    except Exception:
        logger.exception("Failed to stop channel service")
    logger.info("Shutting down API Gateway")


def create_app() -> FastAPI:
    """创建并返回配置完成的 FastAPI 应用实例。"""

    app = FastAPI(
        title="Agent-flow API Gateway",
        description="""
## AgentFlow API Gateway

API Gateway for Agent-flow - A LangGraph-based AI agent backend with sandbox execution capabilities.

### Features

- **Models Management**: Query and retrieve available AI models
- **MCP Configuration**: Manage Model Context Protocol (MCP) server configurations
- **Memory Management**: Access and manage global memory data for personalized conversations
- **Skills Management**: Query and manage skills and their enabled status
- **Artifacts**: Access thread artifacts and generated files
- **Health Monitoring**: System health check endpoints

### Architecture

LangGraph requests are handled by nginx reverse proxy.
This gateway provides custom endpoints for models, MCP configuration, skills, and artifacts.
        """,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "models",
                "description": "Operations for querying available AI models and their configurations",
            },
            {
                "name": "mcp",
                "description": "Manage Model Context Protocol (MCP) server configurations",
            },
            {
                "name": "memory",
                "description": "Access and manage global memory data for personalized conversations",
            },
            {
                "name": "skills",
                "description": "Manage skills and their configurations",
            },
            {
                "name": "artifacts",
                "description": "Access and download thread artifacts and generated files",
            },
            {
                "name": "uploads",
                "description": "Upload and manage user files for threads",
            },
            {
                "name": "agents",
                "description": "Create and manage custom agents with per-agent config and prompts",
            },
            {
                "name": "suggestions",
                "description": "Generate follow-up question suggestions for conversations",
            },
            {
                "name": "channels",
                "description": "Manage IM channel integrations (Feishu, Slack, Telegram)",
            },
            {
                "name": "health",
                "description": "Health check and system status endpoints",
            },
        ],
    )

    # 跨域资源共享（CORS）由 nginx 处理，无需额外添加 FastAPI 中间件

    # 注册路由
    # 模型接口挂载于 /api/models
    app.include_router(models.router)

    # 模型上下文协议（MCP）接口挂载于 /api/mcp
    app.include_router(mcp.router)

    # 记忆接口挂载于 /api/memory
    app.include_router(memory.router)

    # 技能接口挂载于 /api/skills
    app.include_router(skills.router)

    # 产物接口挂载于 /api/threads/{thread_id}/artifacts
    app.include_router(artifacts.router)

    # 上传接口挂载于 /api/threads/{thread_id}/uploads
    app.include_router(uploads.router)

    # 代理接口挂载于 /api/agents
    app.include_router(agents.router)

    # 建议问题接口挂载于 /api/threads/{thread_id}/suggestions
    app.include_router(suggestions.router)

    # 渠道接口挂载于 /api/channels
    app.include_router(channels.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """返回服务健康状态信息。"""
        return {"status": "healthy", "service": "agent-flow-gateway"}

    return app


# 为 uvicorn 创建应用实例
app = create_app()
