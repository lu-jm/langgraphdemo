import { Check, ChevronDown, Loader2, Wrench } from 'lucide-react'

import type { ToolCallView } from '../hooks/useAgent'

function isA2UIToolResult(result: string | undefined): boolean {
  if (!result) return false
  return result.includes('a2ui_operations')
}

function previewArgs(call: ToolCallView): string {
  if (call.args) return JSON.stringify(call.args)
  return call.argsText
}

export function ToolCallList({ toolCalls }: { toolCalls: ToolCallView[] }) {
  if (!toolCalls.length) return null

  return (
    <div className="tool-calls">
      {toolCalls.map((call) => {
        const a2ui = isA2UIToolResult(call.result)
        const args = previewArgs(call)
        return (
          <details key={call.id} className="tool-call">
            <summary className="tool-call__summary">
              <span className={`tool-call__icon tool-call__icon--${call.status}`}>
                {call.status === 'running' ? (
                  <Loader2 size={13} className="spin" />
                ) : (
                  <Check size={13} />
                )}
              </span>
              <Wrench size={13} aria-hidden="true" />
              <code className="tool-call__name">{call.name}</code>
              {a2ui && <span className="tool-call__tag">A2UI</span>}
              <span className="tool-call__args">{args.length > 80 ? `${args.slice(0, 80)}…` : args}</span>
              <ChevronDown size={14} className="tool-call__chevron" aria-hidden="true" />
            </summary>
            <div className="tool-call__body">
              <div className="tool-call__section">
                <span className="tool-call__label">参数</span>
                <pre>{call.args ? JSON.stringify(call.args, null, 2) : call.argsText || '（无）'}</pre>
              </div>
              <div className="tool-call__section">
                <span className="tool-call__label">结果</span>
                <pre className={a2ui ? 'tool-call__result--a2ui' : undefined}>
                  {a2ui
                    ? '已生成 A2UI 界面，见下方渲染结果。'
                    : call.result || (call.status === 'running' ? '执行中…' : '（无）')}
                </pre>
              </div>
            </div>
          </details>
        )
      })}
    </div>
  )
}
