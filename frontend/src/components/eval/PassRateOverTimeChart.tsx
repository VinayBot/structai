import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { EvalPalette } from '../../lib/evalTheme'
import type { EvalRunSummary } from '../../lib/types'

const SERIES_COLORS = (palette: EvalPalette): Record<string, string> => ({
  ollama: palette.primary,
  groq: palette.secondary,
  gateway: palette.tertiary,
})

/** `history` is newest-first, as returned by GET /eval/dashboard. */
export function PassRateOverTimeChart({
  history,
  palette,
}: {
  history: EvalRunSummary[]
  palette: EvalPalette
}) {
  if (history.length === 0) {
    return <p className="eval-text-dim py-10 text-center text-sm">No runs yet</p>
  }

  const chronological = [...history].reverse()
  const providers = Array.from(new Set(chronological.map((r) => r.provider)))
  const colorFor = SERIES_COLORS(palette)

  const rows = chronological.map((run, i) => ({
    idx: i,
    time: new Date(run.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    [run.provider]: run.pass_rate * 100,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={palette.border} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="time" tick={{ fill: palette.textDim, fontSize: 11 }} axisLine={{ stroke: palette.border }} tickLine={false} />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: palette.textDim, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={36}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip
          contentStyle={{ background: palette.surface, border: `1px solid ${palette.border}`, borderRadius: 8 }}
          labelStyle={{ color: palette.textDim }}
          itemStyle={{ fontSize: 12 }}
          formatter={(value) => `${Number(value).toFixed(0)}%`}
        />
        {providers.map((p) => (
          <Line
            key={p}
            type="monotone"
            dataKey={p}
            name={p}
            stroke={colorFor[p] ?? palette.primary}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
