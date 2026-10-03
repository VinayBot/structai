import { motion, useReducedMotion } from 'framer-motion'
import type { Node, NodeProps } from '@xyflow/react'
import { Handle, Position } from '@xyflow/react'
import type { ArchNodeRenderData } from '../../lib/archLayout'
import { ArchIcon } from '../../lib/archIcons'
import { KIND_VISUALS, NODE_STATE_VISUALS } from '../../lib/archVisuals'

type ArchFlowNode = Node<ArchNodeRenderData, 'archNode'>

const TILE_BACKGROUND = 'linear-gradient(180deg, #182238 0%, #0f1726 100%)'
const TILE_SHADOW = '0 2px 0 0 #0a1120, 0 5px 0 0 #060a12, 0 9px 14px -4px rgba(0,0,0,0.55)'
const ENGINE_BACKGROUND = '#2563ff'
const CLOUD_FILL = '#7f8fac'

export function ArchNodeCard({ data, selected }: NodeProps<ArchFlowNode>) {
  const prefersReducedMotion = useReducedMotion()
  const visual = KIND_VISUALS[data.node.kind]
  const kind = data.node.visual_kind

  const resultColor =
    data.runStatus === 'ok'
      ? NODE_STATE_VISUALS.healthy.color
      : data.runStatus === 'error'
        ? NODE_STATE_VISUALS.failed.color
        : data.runStatus === 'modified'
          ? NODE_STATE_VISUALS.degraded.color
          : data.liveState
            ? NODE_STATE_VISUALS[data.liveState].color
            : null

  // Engine blocks are already solid blue - a blue active-glow would disappear against them.
  const activeGlow = kind === 'engine' ? '#eaf1ff' : visual.color
  const borderColor = data.active ? activeGlow : resultColor
  const statusLabel = data.runStatus !== 'idle' ? data.runStatus : data.liveState ?? 'unknown'

  const statusDetail = data.statusDetail
  const statusTooltip =
    statusDetail && (statusDetail.state === 'failed' || statusDetail.state === 'degraded')
      ? [
          `${NODE_STATE_VISUALS[statusDetail.state].label}: ${statusDetail.last_error ?? 'no error detail recorded'}`,
          statusDetail.last_checked_at ? `checked ${new Date(statusDetail.last_checked_at).toLocaleTimeString()}` : null,
        ]
          .filter(Boolean)
          .join(' - ')
      : undefined

  if (kind === 'cloud') {
    return (
      <motion.div
        role="button"
        tabIndex={0}
        aria-label={`${data.node.label} - ${data.node.summary}, press Enter for details`}
        aria-pressed={selected}
        onClick={() => data.onActivate(data.node.id)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            data.onActivate(data.node.id)
          }
        }}
        initial={false}
        animate={
          prefersReducedMotion ? undefined : { filter: data.active || selected ? 'brightness(1.15)' : 'brightness(1)' }
        }
        className="relative flex h-full w-full cursor-pointer items-center justify-center outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <svg viewBox="0 0 200 140" className="absolute inset-0 h-full w-full" aria-hidden="true">
          <path
            d="M46 104 Q18 104 18 78 Q18 56 40 50 Q42 24 68 24 Q84 8 106 20 Q128 2 150 24 Q176 24 176 54 Q194 58 194 82 Q194 104 166 104 Z"
            fill={CLOUD_FILL}
          />
        </svg>
        <span className="relative z-10 text-xs font-semibold text-[#1a2233]">{data.node.label}</span>
      </motion.div>
    )
  }

  return (
    <motion.div
      role="button"
      tabIndex={0}
      aria-label={`${data.node.label} - ${visual.label} node, status ${statusLabel}, press Enter for details`}
      aria-pressed={selected}
      onClick={() => data.onActivate(data.node.id)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          data.onActivate(data.node.id)
        }
      }}
      initial={false}
      animate={
        prefersReducedMotion
          ? undefined
          : data.shake
            ? { x: [0, -6, 6, -4, 4, 0] }
            : data.active
              ? { boxShadow: `0 0 0 3px ${activeGlow}66, 0 0 18px 2px ${activeGlow}55`, x: 0 }
              : { boxShadow: '0 0 0 0px transparent', x: 0 }
      }
      transition={data.shake ? { duration: 0.4 } : { duration: 0.35 }}
      className={`flex h-full w-full cursor-pointer flex-col justify-center gap-1 rounded-lg border px-3 py-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent ${
        selected ? 'border-accent' : kind === 'engine' ? 'border-[#4d7fff]' : 'border-[#263352]'
      } ${borderColor ? 'border-transparent' : ''}`}
      style={{
        background: kind === 'engine' ? ENGINE_BACKGROUND : TILE_BACKGROUND,
        boxShadow: kind === 'engine' ? undefined : TILE_SHADOW,
        ...(borderColor ? { borderColor } : {}),
      }}
    >
      <Handle type="target" position={Position.Left} className="!bg-text-dim" />
      <Handle type="source" position={Position.Right} className="!bg-text-dim" />
      <div className="flex items-center gap-1.5">
        <span
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded"
          style={{ color: kind === 'engine' ? '#eaf1ff' : visual.color }}
        >
          <ArchIcon icon={data.node.icon} size={14} />
        </span>
        <span className={`truncate text-xs font-medium ${kind === 'engine' ? 'text-white' : 'text-text'}`}>
          {data.node.label}
        </span>
        {(data.node.status_key || data.liveState || data.runStatus !== 'idle') && (
          <span
            className="ml-auto h-2 w-2 shrink-0 rounded-full"
            style={{ background: resultColor ?? NODE_STATE_VISUALS.idle.color }}
            aria-label={`status: ${statusLabel}`}
            title={statusTooltip}
          />
        )}
      </div>
      <p className={`truncate text-[10px] ${kind === 'engine' ? 'text-white/70' : 'text-text-dim'}`}>
        {data.node.tag ?? visual.label}
      </p>
    </motion.div>
  )
}
