// Typed wrappers around the /api/auth/* and /api/me endpoints.

import type {
  LoginRequest,
  RefreshRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from '@/types/auth'
import { http } from './client'

export function registerApi(payload: RegisterRequest): Promise<User> {
  return http<User>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  })
}

export function loginApi(payload: LoginRequest): Promise<TokenResponse> {
  return http<TokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  })
}

export function refreshApi(payload: RefreshRequest): Promise<TokenResponse> {
  return http<TokenResponse>('/api/auth/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  })
}

export function meApi(): Promise<User> {
  return http<User>('/api/me')
}
