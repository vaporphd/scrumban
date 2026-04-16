// Pinia store for the authenticated user session.
//
// Responsibilities:
//  - Own the in-memory mirror of the current User + tokens.
//  - Expose login / register / refresh / logout / loadMe / bootstrap actions.
//  - Persist tokens via tokenStorage (localStorage-backed) so a page refresh keeps
//    the session; bootstrap() rehydrates `user` by calling /api/me on startup.
//  - Sync logout across tabs via the `storage` event — when tab A clears the
//    access token, tab B notices and drops its state.

import { defineStore } from 'pinia'
import { loginApi, meApi, refreshApi, registerApi } from '@/api/auth'
import {
  clearTokens,
  getAccess,
  getRefresh,
  setTokens,
  TOKEN_STORAGE_KEYS,
} from '@/api/tokenStorage'
import type {
  LoginRequest,
  RegisterRequest,
  User,
} from '@/types/auth'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  bootstrapPromise: Promise<void> | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    accessToken: getAccess(),
    refreshToken: getRefresh(),
    bootstrapPromise: null,
  }),
  getters: {
    isAuthenticated: (state): boolean => state.user !== null && state.accessToken !== null,
  },
  actions: {
    setSession(access: string, refresh: string): void {
      this.accessToken = access
      this.refreshToken = refresh
      setTokens(access, refresh)
    },

    async loadMe(): Promise<void> {
      const user = await meApi()
      this.user = user
    },

    async login(payload: LoginRequest): Promise<void> {
      const tokens = await loginApi(payload)
      this.setSession(tokens.access_token, tokens.refresh_token)
      await this.loadMe()
    },

    async register(payload: RegisterRequest): Promise<void> {
      // Backend /register returns the new User, not tokens — follow with login so the
      // caller ends up in the same "signed in" state as the login flow.
      await registerApi(payload)
      await this.login({ username: payload.username, password: payload.password })
    },

    async refresh(): Promise<void> {
      const current = this.refreshToken ?? getRefresh()
      if (!current) {
        this.logout()
        return
      }
      try {
        const tokens = await refreshApi({ refresh_token: current })
        this.setSession(tokens.access_token, tokens.refresh_token)
      } catch {
        this.logout()
      }
    },

    logout(): void {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      clearTokens()
    },

    /** Fire once from main.ts. Re-hydrates `user` from the persisted access token.
     * Router guard awaits `bootstrapPromise` before evaluating `requiresAuth`. */
    bootstrap(): Promise<void> {
      if (this.bootstrapPromise) {
        return this.bootstrapPromise
      }
      const run = async (): Promise<void> => {
        if (!this.accessToken) {
          return
        }
        try {
          await this.loadMe()
        } catch {
          // Either /me returned 401 after the fetch wrapper's refresh dance failed,
          // or the network is down. In both cases drop the session — the user will
          // re-authenticate.
          this.logout()
        }
      }
      this.bootstrapPromise = run()
      return this.bootstrapPromise
    },

    /** Wire the cross-tab storage listener. Called once from main.ts. */
    installStorageSync(): void {
      if (typeof window === 'undefined') {
        return
      }
      window.addEventListener('storage', (event: StorageEvent) => {
        if (event.key !== TOKEN_STORAGE_KEYS.ACCESS_KEY) {
          return
        }
        if (event.newValue === null) {
          // Another tab logged out — mirror the state here.
          this.user = null
          this.accessToken = null
          this.refreshToken = null
        } else {
          // Another tab refreshed the access token; pick it up.
          this.accessToken = event.newValue
          this.refreshToken = getRefresh()
        }
      })
    },
  },
})
