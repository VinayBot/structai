import { describe, expect, it } from 'vitest'
import { formatMs } from './format'

describe('formatMs', () => {
  it('formats with one decimal place', () => {
    expect(formatMs(123.456)).toBe('123.5ms')
    expect(formatMs(0)).toBe('0.0ms')
    expect(formatMs(7)).toBe('7.0ms')
  })
})
