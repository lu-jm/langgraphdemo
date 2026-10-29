/** RFC 6901 JSON Pointer 读写；A2UI 额外把 "/" 视为根路径。 */

import type { JsonObject } from '../api/types'

function isRoot(path: string): boolean {
  return path === '' || path === '/'
}

function parse(path: string): string[] {
  return path
    .split('/')
    .slice(1)
    .map((token) => token.replace(/~1/g, '/').replace(/~0/g, '~'))
}

export function getByPointer(root: unknown, path: string): unknown {
  if (isRoot(path)) return root
  let current: unknown = root
  for (const key of parse(path)) {
    if (current === null || current === undefined) return undefined
    if (Array.isArray(current)) {
      const index = Number(key)
      current = Number.isInteger(index) ? current[index] : undefined
      continue
    }
    if (typeof current === 'object') {
      current = (current as JsonObject)[key]
      continue
    }
    return undefined
  }
  return current
}

function clone<T>(value: T): T {
  if (Array.isArray(value)) return value.map((item) => clone(item)) as T
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as JsonObject).map(([key, item]) => [key, clone(item)]),
    ) as T
  }
  return value
}

export function setByPointer(root: unknown, path: string, value: unknown): unknown {
  if (isRoot(path)) return value
  const tokens = parse(path)
  const base: unknown =
    root && typeof root === 'object' ? clone(root) : Array.isArray(root) ? [] : {}

  let current = base as JsonObject | unknown[]
  for (let i = 0; i < tokens.length - 1; i += 1) {
    const key = tokens[i]
    const nextKey = tokens[i + 1]
    const existing = Array.isArray(current)
      ? current[Number(key)]
      : (current as JsonObject)[key]

    if (existing !== null && typeof existing === 'object') {
      current = existing as JsonObject | unknown[]
      continue
    }

    const created: JsonObject | unknown[] = /^\d+$/.test(nextKey) ? [] : {}
    if (Array.isArray(current)) current[Number(key)] = created
    else (current as JsonObject)[key] = created
    current = created
  }

  const last = tokens[tokens.length - 1]
  if (Array.isArray(current)) current[Number(last)] = value
  else (current as JsonObject)[last] = value
  return base
}

export function deleteByPointer(root: unknown, path: string): unknown {
  if (isRoot(path)) return {}
  const tokens = parse(path)
  const base = root && typeof root === 'object' ? clone(root) : {}
  let current = base as JsonObject | unknown[]

  for (let i = 0; i < tokens.length - 1; i += 1) {
    const key = tokens[i]
    const next = Array.isArray(current)
      ? current[Number(key)]
      : (current as JsonObject)[key]
    if (!next || typeof next !== 'object') return base
    current = next as JsonObject | unknown[]
  }

  const last = tokens[tokens.length - 1]
  if (Array.isArray(current)) current.splice(Number(last), 1)
  else delete (current as JsonObject)[last]
  return base
}
