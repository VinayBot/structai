/**
 * Parses a buffer of raw SSE text ("data: {...}\n\n" per event, possibly
 * split across chunk boundaries) into complete JSON events plus whatever
 * incomplete tail should be carried over to the next chunk.
 */
export function extractSseEvents<T>(buffer: string): { events: T[]; rest: string } {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  const events: T[] = []

  for (const part of parts) {
    const line = part.trim()
    if (!line.startsWith('data:')) continue
    const json = line.slice('data:'.length).trim()
    if (!json) continue
    events.push(JSON.parse(json) as T)
  }

  return { events, rest }
}
