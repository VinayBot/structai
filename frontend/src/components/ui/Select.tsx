import type { SelectHTMLAttributes } from 'react'

export function Select({ className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-accent focus:outline-none ${className}`}
      {...props}
    />
  )
}
