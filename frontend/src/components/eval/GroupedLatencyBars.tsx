import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { EvalPalette } from '../../lib/evalTheme'

export interface LatencySeries {
  label: string
  color: string
  avgLatencyByCategory: Record<string, number>
}

export function GroupedLatencyBars({
  series,
  palette,
}: {
  series: LatencySeries[]
  palette: EvalPalette
}) {
  const categories = Array.from(
    new Set(series.flatMap((s) => Object.keys(s.avgLatencyByCategory))),
  ).sort()

  if (categories.length === 0) {
    return <p className="eval-text-dim py-10 text-center text-sm">No latency data yet</p>
  }

  const rows = categories.map((category) => {
    const row: Record<string, string | number> = { category }
    for (const s of series) row[s.label] = s.avgLatencyByCategory[category] ?? 0
    return row
  })

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={palette.border} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="category" tick={{ fill: palette.textDim, fontSize: 11 }} axisLine={{ stroke: palette.border }} tickLine={false} />
        <YAxis
          tick={{ fill: palette.textDim, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={40}
          tickFormatter={(v: number) => `${v}ms`}
        />
        <Tooltip
          contentStyle={{ background: palette.surface, border: `1px solid ${palette.border}`, borderRadius: 8 }}
          labelStyle={{ color: palette.textDim }}
          itemStyle={{ fontSize: 12 }}
          formatter={(value) => `${Number(value).toFixed(1)}ms`}
        />
        {series.map((s) => (
          <Bar key={s.label} dataKey={s.label} name={s.label} fill={s.color} radius={[4, 4, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
