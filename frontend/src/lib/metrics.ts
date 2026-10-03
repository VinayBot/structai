export interface MetricSample {
  name: string
  labels: Record<string, string>
  value: number
}

export interface MetricFamily {
  name: string
  samples: MetricSample[]
}

const LINE_RE = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{(.*)\})?\s+(\S+)$/

function parseLabels(raw: string | undefined): Record<string, string> {
  if (!raw) return {}
  const labels: Record<string, string> = {}
  const labelRe = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g
  let match: RegExpExecArray | null
  while ((match = labelRe.exec(raw)) !== null) {
    labels[match[1]] = match[2].replace(/\\"/g, '"')
  }
  return labels
}

/** Parses Prometheus text exposition format into per-metric sample groups. */
export function parsePrometheusText(text: string): MetricFamily[] {
  const families = new Map<string, MetricFamily>()

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue

    const match = LINE_RE.exec(line)
    if (!match) continue

    const [, name, , labelsRaw, valueRaw] = match
    const value = Number(valueRaw)
    if (Number.isNaN(value)) continue

    const family = families.get(name) ?? { name, samples: [] }
    family.samples.push({ name, labels: parseLabels(labelsRaw), value })
    families.set(name, family)
  }

  return [...families.values()]
}
