import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { AUTH_EXPIRED_EVENT, TOKEN_KEY } from '../../shared/api.js'

const USER_KEY = 'reweave_user'
const AuthContext = createContext(null)

function readStoredUser() {
  try {
    const stored = localStorage.getItem(USER_KEY)
    return stored ? JSON.parse(stored) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser)

  function login(token, role, name) {
    const u = { token, role, name }
    try {
      localStorage.setItem(USER_KEY, JSON.stringify(u))
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      // Storage unavailable (private mode); the session lasts until reload.
    }
    setUser(u)
  }

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(USER_KEY)
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      // Nothing persisted to clear.
    }
    setUser(null)
  }, [])

  // The API client fires this when the server rejects the stored token.
  useEffect(() => {
    window.addEventListener(AUTH_EXPIRED_EVENT, logout)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, logout)
  }, [logout])

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
