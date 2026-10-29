# A2UI Agent Studio（前端）

基于 **React 19 + TypeScript + Vite** 的对话前端，对接本仓库的 FastAPI / LangGraph 后端：

- **流式对话**：调用 `POST /api/agent`（AG-UI SSE），实时渲染 `TEXT_MESSAGE_*`；
- **Markdown 渲染**：`react-markdown` + `remark-gfm`，支持表格、代码块、列表、链接等；
- **A2UI v0.9 渲染**：解析 `TOOL_CALL_RESULT` / `STATE_SNAPSHOT` 中的 `a2ui_operations` 或 `state.a2ui`，用原生 React 组件渲染 Basic Catalog；
- **交互回传**：表单、按钮 action 通过 `POST /api/a2ui/actions` 回传，可转发给 Agent 继续对话；
- **会话恢复**：线程 ID 持久化到 `localStorage`，刷新后通过 `GET /api/threads/{id}` 恢复消息与 surfaces；也支持用 `?threadId=xxx` 直接打开指定会话；
- **健康状态**：轮询 `/health`，展示模型 provider / model 与连接状态。

## 快速开始

先启动后端（仓库根目录）：

```bash
uv run uvicorn app.main:app --reload
# 默认 http://127.0.0.1:8000
```

再启动前端：

```bash
cd web
npm install
npm run dev
# http://127.0.0.1:5173
```

开发服务器会把 `/api`、`/health`、`/ready` 代理到 `http://127.0.0.1:8000`，
无需处理 CORS。若后端地址不同，复制环境变量模板：

```bash
cp .env.example .env
# VITE_PROXY_TARGET=http://127.0.0.1:8000
```

## 构建与部署

```bash
npm run build      # 产物在 web/dist
npm run preview    # 本地预览产物
```

生产环境有两种部署方式：

1. **同源部署**：把 `dist/` 交给 Nginx，并将 `/api`、`/health` 反向代理到 FastAPI；
2. **分离部署**：构建时设置 `VITE_API_BASE_URL=https://api.example.com`，并在后端
   的 `CORS_ORIGINS` 中允许前端域名。

## A2UI 渲染支持

Basic Catalog 组件均已实现：

`Text`、`Image`、`Icon`、`Video`、`AudioPlayer`、`Row`、`Column`、`List`、`Card`、
`Tabs`、`Modal`、`Divider`、`Button`、`TextField`、`CheckBox`、`ChoicePicker`、
`Slider`、`DateTimeInput`。

同时支持：

- `DynamicString` / `DynamicNumber` / `DynamicBoolean` / `DynamicStringList` 的
  字面量、`{ "path": "/x" }` 数据绑定与 `{ "call": ... }` 函数调用；
- 常用 catalog 函数：`required`、`regex`、`length`、`numeric`、`email`、
  `formatString`、`formatNumber`、`formatCurrency`、`formatDate`、`pluralize`、
  `and` / `or` / `not`、`openUrl`；
- `List` / `Row` / `Column` 的模板子节点（`{ componentId, path }`）；
- action：`event` 类型回传后端，`functionCall` 类型本地执行（如 `openUrl`）；
- 内置 `copyResult` action：直接复制结果到剪贴板，不调用后端。

未实现的组件会显示明显的兜底提示，不会导致整页崩溃。

## 目录

```text
web/
├── src/
│   ├── App.tsx                 # 页面布局、消息列表、空状态
│   ├── api/
│   │   ├── client.ts           # REST + AG-UI SSE 客户端
│   │   └── types.ts            # 与后端一致的协议类型
│   ├── a2ui/
│   │   ├── SurfaceView.tsx     # A2UI 组件树渲染器
│   │   ├── icons.tsx           # catalog 图标名 -> lucide 图标
│   │   ├── resolve.ts          # 数据绑定 / 函数调用解析
│   │   ├── jsonPointer.ts      # JSON Pointer 读写
│   │   └── apply.ts            # createSurface / updateComponents 等操作
│   ├── components/
│   │   ├── Composer.tsx        # 输入框与发送/停止
│   │   ├── Markdown.tsx        # Markdown 渲染
│   │   └── ToolCallList.tsx    # 工具调用折叠面板
│   ├── hooks/useAgent.ts       # 会话状态、SSE、action、线程恢复
│   ├── index.css               # 应用样式
│   └── a2ui.css                # A2UI 组件样式
├── vite.config.ts              # 开发代理配置
└── package.json
```

## 说明

- 对话请求只发送当前一条用户消息，历史消息由后端 LangGraph checkpointer 维护；
- `RUN_ERROR` 会显示在对应 assistant 消息内，保留已有内容便于排查；
- 点击 A2UI surface 右上角 `{}` 可查看原始组件 JSON，垃圾桶按钮会同时删除服务端 surface。
