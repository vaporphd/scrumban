// Typed fetch wrapper.
//
// Responsibilities:
//  - Attach `Authorization: Bearer <access>` unless the caller sets `skipAuth`.
//  - Parse `{detail}` bodies into `ApiError` (fetch doesn't throw on non-2xx).
//  - On a 401, refresh the access token exactly once and retry the original request.
//    Concurrent 401s share a single in-flight refresh so ADR-0005's chain-revoke-on-replay
//    doesn't boot the user off every device.
//  - Call the registered failure handler when refresh fails so stores/auth + router can
//    react without this module importing them directly.

import { ApiError, type TokenResponse } from '@/types/auth'
import { clearTokens, getAccess, getRefresh, setTokens } from './tokenStorage'

export interface RequestOptions extends RequestInit {
  /** Skip Authorization header injection and 401→refresh dance. Use for /auth/* calls. */
  skipAuth?: boolean
}

type AuthFailureHandler = () => void

let onAuthFailure: AuthFailureHandler | null = null

export function registerAuthFailureHandler(handler: AuthFailureHandler): void {
  onAuthFailure = handler
}

function buildHeaders(init: HeadersInit | undefined, skipAuth: boolean): Headers {
  const headers = new Headers(init)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (!skipAuth) {
    const token = getAccess()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }
  return headers
}

async function toApiError(res: Response): Promise<ApiError> {
  let detail: string | undefined
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') {
      detail = body.detail
    }
  } catch {
    // Body wasn't JSON (e.g. a 502 from the proxy). Fall back to statusText.
  }
  const message = detail ?? res.statusText ?? `HTTP ${res.status}`
  return new ApiError(res.status, message, detail)
}

/** In-flight refresh shared across all concurrent 401 retries. Resolves to the new access
 * token, or null if refresh failed (in which case onAuthFailure has already fired). */
let refreshInFlight: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  const refreshToken = getRefresh()
  if (!refreshToken) {
    return null
  }
  try {
    const res = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) {
      clearTokens()
      return null
    }
    const tokens = (await res.json()) as TokenResponse
    setTokens(tokens.access_token, tokens.refresh_token)
    return tokens.access_token
  } catch {
    clearTokens()
    return null
  }
}

async function httpInner<T>(
  url: string,
  options: RequestOptions,
  retried: boolean,
): Promise<T> {
  const { skipAuth = false, headers: rawHeaders, ...rest } = options
  const headers = buildHeaders(rawHeaders, skipAuth)
  const res = await fetch(url, { ...rest, headers })

  if (res.ok) {
    // 204 No Content / empty body: callers typing `http<void>` can ignore the return.
    if (res.status === 204) {
      return undefined as T
    }
    return (await res.json()) as T
  }

  if (res.status !== 401 || skipAuth || retried) {
    throw await toApiError(res)
  }

  // Single-flight: all concurrent 401s latch onto the same refresh promise.
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null
    })
  }
  const newAccess = await refreshInFlight

  if (!newAccess) {
    const err = await toApiError(res)
    onAuthFailure?.()
    throw err
  }

  return httpInner<T>(url, options, true)
}

export function http<T>(url: string, options: RequestOptions = {}): Promise<T> {
  return httpInner<T>(url, options, false)
}
