import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { EvalPalette } from '../../lib/evalTheme'

export function OutcomeDonut({
  passed,
  failed,
  palette,
}: {
  passed: number
  failed: number
  palette: EvalPalette
}) {
  const total = passed + failed
  if (total === 0) {
    return <p className="eval-text-dim py-10 text-center text-sm">No runs yet</p>
  }

  const data = [
    { label: 'passed', value: passed, color: palette.success },
    { label: 'failed', value: failed, color: palette.danger },
  ].filter((d) => d.value > 0)

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="label" innerRadius={55} outerRadius={78} paddingAngle={2} strokeWidth={0}>
            {data.map((d) => (
              <Cell key={d.label} fill={d.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: palette.surface, border: `1px solid ${palette.border}`, borderRadius: 8 }}
            labelStyle={{ color: palette.textDim }}
            itemStyle={{ fontSize: 12 }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold" style={{ color: palette.text }}>
          {Math.round((passed / total) * 100)}%
        </span>
        <span className="text-xs" style={{ color: palette.textDim }}>
          {passed} / {total} passed
        </span>
      </div>
    </div>
  )
}
