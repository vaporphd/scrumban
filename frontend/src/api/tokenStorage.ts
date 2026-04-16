// Token holder — shared read/write surface between api/client.ts and stores/auth.ts.
// Breaking the import cycle: client.ts must not depend on stores/auth, so tokens live here
// and both sides read/write through this module.

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    // Storage may be disabled (SSR, private mode, etc.). Treat as "no token".
    return null
  }
}

let accessToken: string | null = readStorage(ACCESS_KEY)
let refreshToken: string | null = readStorage(REFRESH_KEY)

export function getAccess(): string | null {
  return accessToken
}

export function getRefresh(): string | null {
  return refreshToken
}

export function setTokens(access: string, refresh: string): void {
  accessToken = access
  refreshToken = refresh
  try {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  } catch {
    // Best-effort persistence. In-memory tokens still work for this session.
  }
}

export function clearTokens(): void {
  accessToken = null
  refreshToken = null
  try {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  } catch {
    // Nothing to do.
  }
}

export const TOKEN_STORAGE_KEYS = { ACCESS_KEY, REFRESH_KEY } as const
