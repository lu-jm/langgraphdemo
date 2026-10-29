import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'
import type { CSSProperties } from 'react'
import { Braces, LayoutPanelTop, Trash2 } from 'lucide-react'

import type { A2UIComponent, A2UISurface, JsonObject } from '../api/types'
import { getByPointer } from './jsonPointer'
import { A2UIIcon } from './icons'
import {
  isBinding,
  isFunctionCall,
  isRecord,
  performClientFunction,
  resolveBoolean,
  resolveContext,
  resolveNumber,
  resolveString,
  resolveStringList,
  resolveValue,
} from './resolve'
import { Markdown } from '../components/Markdown'

interface SurfaceAction {
  name: string
  context: JsonObject
  sourceComponentId: string
}

interface SurfaceViewProps {
  surface: A2UISurface
  onUpdateData: (surfaceId: string, path: string, value: unknown) => void
  onAction: (surfaceId: string, action: SurfaceAction) => void
  onRemove?: (surfaceId: string) => void
}

interface SurfaceContextValue {
  surface: A2UISurface
  components: Map<string, A2UIComponent>
  rootData: unknown
  updateData: (path: string, value: unknown) => void
  dispatchAction: (sourceComponentId: string, name: string, context: JsonObject) => void
}

const SurfaceContext = createContext<SurfaceContextValue | null>(null)

function useSurface(): SurfaceContextValue {
  const context = useContext(SurfaceContext)
  if (!context) throw new Error('SurfaceContext 未初始化')
  return context
}

function bindingPath(value: unknown): string | null {
  return isBinding(value) ? value.path : null
}

function scopedGet(path: string, data: unknown, root: unknown): unknown {
  const scoped = getByPointer(data, path)
  return scoped !== undefined ? scoped : getByPointer(root, path)
}

const JUSTIFY: Record<string, string> = {
  start: 'flex-start',
  center: 'center',
  end: 'flex-end',
  spaceBetween: 'space-between',
  spaceAround: 'space-around',
  spaceEvenly: 'space-evenly',
}

const ALIGN: Record<string, string> = {
  start: 'flex-start',
  center: 'center',
  end: 'flex-end',
  stretch: 'stretch',
}

interface NodeProps {
  component: A2UIComponent
  data: unknown
  instance: string
}

function ComponentNode({ id, data, instance }: { id: string; data: unknown; instance: string }) {
  const { components } = useSurface()
  const component = components.get(id)
  if (!component) {
    return <span className="a2ui-missing">缺少组件：{id}</span>
  }
  return <Node component={component} data={data} instance={instance} />
}

function Node({ component, data, instance }: NodeProps) {
  switch (component.component) {
    case 'Text':
      return <TextNode component={component} data={data} instance={instance} />
    case 'Image':
      return <ImageNode component={component} data={data} instance={instance} />
    case 'Icon':
      return <IconNode component={component} data={data} instance={instance} />
    case 'Video':
      return <VideoNode component={component} data={data} instance={instance} />
    case 'AudioPlayer':
      return <AudioNode component={component} data={data} instance={instance} />
    case 'Row':
      return <RowNode component={component} data={data} instance={instance} />
    case 'Column':
      return <ColumnNode component={component} data={data} instance={instance} />
    case 'List':
      return <ListNode component={component} data={data} instance={instance} />
    case 'Card':
      return <CardNode component={component} data={data} instance={instance} />
    case 'Tabs':
      return <TabsNode component={component} data={data} instance={instance} />
    case 'Modal':
      return <ModalNode component={component} data={data} instance={instance} />
    case 'Divider':
      return <DividerNode component={component} data={data} instance={instance} />
    case 'Button':
      return <ButtonNode component={component} data={data} instance={instance} />
    case 'TextField':
      return <TextFieldNode component={component} data={data} instance={instance} />
    case 'CheckBox':
      return <CheckBoxNode component={component} data={data} instance={instance} />
    case 'ChoicePicker':
      return <ChoicePickerNode component={component} data={data} instance={instance} />
    case 'Slider':
      return <SliderNode component={component} data={data} instance={instance} />
    case 'DateTimeInput':
      return <DateTimeInputNode component={component} data={data} instance={instance} />
    default:
      return (
        <div className="a2ui-unknown">
          未实现的组件 <code>{component.component}</code>
        </div>
      )
  }
}

function Children({
  value,
  data,
  instance,
}: {
  value: unknown
  data: unknown
  instance: string
}) {
  const { rootData } = useSurface()

  if (Array.isArray(value)) {
    return (
      <>
        {value.map((childId, index) => (
          <ComponentNode
            key={`${instance}-${String(childId)}-${index}`}
            id={String(childId)}
            data={data}
            instance={`${instance}-${index}`}
          />
        ))}
      </>
    )
  }

  if (
    isRecord(value) &&
    typeof value.path === 'string' &&
    typeof value.componentId === 'string'
  ) {
    const list = scopedGet(value.path, data, rootData)
    if (!Array.isArray(list)) return null
    return (
      <>
        {list.map((item, index) => (
          <ComponentNode
            key={`${instance}-tpl-${index}`}
            id={value.componentId as string}
            data={item}
            instance={`${instance}-tpl-${index}`}
          />
        ))}
      </>
    )
  }

  return null
}

function TextNode({ component, data }: NodeProps) {
  const { rootData } = useSurface()
  const text = resolveString(component.text, data, rootData)
  const variant = typeof component.variant === 'string' ? component.variant : 'body'
  return (
    <div className={`a2ui-text a2ui-text--${variant}`}>
      <Markdown>{text}</Markdown>
    </div>
  )
}

function ImageNode({ component, data }: NodeProps) {
  const { rootData } = useSurface()
  const url = resolveString(component.url, data, rootData)
  const description = resolveString(component.description, data, rootData)
  const fit = typeof component.fit === 'string' ? component.fit : 'fill'
  const variant = typeof component.variant === 'string' ? component.variant : 'mediumFeature'
  if (!url) return null
  return (
    <img
      className={`a2ui-image a2ui-image--${variant}`}
      src={url}
      alt={description}
      style={{ objectFit: fit === 'scaleDown' ? 'scale-down' : (fit as CSSProperties['objectFit']) }}
      loading="lazy"
    />
  )
}

function IconNode({ component, data }: NodeProps) {
  const { rootData } = useSurface()
  const accessibility = isRecord(component.accessibility)
    ? resolveString(component.accessibility.label, data, rootData)
    : ''
  return (
    <span className="a2ui-icon" aria-label={accessibility || 'icon'} role="img">
      <A2UIIcon name={resolveValue(component.name, data, rootData)} />
    </span>
  )
}

function VideoNode({ component, data }: NodeProps) {
  const { rootData } = useSurface()
  const url = resolveString(component.url, data, rootData)
  if (!url) return null
  return <video className="a2ui-video" src={url} controls preload="metadata" />
}

function AudioNode({ component, data }: NodeProps) {
  const { rootData } = useSurface()
  const url = resolveString(component.url, data, rootData)
  const description = resolveString(component.description, data, rootData)
  if (!url) return null
  return (
    <div className="a2ui-audio">
      {description && <div className="a2ui-audio__title">{description}</div>}
      <audio src={url} controls preload="metadata" />
    </div>
  )
}

function RowNode({ component, data, instance }: NodeProps) {
  const justify = typeof component.justify === 'string' ? component.justify : 'start'
  const align = typeof component.align === 'string' ? component.align : 'stretch'
  return (
    <div
      className="a2ui-row"
      style={{ justifyContent: JUSTIFY[justify] ?? 'flex-start', alignItems: ALIGN[align] ?? 'stretch' }}
    >
      <Children value={component.children} data={data} instance={instance} />
    </div>
  )
}

function ColumnNode({ component, data, instance }: NodeProps) {
  const justify = typeof component.justify === 'string' ? component.justify : 'start'
  const align = typeof component.align === 'string' ? component.align : 'stretch'
  return (
    <div
      className="a2ui-column"
      style={{ justifyContent: JUSTIFY[justify] ?? 'flex-start', alignItems: ALIGN[align] ?? 'stretch' }}
    >
      <Children value={component.children} data={data} instance={instance} />
    </div>
  )
}

function ListNode({ component, data, instance }: NodeProps) {
  const direction = component.direction === 'horizontal' ? 'horizontal' : 'vertical'
  const align = typeof component.align === 'string' ? component.align : 'stretch'
  return (
    <div
      className={`a2ui-list a2ui-list--${direction}`}
      style={{ alignItems: ALIGN[align] ?? 'stretch' }}
    >
      <Children value={component.children} data={data} instance={instance} />
    </div>
  )
}

function CardNode({ component, data, instance }: NodeProps) {
  const child = typeof component.child === 'string' ? component.child : null
  return (
    <section className="a2ui-card">
      {child ? <ComponentNode id={child} data={data} instance={`${instance}-card`} /> : null}
    </section>
  )
}

function TabsNode({ component, data }: NodeProps) {
  const tabs = Array.isArray(component.tabs) ? component.tabs.filter(isRecord) : []
  const [active, setActive] = useState(0)
  const { rootData } = useSurface()

  if (!tabs.length) return null
  const current = tabs[Math.min(active, tabs.length - 1)]
  const child = typeof current.child === 'string' ? current.child : null

  return (
    <div className="a2ui-tabs">
      <div className="a2ui-tabs__list" role="tablist">
        {tabs.map((tab, index) => (
          <button
            key={index}
            type="button"
            role="tab"
            aria-selected={index === active}
            className={`a2ui-tabs__tab ${index === active ? 'is-active' : ''}`}
            onClick={() => setActive(index)}
          >
            {resolveString(tab.title, data, rootData)}
          </button>
        ))}
      </div>
      <div className="a2ui-tabs__panel" role="tabpanel">
        {child ? <ComponentNode id={child} data={data} instance={`${component.id}-tab-${active}`} /> : null}
      </div>
    </div>
  )
}

function ModalNode({ component, data, instance }: NodeProps) {
  const [open, setOpen] = useState(false)
  const trigger = typeof component.trigger === 'string' ? component.trigger : null
  const content = typeof component.content === 'string' ? component.content : null

  return (
    <>
      <span className="a2ui-modal__trigger" onClick={() => setOpen(true)}>
        {trigger ? <ComponentNode id={trigger} data={data} instance={`${instance}-trigger`} /> : null}
      </span>
      {open && (
        <div className="a2ui-modal__backdrop" role="presentation" onClick={() => setOpen(false)}>
          <div
            className="a2ui-modal"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="a2ui-modal__close"
              aria-label="关闭"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
            {content ? <ComponentNode id={content} data={data} instance={`${instance}-content`} /> : null}
          </div>
        </div>
      )}
    </>
  )
}

function DividerNode({ component }: NodeProps) {
  const axis = component.axis === 'vertical' ? 'vertical' : 'horizontal'
  return <span className={`a2ui-divider a2ui-divider--${axis}`} role="separator" />
}

function ButtonNode({ component, data, instance }: NodeProps) {
  const { rootData, dispatchAction } = useSurface()
  const child = typeof component.child === 'string' ? component.child : null
  const variant = typeof component.variant === 'string' ? component.variant : 'secondary'
  const action = component.action

  const handleClick = () => {
    if (!isRecord(action)) return
    if (isRecord(action.event) && typeof action.event.name === 'string') {
      dispatchAction(
        component.id,
        action.event.name,
        resolveContext(action.event.context, data, rootData),
      )
      return
    }
    if (isFunctionCall(action.functionCall)) {
      performClientFunction(action.functionCall, data, rootData)
    }
  }

  return (
    <button
      type="button"
      className={`a2ui-button a2ui-button--${variant}`}
      onClick={handleClick}
    >
      {child ? <ComponentNode id={child} data={data} instance={`${instance}-button`} /> : null}
    </button>
  )
}

function TextFieldNode({ component, data }: NodeProps) {
  const { rootData, updateData } = useSurface()
  const label = resolveString(component.label, data, rootData)
  const value = resolveString(component.value, data, rootData)
  const path = bindingPath(component.value)
  const variant = typeof component.variant === 'string' ? component.variant : 'shortText'

  const handleChange = (next: string) => {
    if (path) updateData(path, next)
  }

  return (
    <label className="a2ui-field">
      {label && <span className="a2ui-field__label">{label}</span>}
      {variant === 'longText' ? (
        <textarea
          className="a2ui-input a2ui-input--textarea"
          value={value}
          rows={4}
          onChange={(event) => handleChange(event.target.value)}
        />
      ) : (
        <input
          className="a2ui-input"
          type={variant === 'number' ? 'number' : variant === 'obscured' ? 'password' : 'text'}
          value={value}
          pattern={typeof component.validationRegexp === 'string' ? component.validationRegexp : undefined}
          onChange={(event) => handleChange(event.target.value)}
        />
      )}
    </label>
  )
}

function CheckBoxNode({ component, data }: NodeProps) {
  const { rootData, updateData } = useSurface()
  const label = resolveString(component.label, data, rootData)
  const checked = resolveBoolean(component.value, data, rootData)
  const path = bindingPath(component.value)

  return (
    <label className="a2ui-checkbox">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          if (path) updateData(path, event.target.checked)
        }}
      />
      <span>{label}</span>
    </label>
  )
}

function ChoicePickerNode({ component, data }: NodeProps) {
  const { rootData, updateData } = useSurface()
  const label = resolveString(component.label, data, rootData)
  const options = Array.isArray(component.options) ? component.options.filter(isRecord) : []
  const selected = resolveStringList(component.value, data, rootData)
  const path = bindingPath(component.value)
  const multiple = component.variant === 'multipleSelection'

  const toggle = (optionValue: string) => {
    if (!path) return
    if (multiple) {
      updateData(
        path,
        selected.includes(optionValue)
          ? selected.filter((item) => item !== optionValue)
          : [...selected, optionValue],
      )
    } else {
      updateData(path, [optionValue])
    }
  }

  return (
    <fieldset className="a2ui-choice">
      {label && <legend className="a2ui-field__label">{label}</legend>}
      {options.map((option) => {
        const optionValue = String(option.value ?? '')
        const optionLabel = resolveString(option.label, data, rootData)
        return (
          <label key={optionValue} className="a2ui-choice__option">
            <input
              type={multiple ? 'checkbox' : 'radio'}
              name={`choice-${component.id}`}
              checked={selected.includes(optionValue)}
              onChange={() => toggle(optionValue)}
            />
            <span>{optionLabel}</span>
          </label>
        )
      })}
    </fieldset>
  )
}

function SliderNode({ component, data }: NodeProps) {
  const { rootData, updateData } = useSurface()
  const label = resolveString(component.label, data, rootData)
  const min = component.min === undefined ? 0 : resolveNumber(component.min, data, rootData)
  const max = component.max === undefined ? 100 : resolveNumber(component.max, data, rootData)
  const value = resolveNumber(component.value, data, rootData)
  const path = bindingPath(component.value)

  return (
    <label className="a2ui-field">
      {label && (
        <span className="a2ui-field__label">
          {label} <span className="a2ui-field__value">{value}</span>
        </span>
      )}
      <input
        className="a2ui-slider"
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(event) => {
          if (path) updateData(path, Number(event.target.value))
        }}
      />
    </label>
  )
}

function DateTimeInputNode({ component, data }: NodeProps) {
  const { rootData, updateData } = useSurface()
  const value = resolveString(component.value, data, rootData)
  const path = bindingPath(component.value)
  const label = resolveString(component.label, data, rootData)
  const enableDate = component.enableDate !== false
  const enableTime = component.enableTime === true
  const type = enableDate && enableTime ? 'datetime-local' : enableTime ? 'time' : 'date'
  const normalized =
    type === 'datetime-local' ? value.slice(0, 16) : type === 'date' ? value.slice(0, 10) : value

  return (
    <label className="a2ui-field">
      {label && <span className="a2ui-field__label">{label}</span>}
      <input
        className="a2ui-input"
        type={type}
        value={normalized}
        onChange={(event) => {
          if (path) updateData(path, event.target.value)
        }}
      />
    </label>
  )
}

const EMPTY_DATA: Record<string, unknown> = {}

export function SurfaceView({ surface, onUpdateData, onAction, onRemove }: SurfaceViewProps) {
  const [showJson, setShowJson] = useState(false)
  const components = useMemo(
    () => new Map(surface.components.map((component) => [component.id, component])),
    [surface.components],
  )
  const rootData = surface.dataModel ?? EMPTY_DATA
  const root = components.get('root') ?? surface.components[0]

  const updateData = useCallback(
    (path: string, value: unknown) => onUpdateData(surface.surfaceId, path, value),
    [onUpdateData, surface.surfaceId],
  )

  const dispatchAction = useCallback(
    (sourceComponentId: string, name: string, context: JsonObject) => {
      onAction(surface.surfaceId, { name, context, sourceComponentId })
    },
    [onAction, surface.surfaceId],
  )

  const contextValue = useMemo<SurfaceContextValue>(
    () => ({
      surface,
      components,
      rootData,
      updateData,
      dispatchAction,
    }),
    [surface, components, rootData, updateData, dispatchAction],
  )

  const theme = surface.theme ?? {}
  const style = {
    '--a2ui-primary': typeof theme.primaryColor === 'string' ? theme.primaryColor : '#2563eb',
  } as CSSProperties

  return (
    <SurfaceContext.Provider value={contextValue}>
      <section className="surface" style={style}>
        <header className="surface__header">
          <div className="surface__identity">
            <LayoutPanelTop size={14} aria-hidden="true" />
            <span className="surface__name">
              {typeof theme.agentDisplayName === 'string' ? theme.agentDisplayName : 'A2UI Surface'}
            </span>
            <code className="surface__id">{surface.surfaceId}</code>
          </div>
          <div className="surface__actions">
            <span className="surface__badge">A2UI v0.9</span>
            <button
              type="button"
              className={`surface__icon-button ${showJson ? 'is-active' : ''}`}
              aria-label="查看 surface JSON"
              title="查看 surface JSON"
              onClick={() => setShowJson((value) => !value)}
            >
              <Braces size={14} />
            </button>
            {onRemove && (
              <button
                type="button"
                className="surface__icon-button"
                aria-label="移除界面"
                title="移除界面"
                onClick={() => onRemove(surface.surfaceId)}
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </header>

        {showJson ? (
          <pre className="surface__json">
            {JSON.stringify(
              { components: surface.components, dataModel: surface.dataModel },
              null,
              2,
            )}
          </pre>
        ) : (
          <div className="surface__body">
            {root ? (
              <ComponentNode id={root.id} data={rootData} instance={root.id} />
            ) : (
              <p className="a2ui-missing">该 surface 没有可渲染的组件。</p>
            )}
          </div>
        )}
      </section>
    </SurfaceContext.Provider>
  )
}
