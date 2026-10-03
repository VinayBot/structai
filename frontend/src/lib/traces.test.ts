import { describe, expect, it } from 'vitest'
import { groupSpansByTrace } from './traces'
import type { Span } from './types'

function span(overrides: Partial<Span>): Span {
  return {
    span_id: 's1',
    trace_id: 't1',
    parent_span_id: null,
    name: 'structured.loop',
    start_time: 100,
    duration_ms: 10,
    status: 'ok',
    error: null,
    attributes: {},
    ...overrides,
  }
}

describe('groupSpansByTrace', () => {
  it('groups a root span with its children under one trace', () => {
    const spans: Span[] = [
      span({ span_id: 'root', trace_id: 't1', parent_span_id: null, start_time: 100 }),
      span({
        span_id: 'child',
        trace_id: 't1',
        parent_span_id: 'root',
        name: 'gateway.generate',
        start_time: 101,
      }),
    ]

    const groups = groupSpansByTrace(spans)

    expect(groups).toHaveLength(1)
    expect(groups[0].root.span_id).toBe('root')
    expect(groups[0].children).toHaveLength(1)
    expect(groups[0].children[0].span_id).toBe('child')
  })

  it('orders traces newest-first by root start_time', () => {
    const spans: Span[] = [
      span({ span_id: 'older', trace_id: 'old', start_time: 100 }),
      span({ span_id: 'newer', trace_id: 'new', start_time: 200 }),
    ]

    const groups = groupSpansByTrace(spans)

    expect(groups.map((g) => g.traceId)).toEqual(['new', 'old'])
  })

  it('falls back to the first span when no root (parent_span_id null) is present', () => {
    const spans: Span[] = [span({ span_id: 'only', parent_span_id: 'missing-parent' })]

    const groups = groupSpansByTrace(spans)

    expect(groups[0].root.span_id).toBe('only')
    expect(groups[0].children).toHaveLength(0)
  })

  it('returns no groups for an empty span list', () => {
    expect(groupSpansByTrace([])).toEqual([])
  })
})
