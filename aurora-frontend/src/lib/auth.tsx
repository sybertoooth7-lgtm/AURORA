import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, clearToken, getToken, setSessionExpiredHandler, setToken } from './api'

interface SessionUser {
  id: number
  username: string
}

interface AuthContextValue {
  user: SessionUser | null
  login: (username: string, password: string) => Promise<void>
  register: (input: { email: string; username: string; password: string; full_name?: string }) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

// The backend doesn't expose a /auth/me endpoint -- the JWT already carries
// { sub, username }, so we read the session identity straight off the token
// instead of an extra round trip. This does not verify the signature; it's
// only used for display, not for anything security-sensitive.
function decodeSessionUser(token: string): SessionUser | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return { id: Number(payload.sub), username: payload.username }
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(() => {
    const token = getToken()
    return token ? decodeSessionUser(token) : null
  })

  const login = useCallback(async (username: string, password: string) => {
    const { access_token } = await api.login({ username, password })
    setToken(access_token)
    setUser(decodeSessionUser(access_token))
  }, [])

  const register = useCallback(
    async (input: { email: string; username: string; password: string; full_name?: string }) => {
      await api.register(input)
      await login(input.username, input.password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  // When api.ts sees a 401 on a request that carried a token, the token
  // is dead (revoked, expired, or the account's token_version moved on --
  // e.g. a password reset from another device). Log out cleanly here so
  // RequireAuth's next render redirects to /login, instead of the page
  // just silently failing every request.
  useEffect(() => {
    setSessionExpiredHandler(logout)
    return () => setSessionExpiredHandler(null)
  }, [logout])

  const value = useMemo(() => ({ user, login, register, logout }), [user, login, register, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
