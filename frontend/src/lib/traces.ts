import type { Span } from './types'

export interface TraceGroup {
  traceId: string
  root: Span
  children: Span[]
}

/** Groups a flat, newest-first span list into one entry per trace_id. */
export function groupSpansByTrace(spans: Span[]): TraceGroup[] {
  const byTrace = new Map<string, Span[]>()
  for (const span of spans) {
    const list = byTrace.get(span.trace_id)
    if (list) list.push(span)
    else byTrace.set(span.trace_id, [span])
  }

  const groups: TraceGroup[] = []
  for (const [traceId, traceSpans] of byTrace) {
    const root = traceSpans.find((s) => s.parent_span_id === null) ?? traceSpans[0]
    const children = traceSpans
      .filter((s) => s.span_id !== root.span_id)
      .sort((a, b) => a.start_time - b.start_time)
    groups.push({ traceId, root, children })
  }

  return groups.sort((a, b) => b.root.start_time - a.root.start_time)
}
