"""LangGraph checkpointer 工厂。"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.config import Settings

logger = logging.getLogger(__name__)


async def create_checkpointer(
    settings: Settings, stack: AsyncExitStack
) -> BaseCheckpointSaver:
    """按配置创建 checkpointer。

    - ``memory``：进程内存储，重启丢失（默认）；
    - ``sqlite``：持久化到本地文件，适合单机部署。
    """

    if settings.checkpoint_backend == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        path = Path(settings.checkpoint_sqlite_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("使用 SQLite checkpointer：%s", path)
        return await stack.enter_async_context(
            AsyncSqliteSaver.from_conn_string(str(path))
        )

    from langgraph.checkpoint.memory import MemorySaver

    logger.info("使用内存 checkpointer（重启后会话丢失）")
    return MemorySaver()
