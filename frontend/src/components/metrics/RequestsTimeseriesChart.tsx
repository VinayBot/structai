import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TimeseriesPoint } from '../../lib/types'

const ACCENT = '#7c5cff'
const DANGER = '#ff5c6c'
const BORDER = '#2a2a38'
const TEXT_DIM = '#9494a3'
const SURFACE = '#1c1c27'

export function RequestsTimeseriesChart({ points }: { points: TimeseriesPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="requestsFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ACCENT} stopOpacity={0.35} />
            <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="errorsFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={DANGER} stopOpacity={0.35} />
            <stop offset="100%" stopColor={DANGER} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={BORDER} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="minute"
          tick={{ fill: TEXT_DIM, fontSize: 11 }}
          interval={9}
          axisLine={{ stroke: BORDER }}
          tickLine={false}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: TEXT_DIM, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={28}
        />
        <Tooltip
          contentStyle={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8 }}
          labelStyle={{ color: TEXT_DIM }}
          itemStyle={{ fontSize: 12 }}
        />
        <Area
          type="monotone"
          dataKey="requests"
          name="requests"
          stroke={ACCENT}
          fill="url(#requestsFill)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="errors"
          name="errors"
          stroke={DANGER}
          fill="url(#errorsFill)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
