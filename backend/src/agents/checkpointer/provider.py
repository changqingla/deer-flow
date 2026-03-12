"""同步版 Checkpointer 提供器。

为 LangGraph 图编译与 CLI 工具提供：
- 同步单例
- 同步上下文管理器

支持后端：memory、sqlite、postgres。

用法::

    from src.agents.checkpointer.provider import get_checkpointer, checkpointer_context

    # 单例：多次调用复用，进程退出时关闭
    cp = get_checkpointer()

    # 一次性实例：每个 with 块独立创建并在退出时关闭
    with checkpointer_context() as cp:
        graph.invoke(input, config={"configurable": {"thread_id": "1"}})
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator

from langgraph.types import Checkpointer

from src.config.app_config import get_app_config
from src.config.checkpointer_config import CheckpointerConfig
from src.config.paths import resolve_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 错误消息常量（aio.provider 也会复用）
# ---------------------------------------------------------------------------

SQLITE_INSTALL = "langgraph-checkpoint-sqlite is required for the SQLite checkpointer. Install it with: uv add langgraph-checkpoint-sqlite"
POSTGRES_INSTALL = "langgraph-checkpoint-postgres is required for the PostgreSQL checkpointer. Install it with: uv add langgraph-checkpoint-postgres psycopg[binary] psycopg-pool"
POSTGRES_CONN_REQUIRED = "checkpointer.connection_string is required for the postgres backend"

# ---------------------------------------------------------------------------
# 同步工厂
# ---------------------------------------------------------------------------


def _resolve_sqlite_conn_str(raw: str) -> str:
    """解析 SQLite 连接串。

    SQLite 特殊值（``":memory:"`` 与 ``file:`` URI）会原样返回；
    普通文件系统路径（相对或绝对）会通过 :func:`resolve_path`
    解析为绝对路径字符串。
    """
    if raw == ":memory:" or raw.startswith("file:"):
        return raw
    return str(resolve_path(raw))


@contextlib.contextmanager
def _sync_checkpointer_cm(config: CheckpointerConfig) -> Iterator[Checkpointer]:
    """创建并返回配置好的 ``Checkpointer``。

    底层连接或连接池的资源清理由本模块更高层的辅助方法负责
    （例如单例工厂或上下文管理器）；本函数不返回独立清理回调。
    """
    if config.type == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        logger.info("Checkpointer: using InMemorySaver (in-process, not persistent)")
        yield InMemorySaver()
        return

    if config.type == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise ImportError(SQLITE_INSTALL) from exc

        conn_str = _resolve_sqlite_conn_str(config.connection_string or "store.db")
        with SqliteSaver.from_conn_string(conn_str) as saver:
            saver.setup()
            logger.info("Checkpointer: using SqliteSaver (%s)", conn_str)
            yield saver
        return

    if config.type == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise ImportError(POSTGRES_INSTALL) from exc

        if not config.connection_string:
            raise ValueError(POSTGRES_CONN_REQUIRED)

        with PostgresSaver.from_conn_string(config.connection_string) as saver:
            saver.setup()
            logger.info("Checkpointer: using PostgresSaver")
            yield saver
        return

    raise ValueError(f"Unknown checkpointer type: {config.type!r}")


# ---------------------------------------------------------------------------
# 同步单例
# ---------------------------------------------------------------------------

_checkpointer: Checkpointer | None = None
_checkpointer_ctx = None  # open context manager keeping the connection alive


def get_checkpointer() -> Checkpointer:
    """获取 Checkpointer 单例。

    当 *config.yaml* 未配置 checkpointer 时，返回 ``InMemorySaver``。

    异常：
        ImportError: 已配置后端但缺少对应依赖包时抛出。
        ValueError: 后端需要 ``connection_string`` 但未提供时抛出。
    """
    global _checkpointer, _checkpointer_ctx

    if _checkpointer is not None:
        return _checkpointer

    # 在读取 checkpointer 配置前确保 app 配置已加载
    # 避免 config.yaml 实际存在 checkpointer 配置但尚未加载时，
    # 被误判为应返回 InMemorySaver。
    from src.config.app_config import _app_config
    from src.config.checkpointer_config import get_checkpointer_config

    if _app_config is None:
        # 仅在配置未初始化时加载
        # 测试环境中可能直接通过 set_checkpointer_config() 注入配置
        try:
            get_app_config()
        except FileNotFoundError:
            # 测试环境没有 config.yaml 属于预期场景
            # 测试会通过 set_checkpointer_config() 直接设置配置
            pass

    config = get_checkpointer_config()
    if config is None:
        from langgraph.checkpoint.memory import InMemorySaver

        logger.info("Checkpointer: using InMemorySaver (in-process, not persistent)")
        _checkpointer = InMemorySaver()
        return _checkpointer

    _checkpointer_ctx = _sync_checkpointer_cm(config)
    _checkpointer = _checkpointer_ctx.__enter__()

    return _checkpointer


def reset_checkpointer() -> None:
    """重置 Checkpointer 单例并释放资源。

    会关闭已打开的后端连接并清空缓存实例。
    适用于测试场景或配置变更之后。
    """
    global _checkpointer, _checkpointer_ctx
    if _checkpointer_ctx is not None:
        try:
            _checkpointer_ctx.__exit__(None, None, None)
        except Exception:
            logger.warning("Error during checkpointer cleanup", exc_info=True)
        _checkpointer_ctx = None
    _checkpointer = None


# ---------------------------------------------------------------------------
# 同步上下文管理器
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def checkpointer_context() -> Iterator[Checkpointer]:
    """获取非缓存型 Checkpointer 上下文。

    与 :func:`get_checkpointer` 不同，此方法**不会缓存实例**；
    每个 ``with`` 块都会独立创建并销毁连接。适用于 CLI 脚本或
    需要确定性清理的测试场景::

        with checkpointer_context() as cp:
            graph.invoke(input, config={"configurable": {"thread_id": "1"}})

    当 *config.yaml* 未配置 checkpointer 时，产出 ``InMemorySaver``。
    """

    config = get_app_config()
    if config.checkpointer is None:
        from langgraph.checkpoint.memory import InMemorySaver

        yield InMemorySaver()
        return

    with _sync_checkpointer_cm(config.checkpointer) as saver:
        yield saver
