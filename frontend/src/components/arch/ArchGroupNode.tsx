import type { Node, NodeProps } from '@xyflow/react'
import type { ArchGroupRenderData } from '../../lib/archLayout'
import { GROUP_COLOR_VISUALS } from '../../lib/archVisuals'

type ArchGroupNode = Node<ArchGroupRenderData, 'archGroup'>

export function ArchGroupNode({ data }: NodeProps<ArchGroupNode>) {
  const visual = GROUP_COLOR_VISUALS[data.color]
  return (
    <div
      className="relative h-full w-full rounded-2xl border-[1.5px]"
      style={{
        borderColor: `${visual.border}80`,
        background: 'linear-gradient(180deg, #1a2233 0%, #121826 100%)',
      }}
    >
      <span
        className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider"
        style={{ background: '#050b18', color: visual.text, border: `1px solid ${visual.border}80` }}
      >
        {data.tag}
      </span>
    </div>
  )
}
