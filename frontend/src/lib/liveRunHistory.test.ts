import { afterEach, describe, expect, it } from 'vitest'
import {
  loadLiveRunHistory,
  pushLiveRunHistory,
  saveLiveRunHistory,
  type LiveRunHistoryEntry,
} from './liveRunHistory'

function makeEntry(id: string): LiveRunHistoryEntry {
  return {
    id,
    ranAt: '2026-01-01T00:00:00.000Z',
    request: {
      prompt: `prompt-${id}`,
      schema_def: { fields: [{ name: 'title', type: 'string', description: '', required: true }] },
      tier: 'fast',
      provider: 'auto',
      model: null,
      strict_provider: false,
    },
    passed: true,
    summary: 'Passed',
    finalEvent: null,
  }
}

describe('pushLiveRunHistory', () => {
  it('prepends the new entry so the most recent run is first', () => {
    const result = pushLiveRunHistory([makeEntry('a')], makeEntry('b'))
    expect(result.map((e) => e.id)).toEqual(['b', 'a'])
  })

  it('caps the list at 10 entries, dropping the oldest', () => {
    const existing = Array.from({ length: 10 }, (_, i) => makeEntry(`old-${i}`))
    const result = pushLiveRunHistory(existing, makeEntry('new'))
    expect(result).toHaveLength(10)
    expect(result[0].id).toBe('new')
    expect(result.some((e) => e.id === 'old-9')).toBe(false)
  })
})

describe('loadLiveRunHistory / saveLiveRunHistory', () => {
  afterEach(() => {
    localStorage.clear()
  })

  it('returns an empty array when nothing is stored', () => {
    expect(loadLiveRunHistory()).toEqual([])
  })

  it('returns an empty array when the stored value is not valid JSON', () => {
    localStorage.setItem('arch:liveRunHistory', 'not json')
    expect(loadLiveRunHistory()).toEqual([])
  })

  it('returns an empty array when the stored value is not an array', () => {
    localStorage.setItem('arch:liveRunHistory', JSON.stringify({ not: 'an array' }))
    expect(loadLiveRunHistory()).toEqual([])
  })

  it('round-trips entries through save then load', () => {
    const entries = [makeEntry('a'), makeEntry('b')]
    saveLiveRunHistory(entries)
    expect(loadLiveRunHistory()).toEqual(entries)
  })
})
