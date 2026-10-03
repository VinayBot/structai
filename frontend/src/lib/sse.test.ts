import { describe, expect, it } from 'vitest'
import { extractSseEvents } from './sse'

interface Payload {
  stage: string
  value?: number
}

describe('extractSseEvents', () => {
  it('parses a single complete event', () => {
    const { events, rest } = extractSseEvents<Payload>('data: {"stage":"done"}\n\n')
    expect(events).toEqual([{ stage: 'done' }])
    expect(rest).toBe('')
  })

  it('parses multiple complete events in one buffer', () => {
    const buffer = 'data: {"stage":"generating"}\n\ndata: {"stage":"done"}\n\n'
    const { events, rest } = extractSseEvents<Payload>(buffer)
    expect(events).toEqual([{ stage: 'generating' }, { stage: 'done' }])
    expect(rest).toBe('')
  })

  it('holds back an incomplete trailing chunk', () => {
    const buffer = 'data: {"stage":"generating"}\n\ndata: {"stage":"d'
    const { events, rest } = extractSseEvents<Payload>(buffer)
    expect(events).toEqual([{ stage: 'generating' }])
    expect(rest).toBe('data: {"stage":"d')
  })

  it('reassembles an event split across two reads', () => {
    const first = extractSseEvents<Payload>('data: {"stage":"d')
    expect(first.events).toEqual([])
    const second = extractSseEvents<Payload>(`${first.rest}one"}\n\n`)
    expect(second.events).toEqual([{ stage: 'done' }])
    expect(second.rest).toBe('')
  })

  it('ignores blank lines and non-data lines', () => {
    const buffer = '\n\ndata: {"stage":"done","value":1}\n\n'
    const { events } = extractSseEvents<Payload>(buffer)
    expect(events).toEqual([{ stage: 'done', value: 1 }])
  })

  it('returns no events for an empty buffer', () => {
    const { events, rest } = extractSseEvents<Payload>('')
    expect(events).toEqual([])
    expect(rest).toBe('')
  })
})
