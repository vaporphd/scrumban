// Typed wrapper around the Telegram-link endpoints (ADR-0003).
// Kept separate from `api/auth.ts` because the link flow logically belongs
// to the Telegram bot integration, not the username/password auth surface.

import type { TgLinkCodeResponse } from '@/types/auth'
import { http } from './client'

export function issueTgLinkCode(): Promise<TgLinkCodeResponse> {
  return http<TgLinkCodeResponse>('/api/me/tg-link-code', { method: 'POST' })
}
