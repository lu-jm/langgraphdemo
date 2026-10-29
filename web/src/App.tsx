import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  Check,
  Copy,
  LayoutPanelTop,
  MessageSquare,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  WifiOff,
} from 'lucide-react'

import { Markdown } from './components/Markdown'
import { Composer } from './components/Composer'
import { ToolCallList } from './components/ToolCallList'
import { SurfaceView } from './a2ui/SurfaceView'
import { useAgent, type ChatMessage } from './hooks/useAgent'
import type { SurfaceMap } from './a2ui/apply'

const SUGGESTIONS = [
  {
    title: '计算结果卡片',
    prompt: '帮我计算 128 乘以 37，并把结果做成 A2UI 卡片。',
  },
  {
    title: '生成注册表单',
    prompt: '用 A2UI 生成一个注册表单，包含姓名、邮箱、订阅选项和提交按钮。',
  },
  {
    title: '任务进度面板',
    prompt: '做一个展示本周任务进度的 A2UI 界面，包含完成率滑块和任务清单。',
  },
  {
    title: 'Markdown 对比表格',
    prompt: '用 Markdown 表格对比 React、Vue 和 Svelte 的优缺点。',
  },
]

function messageHasText(message: ChatMessage): boolean {
  return message.content.trim().length > 0
}

function MessageItem({
  message,
  surfaces,
  onUpdateData,
  onAction,
  onRemove,
}: {
  message: ChatMessage
  surfaces: SurfaceMap
  onUpdateData: (surfaceId: string, path: string, value: unknown) => void
  onAction: (
    surfaceId: string,
    action: { name: string; context: Record<string, unknown>; sourceComponentId: string },
  ) => void
  onRemove: (surfaceId: string) => void
}) {
  if (message.role === 'user') {
    return (
      <article className="message message--user">
        <div className="message__user-bubble">{message.content}</div>
      </article>
    )
  }

  const attachedSurfaces = message.surfaceIds
    .map((surfaceId) => surfaces[surfaceId])
    .filter(Boolean)

  return (
    <article className="message message--assistant">
      <div className="avatar">
        <Bot size={18} />
      </div>
      <div className="message__body">
        <div className="message__meta">
          <span className="message__author">Agent</span>
          {message.streaming && (
            <span className="message__streaming">
              <span className="pulse" /> 生成中
            </span>
          )}
        </div>

        <ToolCallList toolCalls={message.toolCalls} />

        {messageHasText(message) && (
          <div className="message__content">
            <Markdown>{message.content}</Markdown>
          </div>
        )}

        {!messageHasText(message) &&
          message.streaming &&
          message.toolCalls.length === 0 &&
          !attachedSurfaces.length && (
            <div className="typing" aria-label="正在生成">
              <span />
              <span />
              <span />
            </div>
          )}

        {attachedSurfaces.length > 0 && (
          <div className="message__surfaces">
            {attachedSurfaces.map((surface) => (
              <SurfaceView
                key={surface.surfaceId}
                surface={surface}
                onUpdateData={onUpdateData}
                onAction={onAction}
                onRemove={onRemove}
              />
            ))}
          </div>
        )}

        {message.error && (
          <div className="message__error" role="alert">
            <AlertTriangle size={16} />
            <div>
              <strong>运行出错</strong>
              <p>{message.error}</p>
            </div>
          </div>
        )}
      </div>
    </article>
  )
}

export default function App() {
  const agent = useAgent()
  const scrollRef = useRef<HTMLElement>(null)
  const stickToBottomRef = useRef(true)
  const messageCountRef = useRef(0)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const element = scrollRef.current
    if (!element) return
    const grew = agent.messages.length > messageCountRef.current
    messageCountRef.current = agent.messages.length
    if (!grew && !stickToBottomRef.current) return
    const frame = requestAnimationFrame(() => {
      element.scrollTop = element.scrollHeight
    })
    return () => cancelAnimationFrame(frame)
  }, [agent.messages, agent.surfaces])

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(timer)
  }, [copied])

  const onScroll = () => {
    const element = scrollRef.current
    if (!element) return
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight
    stickToBottomRef.current = distance < 140
  }

  const copyThreadId = async () => {
    try {
      await navigator.clipboard.writeText(agent.threadId)
      setCopied(true)
      agent.notify('会话 ID 已复制')
    } catch {
      agent.notify(`会话 ID：${agent.threadId}`)
    }
  }

  const disconnected = Boolean(agent.backendError)
  const modelReady = agent.health?.model.configured !== false
  const disabled = disconnected || agent.restoring

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="brand">
            <span className="brand__mark">
              <Sparkles size={20} />
            </span>
            <div className="brand__text">
              <h1>A2UI Agent Studio</h1>
              <p>LangGraph · AG-UI · A2UI v0.9</p>
            </div>
          </div>

          <div className="topbar__actions">
            <button
              type="button"
              className={`status-pill ${disconnected ? 'is-offline' : modelReady ? 'is-online' : 'is-warning'}`}
              onClick={() => void agent.refreshHealth()}
              title={disconnected ? agent.backendError ?? '后端未连接' : '点击刷新健康状态'}
            >
              <span className="status-pill__dot" />
              <span className="status-pill__text">
                {disconnected
                  ? '后端未连接'
                  : agent.health
                    ? `${agent.health.model.provider} · ${agent.health.model.name}`
                    : '连接中…'}
              </span>
            </button>

            <div className="thread-pill" title={`会话 ID：${agent.threadId}`}>
              <MessageSquare size={13} />
              <code>{agent.threadId}</code>
              <button type="button" onClick={copyThreadId} aria-label="复制会话 ID" title="复制会话 ID">
                {copied ? <Check size={13} /> : <Copy size={13} />}
              </button>
            </div>

            <button
              type="button"
              className="btn"
              onClick={() => void agent.loadDemo()}
              disabled={agent.busy || disabled}
              title="加载后端内置的 A2UI 表单示例"
            >
              <LayoutPanelTop size={15} />
              <span>示例界面</span>
            </button>
            <button
              type="button"
              className="btn"
              onClick={agent.newThread}
              disabled={agent.busy}
              title="开启新会话（不删除后端记录）"
            >
              <Plus size={15} />
              <span>新会话</span>
            </button>
            <button
              type="button"
              className="btn btn--icon"
              onClick={() => void agent.clearThread()}
              disabled={agent.busy}
              aria-label="删除当前会话"
              title="删除当前会话"
            >
              <Trash2 size={15} />
            </button>
          </div>
        </div>
      </header>

      <main className="main" ref={scrollRef} onScroll={onScroll}>
        <div className="container">
          {disconnected && (
            <div className="banner banner--error" role="alert">
              <WifiOff size={16} />
              <div>
                <strong>无法连接后端服务</strong>
                <p>{agent.backendError}</p>
                <p className="banner__hint">
                  请确认已启动 <code>uv run uvicorn app.main:app --reload</code>，默认代理到
                  http://127.0.0.1:8000。
                </p>
              </div>
              <button type="button" className="btn" onClick={() => void agent.refreshHealth()}>
                <RefreshCw size={14} /> 重试
              </button>
            </div>
          )}

          {!disconnected && agent.health && !modelReady && (
            <div className="banner banner--warn" role="alert">
              <AlertTriangle size={16} />
              <div>
                <strong>模型未配置</strong>
                <p>请在 .env 中设置 OPENAI_API_KEY / ZHIPUAI_API_KEY，/api/chat 将返回 503。</p>
              </div>
            </div>
          )}

          {agent.restoring ? (
            <div className="restoring">
              <div className="skeleton skeleton--title" />
              <div className="skeleton skeleton--line" />
              <div className="skeleton skeleton--line skeleton--short" />
            </div>
          ) : agent.messages.length === 0 ? (
            <section className="empty">
              <div className="empty__badge">
                <Sparkles size={26} />
              </div>
              <h2>用对话生成原生界面</h2>
              <p className="empty__lead">
                Agent 的文本回答以 Markdown 流式渲染，A2UI 工具结果会被解析并即时渲染为可交互组件。
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((item) => (
                  <button
                    key={item.title}
                    type="button"
                    className="suggestion"
                    disabled={agent.busy || disabled}
                    onClick={() => void agent.send(item.prompt)}
                  >
                    <span className="suggestion__title">{item.title}</span>
                    <span className="suggestion__prompt">{item.prompt}</span>
                  </button>
                ))}
              </div>
              <div className="empty__features">
                <span>Markdown 流式渲染</span>
                <span>A2UI 组件树</span>
                <span>表单与按钮 action</span>
                <span>会话记忆</span>
              </div>
            </section>
          ) : (
            <div className="messages">
              {agent.messages.map((message) => (
                <MessageItem
                  key={message.id}
                  message={message}
                  surfaces={agent.surfaces}
                  onUpdateData={agent.updateSurfaceData}
                  onAction={agent.handleAction}
                  onRemove={agent.hideSurface}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      <div className="composer-wrap">
        <div className="container">
          <Composer
            busy={agent.busy}
            disabled={disabled}
            onSend={(text) => void agent.send(text)}
            onStop={agent.stop}
          />
        </div>
      </div>

      {agent.toast && (
        <div className="toast" role="status">
          <span>{agent.toast}</span>
          <button type="button" onClick={agent.dismissToast} aria-label="关闭提示">
            ×
          </button>
        </div>
      )}
    </div>
  )
}
