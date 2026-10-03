import { Chip } from '../../components/ui/Chip'
import { Spinner } from '../../components/ui/Spinner'
import type { StreamEvent } from '../../lib/types'

const STAGE_LABEL: Record<StreamEvent['stage'], string> = {
  generating: 'Generating',
  validating: 'Validating',
  retrying: 'Retrying',
  output_leak: 'Blocked (output leak)',
  output_pii: 'Blocked (output PII)',
  done: 'Done',
  error: 'Error',
}

const TERMINAL_STAGES: StreamEvent['stage'][] = ['done', 'error', 'output_leak', 'output_pii']

function toneFor(stage: StreamEvent['stage'], isLast: boolean) {
  if (stage === 'done') return 'success' as const
  if (stage === 'error' || stage === 'output_leak' || stage === 'output_pii') return 'danger' as const
  if (stage === 'retrying') return 'warning' as const
  return isLast ? ('accent' as const) : ('neutral' as const)
}

export function StageChips({ events }: { events: StreamEvent[] }) {
  if (events.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {events.map((event, index) => {
        const isLast = index === events.length - 1
        const isActive = isLast && !TERMINAL_STAGES.includes(event.stage)
        return (
          <Chip key={index} tone={toneFor(event.stage, isLast)}>
            {isActive && <Spinner className="h-3 w-3" />}
            {STAGE_LABEL[event.stage]}
            {event.attempt > 0 && ` · attempt ${event.attempt}`}
          </Chip>
        )
      })}
    </div>
  )
}
