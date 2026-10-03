import { formatMs } from '../../lib/format'

export interface HeadToHeadSeries {
  label: string
  color: string
  byCategory: Record<string, { total: number; passed: number }>
  avgLatencyByCategory: Record<string, number>
}

export function HeadToHeadTable({ series }: { series: HeadToHeadSeries[] }) {
  const categories = Array.from(
    new Set(series.flatMap((s) => Object.keys(s.byCategory))),
  ).sort()

  if (categories.length === 0) {
    return <p className="eval-text-dim py-6 text-center text-sm">No data yet</p>
  }

  return (
    <div className="space-y-2">
      {series.length < 2 && (
        <p className="eval-text-dim text-xs">Run both Ollama and Groq to compare head-to-head.</p>
      )}
      <table className="w-full text-xs">
        <thead>
          <tr className="eval-text-dim text-left">
            <th className="pb-2 pr-3 font-medium">Category</th>
            {series.map((s) => (
              <th key={s.label} className="pb-2 pr-3 text-right font-medium" style={{ color: s.color }}>
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => (
            <tr key={category} className="eval-border border-t">
              <td className="py-1.5 pr-3" style={{ color: 'var(--eval-text)' }}>
                {category}
              </td>
              {series.map((s) => {
                const bucket = s.byCategory[category]
                const rate = bucket && bucket.total > 0 ? (bucket.passed / bucket.total) * 100 : null
                const latency = s.avgLatencyByCategory[category]
                return (
                  <td key={s.label} className="py-1.5 pr-3 text-right" style={{ color: 'var(--eval-text)' }}>
                    {rate === null ? (
                      <span className="eval-text-dim">—</span>
                    ) : (
                      <>
                        {rate.toFixed(0)}%{' '}
                        <span className="eval-text-dim">({formatMs(latency ?? 0)})</span>
                      </>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
