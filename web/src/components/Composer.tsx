import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Square } from 'lucide-react'

interface ComposerProps {
  busy: boolean
  disabled?: boolean
  onSend: (text: string) => void
  onStop: () => void
}

export function Composer({ busy, disabled, onSend, onStop }: ComposerProps) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`
  }, [text])

  const submit = () => {
    const value = text.trim()
    if (!value || busy || disabled) return
    onSend(value)
    setText('')
  }

  return (
    <div className="composer">
      <div className={`composer__box ${disabled ? 'is-disabled' : ''}`}>
        <textarea
          ref={textareaRef}
          className="composer__input"
          value={text}
          rows={1}
          placeholder={
            disabled
              ? '后端服务未连接，请先启动 API 服务…'
              : '描述你想要的回答或界面，例如：把 128×37 的结果做成卡片'
          }
          disabled={disabled}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        {busy ? (
          <button
            type="button"
            className="composer__send composer__send--stop"
            aria-label="停止生成"
            title="停止生成"
            onClick={onStop}
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            className="composer__send"
            aria-label="发送"
            title="发送（Enter）"
            disabled={disabled || !text.trim()}
            onClick={submit}
          >
            <ArrowUp size={18} />
          </button>
        )}
      </div>
      <div className="composer__hint">
        <span>Enter 发送 · Shift + Enter 换行</span>
        <span>支持 Markdown 与 A2UI 交互界面</span>
      </div>
    </div>
  )
}
