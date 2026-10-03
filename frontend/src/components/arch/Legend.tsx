import { motion } from 'framer-motion'
import { KIND_VISUALS, EDGE_KIND_VISUALS, NODE_STATE_VISUALS } from '../../lib/archVisuals'

/** Mirrors the real state logic in app/services/arch_service.py::_provider_node_state. */
const NODE_STATE_MEANINGS: Record<keyof typeof NODE_STATE_VISUALS, string> = {
  healthy: 'responded to its last live check, under 2s',
  degraded: 'responded, but took over 2s',
  failed: "didn't respond to its last live check",
  idle: 'no live check performed yet',
}

export function Legend({ onClose }: { onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.18 }}
      className="absolute right-4 top-16 z-30 w-64 rounded-xl border border-border bg-surface p-4 shadow-xl"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-text-dim">Legend</h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close legend"
          className="rounded p-0.5 text-text-dim hover:bg-surface-raised hover:text-text"
        >
          ✕
        </button>
      </div>

      <div className="mt-3 space-y-1.5">
        {Object.entries(KIND_VISUALS).map(([kind, visual]) => (
          <div key={kind} className="flex items-center gap-2 text-xs text-text">
            <span
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-[8px] font-bold text-bg"
              style={{ background: visual.color }}
            >
              {visual.badge}
            </span>
            {visual.label}
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-1.5 border-t border-border pt-3">
        {Object.entries(NODE_STATE_VISUALS).map(([state, visual]) => (
          <div key={state} className="flex items-center gap-2 text-xs text-text">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: visual.color }} />
            <span>
              {visual.label}
              <span className="text-text-dim"> - {NODE_STATE_MEANINGS[state as keyof typeof NODE_STATE_MEANINGS]}</span>
            </span>
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-1.5 border-t border-border pt-3">
        {Object.entries(EDGE_KIND_VISUALS).map(([kind, visual]) => (
          <div key={kind} className="flex items-center gap-2 text-xs text-text">
            <svg width="20" height="6" aria-hidden="true">
              <line
                x1="0"
                y1="3"
                x2="20"
                y2="3"
                stroke="#7fe3d8"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeDasharray={visual.dash ?? '4 4'}
              />
            </svg>
            {visual.label}
          </div>
        ))}
      </div>
    </motion.div>
  )
}
