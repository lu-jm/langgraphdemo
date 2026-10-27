"""会话（thread）查询与删除。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.a2ui.service import A2UIService
from app.config import Settings
from app.errors import NotFoundError
from app.schemas.a2ui import SurfacePayload
from app.schemas.threads import ThreadDetail, ThreadSummary
from app.services.serializers import serialize_messages

logger = logging.getLogger(__name__)


class ThreadService:
    def __init__(
        self,
        *,
        settings: Settings,
        graph,
        a2ui_service: A2UIService,
    ) -> None:
        self.settings = settings
        self.graph = graph
        self.a2ui_service = a2ui_service

    @property
    def checkpointer(self):
        return getattr(self.graph, "checkpointer", None)

    async def list_threads(self) -> list[ThreadSummary]:
        """列出 checkpointer 中存在的线程（按最近更新时间倒序）。"""

        summaries: dict[str, ThreadSummary] = {}
        checkpointer = self.checkpointer
        if checkpointer is None:
            return []

        try:
            async for item in checkpointer.alist(None):
                thread_id = (
                    item.config.get("configurable", {}).get("thread_id")
                    if item.config
                    else None
                )
                if not thread_id:
                    continue
                updated_at = _checkpoint_time(item)
                channel_values = (item.checkpoint or {}).get("channel_values", {})
                message_count = len(channel_values.get("messages", []) or [])
                current = summaries.get(thread_id)
                if current is None:
                    summaries[thread_id] = ThreadSummary(
                        thread_id=thread_id,
                        message_count=message_count,
                        surface_count=self.a2ui_service.store.surface_count(thread_id),
                        updated_at=updated_at,
                    )
                else:
                    current.message_count = max(current.message_count, message_count)
                    if updated_at and (
                        current.updated_at is None or updated_at > current.updated_at
                    ):
                        current.updated_at = updated_at
        except Exception:  # pragma: no cover - 不同 checkpointer 实现差异
            logger.exception("列举线程失败，尝试从内存 storage 读取")
            storage = getattr(checkpointer, "storage", None)
            if isinstance(storage, dict):
                for thread_id in storage:
                    summaries.setdefault(
                        thread_id,
                        ThreadSummary(
                            thread_id=thread_id,
                            surface_count=self.a2ui_service.store.surface_count(
                                thread_id
                            ),
                        ),
                    )

        return sorted(
            summaries.values(),
            key=lambda item: item.updated_at or datetime(1, 1, 1, tzinfo=UTC),
            reverse=True,
        )

    async def get_thread(self, thread_id: str) -> ThreadDetail:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await self.graph.aget_state(config)
        values = getattr(snapshot, "values", None) or {}
        messages = values.get("messages", []) or []
        if not messages:
            raise NotFoundError(
                f"会话 {thread_id!r} 不存在或没有消息",
                details={"threadId": thread_id},
            )

        return ThreadDetail(
            thread_id=thread_id,
            messages=serialize_messages(messages),
            surfaces=[
                SurfacePayload.from_surface(surface)
                for surface in self.a2ui_service.list_surfaces(thread_id)
            ],
            a2ui_operations=values.get("a2ui", []) or [],
        )

    async def delete_thread(self, thread_id: str) -> None:
        checkpointer = self.checkpointer
        if checkpointer is not None:
            try:
                await checkpointer.adelete_thread(thread_id)
            except Exception as exc:  # noqa: BLE001 - 兼容不同 checkpointer 实现
                logger.warning("删除 checkpoint 失败（thread=%s）：%s", thread_id, exc)
        self.a2ui_service.clear_thread(thread_id)


def _checkpoint_time(item: Any) -> datetime | None:
    checkpoint = getattr(item, "checkpoint", None) or {}
    raw = checkpoint.get("ts")
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    if isinstance(raw, datetime):
        return raw
    return None
