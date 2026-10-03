import { useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react'
import type { Edge, EdgeProps } from '@xyflow/react'
import type { ArchEdgeRenderData } from '../../lib/archLayout'
import { EDGE_KIND_VISUALS } from '../../lib/archVisuals'

type ArchFlowEdge = Edge<ArchEdgeRenderData, 'archEdge'>
type Point = { x: number; y: number }

/** Straight-segment path through elkjs's orthogonal bend points - sharp 90-degree corners are the expected look for this routing style, no rounding needed. */
function orthogonalPath(points: Point[]): string {
  const [first, ...rest] = points
  return `M ${first.x} ${first.y} ${rest.map((p) => `L ${p.x} ${p.y}`).join(' ')}`
}

/** Point at the midpoint of the path's total length, for label placement. */
function pathMidpoint(points: Point[]): Point {
  const segmentLengths = points.slice(1).map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y))
  const total = segmentLengths.reduce((sum, len) => sum + len, 0)
  let remaining = total / 2
  for (let i = 0; i < segmentLengths.length; i++) {
    const len = segmentLengths[i]
    if (remaining <= len || i === segmentLengths.length - 1) {
      const t = len === 0 ? 0 : remaining / len
      const a = points[i]
      const b = points[i + 1]
      return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }
    }
    remaining -= len
  }
  return points[0]
}

export function ArchEdgeLine({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  data,
  markerEnd,
}: EdgeProps<ArchFlowEdge>) {
  const prefersReducedMotion = useReducedMotion()
  const [hovered, setHovered] = useState(false)

  const [fallbackPath, fallbackLabelX, fallbackLabelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 8,
  })

  if (!data) return null

  const usingElkPoints = (data.points?.length ?? 0) >= 2
  const edgePath = usingElkPoints ? orthogonalPath(data.points!) : fallbackPath
  const { x: labelX, y: labelY } = usingElkPoints ? pathMidpoint(data.points!) : { x: fallbackLabelX, y: fallbackLabelY }

  const visual = EDGE_KIND_VISUALS[data.edge.kind]
  const color = data.active ? '#f0cc6b' : data.edge.kind === 'feedback' ? '#5a6b8c' : '#7fe3d8'
  const showLabel = data.active || selected || hovered

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: color,
          strokeWidth: data.active ? 2.5 : 1.5,
          strokeDasharray: visual.dash ?? '4 4',
          strokeLinecap: 'round',
        }}
      />
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={16}
        style={{ cursor: 'pointer' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => data.onActivate(data.edge.id)}
      />
      {data.active && data.runToken !== undefined && !prefersReducedMotion && (
        <circle r="4.5" fill="#f0cc6b" style={{ filter: 'drop-shadow(0 0 4px #f0cc6b)' }}>
          <animateMotion
            key={`${id}-${data.runToken}`}
            dur="0.45s"
            repeatCount="1"
            fill="freeze"
            path={edgePath}
          />
        </circle>
      )}
      {showLabel && (
        <EdgeLabelRenderer>
          <button
            type="button"
            onClick={() => data.onActivate(data.edge.id)}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
            }}
            className={`rounded border px-1.5 py-0.5 text-[9px] font-medium shadow-sm transition-colors ${
              data.active
                ? 'border-gold bg-gold/20 text-gold'
                : 'border-border bg-surface text-text-dim hover:border-accent hover:text-text'
            }`}
          >
            {data.edge.label}
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
