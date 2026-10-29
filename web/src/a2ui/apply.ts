/** 把 A2UI 操作序列应用到本地 surface 集合。 */

import type { A2UIMessage, A2UISurface } from '../api/types'
import { deleteByPointer, setByPointer } from './jsonPointer'

export type SurfaceMap = Record<string, A2UISurface>

export interface ApplyResult {
  surfaces: SurfaceMap
  touched: string[]
}

export function normalizeSurface(surface: A2UISurface): A2UISurface {
  return {
    ...surface,
    components: surface.components ?? [],
    dataModel: surface.dataModel ?? {},
  }
}

export function applyOperations(
  current: SurfaceMap,
  operations: A2UIMessage[],
): ApplyResult {
  if (!operations.length) return { surfaces: current, touched: [] }

  const next: SurfaceMap = { ...current }
  const touched = new Set<string>()

  for (const operation of operations) {
    if (operation.createSurface) {
      const payload = operation.createSurface
      next[payload.surfaceId] = {
        surfaceId: payload.surfaceId,
        catalogId: payload.catalogId,
        theme: payload.theme ?? null,
        sendDataModel: payload.sendDataModel ?? false,
        components: [],
        dataModel: {},
      }
      touched.add(payload.surfaceId)
      continue
    }

    if (operation.updateComponents) {
      const payload = operation.updateComponents
      const existing = next[payload.surfaceId]
      if (!existing) continue
      const byId = new Map(existing.components.map((component) => [component.id, component]))
      for (const component of payload.components) byId.set(component.id, component)
      next[payload.surfaceId] = {
        ...existing,
        components: Array.from(byId.values()),
      }
      touched.add(payload.surfaceId)
      continue
    }

    if (operation.updateDataModel) {
      const payload = operation.updateDataModel
      const existing = next[payload.surfaceId]
      if (!existing) continue
      const path = payload.path ?? '/'
      const hasValue = 'value' in payload
      next[payload.surfaceId] = {
        ...existing,
        dataModel: hasValue
          ? setByPointer(existing.dataModel, path, payload.value)
          : deleteByPointer(existing.dataModel, path),
      }
      touched.add(payload.surfaceId)
      continue
    }

    if (operation.deleteSurface) {
      const surfaceId = operation.deleteSurface.surfaceId
      delete next[surfaceId]
      touched.add(surfaceId)
    }
  }

  return { surfaces: next, touched: Array.from(touched) }
}

export function mergeServerSurfaces(
  current: SurfaceMap,
  surfaces: A2UISurface[],
): ApplyResult {
  const next = { ...current }
  const touched: string[] = []
  for (const surface of surfaces) {
    const normalized = normalizeSurface(surface)
    const existing = current[surface.surfaceId]
    // 数据模型通常由客户端编辑、通过 action 回传，服务端保存的可能是旧值；
    // 已有 surface 保留本地 dataModel，仅同步服务端的组件与主题。
    // 若服务端只保存了 createSurface（updateComponents 校验失败），本地已经
    // 渲染出的组件不能被空数组覆盖，否则回答结束时会瞬间“消失”。
    const components =
      normalized.components.length === 0 && existing && existing.components.length > 0
        ? existing.components
        : normalized.components
    next[surface.surfaceId] = existing
      ? { ...normalized, components, dataModel: existing.dataModel }
      : normalized
    touched.push(surface.surfaceId)
  }
  return { surfaces: next, touched }
}

export function removeSurface(current: SurfaceMap, surfaceId: string): SurfaceMap {
  if (!(surfaceId in current)) return current
  const next = { ...current }
  delete next[surfaceId]
  return next
}
