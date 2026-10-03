import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ApiError, authApi } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'

export function RegisterPage() {
  const prefersReducedMotion = useReducedMotion()
  const { register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [emailMessage, setEmailMessage] = useState<string | null>(null)
  const [emailSuggestion, setEmailSuggestion] = useState<string | null>(null)
  const [checkingEmail, setCheckingEmail] = useState(false)

  async function handleEmailBlur() {
    if (!email) return
    setCheckingEmail(true)
    setEmailMessage(null)
    setEmailSuggestion(null)
    try {
      const result = await authApi.checkEmail(email)
      if (!result.valid) {
        setEmailMessage(result.message)
        setEmailSuggestion(result.suggestion)
      } else if (result.warning) {
        setEmailMessage(result.warning)
      }
    } catch (err) {
      if (err instanceof ApiError) setEmailMessage(err.message)
    } finally {
      setCheckingEmail(false)
    }
  }

  function applySuggestion() {
    if (!emailSuggestion) return
    setEmail(emailSuggestion)
    setEmailMessage(null)
    setEmailSuggestion(null)
    setError(null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register(email, password)
      navigate('/app/chat')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        setEmailSuggestion(err.suggestion)
      } else {
        setError('Registration failed')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <motion.div
        initial={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, y: 12, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="w-full max-w-sm"
      >
        <Card>
          <h1 className="mb-6 text-xl font-semibold text-text">Create an account</h1>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setEmailMessage(null)
                  setEmailSuggestion(null)
                }}
                onBlur={handleEmailBlur}
                required
              />
              {checkingEmail && <p className="mt-1 text-xs text-text-dim">Checking email…</p>}
              {emailMessage && (
                <p className="mt-1 text-xs text-text-dim">
                  {emailMessage}
                  {emailSuggestion && (
                    <>
                      {' '}
                      Did you mean{' '}
                      <button
                        type="button"
                        onClick={applySuggestion}
                        className="text-accent hover:underline"
                      >
                        {emailSuggestion}
                      </button>
                      ?
                    </>
                  )}
                </p>
              )}
            </div>
            <Input
              type="password"
              placeholder="password (8+ chars, at least one digit)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
            {error && (
              <p className="text-sm text-danger">
                {error}
                {emailSuggestion && (
                  <>
                    {' '}
                    Did you mean{' '}
                    <button
                      type="button"
                      onClick={applySuggestion}
                      className="text-accent hover:underline"
                    >
                      {emailSuggestion}
                    </button>
                    ?
                  </>
                )}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? 'Creating account…' : 'Sign up'}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-text-dim">
            Already have an account?{' '}
            <Link to="/login" className="text-accent hover:underline">
              Log in
            </Link>
          </p>
        </Card>
      </motion.div>
    </div>
  )
}
