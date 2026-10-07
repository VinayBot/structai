import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi, clearTokens, getAccessToken, getRefreshToken, setTokens } from '../lib/api'
import type { User } from '../lib/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  loginWithGithub: (code: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function bootstrap() {
      if (!getAccessToken()) {
        setLoading(false)
        return
      }
      try {
        setUser(await authApi.me())
      } catch {
        clearTokens()
      } finally {
        setLoading(false)
      }
    }
    void bootstrap()
  }, [])

  async function login(email: string, password: string) {
    const tokens = await authApi.login(email, password)
    setTokens(tokens)
    setUser(await authApi.me())
  }

  async function register(email: string, password: string) {
    await authApi.register(email, password)
    await login(email, password)
  }

  async function loginWithGithub(code: string) {
    const tokens = await authApi.githubCallback(code)
    setTokens(tokens)
    setUser(await authApi.me())
  }

  async function logout() {
    const refreshToken = getRefreshToken()
    try {
      if (refreshToken) await authApi.logout(refreshToken)
    } finally {
      clearTokens()
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginWithGithub, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
