"""异步版 Checkpointer 提供器。

为需要正确资源清理的长生命周期异步服务提供**异步上下文管理器**。

支持后端：memory、sqlite、postgres。

用法（例如 FastAPI lifespan）：:

    from src.agents.checkpointer.async_provider import make_checkpointer

    async with make_checkpointer() as checkpointer:
        app.state.checkpointer = checkpointer  # 未配置时为 InMemorySaver

同步用法请见 :mod:`src.agents.checkpointer.provider`。
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator

from langgraph.types import Checkpointer

from src.agents.checkpointer.provider import (
    POSTGRES_CONN_REQUIRED,
    POSTGRES_INSTALL,
    SQLITE_INSTALL,
    _resolve_sqlite_conn_str,
)
from src.config.app_config import get_app_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 异步工厂
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def _async_checkpointer(config) -> AsyncIterator[Checkpointer]:
    """构建并托管 Checkpointer 生命周期的异步上下文管理器。"""
    if config.type == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        yield InMemorySaver()
        return

    if config.type == "sqlite":
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError as exc:
            raise ImportError(SQLITE_INSTALL) from exc

        import pathlib

        conn_str = _resolve_sqlite_conn_str(config.connection_string or "store.db")
        # 仅对真实文件系统路径创建父目录
        if conn_str != ":memory:" and not conn_str.startswith("file:"):
            pathlib.Path(conn_str).parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(conn_str) as saver:
            await saver.setup()
            yield saver
        return

    if config.type == "postgres":
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError as exc:
            raise ImportError(POSTGRES_INSTALL) from exc

        if not config.connection_string:
            raise ValueError(POSTGRES_CONN_REQUIRED)

        async with AsyncPostgresSaver.from_conn_string(config.connection_string) as saver:
            await saver.setup()
            yield saver
        return

    raise ValueError(f"Unknown checkpointer type: {config.type!r}")


# ---------------------------------------------------------------------------
# 对外异步上下文管理器
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def make_checkpointer() -> AsyncIterator[Checkpointer]:
    """创建 Checkpointer 异步上下文。

    进入上下文时打开资源，退出时释放资源，不依赖全局状态::

        async with make_checkpointer() as checkpointer:
            app.state.checkpointer = checkpointer

    当 *config.yaml* 未配置 checkpointer 时，产出 ``InMemorySaver``。
    """

    config = get_app_config()

    if config.checkpointer is None:
        from langgraph.checkpoint.memory import InMemorySaver

        yield InMemorySaver()
        return

    async with _async_checkpointer(config.checkpointer) as saver:
        yield saver
