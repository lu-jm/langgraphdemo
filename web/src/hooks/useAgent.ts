/** 对话状态管理：AG-UI SSE、A2UI 操作、action 回传与线程恢复。 */

import { useCallback, useEffect, useRef, useState } from 'react'

import {
  deleteThread as deleteThreadApi,
  fetchDemoSurface,
  fetchHealth,
  fetchThread,
  sendA2UIAction,
  streamAgentRun,
} from '../api/client'
import type {
  A2UIMessage,
  AgentEvent,
  HealthInfo,
  JsonObject,
  StateSnapshotEvent,
  ThreadDetail,
  ToolCallResultEvent,
} from '../api/types'
import { applyOperations, mergeServerSurfaces, removeSurface, type SurfaceMap } from '../a2ui/apply'
import { setByPointer } from '../a2ui/jsonPointer'

export interface ToolCallView {
  id: string
  name: string
  argsText: string
  args?: JsonObject
  result?: string
  status: 'running' | 'done'
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: number
  toolCalls: ToolCallView[]
  surfaceIds: string[]
  streaming?: boolean
  error?: string
}

export interface SurfaceActionInput {
  name: string
  context: JsonObject
  sourceComponentId: string
}

const DEFAULT_THREAD = `web-${crypto.randomUUID().slice(0, 8)}`

function loadThreadId(): string {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('threadId')
    if (fromUrl) return fromUrl
  } catch {
    // URL 不可用时退回 localStorage
  }
  try {
    return localStorage.getItem('a2ui.threadId') || DEFAULT_THREAD
  } catch {
    return DEFAULT_THREAD
  }
}

function saveThreadId(threadId: string): void {
  try {
    localStorage.setItem('a2ui.threadId', threadId)
  } catch {
    // localStorage 不可用时忽略
  }
  try {
    const url = new URL(window.location.href)
    url.searchParams.set('threadId', threadId)
    window.history.replaceState(null, '', url)
  } catch {
    // 忽略 URL 更新失败
  }
}

function contentToText(content: unknown): string {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === 'string') return part
        if (part && typeof part === 'object' && 'text' in part) {
          return String((part as { text: unknown }).text)
        }
        return ''
      })
      .join('')
  }
  if (content === null || content === undefined) return ''
  return JSON.stringify(content)
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

function extractOperations(content: string): A2UIMessage[] {
  const parsed = parseJson(content)
  if (!parsed) return []
  if (Array.isArray(parsed)) return parsed as A2UIMessage[]
  if (typeof parsed === 'object' && parsed !== null) {
    const operations = (parsed as { a2ui_operations?: unknown }).a2ui_operations
    if (Array.isArray(operations)) return operations as A2UIMessage[]
  }
  return []
}

function threadToMessages(thread: ThreadDetail): ChatMessage[] {
  const messages: ChatMessage[] = []
  for (const message of thread.messages) {
    const content = contentToText(message.content)
    if (message.role === 'user') {
      messages.push({
        id: message.id || crypto.randomUUID(),
        role: 'user',
        content,
        createdAt: Date.now(),
        toolCalls: [],
        surfaceIds: [],
      })
      continue
    }
    if (message.role !== 'assistant') continue
    const toolCalls: ToolCallView[] = (message.toolCalls ?? []).map((call) => ({
      id: call.id,
      name: call.name,
      argsText: JSON.stringify(call.args ?? {}),
      args: call.args,
      status: 'done',
    }))
    if (!content.trim() && !toolCalls.length) continue
    messages.push({
      id: message.id || crypto.randomUUID(),
      role: 'assistant',
      content,
      createdAt: Date.now(),
      toolCalls,
      surfaceIds: [],
    })
  }

  const surfaceIds = thread.surfaces.map((surface) => surface.surfaceId)
  if (surfaceIds.length) {
    const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant')
    if (lastAssistant) lastAssistant.surfaceIds = surfaceIds
    else
      messages.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        createdAt: Date.now(),
        toolCalls: [],
        surfaceIds,
      })
  }
  return messages
}

export function useAgent() {
  const [threadId, setThreadId] = useState(loadThreadId)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [surfaces, setSurfaces] = useState<SurfaceMap>({})
  const [busy, setBusy] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [backendError, setBackendError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const surfacesRef = useRef<SurfaceMap>({})
  const busyRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const toastTimerRef = useRef<number | null>(null)
  const initialThreadRef = useRef(threadId)

  const showToast = useCallback((message: string) => {
    setToast(message)
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current)
    toastTimerRef.current = window.setTimeout(() => setToast(null), 3200)
  }, [])

  const refreshHealth = useCallback(async () => {
    try {
      const info = await fetchHealth()
      setHealth(info)
      setBackendError(null)
    } catch (error) {
      setHealth(null)
      setBackendError(error instanceof Error ? error.message : '无法连接后端服务')
    }
  }, [])

  useEffect(() => {
    void refreshHealth()
    const timer = window.setInterval(() => void refreshHealth(), 30_000)
    return () => window.clearInterval(timer)
  }, [refreshHealth])

  useEffect(() => {
    saveThreadId(threadId)
  }, [threadId])

  useEffect(() => {
    const thread = initialThreadRef.current
    let cancelled = false

    fetchThread(thread)
      .then((detail) => {
        if (cancelled || !detail) return
        setMessages(threadToMessages(detail))
        const next: SurfaceMap = {}
        for (const surface of detail.surfaces) next[surface.surfaceId] = surface
        surfacesRef.current = next
        setSurfaces(next)
      })
      .catch(() => {
        // 恢复失败时保持空会话
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const patchMessage = useCallback(
    (id: string, patch: (message: ChatMessage) => ChatMessage) => {
      setMessages((current) =>
        current.map((message) => (message.id === id ? patch(message) : message)),
      )
    },
    [],
  )

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || busyRef.current) return

      busyRef.current = true
      setBusy(true)

      const runId = `assistant-${crypto.randomUUID()}`
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        createdAt: Date.now(),
        toolCalls: [],
        surfaceIds: [],
      }
      const assistantMessage: ChatMessage = {
        id: runId,
        role: 'assistant',
        content: '',
        createdAt: Date.now(),
        toolCalls: [],
        surfaceIds: [],
        streaming: true,
      }
      setMessages((current) => [...current, userMessage, assistantMessage])

      const controller = new AbortController()
      abortRef.current = controller
      const runSurfaceIds = new Set<string>()
      const appliedOperationKeys = new Set<string>()
      const preexistingSurfaceIds = new Set(Object.keys(surfacesRef.current))

      const attachSurfaces = () => {
        patchMessage(runId, (message) => ({
          ...message,
          surfaceIds: Array.from(runSurfaceIds).filter((id) => Boolean(surfacesRef.current[id])),
        }))
      }

      const applyLive = (operations: unknown) => {
        if (!Array.isArray(operations) || !operations.length) return
        const key = JSON.stringify(operations)
        if (appliedOperationKeys.has(key)) return
        appliedOperationKeys.add(key)

        const result = applyOperations(surfacesRef.current, operations as A2UIMessage[])
        surfacesRef.current = result.surfaces
        setSurfaces(result.surfaces)
        for (const id of result.touched) {
          if (result.surfaces[id]) runSurfaceIds.add(id)
        }
        attachSurfaces()
      }

      const handleEvent = (event: AgentEvent) => {
        switch (event.type) {
          case 'TEXT_MESSAGE_CONTENT': {
            const delta = typeof event.delta === 'string' ? event.delta : ''
            if (!delta) return
            patchMessage(runId, (message) => ({
              ...message,
              content: message.content + delta,
            }))
            return
          }
          case 'TOOL_CALL_START': {
            const toolCallId = String(event.toolCallId ?? crypto.randomUUID())
            const name = String(event.toolCallName ?? 'tool')
            patchMessage(runId, (message) => ({
              ...message,
              toolCalls: [
                ...message.toolCalls,
                { id: toolCallId, name, argsText: '', status: 'running' },
              ],
            }))
            return
          }
          case 'TOOL_CALL_ARGS': {
            const toolCallId = String(event.toolCallId ?? '')
            const delta = typeof event.delta === 'string' ? event.delta : ''
            if (!toolCallId || !delta) return
            patchMessage(runId, (message) => ({
              ...message,
              toolCalls: message.toolCalls.map((call) =>
                call.id === toolCallId ? { ...call, argsText: call.argsText + delta } : call,
              ),
            }))
            return
          }
          case 'TOOL_CALL_END': {
            const toolCallId = String(event.toolCallId ?? '')
            patchMessage(runId, (message) => ({
              ...message,
              toolCalls: message.toolCalls.map((call) => {
                if (call.id !== toolCallId) return call
                const args = parseJson(call.argsText)
                return {
                  ...call,
                  args:
                    args && typeof args === 'object' && !Array.isArray(args)
                      ? (args as JsonObject)
                      : call.args,
                }
              }),
            }))
            return
          }
          case 'TOOL_CALL_RESULT': {
            const result = event as ToolCallResultEvent
            const content = typeof result.content === 'string' ? result.content : ''
            patchMessage(runId, (message) => ({
              ...message,
              toolCalls: message.toolCalls.map((call) =>
                call.id === result.toolCallId
                  ? { ...call, result: content, status: 'done' }
                  : call,
              ),
            }))
            applyLive(extractOperations(content))
            return
          }
          case 'STATE_SNAPSHOT': {
            const snapshot = (event as StateSnapshotEvent).snapshot
            if (snapshot && Array.isArray(snapshot.a2ui)) applyLive(snapshot.a2ui)
            return
          }
          case 'RUN_ERROR': {
            const message =
              typeof event.message === 'string' ? event.message : 'Agent 运行失败'
            patchMessage(runId, (current) => ({
              ...current,
              streaming: false,
              error: message,
            }))
            return
          }
          case 'RUN_FINISHED': {
            patchMessage(runId, (current) => ({ ...current, streaming: false }))
            return
          }
          default:
            return
        }
      }

      try {
        await streamAgentRun({
          threadId,
          text: trimmed,
          signal: controller.signal,
          onEvent: handleEvent,
        })
        patchMessage(runId, (message) => ({ ...message, streaming: false }))
      } catch (error) {
        if (controller.signal.aborted) {
          patchMessage(runId, (message) => ({ ...message, streaming: false }))
        } else {
          const message = error instanceof Error ? error.message : '请求失败'
          patchMessage(runId, (current) => ({
            ...current,
            streaming: false,
            error: message,
          }))
        }
      } finally {
        busyRef.current = false
        setBusy(false)
        abortRef.current = null

        // 以服务端 surface store 为准做一次对账（含动态 A2UI 子 Agent 的结果）。
        try {
          const detail = await fetchThread(threadId)
          if (detail?.surfaces.length) {
            const merged = mergeServerSurfaces(surfacesRef.current, detail.surfaces)
            surfacesRef.current = merged.surfaces
            setSurfaces(merged.surfaces)
            for (const surface of detail.surfaces) {
              if (!preexistingSurfaceIds.has(surface.surfaceId)) {
                runSurfaceIds.add(surface.surfaceId)
              }
            }
            attachSurfaces()
          }
        } catch {
          // 对账失败不影响当前会话
        }
      }
    },
    [patchMessage, threadId],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const newThread = useCallback(() => {
    abortRef.current?.abort()
    const next = `web-${crypto.randomUUID().slice(0, 8)}`
    saveThreadId(next)
    setThreadId(next)
    setMessages([])
    setSurfaces({})
    surfacesRef.current = {}
    showToast('已创建新会话')
  }, [showToast])

  const loadDemo = useCallback(async () => {
    if (busyRef.current) return
    try {
      const demo = await fetchDemoSurface(threadId)
      const result = applyOperations(surfacesRef.current, demo.messages)
      surfacesRef.current = result.surfaces
      setSurfaces(result.surfaces)
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '已加载 A2UI 联调示例。你可以填写表单并点击「提交」，观察 action 回传与 Agent 响应。',
          createdAt: Date.now(),
          toolCalls: [],
          surfaceIds: [demo.surfaceId],
        },
      ])
      showToast('A2UI 示例已加载')
    } catch (error) {
      showToast(error instanceof Error ? error.message : '加载示例失败')
    }
  }, [showToast, threadId])

  const updateSurfaceData = useCallback(
    (surfaceId: string, path: string, value: unknown) => {
      const surface = surfacesRef.current[surfaceId]
      if (!surface) return
      const next: SurfaceMap = {
        ...surfacesRef.current,
        [surfaceId]: {
          ...surface,
          dataModel: setByPointer(surface.dataModel, path, value),
        },
      }
      surfacesRef.current = next
      setSurfaces(next)
    },
    [],
  )

  const deleteThreadSurface = useCallback(
    async (surfaceId: string) => {
      try {
        await fetch(
          `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/a2ui/surfaces/${encodeURIComponent(surfaceId)}?threadId=${encodeURIComponent(threadId)}`,
          { method: 'DELETE' },
        )
      } catch {
        // 仅隐藏，忽略删除失败
      }
    },
    [threadId],
  )

  const hideSurface = useCallback(
    (surfaceId: string) => {
      const next = removeSurface(surfacesRef.current, surfaceId)
      surfacesRef.current = next
      setSurfaces(next)
      setMessages((current) =>
        current.map((message) => ({
          ...message,
          surfaceIds: message.surfaceIds.filter((id) => id !== surfaceId),
        })),
      )
      void deleteThreadSurface(surfaceId)
    },
    [deleteThreadSurface],
  )

  const handleAction = useCallback(
    async (surfaceId: string, action: SurfaceActionInput) => {
      if (action.name === 'copyResult') {
        const value = action.context.result
        const text = typeof value === 'string' ? value : JSON.stringify(value)
        try {
          await navigator.clipboard.writeText(text)
          showToast('已复制到剪贴板')
        } catch {
          showToast(`复制失败：${text}`)
        }
        return
      }

      if (busyRef.current) return
      busyRef.current = true
      setBusy(true)

      const controller = new AbortController()
      abortRef.current = controller
      const placeholderId = `action-${crypto.randomUUID()}`
      const contextText = JSON.stringify(action.context)
      const knownSurfaceIds = new Set(Object.keys(surfacesRef.current))
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: `【界面操作】${action.name} ${contextText}`,
          createdAt: Date.now(),
          toolCalls: [],
          surfaceIds: [],
        },
        {
          id: placeholderId,
          role: 'assistant',
          content: '',
          createdAt: Date.now(),
          toolCalls: [],
          surfaceIds: [],
          streaming: true,
        },
      ])

      try {
        const response = await sendA2UIAction(
          threadId,
          {
            name: action.name,
            surfaceId,
            sourceComponentId: action.sourceComponentId,
            timestamp: new Date().toISOString(),
            context: action.context,
          },
          true,
          controller.signal,
        )

        const merged = mergeServerSurfaces(surfacesRef.current, response.surfaces)
        surfacesRef.current = merged.surfaces
        setSurfaces(merged.surfaces)

        if (response.chat) {
          const chat = response.chat
          const chatSurfaces = mergeServerSurfaces(surfacesRef.current, chat.a2ui)
          surfacesRef.current = chatSurfaces.surfaces
          setSurfaces(chatSurfaces.surfaces)

          const content = contentToText(chat.message.content)
          // 只把本次 action 新产生的 surface 挂到该条消息，避免重复渲染历史界面。
          const surfaceIds = chat.a2ui
            .map((surface) => surface.surfaceId)
            .filter((id) => !knownSurfaceIds.has(id))
          patchMessage(placeholderId, (message) => ({
            ...message,
            content,
            streaming: false,
            toolCalls: (chat.toolCalls ?? []).map((call) => ({
              id: call.id,
              name: call.name,
              argsText: JSON.stringify(call.args ?? {}),
              args: call.args,
              status: 'done',
            })),
            surfaceIds,
          }))
        } else {
          patchMessage(placeholderId, (message) => ({
            ...message,
            content: `操作「${action.name}」已提交。`,
            streaming: false,
          }))
        }
      } catch (error) {
        if (controller.signal.aborted) {
          patchMessage(placeholderId, (message) => ({
            ...message,
            content: '操作已取消。',
            streaming: false,
          }))
        } else {
          const message = error instanceof Error ? error.message : '操作提交失败'
          patchMessage(placeholderId, (current) => ({
            ...current,
            streaming: false,
            error: message,
          }))
          showToast(`操作已发送，但 Agent 处理失败：${message}`)
        }
      } finally {
        busyRef.current = false
        setBusy(false)
        abortRef.current = null
      }
    },
    [patchMessage, showToast, threadId],
  )

  const clearThread = useCallback(async () => {
    abortRef.current?.abort()
    try {
      await deleteThreadApi(threadId)
    } catch {
      // 后端未启动时仍允许清空本地会话
    }
    const next = `web-${crypto.randomUUID().slice(0, 8)}`
    saveThreadId(next)
    setThreadId(next)
    setMessages([])
    setSurfaces({})
    surfacesRef.current = {}
    showToast('会话已清空')
  }, [showToast, threadId])

  return {
    threadId,
    messages,
    surfaces,
    busy,
    restoring,
    health,
    backendError,
    toast,
    send,
    stop,
    newThread,
    clearThread,
    loadDemo,
    updateSurfaceData,
    handleAction,
    hideSurface,
    refreshHealth,
    notify: showToast,
    dismissToast: () => setToast(null),
  }
}
