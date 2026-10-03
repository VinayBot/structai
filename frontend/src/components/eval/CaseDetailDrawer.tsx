import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { CaseResult, GoldenCase } from '../../lib/types'
import { formatMs } from '../../lib/format'
import { Chip } from '../ui/Chip'
import { JsonView } from '../ui/JsonView'

export function CaseDetailDrawer({
  goldenCase,
  result,
  onClose,
}: {
  goldenCase: GoldenCase | null
  result: CaseResult | null
  onClose: () => void
}) {
  useEffect(() => {
    if (!goldenCase) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [goldenCase, onClose])

  return (
    <AnimatePresence>
      {goldenCase && (
        <>
          <motion.div
            key="backdrop"
            className="fixed inset-0 z-40 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            key="drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`${goldenCase.id} details`}
            className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-border bg-surface shadow-xl sm:w-[440px]"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-border p-4">
              <div>
                <h2 className="text-sm font-semibold text-text">{goldenCase.id}</h2>
                <p className="text-xs text-text-dim">{goldenCase.category}</p>
              </div>
              <button type="button" onClick={onClose} className="text-text-dim hover:text-text" aria-label="Close">
                ✕
              </button>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {result && (
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={result.passed ? 'success' : 'danger'}>{result.passed ? 'pass' : 'fail'}</Chip>
                  {result.provider && <Chip tone="neutral">{result.provider}</Chip>}
                  {result.model && <Chip tone="neutral">{result.model}</Chip>}
                  <Chip tone="neutral">{formatMs(result.latency_ms)}</Chip>
                  {result.attempts !== null && <Chip tone="neutral">{result.attempts} attempt(s)</Chip>}
                </div>
              )}

              {result?.reason && <p className="text-xs text-danger">{result.reason}</p>}

              {result?.trace_id && (
                <p className="text-xs text-text-dim">
                  trace id: <span className="font-mono text-text">{result.trace_id}</span>
                </p>
              )}

              <div>
                <p className="mb-1 text-xs font-medium text-text-dim">Prompt</p>
                <p className="rounded-lg border border-border bg-surface-raised p-3 text-xs text-text">
                  {goldenCase.prompt}
                </p>
              </div>

              <div>
                <p className="mb-1 text-xs font-medium text-text-dim">Schema</p>
                <JsonView data={goldenCase.schema_def} defaultExpanded={false} />
              </div>

              {result && (
                <div>
                  <p className="mb-1 text-xs font-medium text-text-dim">Output</p>
                  <JsonView data={result.data} defaultExpanded />
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
