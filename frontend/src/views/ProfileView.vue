<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { issueTgLinkCode } from '@/api/tgLink'
import { useAuthStore } from '@/stores/auth'
import { ApiError, type TgLinkCodeResponse } from '@/types/auth'

const auth = useAuthStore()
const router = useRouter()

const linkCode = ref<TgLinkCodeResponse | null>(null)
const linkError = ref<string | null>(null)
const issuing = ref(false)

const deepLink = computed<string | null>(() => {
  if (!linkCode.value || !linkCode.value.bot_username) {
    return null
  }
  return `https://t.me/${linkCode.value.bot_username}?start=${linkCode.value.code}`
})

const expiresInLabel = computed<string | null>(() => {
  if (!linkCode.value) return null
  // Plain minutes-from-now math — Intl.RelativeTimeFormat is overkill for
  // a 0-15 minute window and pulls more locale baggage than we need here.
  const expiresAt = new Date(linkCode.value.expires_at).getTime()
  const minutes = Math.max(0, Math.round((expiresAt - Date.now()) / 60_000))
  if (minutes <= 0) return 'expired'
  if (minutes === 1) return 'in 1 minute'
  return `in ${minutes} minutes`
})

async function onIssueLinkCode(): Promise<void> {
  if (issuing.value) return
  linkError.value = null
  issuing.value = true
  try {
    linkCode.value = await issueTgLinkCode()
  } catch (e) {
    if (e instanceof ApiError) {
      linkError.value = e.detail ?? e.message
    } else {
      linkError.value = (e as Error).message
    }
  } finally {
    issuing.value = false
  }
}

async function onLogout(): Promise<void> {
  auth.logout()
  await router.push('/login')
}
</script>

<template>
  <section v-if="auth.user" class="profile">
    <h2>Profile</h2>
    <dl>
      <dt>ID</dt>
      <dd>{{ auth.user.id }}</dd>
      <dt>Username</dt>
      <dd>{{ auth.user.username }}</dd>
      <dt>Display name</dt>
      <dd>{{ auth.user.display_name }}</dd>
      <dt>Role</dt>
      <dd>{{ auth.user.role }}</dd>
      <dt>Telegram</dt>
      <dd>
        <span v-if="auth.user.tg_user_id !== null">
          Linked<span v-if="auth.user.tg_username"> as @{{ auth.user.tg_username }}</span>
        </span>
        <span v-else>Not linked</span>
      </dd>
    </dl>

    <section v-if="auth.user.tg_user_id === null" class="link-tg">
      <h3>Link Telegram</h3>
      <p class="hint">
        Generate a one-time code and send <code>/start &lt;code&gt;</code> to the bot to link
        your account.
      </p>
      <button type="button" :disabled="issuing" @click="onIssueLinkCode">
        {{ issuing ? 'Generating…' : linkCode ? 'Generate new code' : 'Link Telegram' }}
      </button>

      <div v-if="linkCode" class="code-box">
        <p>
          Send to bot: <code>/start {{ linkCode.code }}</code>
        </p>
        <p v-if="deepLink">
          <a :href="deepLink" target="_blank" rel="noopener noreferrer">Open in Telegram</a>
        </p>
        <p class="meta">Code expires {{ expiresInLabel }}.</p>
      </div>

      <p v-if="linkError" class="error" role="alert">{{ linkError }}</p>
    </section>

    <button type="button" class="logout" @click="onLogout">Log out</button>
  </section>
</template>

<style scoped>
.profile {
  max-width: 24rem;
  margin: 2rem auto;
}
dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.5rem 1rem;
  margin: 1rem 0 1.5rem;
}
dt {
  font-weight: 600;
}
dd {
  margin: 0;
}
button {
  padding: 0.5rem 1rem;
  font: inherit;
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.6;
}
.link-tg {
  margin: 1.5rem 0;
  padding: 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
}
.link-tg h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}
.link-tg .hint {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: #555;
}
.code-box {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 0.9rem;
}
.code-box p {
  margin: 0.25rem 0;
}
.code-box .meta {
  font-size: 0.8rem;
  color: #666;
}
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.error {
  color: #b00020;
  margin-top: 0.75rem;
}
.logout {
  margin-top: 1rem;
}
</style>
