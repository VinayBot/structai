import { useState } from 'react'
import { siGithub } from 'simple-icons'
import { authApi, ApiError } from '../../lib/api'
import { Button } from '../ui/Button'

export const GITHUB_OAUTH_STATE_KEY = 'structai_github_oauth_state'

export function GithubLoginButton() {
  const [error, setError] = useState<string | null>(null)
  const [redirecting, setRedirecting] = useState(false)

  async function handleClick() {
    setError(null)
    setRedirecting(true)
    try {
      const state = crypto.randomUUID()
      sessionStorage.setItem(GITHUB_OAUTH_STATE_KEY, state)
      const { authorize_url } = await authApi.githubLogin(state)
      window.location.href = authorize_url
    } catch (err) {
      setRedirecting(false)
      setError(err instanceof ApiError ? err.message : 'GitHub login is unavailable right now')
    }
  }

  return (
    <div>
      <Button
        type="button"
        variant="secondary"
        className="w-full"
        onClick={handleClick}
        disabled={redirecting}
      >
        <svg role="img" viewBox="0 0 24 24" className="h-4 w-4 fill-current">
          <path d={siGithub.path} />
        </svg>
        {redirecting ? 'Redirecting…' : 'Continue with GitHub'}
      </Button>
      {error && <p className="mt-2 text-center text-xs text-danger">{error}</p>}
    </div>
  )
}
