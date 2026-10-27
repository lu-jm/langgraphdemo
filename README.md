# LangGraph A2UI Agent

基于 **LangGraph + FastAPI** 的 Agent 后端，同时支持：

- **AG-UI** 标准 SSE 流式协议（`ag-ui-langgraph`），可直接对接 CopilotKit 等 AG-UI 客户端；
- **A2UI v0.9** 生成式界面协议，让 Agent 用结构化 JSON 驱动前端渲染原生 UI；
- 会话记忆、工具调用、A2UI surface 管理以及客户端 action 回传。

项目由原有「LangGraph 计算器 Agent」扩展而来，保留了 `add` / `multiply` 数学工具和智谱 GLM 接入，并新增：

- 固定 schema 的计算结果卡片（`render_calculation_card`）；
- 由 LLM 子 Agent 动态生成的完整界面（`generate_a2ui`）；
- A2UI surface / action 的 REST 管理与持久化同步；
- 可切换的内存 / SQLite checkpoint 会话存储。

> 当前 A2UI 目标版本为 **v0.9**，官方 v0.9.1 仅作为后续兼容方向。

---

## 功能特性

| 能力 | 说明 |
| --- | --- |
| 非流式对话 | `POST /api/chat`，返回最终 assistant 消息、工具调用和 A2UI surfaces |
| AG-UI 流式对话 | `POST /api/agent`，返回 `TEXT_MESSAGE_*`、`TOOL_CALL_*`、`STATE_*`、`RUN_*` 等 SSE 事件 |
| 会话管理 | 列出 / 查看 / 删除 thread，支持 `MemorySaver` 与 `AsyncSqliteSaver` |
| A2UI 消息处理 | 官方 JSON Schema 校验、组件图校验、增量更新、事务回滚 |
| A2UI 工具结果 | 工具统一返回 `{"a2ui_operations": [...]}`，兼容前端 A2UI middleware |
| 固定 / 动态 A2UI | 后端代码构建固定卡片；LLM 子 Agent 按自然语言生成任意界面 |
| 可观测性 | 请求 ID、处理耗时、结构化日志、健康检查 |
| 离线可测 | 注入 Fake ChatModel，无需真实 API Key 即可跑完整测试 |

---

## 技术栈

- Python **3.13**
- FastAPI 0.162 + Uvicorn
- LangGraph 1.2 + LangChain 1.x
- `ag-ui-langgraph` / `ag-ui-protocol`
- `ag-ui-a2ui-toolkit`
- Pydantic v2 + pydantic-settings
- JSON Schema（Draft 2020-12）+ jsonschema
- pytest + pytest-asyncio

依赖使用 [uv](https://docs.astral.sh/uv/) 管理。

---

## 快速开始

### 1. 安装依赖

```bash
cd lang-graph
uv sync
```

### 2. 配置模型

复制环境变量模板并填入真实 API Key：

```bash
cp .env.example .env
```

默认使用智谱 GLM：

```dotenv
LLM_PROVIDER=zhipu
ZHIPUAI_API_KEY=your-zhipu-key
ZHIPUAI_MODEL=glm-4.7
```

也可以切换到 OpenAI 或兼容接口：

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=https://api.openai.com/v1
```

> `.env` 已在 `.gitignore` 中忽略，代码中不包含任何硬编码 Key。

### 3. 启动服务

```bash
uv run uvicorn app.main:app --reload
```

或者：

```bash
uv run agent-api
# 或
uv run python main.py --serve
```

启动后：

- Swagger UI：<http://127.0.0.1:8000/docs>
- ReDoc：<http://127.0.0.1:8000/redoc>
- 健康检查：<http://127.0.0.1:8000/health>

未配置 API Key 时应用仍可启动，A2UI REST 接口正常工作；`/api/chat` 会返回
`503 model_not_configured`。

### 4. 命令行单次对话

```bash
uv run python main.py "1 加 1 等于几？"
uv run python main.py "用卡片展示 12 乘 8 的结果"
```

---

## 目录结构

```text
.
├── app/
│   ├── main.py                 # FastAPI 应用工厂、lifespan、异常处理
│   ├── config.py               # pydantic-settings 配置
│   ├── checkpoint.py           # Memory / SQLite checkpointer 工厂
│   ├── errors.py               # 统一业务异常
│   ├── logging_config.py
│   ├── agent/
│   │   ├── graph.py            # LangGraph 图：agent → tools → sync_a2ui
│   │   ├── llm.py              # 智谱 / OpenAI 模型工厂
│   │   ├── prompts.py          # 系统提示词
│   │   ├── state.py            # AgentState（含 a2ui / ag-ui / tools）
│   │   └── tools/
│   │       ├── math.py         # add / multiply
│   │       └── a2ui_tools.py   # 固定卡片 + 动态 A2UI
│   ├── a2ui/
│   │   ├── models.py           # v0.9 四类消息与客户端 action
│   │   ├── validation.py       # 官方 JSON Schema + 组件图校验
│   │   ├── service.py          # A2UI 业务逻辑
│   │   ├── store.py            # 线程隔离 surface/action 存储
│   │   ├── builder.py          # SurfaceBuilder / demo_surface
│   │   ├── toolkit.py          # a2ui_operations 解析与包装
│   │   ├── catalog.py          # Basic Catalog 加载
│   │   └── spec/v0_9/          # vendored 官方 schema
│   ├── api/
│   │   ├── router.py
│   │   ├── dependencies.py
│   │   └── routes/{system,chat,threads,a2ui,agent}.py
│   ├── schemas/                # API 请求 / 响应模型（camelCase）
│   └── services/               # chat / thread 业务服务
├── tests/                      # 44 个离线测试
├── main.py                     # 命令行入口
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## 架构与请求流程

```text
                        ┌──────────────────────────────┐
HTTP / AG-UI Client ──▶ │ FastAPI                      │
                        │  /api/chat                   │
                        │  /api/agent (AG-UI SSE)      │
                        │  /api/a2ui/*                 │
                        └──────────────┬───────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────┐
                        │ LangGraph                    │
                        │                              │
                        │  START → agent               │
                        │           │                  │
                        │     tools_condition          │
                        │        │        │            │
                        │      tools      END          │
                        │        │                     │
                        │   sync_a2ui ───┘             │
                        └──────────────┬───────────────┘
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
          ┌────────────────────┐              ┌────────────────────┐
          │ Checkpointer       │              │ A2UI SurfaceStore  │
          │ memory / sqlite    │              │ thread 隔离        │
          └────────────────────┘              └────────────────────┘
```

### A2UI 工具调用链路

1. 用户请求「把 3 乘 3 的结果做成卡片」；
2. Agent 调用 `render_calculation_card(expression="3 * 3", result="9")`；
3. 工具返回符合 AG-UI / A2UI 生态约定的 JSON：

   ```json
   {
     "a2ui_operations": [
       {"version": "v0.9", "createSurface": {"surfaceId": "calc-xxx", "catalogId": "..."}},
       {"version": "v0.9", "updateComponents": {"surfaceId": "calc-xxx", "components": []}},
       {"version": "v0.9", "updateDataModel": {"surfaceId": "calc-xxx", "path": "/", "value": {}}}
     ]
   }
   ```

4. `sync_a2ui` 节点解析 `a2ui_operations`，写入 SurfaceStore，并把操作列表写入
   state 的 `a2ui` 字段；
5. 前端 A2UI middleware 根据工具结果直接渲染；或通过 `GET /api/a2ui/surfaces`
   拉取服务端保存的 surface；
6. 用户在界面上点击按钮 / 提交表单时，前端把 action 发到
   `POST /api/a2ui/actions`，可选转发给 Agent 继续对话。

### 两类 A2UI 生成方式

- **固定 schema（后端构建）**：`render_calculation_card` 用 `SurfaceBuilder`
  生成稳定的卡片结构，只把计算结果等数据交给前端。
- **动态生成（LLM 子 Agent）**：`generate_a2ui` 来自
  `ag_ui_langgraph.get_a2ui_tools`，根据自然语言生成完整 surface；
  可通过 `ENABLE_DYNAMIC_A2UI=false` 关闭。

---

## API 速览

完整参数与响应模型请查看 `/docs`。

### 系统

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 服务信息与端点列表 |
| GET | `/health` | 模型、A2UI、checkpoint 健康信息 |
| GET | `/ready` | 就绪检查（不进入 OpenAPI） |

### 对话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/chat` | 非流式对话 |
| POST | `/api/agent` | AG-UI SSE 流式对话 |
| GET | `/api/agent/health` | AG-UI Agent 能力信息 |
| GET | `/api/threads` | 列出会话 |
| GET | `/api/threads/{thread_id}` | 会话消息、surfaces、最近 A2UI 操作 |
| DELETE | `/api/threads/{thread_id}` | 删除会话与 surfaces |

### A2UI

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/a2ui/catalog` | Basic Catalog 完整 JSON |
| GET | `/api/a2ui/components` | 组件清单（简要） |
| GET | `/api/a2ui/schema` | 服务端消息 JSON Schema |
| GET | `/api/a2ui/client-schema` | 客户端事件 JSON Schema |
| GET | `/api/a2ui/demo?threadId=demo` | 生成联调 surface |
| GET | `/api/a2ui/surfaces?threadId=...` | 列出线程 surfaces |
| GET | `/api/a2ui/surfaces/{surface_id}?threadId=...` | 获取 surface |
| DELETE | `/api/a2ui/surfaces/{surface_id}?threadId=...` | 删除 surface |
| POST | `/api/a2ui/messages` | 应用 A2UI 消息（单条或批量） |
| POST | `/api/a2ui/actions` | 接收客户端 action，可转发给 Agent |
| GET | `/api/a2ui/actions?threadId=...` | 查看最近 actions |

> 请求与响应中的 JSON 字段统一使用 **camelCase**（如 `threadId`、`surfaceId`），
> 同时兼容 snake_case 入参。

---

## 使用示例

### 1. 非流式对话

```bash
curl -s http://127.0.0.1:8000/api/chat \
  -H 'content-type: application/json' \
  -d '{
    "message": "3 乘 4 等于多少？把结果做成卡片。",
    "threadId": "thread-demo"
  }'
```

响应示例（节选）：

```json
{
  "threadId": "thread-demo",
  "runId": "run-...",
  "message": {
    "role": "assistant",
    "content": "已为你生成计算结果卡片。"
  },
  "toolCalls": [
    {"id": "call-...", "name": "render_calculation_card", "args": {"expression": "3 * 4", "result": "12"}}
  ],
  "a2ui": [
    {
      "surfaceId": "calc-...",
      "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json",
      "components": [{"id": "root", "component": "Card", "child": "content"}],
      "dataModel": {"expression": "3 * 4", "result": "12"}
    }
  ]
}
```

### 2. AG-UI SSE 流式对话

```bash
curl -N http://127.0.0.1:8000/api/agent \
  -H 'accept: text/event-stream' \
  -H 'content-type: application/json' \
  -d '{
    "threadId": "thread-agui",
    "runId": "run-1",
    "messages": [
      {"id": "msg-1", "role": "user", "content": "渲染 3*3 的结果卡片"}
    ],
    "state": {},
    "tools": [],
    "context": [],
    "forwardedProps": {}
  }'
```

事件流通常包含：

```text
RUN_STARTED
STATE_SNAPSHOT
TEXT_MESSAGE_START / CONTENT / END
TOOL_CALL_START / ARGS / END / RESULT
RUN_FINISHED
```

`TOOL_CALL_RESULT.content` 中会包含 `a2ui_operations`，前端 A2UI middleware 可据此
直接渲染界面。默认不输出体积较大的 `RAW` 事件，可用
`AGUI_EMIT_RAW_EVENTS=true` 打开调试。

### 3. 生成并查看 A2UI 示例

```bash
curl -s 'http://127.0.0.1:8000/api/a2ui/demo?threadId=demo'
```

返回 `messages`（可直接交给前端）、`surfaceId`、`surfaces`、`warnings`、`errors`。

### 4. 手动推送 A2UI 消息

```bash
curl -s http://127.0.0.1:8000/api/a2ui/messages \
  -H 'content-type: application/json' \
  -d '{
    "threadId": "demo",
    "strict": true,
    "messages": [
      {
        "version": "v0.9",
        "createSurface": {
          "surfaceId": "hello",
          "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
        }
      },
      {
        "version": "v0.9",
        "updateComponents": {
          "surfaceId": "hello",
          "components": [
            {"id": "root", "component": "Column", "children": ["text"]},
            {"id": "text", "component": "Text", "text": "Hello A2UI", "variant": "h2"}
          ]
        }
      }
    ]
  }'
```

严格模式下重复 `createSurface` 返回 `409 surface_already_exists`；非严格模式会
重置同名 surface。

### 5. 回传客户端 action

```bash
curl -s http://127.0.0.1:8000/api/a2ui/actions \
  -H 'content-type: application/json' \
  -d '{
    "threadId": "demo",
    "forwardToAgent": false,
    "action": {
      "name": "submitDemoForm",
      "surfaceId": "demo-xxxxxxxx",
      "sourceComponentId": "submit_button",
      "timestamp": "2026-10-27T00:00:00Z",
      "context": {"name": "Alice"}
    }
  }'
```

`forwardToAgent=true` 时，action 会被转换成一条用户消息交给 Agent，并在响应的
`chat` 字段返回对话结果（需要配置模型）。

---

## 配置项

所有配置均可通过环境变量或 `.env` 设置，字段名大小写不敏感。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `LangGraph A2UI Agent` | 应用名称 |
| `APP_VERSION` | `0.1.0` | 版本号 |
| `ENVIRONMENT` | `development` | `development` / `test` / `production` |
| `DEBUG` | `false` | 调试模式（CLI 启动时开启 reload） |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 监听地址 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CORS_ORIGINS` | `*` | 允许来源，逗号分隔；生产环境请收紧 |
| `LLM_PROVIDER` | `zhipu` | `zhipu` 或 `openai` |
| `ZHIPUAI_API_KEY` | 空 | 智谱 API Key |
| `ZHIPUAI_MODEL` | `glm-4.7` | 智谱模型名 |
| `ZHIPUAI_TEMPERATURE` | `0.3` | 采样温度 |
| `OPENAI_API_KEY` | 空 | OpenAI / 兼容接口 Key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI 模型名 |
| `OPENAI_BASE_URL` | 空 | 自定义兼容接口地址 |
| `OPENAI_TEMPERATURE` | `0.3` | 采样温度 |
| `AGENT_RECURSION_LIMIT` | `30` | LangGraph 最大步数 |
| `AGENT_PARALLEL_TOOL_CALLS` | `false` | 是否允许并行工具调用 |
| `ENABLE_DYNAMIC_A2UI` | `true` | 是否启用 `generate_a2ui` 动态界面 |
| `AGUI_EMIT_RAW_EVENTS` | `false` | 是否输出 AG-UI `RAW` 事件 |
| `AGUI_EMIT_SUBAGENT_EVENTS` | `false` | 是否输出子 Agent 事件 |
| `A2UI_CATALOG_ID` | Basic Catalog URL | 默认 catalog |
| `A2UI_MAX_SURFACES_PER_THREAD` | `50` | 单线程 surface 上限（FIFO 淘汰） |
| `A2UI_MAX_ACTIONS_PER_THREAD` | `100` | 单线程 action 记录上限 |
| `CHECKPOINT_BACKEND` | `memory` | `memory` 或 `sqlite` |
| `CHECKPOINT_SQLITE_PATH` | `data/checkpoints.sqlite` | SQLite 文件路径 |
| `DOCS_URL` / `REDOC_URL` / `OPENAPI_URL` | `/docs` / `/redoc` / `/openapi.json` | 文档路径 |

### 持久化

```dotenv
CHECKPOINT_BACKEND=sqlite
CHECKPOINT_SQLITE_PATH=data/checkpoints.sqlite
```

SQLite checkpointer 在 lifespan 中通过 `AsyncExitStack` 创建并自动关闭，适合
单机部署。A2UI surface 目前存放在进程内 `SurfaceStore` 中，重启后清空；如需
多实例生产部署，可替换 `app/a2ui/store.py` 为 Redis / 数据库实现。

---

## 测试

```bash
uv run pytest
```

当前包含 44 个测试，覆盖：

- A2UI 消息模型、camelCase 序列化、官方 Schema 校验；
- SurfaceBuilder 与组件图（root、循环、悬空引用）；
- Surface CRUD、事务回滚、线程隔离、action 记录；
- FastAPI 系统 / 对话 / 线程 / A2UI 路由；
- AG-UI SSE 事件流与 `a2ui_operations` 工具结果；
- 数学工具与固定卡片工具。

测试通过注入 Fake ChatModel 运行，不需要真实 API Key。测试文件：

```text
tests/
├── conftest.py             # 应用 / graph / service fixtures
├── helpers.py              # FakeToolChatModel、SSE 解析
├── test_system.py
├── test_a2ui_models.py
├── test_a2ui_service.py
├── test_a2ui_api.py
├── test_chat_api.py
├── test_agui_endpoint.py
└── test_tools.py
```

---

## Docker

```bash
docker build -t langgraph-a2ui .
docker run --rm -p 8000:8000 --env-file .env langgraph-a2ui
```

镜像基于 `python:3.13-slim`，使用 uv 安装锁定依赖。

---

## 生产注意事项

1. **API Key**：只通过环境变量 / Secret Manager 注入，不要提交 `.env`。
2. **CORS**：将 `CORS_ORIGINS` 设置为具体前端域名，不要使用 `*`。
3. **状态存储**：`MemorySaver` 和 `SurfaceStore` 都是进程内存储，多 worker /
   多实例部署时需要共享存储（Redis / PostgreSQL），否则会话和 surface 会分裂。
4. **SQLite**：适合单机；多实例请换成服务型 checkpointer。
5. **AG-UI 事件**：生产环境保持 `AGUI_EMIT_RAW_EVENTS=false`，减少带宽和日志体积。
6. **超时与限流**：建议在网关层为 `/api/agent` 和 `/api/chat` 增加超时、限流与
   鉴权；当前示例未内置认证。
7. **A2UI 校验**：所有入口消息都会经过官方 JSON Schema 与组件图校验；自定义
   catalog 会使用宽松组件校验，请在前端做好渲染兜底。
8. **日志**：通过 `LOG_LEVEL` 控制；请求响应头包含 `X-Request-ID` 与
   `X-Process-Time-Ms`，便于链路排查。

---

## 相关协议

- AG-UI：<https://docs.ag-ui.com/>
- A2UI：<https://a2ui.org/>
- LangGraph：<https://langchain-ai.github.io/langgraph/>
