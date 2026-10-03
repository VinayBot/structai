import { AnimatePresence, motion } from 'framer-motion'
import type { ArchEdge } from '../../lib/types'
import { EDGE_KIND_VISUALS } from '../../lib/archVisuals'
import { Chip } from '../ui/Chip'

interface EdgeDetailPopoverProps {
  edge: ArchEdge | null
  onClose: () => void
}

export function EdgeDetailPopover({ edge, onClose }: EdgeDetailPopoverProps) {
  return (
    <AnimatePresence>
      {edge && (
        <motion.div
          role="dialog"
          aria-label={`${edge.label} edge details`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.18 }}
          className="absolute bottom-4 left-4 z-30 w-72 rounded-xl border border-border bg-surface p-4 shadow-xl"
        >
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-sm font-semibold text-text">{edge.label}</h3>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close edge details"
              className="rounded p-0.5 text-text-dim hover:bg-surface-raised hover:text-text"
            >
              ✕
            </button>
          </div>
          <div className="mt-2">
            <Chip tone="neutral">{EDGE_KIND_VISUALS[edge.kind].label}</Chip>
          </div>
          <p className="mt-2.5 text-xs text-text-dim">{edge.contract}</p>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
