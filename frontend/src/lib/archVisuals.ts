import type { ArchEdge, ArchGroupColor, ArchNodeKind, ArchNodeState } from './types'

interface KindVisual {
  label: string
  badge: string
  color: string
}

/**
 * Poster palette: navy canvas (#050b18), electric-blue "engine" blocks (#2563ff),
 * dashed teal connectors (#7fe3d8, see ArchEdgeLine.tsx) - KIND_VISUALS still drives
 * the drawer's badge/subtitle (semantic `kind`, independent of poster `visual_kind`).
 */
export const KIND_VISUALS: Record<ArchNodeKind, KindVisual> = {
  client: { label: 'Client', badge: 'CL', color: '#7c9bff' },
  edge: { label: 'Edge', badge: 'ED', color: '#f0cc6b' },
  guardrail: { label: 'Guardrail', badge: 'GD', color: '#b89cf7' },
  service: { label: 'Service', badge: 'SV', color: '#3ddbb0' },
  gateway: { label: 'Gateway', badge: 'GW', color: '#2563ff' },
  provider: { label: 'Model provider', badge: 'PR', color: '#ffb454' },
  data: { label: 'Data', badge: 'DB', color: '#8ea3c9' },
  observability: { label: 'Observability', badge: 'OB', color: '#4ea1ff' },
  mcp: { label: 'MCP', badge: 'MC', color: '#7c9bff' },
  infra: { label: 'Infrastructure', badge: 'IN', color: '#8ea3c9' },
}

export const GROUP_COLOR_VISUALS: Record<ArchGroupColor, { border: string; text: string }> = {
  gold: { border: '#c9a04a', text: '#f0cc6b' },
  purple: { border: '#8b7cf6', text: '#b4a7fa' },
  neutral: { border: '#263352', text: '#7f93b8' },
}

export const NODE_STATE_VISUALS: Record<ArchNodeState, { color: string; label: string }> = {
  healthy: { color: '#3ddbb0', label: 'Healthy' },
  degraded: { color: '#ffb454', label: 'Degraded' },
  failed: { color: '#ff6b7a', label: 'Failed' },
  idle: { color: '#5a6b8c', label: 'Idle' },
}

export const EDGE_KIND_VISUALS: Record<ArchEdge['kind'], { label: string; dash?: string }> = {
  sync: { label: 'Sync call' },
  async: { label: 'Async / persisted', dash: '6 4' },
  observability: { label: 'Observability side-channel', dash: '2 3' },
  feedback: { label: 'Feedback (retry / error)', dash: '5 4' },
}
