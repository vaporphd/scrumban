<script setup lang="ts"></script>

<template>
  <div class="app">
    <header>
      <h1>Scrumban</h1>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  --bg: #fafafa;
  --fg: #1a1a1a;
  font-family: system-ui, -apple-system, sans-serif;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
}
.app {
  min-height: 100vh;
}
header {
  padding: 1rem 2rem;
  border-bottom: 1px solid #e5e5e5;
}
main {
  padding: 2rem;
}
</style>
