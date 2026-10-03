import { formatMs } from '../../lib/format'
import type { EvalLeaderboardEntry } from '../../lib/types'

export function LeaderboardCard({ entries }: { entries: EvalLeaderboardEntry[] }) {
  if (entries.length === 0) {
    return <p className="eval-text-dim py-6 text-center text-sm">No runs yet</p>
  }

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="eval-text-dim text-left">
          <th className="pb-2 pr-3 font-medium">Provider</th>
          <th className="pb-2 pr-3 font-medium">Model</th>
          <th className="pb-2 pr-3 text-right font-medium">Runs</th>
          <th className="pb-2 pr-3 text-right font-medium">Avg pass rate</th>
          <th className="pb-2 text-right font-medium">Avg latency</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={`${e.provider}:${e.model}`} className="eval-border border-t">
            <td className="py-1.5 pr-3" style={{ color: 'var(--eval-text)' }}>
              {e.provider}
            </td>
            <td className="eval-text-dim py-1.5 pr-3 font-mono">{e.model ?? '—'}</td>
            <td className="py-1.5 pr-3 text-right" style={{ color: 'var(--eval-text)' }}>
              {e.runs}
            </td>
            <td className="py-1.5 pr-3 text-right" style={{ color: 'var(--eval-text)' }}>
              {(e.avg_pass_rate * 100).toFixed(0)}%
            </td>
            <td className="eval-text-dim py-1.5 text-right">{formatMs(e.avg_latency_ms)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
