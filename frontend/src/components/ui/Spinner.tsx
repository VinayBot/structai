export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-text-dim/30 border-t-accent ${className}`}
      aria-label="loading"
    />
  )
}
