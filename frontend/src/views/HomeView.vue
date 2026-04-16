<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <section>
    <h2>Welcome, {{ auth.user?.display_name }}</h2>
    <p>
      You're signed in as <strong>{{ auth.user?.username }}</strong>.
    </p>
  </section>
</template>
