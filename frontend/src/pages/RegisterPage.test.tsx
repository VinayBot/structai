import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RegisterPage } from './RegisterPage'
import { ApiError } from '../lib/api'

const { checkEmail } = vi.hoisted(() => ({
  checkEmail: vi.fn(),
}))

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    authApi: { ...actual.authApi, checkEmail },
  }
})

const { register } = vi.hoisted(() => ({
  register: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), register, logout: vi.fn() }),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  )
}

describe('RegisterPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows the inline message and suggestion when the email check flags a typo', async () => {
    checkEmail.mockResolvedValue({
      valid: false,
      message: 'This looks like a typo of a popular email provider.',
      suggestion: 'user@gmail.com',
      warning: null,
    })
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByPlaceholderText('you@example.com'), 'user@gmial.com')
    await user.tab()

    expect(checkEmail).toHaveBeenCalledWith('user@gmial.com')
    expect(
      await screen.findByText(/this looks like a typo of a popular email provider/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'user@gmail.com' })).toBeInTheDocument()
  })

  it('applies the suggestion and clears the message when the suggestion button is clicked', async () => {
    checkEmail.mockResolvedValue({
      valid: false,
      message: 'This looks like a typo of a popular email provider.',
      suggestion: 'user@gmail.com',
      warning: null,
    })
    const user = userEvent.setup()
    renderPage()

    const input = screen.getByPlaceholderText('you@example.com')
    await user.type(input, 'user@gmial.com')
    await user.tab()
    await screen.findByRole('button', { name: 'user@gmail.com' })

    await user.click(screen.getByRole('button', { name: 'user@gmail.com' }))

    expect(input).toHaveValue('user@gmail.com')
    expect(
      screen.queryByText(/this looks like a typo of a popular email provider/i),
    ).not.toBeInTheDocument()
  })

  it('shows a non-blocking warning without a suggestion button when the address is otherwise valid', async () => {
    checkEmail.mockResolvedValue({
      valid: true,
      message: null,
      suggestion: null,
      warning: 'Could not confirm this domain accepts mail; proceed with caution.',
    })
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByPlaceholderText('you@example.com'), 'user@flaky-resolver.example')
    await user.tab()

    expect(
      await screen.findByText(/could not confirm this domain accepts mail/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /did you mean/i })).not.toBeInTheDocument()
  })

  it('shows the clickable suggestion under the submit error when registration fails with a suggestion', async () => {
    register.mockRejectedValue(
      new ApiError(422, 'invalid_email_domain', 'This domain looks like a typo.', 'req-1', null, 'alice@gmail.com'),
    )
    checkEmail.mockResolvedValue({ valid: true, message: null, suggestion: null, warning: null })
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByPlaceholderText('you@example.com'), 'alice@gmial.com')
    await user.type(
      screen.getByPlaceholderText('password (8+ chars, at least one digit)'),
      'password123',
    )
    await user.click(screen.getByRole('button', { name: 'Sign up' }))

    expect(await screen.findByText(/this domain looks like a typo/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'alice@gmail.com' })).toBeInTheDocument()
  })

  it('does not call checkEmail when the email field is blurred empty', async () => {
    const user = userEvent.setup()
    renderPage()

    screen.getByPlaceholderText('you@example.com').focus()
    await user.tab()

    await waitFor(() => expect(checkEmail).not.toHaveBeenCalled())
  })
})
