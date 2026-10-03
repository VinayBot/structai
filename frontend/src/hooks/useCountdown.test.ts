import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCountdown } from './useCountdown'

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T00:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns null when there is no target', () => {
    const { result } = renderHook(() => useCountdown(null))
    expect(result.current).toBeNull()
  })

  it('counts down to zero and clamps there', () => {
    const target = Date.now() + 5000
    const { result } = renderHook(() => useCountdown(target))
    expect(result.current).toBe(5)

    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(result.current).toBe(2)

    act(() => {
      vi.advanceTimersByTime(10000)
    })
    expect(result.current).toBe(0)
  })

  it('resets immediately when the target itself changes', () => {
    const { result, rerender } = renderHook(({ target }) => useCountdown(target), {
      initialProps: { target: Date.now() + 1000 as number | null },
    })
    expect(result.current).toBe(1)

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current).toBe(0)

    act(() => {
      rerender({ target: Date.now() + 8000 })
    })
    expect(result.current).toBe(8)
  })
})
