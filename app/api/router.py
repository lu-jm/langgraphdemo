"""聚合 API 路由。"""

from fastapi import APIRouter

from app.api.routes import a2ui, agent, chat, threads

api_router = APIRouter()
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(threads.router, tags=["threads"])
api_router.include_router(a2ui.router, tags=["a2ui"])
api_router.include_router(agent.router, tags=["ag-ui"])
