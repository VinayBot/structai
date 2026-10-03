import { useEffect, useState } from 'react'

/**
 * Ticks once a second while `targetMs` is set, returning whole seconds remaining
 * (never negative). Resets immediately (no 1s lag) whenever `targetMs` itself changes,
 * matching the live countdown pattern used for both the Live Run 429 retry banner and
 * the Inspector dock's token-expiry display.
 */
export function useCountdown(targetMs: number | null): number | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (targetMs === null) return
    setNow(Date.now())
    const interval = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(interval)
  }, [targetMs])

  if (targetMs === null) return null
  return Math.max(0, Math.ceil((targetMs - now) / 1000))
}
