import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { GITHUB_OAUTH_STATE_KEY } from '../components/auth/GithubLoginButton'
import { Card } from '../components/ui/Card'

export function GithubCallbackPage() {
  const [searchParams] = useSearchParams()
  const { loginWithGithub } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const ranOnce = useRef(false)

  useEffect(() => {
    if (ranOnce.current) return
    ranOnce.current = true

    async function run() {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const expectedState = sessionStorage.getItem(GITHUB_OAUTH_STATE_KEY)
      sessionStorage.removeItem(GITHUB_OAUTH_STATE_KEY)

      if (!code || !state || !expectedState || state !== expectedState) {
        setError('That GitHub login link is invalid or expired. Please try again.')
        return
      }

      try {
        await loginWithGithub(code)
        navigate('/app/chat', { replace: true })
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'GitHub login failed')
      }
    }
    void run()
  }, [searchParams, loginWithGithub, navigate])

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm text-center">
        {error ? (
          <>
            <p className="text-sm text-danger">{error}</p>
            <Link to="/login" className="mt-4 inline-block text-sm text-accent hover:underline">
              Back to login
            </Link>
          </>
        ) : (
          <p className="text-sm text-text-dim">Finishing GitHub sign-in…</p>
        )}
      </Card>
    </div>
  )
}
