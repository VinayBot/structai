import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from 'recharts'
import type { EvalPalette } from '../../lib/evalTheme'

/** Semi-circle gauge of the fraction of cases that passed on their first attempt. */
export function FirstTryGauge({
  firstTryRate,
  palette,
}: {
  firstTryRate: number | null
  palette: EvalPalette
}) {
  if (firstTryRate === null) {
    return <p className="eval-text-dim py-10 text-center text-sm">No runs yet</p>
  }

  const pct = Math.round(firstTryRate * 100)
  const data = [{ value: pct, fill: palette.primary }]

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={140}>
        <RadialBarChart
          cx="50%"
          cy="100%"
          innerRadius="70%"
          outerRadius="100%"
          barSize={16}
          data={data}
          startAngle={180}
          endAngle={0}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar dataKey="value" cornerRadius={8} background={{ fill: palette.border }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="text-2xl font-semibold" style={{ color: palette.text }}>
          {pct}%
        </span>
        <span className="text-xs" style={{ color: palette.textDim }}>
          first-try pass rate
        </span>
      </div>
    </div>
  )
}
