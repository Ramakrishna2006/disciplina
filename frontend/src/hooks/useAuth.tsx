import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import { ApiError, api } from "@/services/api"
import type { User } from "@/types/api"

type Status = "loading" | "signed-in" | "signed-out"

interface AuthContextValue {
  user: User | null
  status: Status
  login: (email: string, password: string) => Promise<User>
  register: (name: string, email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  /** After the Settings page saved a change: show the new name, theme, ... everywhere. */
  updateUser: (user: User) => void
  /** After the account was deleted: forget the user (the server already cleared the cookies). */
  forget: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Knows who is signed in. On first load it asks the backend (/api/auth/me): the httpOnly cookies
 * decide, so a page reload keeps you signed in and nothing secret is kept in JavaScript.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<Status>("loading")

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((me) => {
        if (!cancelled) {
          setUser(me)
          setStatus("signed-in")
        }
      })
      .catch(() => {
        // 401 = not signed in. Any other failure (server down) also starts signed out; pages that
        // need data show their own error with a "Try again" button.
        if (!cancelled) setStatus("signed-out")
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const me = await api.login(email, password)
    setUser(me)
    setStatus("signed-in")
    return me
  }, [])

  const register = useCallback(async (name: string, email: string, password: string) => {
    const me = await api.register(name, email, password)
    setUser(me)
    setStatus("signed-in")
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch (e) {
      // Even if the server cannot be reached, forget the user here; the cookies expire on their own.
      if (!(e instanceof ApiError)) throw e
    } finally {
      setUser(null)
      setStatus("signed-out")
    }
  }, [])

  const updateUser = useCallback((next: User) => setUser(next), [])
  const forget = useCallback(() => {
    setUser(null)
    setStatus("signed-out")
  }, [])

  const value = useMemo(
    () => ({ user, status, login, register, logout, updateUser, forget }),
    [user, status, login, register, logout, updateUser, forget]
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>")
  return ctx
}
