import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, clearToken, getToken, setSessionExpiredHandler, setToken } from './api'
import type { User } from './types'

// The live /auth/me profile. After login (or on boot with a stored token)
// we fill it in from the real endpoint so email_verified and friends are
// accurate; while that's in flight we show the fast JWT-derived identity.
export type SessionUser = Pick<User, 'id' | 'username' | 'email' | 'email_verified'>

interface AuthContextValue {
  user: SessionUser | null
  login: (username: string, password: string) => Promise<void>
  register: (input: { email: string; username: string; password: string; full_name?: string }) => Promise<void>
  logout: () => void
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

// Placeholder profile used the moment a token exists, before /auth/me
// returns the real one. Never falsy-identity: the session is navigable
// immediately, the banner just stays quiet until the profile lands.
function placeholderSession(token: string): SessionUser | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return { id: Number(payload.sub), username: payload.username, email: '', email_verified: false }
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(() => {
    const token = getToken()
    return token ? placeholderSession(token) : null
  })

  const refreshProfile = useCallback(async () => {
    if (!getToken()) return
    try {
      const profile = await api.me()
      setUser(profile)
    } catch {
      // Token is invalid/expired -- api.request already handled the 401
      // session-expiry path; nothing more to do here.
    }
  }, [])

  const login = useCallback(
    async (username: string, password: string) => {
      const { access_token } = await api.login({ username, password })
      setToken(access_token)
      setUser(placeholderSession(access_token))
      await refreshProfile()
    },
    [refreshProfile],
  )

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

  // Some providers land users on /app after a page refresh; pull the real
  // profile (email_verified, email) once on boot.
  useEffect(() => {
    void refreshProfile()
  }, [refreshProfile])

  const value = useMemo(
    () => ({ user, login, register, logout, refreshProfile }),
    [user, login, register, logout, refreshProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}