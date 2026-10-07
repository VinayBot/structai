import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GithubCallbackPage } from './GithubCallbackPage'
import { GITHUB_OAUTH_STATE_KEY } from '../components/auth/GithubLoginButton'
import { ApiError } from '../lib/api'

const { loginWithGithub } = vi.hoisted(() => ({
  loginWithGithub: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), register: vi.fn(), loginWithGithub, logout: vi.fn() }),
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/auth/github/callback" element={<GithubCallbackPage />} />
        <Route path="/app/chat" element={<div>chat landing</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('GithubCallbackPage', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('completes login and navigates when code and state match', async () => {
    sessionStorage.setItem(GITHUB_OAUTH_STATE_KEY, 'matching-state')
    loginWithGithub.mockResolvedValue(undefined)

    renderAt('/auth/github/callback?code=abc123&state=matching-state')

    expect(await screen.findByText('chat landing')).toBeInTheDocument()
    expect(loginWithGithub).toHaveBeenCalledWith('abc123')
    expect(sessionStorage.getItem(GITHUB_OAUTH_STATE_KEY)).toBeNull()
  })

  it('shows an error and never calls loginWithGithub when state does not match', async () => {
    sessionStorage.setItem(GITHUB_OAUTH_STATE_KEY, 'expected-state')

    renderAt('/auth/github/callback?code=abc123&state=tampered-state')

    expect(await screen.findByText(/invalid or expired/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to login/i })).toBeInTheDocument()
    expect(loginWithGithub).not.toHaveBeenCalled()
  })

  it('shows an error when there is no stored state at all (e.g. a stale or replayed link)', async () => {
    renderAt('/auth/github/callback?code=abc123&state=anything')

    expect(await screen.findByText(/invalid or expired/i)).toBeInTheDocument()
    expect(loginWithGithub).not.toHaveBeenCalled()
  })

  it('shows the backend error message when loginWithGithub rejects', async () => {
    sessionStorage.setItem(GITHUB_OAUTH_STATE_KEY, 'matching-state')
    loginWithGithub.mockRejectedValue(
      new ApiError(502, 'oauth_failed', 'github rejected the authorization code', 'req-1'),
    )

    renderAt('/auth/github/callback?code=abc123&state=matching-state')

    expect(await screen.findByText(/github rejected the authorization code/i)).toBeInTheDocument()
  })
})
