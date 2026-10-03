import { Card } from '../ui/Card'

function Block({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-surface-raised ${className}`} />
}

export function MetricsSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading metrics summary">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Card key={i} className="space-y-2 p-4">
            <Block className="h-3 w-16" />
            <Block className="h-7 w-12" />
          </Card>
        ))}
      </div>

      <Card>
        <Block className="mb-3 h-4 w-56" />
        <Block className="h-[220px] w-full" />
      </Card>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card className="space-y-3">
          <Block className="h-4 w-32" />
          <Block className="h-[180px] w-full" />
        </Card>
        <Card className="space-y-3">
          <Block className="h-4 w-24" />
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Block key={i} className="h-6 w-28" />
            ))}
          </div>
        </Card>
      </div>

      <Card className="space-y-3">
        <Block className="h-4 w-24" />
        {Array.from({ length: 3 }, (_, i) => (
          <Block key={i} className="h-5 w-full" />
        ))}
      </Card>

      <Card className="space-y-3">
        <Block className="h-4 w-36" />
        {Array.from({ length: 2 }, (_, i) => (
          <Block key={i} className="h-5 w-full" />
        ))}
      </Card>
    </div>
  )
}
