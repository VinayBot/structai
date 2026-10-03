import { useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

export interface ToastData {
  id: number
  tone: 'danger' | 'success'
  title: string
  detail?: string
}

interface ToastProps {
  toast: ToastData | null
  onDismiss: () => void
}

export function Toast({ toast, onDismiss }: ToastProps) {
  const prefersReducedMotion = useReducedMotion()

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(onDismiss, 5000)
    return () => clearTimeout(timer)
  }, [toast, onDismiss])

  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          role="alert"
          aria-live="assertive"
          initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 16 }}
          transition={{ duration: 0.2 }}
          className={`fixed bottom-4 left-1/2 z-50 w-[min(92vw,22rem)] -translate-x-1/2 rounded-xl border p-3 shadow-xl ${
            toast.tone === 'danger'
              ? 'border-danger/50 bg-danger/15 text-danger'
              : 'border-success/50 bg-success/15 text-success'
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-semibold">{toast.title}</p>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss notification"
              className="shrink-0 opacity-70 hover:opacity-100"
            >
              ✕
            </button>
          </div>
          {toast.detail && <p className="mt-1 text-xs opacity-90">{toast.detail}</p>}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
