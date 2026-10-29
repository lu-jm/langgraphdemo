/** 与后端 app/schemas 对应的前端类型定义。 */

export type JsonObject = Record<string, unknown>

export interface SurfaceTheme {
  primaryColor?: string
  agentDisplayName?: string
  [key: string]: unknown
}

export interface A2UIComponent {
  id: string
  component: string
  [key: string]: unknown
}

export interface A2UISurface {
  surfaceId: string
  catalogId: string
  theme?: SurfaceTheme | null
  sendDataModel?: boolean
  components: A2UIComponent[]
  dataModel: unknown
  revision?: number
}

/** 后端 SurfacePayload（GET /api/a2ui/surfaces、/api/threads/{id}）。 */
export interface ServerSurface extends A2UISurface {
  threadId: string
  createdAt?: string
  updatedAt?: string
}

/** A2UI 服务端 -> 客户端消息信封，四个操作字段中恰好出现一个。 */
export interface A2UIMessage {
  version: 'v0.9'
  createSurface?: {
    surfaceId: string
    catalogId: string
    theme?: SurfaceTheme | null
    sendDataModel?: boolean
  }
  updateComponents?: {
    surfaceId: string
    components: A2UIComponent[]
  }
  updateDataModel?: {
    surfaceId: string
    path?: string
    value?: unknown
  }
  deleteSurface?: { surfaceId: string }
}

export interface ToolCallPayload {
  id: string
  name: string
  args: JsonObject
}

export interface ChatMessagePayload {
  id?: string | null
  role: 'system' | 'user' | 'assistant' | 'tool' | 'developer'
  content: unknown
  name?: string | null
  toolCallId?: string | null
  toolCalls?: ToolCallPayload[]
}

export interface ChatResponse {
  threadId: string
  runId: string
  message: ChatMessagePayload
  toolCalls: ToolCallPayload[]
  a2ui: ServerSurface[]
  warnings?: string[]
}

export interface ThreadDetail {
  threadId: string
  messages: ChatMessagePayload[]
  surfaces: ServerSurface[]
  a2uiOperations: A2UIMessage[]
}

export interface HealthInfo {
  status: string
  version: string
  environment: string
  model: { provider: string; name: string; configured: boolean }
  a2ui: { protocolVersion: string; catalogId: string }
  checkpoint: { backend: string }
}

export interface DemoResponse {
  threadId: string
  surfaceId: string
  messages: A2UIMessage[]
  surfaces: ServerSurface[]
  warnings: unknown[]
  errors: unknown[]
}

export interface A2UIActionPayload {
  name: string
  surfaceId: string
  sourceComponentId: string
  timestamp: string
  context: JsonObject
}

export interface A2UIActionResponse {
  accepted: boolean
  action: A2UIActionPayload
  surfaces: ServerSurface[]
  chat?: ChatResponse | null
}

/** AG-UI SSE 事件（只声明前端会用到的字段）。 */
export interface AgentEvent {
  type: string
  [key: string]: unknown
}

export interface ToolCallResultEvent extends AgentEvent {
  type: 'TOOL_CALL_RESULT'
  toolCallId: string
  content: string
}

export interface StateSnapshotEvent extends AgentEvent {
  type: 'STATE_SNAPSHOT'
  snapshot?: { a2ui?: A2UIMessage[]; messages?: unknown[] }
}
