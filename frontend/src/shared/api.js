// HTTP client shared by every feature's api.js: attaches the bearer token and
// turns error responses into ApiError. Each feature declares its own endpoint
// functions next to the code that uses them; the matching Pydantic models live
// in the same-named package under backend/app/.

const BASE = '/api'
export const TOKEN_KEY = 'reweave_token'

// Fired when the server rejects a stored token (expired or revoked), so the
// auth context can sign the user out instead of leaving pages half-loaded.
export const AUTH_EXPIRED_EVENT = 'auth:expired'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

async function errorMessage(res) {
  const text = await res.text()
  try {
    const { detail } = JSON.parse(text)
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  } catch {
    // Not JSON; fall through to the raw body.
  }
  return text || res.statusText
}

export async function request(path, options = {}) {
  const token = readToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    if (res.status === 401 && token) window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
    throw new ApiError(res.status, await errorMessage(res))
  }
  return res.json()
}

export function postJson(path, body, method = 'POST') {
  return request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
