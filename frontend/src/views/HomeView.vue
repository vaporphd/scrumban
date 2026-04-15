<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '@/api/client'

const status = ref<string>('…')

onMounted(async () => {
  try {
    const data = await http<{ status: string }>('/api/health')
    status.value = data.status
  } catch (e) {
    status.value = `error: ${(e as Error).message}`
  }
})
</script>

<template>
  <section>
    <p>API health: <strong>{{ status }}</strong></p>
  </section>
</template>
