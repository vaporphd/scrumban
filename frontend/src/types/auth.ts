// Mirrors backend/app/domain/auth.py. Keep in sync when the pydantic schemas change.

export type UserRole = 'owner' | 'member'

export interface User {
  id: number
  username: string
  display_name: string
  role: UserRole
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  display_name: string
}

export interface RefreshRequest {
  refresh_token: string
}

export class ApiError extends Error {
  readonly status: number
  readonly detail?: string

  constructor(status: number, message: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}
