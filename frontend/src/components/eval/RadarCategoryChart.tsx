import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { EvalPalette } from '../../lib/evalTheme'

export interface CategorySeries {
  label: string
  color: string
  byCategory: Record<string, { total: number; passed: number }>
}

export function RadarCategoryChart({
  series,
  palette,
}: {
  series: CategorySeries[]
  palette: EvalPalette
}) {
  const categories = Array.from(
    new Set(series.flatMap((s) => Object.keys(s.byCategory))),
  ).sort()

  if (categories.length === 0) {
    return <p className="eval-text-dim py-10 text-center text-sm">No category data yet</p>
  }

  const rows = categories.map((category) => {
    const row: Record<string, string | number> = { category }
    for (const s of series) {
      const bucket = s.byCategory[category]
      row[s.label] = bucket && bucket.total > 0 ? (bucket.passed / bucket.total) * 100 : 0
    }
    return row
  })

  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={rows} outerRadius="75%">
        <PolarGrid stroke={palette.border} />
        <PolarAngleAxis dataKey="category" tick={{ fill: palette.textDim, fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: palette.surface, border: `1px solid ${palette.border}`, borderRadius: 8 }}
          labelStyle={{ color: palette.textDim }}
          itemStyle={{ fontSize: 12 }}
          formatter={(value) => `${Number(value).toFixed(0)}%`}
        />
        {series.map((s) => (
          <Radar
            key={s.label}
            name={s.label}
            dataKey={s.label}
            stroke={s.color}
            fill={s.color}
            fillOpacity={0.25}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  )
}
