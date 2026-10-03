import { NavLink, useLocation, useOutlet } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useAuth } from '../../context/AuthContext'
import { Button } from '../ui/Button'

const NAV_ITEMS = [
  { to: '/app/chat', label: 'Chat' },
  { to: '/app/projects', label: 'Projects' },
  { to: '/app/architecture', label: 'Architecture' },
  { to: '/app/traces', label: 'Traces' },
  { to: '/app/metrics', label: 'Metrics' },
  { to: '/app/evaluation', label: 'Evaluation' },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const outlet = useOutlet()
  const prefersReducedMotion = useReducedMotion()

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r border-border bg-surface p-4">
        <div className="mb-8 px-2 text-lg font-semibold text-text">StructAI</div>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `relative overflow-hidden rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'text-accent' : 'text-text-dim hover:bg-surface-raised hover:text-text'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-lg bg-accent/15"
                      transition={
                        prefersReducedMotion
                          ? { duration: 0 }
                          : { type: 'spring', bounce: 0.2, duration: 0.4 }
                      }
                    />
                  )}
                  <span className="relative z-10">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-2 border-t border-border pt-4">
          <div className="truncate px-2 text-xs text-text-dim">{user?.email}</div>
          <Button variant="ghost" className="w-full justify-start" onClick={() => void logout()}>
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto bg-bg p-8">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}
