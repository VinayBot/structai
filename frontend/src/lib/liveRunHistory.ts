import type { ArchLiveRunEvent, ArchLiveRunRequest } from './types'

const HISTORY_STORAGE_KEY = 'arch:liveRunHistory'
const MAX_HISTORY = 10

export interface LiveRunHistoryEntry {
  id: string
  ranAt: string
  request: ArchLiveRunRequest
  passed: boolean
  summary: string
  finalEvent: ArchLiveRunEvent | null
}

export function loadLiveRunHistory(): LiveRunHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as LiveRunHistoryEntry[]) : []
  } catch {
    return []
  }
}

export function saveLiveRunHistory(entries: LiveRunHistoryEntry[]): void {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // best-effort persistence only
  }
}

/** Prepends a new entry, newest first, capped at the last MAX_HISTORY runs. */
export function pushLiveRunHistory(
  entries: LiveRunHistoryEntry[],
  entry: LiveRunHistoryEntry,
): LiveRunHistoryEntry[] {
  return [entry, ...entries].slice(0, MAX_HISTORY)
}
