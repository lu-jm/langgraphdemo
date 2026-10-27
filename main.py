"""命令行入口。

用法：

    uv run python main.py "1 加 1 等于几？"
    uv run python main.py --serve
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.a2ui.service import A2UIService
from app.agent.graph import build_graph
from app.config import get_settings
from app.errors import ModelNotConfiguredError


async def _run_once(question: str) -> None:
    settings = get_settings()
    if not settings.model_configured:
        raise ModelNotConfiguredError()

    service = A2UIService(default_catalog_id=settings.a2ui_catalog_id)
    graph = build_graph(
        settings,
        checkpointer=MemorySaver(),
        a2ui_service=service,
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=question)]},
        {
            "configurable": {"thread_id": "cli"},
            "recursion_limit": settings.agent_recursion_limit,
        },
    )

    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage) and message.content:
            print(message.content)
            break
    else:
        print("（Agent 没有返回文本内容）")

    surfaces = service.list_surfaces("cli")
    if surfaces:
        print(f"\n已生成 {len(surfaces)} 个 A2UI surface：")
        for surface in surfaces:
            print(f"- {surface.surface_id}（{len(surface.components)} 个组件）")


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph + A2UI Agent CLI")
    parser.add_argument(
        "question",
        nargs="?",
        default="1 加 1 等于几？",
        help="要问 Agent 的问题",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="启动 FastAPI 服务而不是执行单次问答",
    )
    args = parser.parse_args()

    if args.serve:
        from app.main import run

        run()
        return

    try:
        asyncio.run(_run_once(args.question))
    except ModelNotConfiguredError as exc:
        print(f"错误：{exc.message}\n{exc.details}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
