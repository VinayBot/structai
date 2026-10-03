import { useRef } from 'react'
import type { ReactNode } from 'react'

export const DOCK_MIN_WIDTH = 280
export const DOCK_MAX_WIDTH = 560
export const DOCK_DEFAULT_WIDTH = 320

interface SideDockProps {
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
  width: number
  onWidthChange: (width: number) => void
  title: string
  headerExtra?: ReactNode
  children: ReactNode
}

/**
 * Collapsible/resizable wrapper around the Architecture tab's right panel
 * (Scenarios/Live Run). Collapsed by default so the canvas gets the full
 * width on first load; `ArchitecturePage` auto-expands it on a node click or
 * a Live Run start by flipping `collapsed` to false.
 */
export function SideDock({
  collapsed,
  onCollapsedChange,
  width,
  onWidthChange,
  title,
  headerExtra,
  children,
}: SideDockProps) {
  const dragState = useRef<{ startX: number; startWidth: number } | null>(null)

  function handleResizeStart(event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault()
    dragState.current = { startX: event.clientX, startWidth: width }

    function handleMove(moveEvent: PointerEvent) {
      const drag = dragState.current
      if (!drag) return
      const delta = drag.startX - moveEvent.clientX
      const next = Math.min(DOCK_MAX_WIDTH, Math.max(DOCK_MIN_WIDTH, drag.startWidth + delta))
      onWidthChange(next)
    }
    function handleUp() {
      dragState.current = null
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  if (collapsed) {
    return (
      <button
        type="button"
        aria-label={`Expand ${title}`}
        onClick={() => onCollapsedChange(false)}
        className="flex shrink-0 flex-col items-center justify-center gap-2 border-t border-border bg-surface px-2 py-3 text-xs font-medium text-text-dim hover:text-text md:h-auto md:w-9 md:border-l md:border-t-0 md:py-4"
      >
        <span className="md:[writing-mode:vertical-rl]">{title}</span>
      </button>
    )
  }

  return (
    <aside
      style={{ '--dock-width': `${width}px` } as React.CSSProperties}
      className="relative flex h-72 shrink-0 flex-col border-t border-border bg-surface md:h-auto md:w-[var(--dock-width)] md:border-l md:border-t-0"
    >
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panel"
        onPointerDown={handleResizeStart}
        className="absolute inset-y-0 left-0 hidden w-1.5 -translate-x-1/2 cursor-col-resize touch-none md:block hover:bg-accent/40"
      />
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text">{title}</h2>
        <div className="flex items-center gap-2">
          {headerExtra}
          <button
            type="button"
            aria-label={`Collapse ${title}`}
            onClick={() => onCollapsedChange(true)}
            className="rounded px-1.5 py-0.5 text-xs text-text-dim hover:bg-surface-raised hover:text-text"
          >
            ✕
          </button>
        </div>
      </div>
      {children}
    </aside>
  )
}
