import { Chip } from '../../components/ui/Chip'
import type { StructuredAnswerResponse } from '../../lib/types'

export function ResultView({ result }: { result: StructuredAnswerResponse }) {
  const pii = result.meta.pii
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Chip tone="accent">{result.provider}</Chip>
        <Chip tone="neutral">{result.model}</Chip>
        <Chip tone="neutral">
          {result.attempts} attempt{result.attempts === 1 ? '' : 's'}
        </Chip>
        {pii.found && (
          <Chip tone="warning">PII redacted: {pii.categories.join(', ')}</Chip>
        )}
      </div>
      <pre className="overflow-x-auto rounded-lg border border-border bg-surface-raised p-3 text-sm text-text">
        {JSON.stringify(result.data, null, 2)}
      </pre>
    </div>
  )
}
