import type { ArchNodeState, ArchStatusResponse } from '../../lib/types'
import { formatMs } from '../../lib/format'
import { Chip } from '../ui/Chip'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'

interface StatusBarProps {
  status: ArchStatusResponse | null
  loading: boolean
  onRefresh: () => void
  buildTime: string | null
}

const NODE_STATE_TONE: Record<ArchNodeState, 'success' | 'warning' | 'danger' | 'neutral'> = {
  healthy: 'success',
  degraded: 'warning',
  failed: 'danger',
  idle: 'neutral',
}

function statusChipTone(p: ArchStatusResponse['ollama']): 'success' | 'danger' | 'neutral' {
  if (p.available) return 'success'
  if (p.detail.startsWith('disabled')) return 'neutral'
  return 'danger'
}

function ProviderChip({ name, p }: { name: string; p: ArchStatusResponse['ollama'] }) {
  return (
    <div className="flex items-center gap-1.5">
      <Chip tone={statusChipTone(p)}>
        {name}
        {p.latency_ms !== null ? ` - ${formatMs(p.latency_ms)}` : ''}
      </Chip>
    </div>
  )
}

export function StatusBar({ status, loading, onRefresh, buildTime }: StatusBarProps) {
  const dbState = status?.nodes['persistence']?.state ?? null

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface px-4 py-2">
      {status ? (
        <>
          <ProviderChip name="Ollama" p={status.ollama} />
          <ProviderChip name="Groq" p={status.groq} />
          <ProviderChip name="MCP" p={status.mcp} />
          <Chip tone={dbState ? NODE_STATE_TONE[dbState] : 'neutral'}>
            Database {dbState ?? 'unknown'}
          </Chip>
          <span className="text-xs text-text-dim">
            checked {new Date(status.checked_at).toLocaleTimeString()}
          </span>
        </>
      ) : (
        <span className="text-xs text-text-dim">Checking provider status...</span>
      )}
      {buildTime ? (
        <span className="text-xs text-text-dim">build {buildTime}</span>
      ) : null}
      <Button variant="ghost" onClick={onRefresh} disabled={loading} className="ml-auto">
        {loading ? <Spinner /> : 'Refresh'}
      </Button>
    </div>
  )
}
