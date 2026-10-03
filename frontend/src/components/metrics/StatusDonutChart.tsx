import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { StatusBucket } from '../../lib/types'

const COLORS: Record<string, string> = {
  '2xx': '#35d08f',
  '4xx': '#ffb454',
  '5xx': '#ff5c6c',
}
const BORDER = '#2a2a38'
const SURFACE = '#1c1c27'
const TEXT_DIM = '#9494a3'

export function StatusDonutChart({ byStatus }: { byStatus: StatusBucket }) {
  const data = (['2xx', '4xx', '5xx'] as const)
    .map((bucket) => ({ bucket, value: byStatus[bucket] }))
    .filter((d) => d.value > 0)

  if (data.length === 0) {
    return <p className="py-10 text-center text-sm text-text-dim">No requests yet</p>
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="bucket"
          innerRadius={45}
          outerRadius={70}
          paddingAngle={2}
        >
          {data.map((d) => (
            <Cell key={d.bucket} fill={COLORS[d.bucket]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8 }}
          labelStyle={{ color: TEXT_DIM }}
          itemStyle={{ fontSize: 12 }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
