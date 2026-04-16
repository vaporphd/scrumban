import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { registerAuthFailureHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Must come after app.use(pinia): useAuthStore() requires an active Pinia instance.
const auth = useAuthStore()
auth.installStorageSync()

// When the fetch client's refresh attempt fails, drop the session and bounce to /login.
// Lambda defers useAuthStore() to call-time; the handler may fire later when pinia + router
// are both fully wired.
registerAuthFailureHandler(() => {
  useAuthStore().logout()
  void router.push('/login')
})

// Kick off /api/me rehydration; router guard awaits bootstrapPromise before evaluating
// requiresAuth. We don't await here so first paint isn't blocked.
void auth.bootstrap()

app.mount('#app')
