import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { buttonClasses } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

const MotionLink = motion.create(Link)

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
}

const FEATURES = [
  {
    title: 'Guaranteed-valid JSON',
    body: 'Define any schema you like. The gateway retries with corrective feedback until the response actually validates — or tells you clearly why it couldn’t.',
  },
  {
    title: 'Local or free-tier models',
    body: 'Runs on your own Ollama models or the Groq free tier, with automatic fallback between providers.',
  },
  {
    title: 'Guardrails built in',
    body: 'Prompt-injection screening, PII redaction, rate limits, and daily quotas sit between your prompt and the model by default.',
  },
]

export function LandingPage() {
  const prefersReducedMotion = useReducedMotion()
  const initial = prefersReducedMotion ? 'show' : 'hidden'

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[420px] bg-cover bg-center opacity-20"
        style={{ backgroundImage: 'url(/hero.jpg)' }}
        aria-hidden="true"
      />

      <header className="relative flex items-center justify-between px-8 py-6">
        <div className="text-lg font-semibold">StructAI</div>
        <div className="flex gap-3">
          <MotionLink
            to="/login"
            whileHover={prefersReducedMotion ? undefined : { scale: 1.04 }}
            whileTap={prefersReducedMotion ? undefined : { scale: 0.97 }}
            className={buttonClasses('ghost')}
          >
            Log in
          </MotionLink>
          <MotionLink
            to="/register"
            whileHover={prefersReducedMotion ? undefined : { scale: 1.04 }}
            whileTap={prefersReducedMotion ? undefined : { scale: 0.97 }}
            className={buttonClasses('primary')}
          >
            Sign up
          </MotionLink>
        </div>
      </header>

      <main className="relative flex flex-1 flex-col items-center justify-center px-8 text-center">
        <motion.h1
          initial={initial}
          animate="show"
          variants={fadeUp}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="max-w-2xl text-5xl font-semibold tracking-tight text-text"
        >
          Ask anything. Get answers in your structure.
        </motion.h1>
        <motion.p
          initial={initial}
          animate="show"
          variants={fadeUp}
          transition={{ duration: 0.5, delay: 0.08, ease: 'easeOut' }}
          className="mt-4 max-w-xl text-text-dim"
        >
          Define the exact JSON shape you want back, and StructAI guarantees the model's answer
          validates against it &mdash; every time.
        </motion.p>
        <motion.div
          initial={initial}
          animate="show"
          variants={fadeUp}
          transition={{ duration: 0.5, delay: 0.16, ease: 'easeOut' }}
          className="mt-8 flex gap-3"
        >
          <MotionLink
            to="/register"
            whileHover={prefersReducedMotion ? undefined : { scale: 1.04 }}
            whileTap={prefersReducedMotion ? undefined : { scale: 0.97 }}
            className={buttonClasses('primary', 'px-6 py-3 text-base')}
          >
            Get started
          </MotionLink>
          <MotionLink
            to="/login"
            whileHover={prefersReducedMotion ? undefined : { scale: 1.04 }}
            whileTap={prefersReducedMotion ? undefined : { scale: 0.97 }}
            className={buttonClasses('secondary', 'px-6 py-3 text-base')}
          >
            I already have an account
          </MotionLink>
        </motion.div>

        <div className="mt-20 grid max-w-4xl gap-4 text-left sm:grid-cols-3">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={initial}
              animate="show"
              variants={fadeUp}
              transition={{ duration: 0.5, delay: 0.24 + i * 0.08, ease: 'easeOut' }}
            >
              <Card>
                <h2 className="mb-2 text-sm font-semibold text-text">{feature.title}</h2>
                <p className="text-sm text-text-dim">{feature.body}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  )
}
