"""A2UI Surface 的内存存储。

生产环境可将本模块替换为 Redis/数据库实现；接口保持同步方法，便于在
LangGraph 节点与 FastAPI 路由中直接调用。
"""

from __future__ import annotations

import copy
from collections import OrderedDict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.a2ui.constants import BASIC_CATALOG_ID


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Surface:
    thread_id: str
    surface_id: str
    catalog_id: str = BASIC_CATALOG_ID
    theme: dict[str, Any] | None = None
    send_data_model: bool = False
    components: OrderedDict[str, dict[str, Any]] = field(default_factory=OrderedDict)
    data_model: Any = field(default_factory=dict)
    revision: int = 0
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def touch(self) -> None:
        self.revision += 1
        self.updated_at = utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "threadId": self.thread_id,
            "surfaceId": self.surface_id,
            "catalogId": self.catalog_id,
            "theme": self.theme,
            "sendDataModel": self.send_data_model,
            "components": copy.deepcopy(list(self.components.values())),
            "dataModel": copy.deepcopy(self.data_model),
            "revision": self.revision,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }

    def to_summary(self) -> dict[str, Any]:
        return {
            "threadId": self.thread_id,
            "surfaceId": self.surface_id,
            "catalogId": self.catalog_id,
            "componentCount": len(self.components),
            "revision": self.revision,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }

    def to_messages(self) -> list[dict[str, Any]]:
        """把当前 surface 还原为完整的 A2UI 消息序列（用于重放）。"""

        messages = [
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": self.surface_id,
                    "catalogId": self.catalog_id,
                    **({"theme": self.theme} if self.theme is not None else {}),
                    **({"sendDataModel": True} if self.send_data_model else {}),
                },
            },
            {
                "version": "v0.9",
                "updateComponents": {
                    "surfaceId": self.surface_id,
                    "components": copy.deepcopy(list(self.components.values())),
                },
            },
        ]
        if self.data_model not in (None, {}):
            messages.append(
                {
                    "version": "v0.9",
                    "updateDataModel": {
                        "surfaceId": self.surface_id,
                        "path": "/",
                        "value": copy.deepcopy(self.data_model),
                    },
                }
            )
        return messages


class SurfaceStore:
    """线程隔离的 surface 与 action 存储。"""

    def __init__(
        self,
        *,
        max_surfaces_per_thread: int = 50,
        max_actions_per_thread: int = 100,
    ) -> None:
        self._lock = RLock()
        self._surfaces: dict[str, OrderedDict[str, Surface]] = {}
        self._actions: dict[str, deque[dict[str, Any]]] = {}
        self.max_surfaces_per_thread = max_surfaces_per_thread
        self.max_actions_per_thread = max_actions_per_thread

    # -- surfaces ---------------------------------------------------------

    def create(self, surface: Surface) -> Surface:
        with self._lock:
            thread = self._surfaces.setdefault(surface.thread_id, OrderedDict())
            while len(thread) >= self.max_surfaces_per_thread:
                thread.popitem(last=False)
            thread[surface.surface_id] = surface
            return surface

    def get(self, thread_id: str, surface_id: str) -> Surface | None:
        with self._lock:
            return self._surfaces.get(thread_id, {}).get(surface_id)

    def list(self, thread_id: str) -> list[Surface]:
        with self._lock:
            thread = self._surfaces.get(thread_id, {})
            return sorted(
                thread.values(), key=lambda surface: surface.updated_at, reverse=True
            )

    def replace(self, thread_id: str, surface_id: str, surface: Surface) -> None:
        with self._lock:
            self._surfaces.setdefault(thread_id, OrderedDict())[surface_id] = surface

    def delete(self, thread_id: str, surface_id: str) -> bool:
        with self._lock:
            thread = self._surfaces.get(thread_id)
            if not thread or surface_id not in thread:
                return False
            del thread[surface_id]
            if not thread:
                self._surfaces.pop(thread_id, None)
            return True

    def clear_thread(self, thread_id: str) -> None:
        with self._lock:
            self._surfaces.pop(thread_id, None)
            self._actions.pop(thread_id, None)

    def thread_ids(self) -> list[str]:
        with self._lock:
            return list(self._surfaces.keys())

    def surface_count(self, thread_id: str | None = None) -> int:
        with self._lock:
            if thread_id is not None:
                return len(self._surfaces.get(thread_id, {}))
            return sum(len(thread) for thread in self._surfaces.values())

    # -- actions ----------------------------------------------------------

    def record_action(self, thread_id: str, action: dict[str, Any]) -> None:
        with self._lock:
            bucket = self._actions.setdefault(
                thread_id, deque(maxlen=self.max_actions_per_thread)
            )
            bucket.appendleft(action)

    def list_actions(self, thread_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._actions.get(thread_id, ()))

    @contextmanager
    def transaction(self, thread_id: str) -> Iterator[None]:
        """对单个线程的 surface 做原子更新：异常时回滚。"""

        with self._lock:
            backup = copy.deepcopy(self._surfaces.get(thread_id))
            try:
                yield
            except Exception:
                if backup is None:
                    self._surfaces.pop(thread_id, None)
                else:
                    self._surfaces[thread_id] = backup
                raise
