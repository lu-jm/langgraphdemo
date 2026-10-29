/** A2UI DynamicValue 解析：字面量、DataBinding、FunctionCall。 */

import type { JsonObject } from '../api/types'
import { getByPointer } from './jsonPointer'

export function isRecord(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isBinding(value: unknown): value is { path: string } {
  return isRecord(value) && typeof value.path === 'string'
}

export function isFunctionCall(
  value: unknown,
): value is { call: string; args?: JsonObject } {
  return isRecord(value) && typeof value.call === 'string'
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export function resolveValue(value: unknown, data: unknown, root: unknown = data): unknown {
  if (isBinding(value)) {
    const scoped = getByPointer(data, value.path)
    if (scoped !== undefined) return scoped
    return getByPointer(root, value.path)
  }
  if (isFunctionCall(value)) {
    return callFunction(value.call, value.args, data, root)
  }
  return value
}

export function resolveString(value: unknown, data: unknown, root: unknown = data): string {
  return stringify(resolveValue(value, data, root))
}

export function resolveNumber(value: unknown, data: unknown, root: unknown = data): number {
  const resolved = resolveValue(value, data, root)
  const parsed = typeof resolved === 'number' ? resolved : Number(resolved)
  return Number.isFinite(parsed) ? parsed : 0
}

export function resolveBoolean(value: unknown, data: unknown, root: unknown = data): boolean {
  return Boolean(resolveValue(value, data, root))
}

export function resolveStringList(
  value: unknown,
  data: unknown,
  root: unknown = data,
): string[] {
  const resolved = resolveValue(value, data, root)
  if (Array.isArray(resolved)) return resolved.map((item) => stringify(item))
  return resolved === undefined || resolved === null ? [] : [stringify(resolved)]
}

/** 解析 action.context：每一项都可能是字面量或 DataBinding。 */
export function resolveContext(
  context: unknown,
  data: unknown,
  root: unknown = data,
): JsonObject {
  if (!isRecord(context)) return {}
  return Object.fromEntries(
    Object.entries(context).map(([key, value]) => [key, resolveValue(value, data, root)]),
  )
}

function pad(value: number, length = 2): string {
  return String(value).padStart(length, '0')
}

function formatDateToken(pattern: string, date: Date): string {
  const monthsShort = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const monthsLong = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ]
  const daysShort = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const daysLong = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
  const hours = date.getHours()

  return pattern.replace(
    /yyyy|yy|MMMM|MMM|MM|M|dd|d|EEEE|E|HH|H|hh|h|mm|m|ss|s|a/g,
    (token) => {
      switch (token) {
        case 'yyyy': return String(date.getFullYear())
        case 'yy': return pad(date.getFullYear() % 100)
        case 'MMMM': return monthsLong[date.getMonth()]
        case 'MMM': return monthsShort[date.getMonth()]
        case 'MM': return pad(date.getMonth() + 1)
        case 'M': return String(date.getMonth() + 1)
        case 'dd': return pad(date.getDate())
        case 'd': return String(date.getDate())
        case 'EEEE': return daysLong[date.getDay()]
        case 'E': return daysShort[date.getDay()]
        case 'HH': return pad(hours)
        case 'H': return String(hours)
        case 'hh': return pad(hours % 12 || 12)
        case 'h': return String(hours % 12 || 12)
        case 'mm': return pad(date.getMinutes())
        case 'm': return String(date.getMinutes())
        case 'ss': return pad(date.getSeconds())
        case 's': return String(date.getSeconds())
        case 'a': return hours < 12 ? 'AM' : 'PM'
        default: return token
      }
    },
  )
}

function interpolate(template: string, data: unknown, root: unknown): string {
  return template
    .replace(/\\\$\{/g, '\u0000')
    .replace(/\$\{([^}]*)\}/g, (_match, rawExpression: string) => {
      const expression = rawExpression.trim()
      if (!expression) return ''
      if (expression.startsWith('/') || expression.startsWith('~')) {
        return stringify(getByPointer(root, expression))
      }
      if (isRecord(data) && expression in data) return stringify(data[expression])
      return ''
    })
    .replace(/\u0000/g, '${')
}

export function callFunction(
  call: string,
  args: JsonObject | undefined,
  data: unknown,
  root: unknown,
): unknown {
  const values = args ?? {}
  const arg = (key: string) => resolveValue(values[key], data, root)

  switch (call) {
    case 'required': {
      const value = arg('value')
      return (
        value !== null &&
        value !== undefined &&
        !(typeof value === 'string' && value.trim() === '') &&
        !(Array.isArray(value) && value.length === 0)
      )
    }
    case 'regex': {
      try {
        return new RegExp(stringify(arg('pattern'))).test(stringify(arg('value')))
      } catch {
        return false
      }
    }
    case 'length': {
      const length = stringify(arg('value')).length
      const min = values.min === undefined ? 0 : resolveNumber(values.min, data, root)
      const max = values.max === undefined ? Number.POSITIVE_INFINITY : resolveNumber(values.max, data, root)
      return length >= min && length <= max
    }
    case 'numeric': {
      const value = resolveNumber(values.value, data, root)
      const min = values.min === undefined ? Number.NEGATIVE_INFINITY : resolveNumber(values.min, data, root)
      const max = values.max === undefined ? Number.POSITIVE_INFINITY : resolveNumber(values.max, data, root)
      return value >= min && value <= max
    }
    case 'email': {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(stringify(arg('value')))
    }
    case 'and': {
      const list = arg('values')
      return Array.isArray(list) ? list.every(Boolean) : false
    }
    case 'or': {
      const list = arg('values')
      return Array.isArray(list) ? list.some(Boolean) : false
    }
    case 'not': {
      return !arg('value')
    }
    case 'formatString': {
      return interpolate(stringify(arg('value')), data, root)
    }
    case 'formatNumber': {
      const decimals = values.decimals === undefined ? undefined : resolveNumber(values.decimals, data, root)
      const grouping = values.grouping === undefined ? true : resolveBoolean(values.grouping, data, root)
      return new Intl.NumberFormat(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
        useGrouping: grouping,
      }).format(resolveNumber(values.value, data, root))
    }
    case 'formatCurrency': {
      const currency = stringify(arg('currency')) || 'USD'
      const decimals = values.decimals === undefined ? undefined : resolveNumber(values.decimals, data, root)
      try {
        return new Intl.NumberFormat(undefined, {
          style: 'currency',
          currency,
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }).format(resolveNumber(values.value, data, root))
      } catch {
        return `${resolveNumber(values.value, data, root)} ${currency}`
      }
    }
    case 'formatDate': {
      const value = arg('value')
      const date = value instanceof Date ? value : new Date(stringify(value))
      if (Number.isNaN(date.getTime())) return ''
      return formatDateToken(stringify(arg('format')) || 'yyyy-MM-dd', date)
    }
    case 'pluralize': {
      const count = resolveNumber(values.value, data, root)
      let category = 'other'
      try {
        category = new Intl.PluralRules('en').select(count)
      } catch {
        category = count === 1 ? 'one' : 'other'
      }
      return stringify(values[category] ?? values.other ?? '')
    }
    case 'openUrl': {
      return stringify(arg('url'))
    }
    default:
      return ''
  }
}

/** 执行客户端函数型 action（目前只处理 openUrl）。 */
export function performClientFunction(
  functionCall: { call: string; args?: JsonObject },
  data: unknown,
  root: unknown,
): void {
  if (functionCall.call === 'openUrl') {
    const url = stringify(resolveValue(functionCall.args?.url, data, root))
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }
}
