import type {
  A2UIActionPayload,
  A2UIActionResponse,
  A2UIMessage,
  AgentEvent,
  DemoResponse,
  HealthInfo,
  ThreadDetail,
} from './types'

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
export const API_BASE = RAW_BASE.replace(/\/+$/, '')

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

function errorMessage(status: number, body: unknown): string {
  if (typeof body === 'string' && body.trim()) return `${status} ${body}`
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>
    const error = record.error
    if (error && typeof error === 'object') {
      const message = (error as Record<string, unknown>).message
      if (typeof message === 'string') return message
    }
    if (typeof record.detail === 'string') return record.detail
  }
  return `请求失败（HTTP ${status}）`
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init)
  const body = await parseBody(response)
  if (!response.ok) {
    throw new Error(errorMessage(response.status, body))
  }
  return body as T
}

const JSON_HEADERS = { 'content-type': 'application/json' }

export function fetchHealth(): Promise<HealthInfo> {
  return request<HealthInfo>('/health')
}

export async function fetchThread(threadId: string): Promise<ThreadDetail | null> {
  const response = await fetch(apiUrl(`/api/threads/${encodeURIComponent(threadId)}`))
  if (response.status === 404) return null
  const body = await parseBody(response)
  if (!response.ok) throw new Error(errorMessage(response.status, body))
  return body as ThreadDetail
}

export function deleteThread(threadId: string): Promise<void> {
  return request<void>(`/api/threads/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
  })
}

export function fetchDemoSurface(threadId: string): Promise<DemoResponse> {
  return request<DemoResponse>(
    `/api/a2ui/demo?threadId=${encodeURIComponent(threadId)}`,
  )
}

export function sendA2UIAction(
  threadId: string,
  action: A2UIActionPayload,
  forwardToAgent: boolean,
  signal?: AbortSignal,
): Promise<A2UIActionResponse> {
  return request<A2UIActionResponse>('/api/a2ui/actions', {
    method: 'POST',
    headers: JSON_HEADERS,
    signal,
    body: JSON.stringify({ threadId, action, forwardToAgent }),
  })
}

export interface StreamOptions {
  threadId: string
  text: string
  signal?: AbortSignal
  onEvent: (event: AgentEvent) => void
}

/** 调用 AG-UI SSE 端点，逐条解析 data: {...} 事件。 */
export async function streamAgentRun({
  threadId,
  text,
  signal,
  onEvent,
}: StreamOptions): Promise<void> {
  const response = await fetch(apiUrl('/api/agent'), {
    method: 'POST',
    headers: {
      accept: 'text/event-stream',
      'content-type': 'application/json',
    },
    signal,
    body: JSON.stringify({
      threadId,
      runId: `run-${crypto.randomUUID()}`,
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: text,
        },
      ],
      state: {},
      tools: [],
      context: [],
      forwardedProps: {},
    }),
  })

  if (!response.ok) {
    const body = await parseBody(response)
    throw new Error(errorMessage(response.status, body))
  }
  if (!response.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (chunk: string) => {
    const dataLines = chunk
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
    if (!dataLines.length) return
    const data = dataLines.join('\n')
    if (!data || data === '[DONE]') return
    try {
      onEvent(JSON.parse(data) as AgentEvent)
    } catch {
      // 忽略无法解析的心跳/注释事件
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let separator = buffer.indexOf('\n\n')
      while (separator >= 0) {
        const chunk = buffer.slice(0, separator)
        buffer = buffer.slice(separator + 2)
        dispatch(chunk)
        separator = buffer.indexOf('\n\n')
      }
    }
    if (buffer.trim()) dispatch(buffer)
  } finally {
    reader.releaseLock()
  }
}

export type { A2UIMessage }
