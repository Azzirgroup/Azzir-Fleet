<template>
  <div class="flex h-screen w-screen overflow-hidden bg-gray-50 text-gray-900">
    <!-- Sidebar -->
    <aside
      class="azzir-brand flex w-56 shrink-0 flex-col text-white transition-all"
      :class="{ '-ml-56': !sidebar }"
    >
      <div class="flex items-center gap-2 px-4 py-4">
        <img :src="logo" class="h-8 w-8 rounded" />
        <div class="font-semibold leading-tight">Azzir Sales</div>
      </div>
      <nav class="flex-1 space-y-1 overflow-y-auto px-2 pb-4 text-sm">
        <router-link
          v-for="l in links"
          :key="l.to"
          :to="l.to"
          class="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/10"
          :class="{ 'bg-white/15 font-medium': isActive(l.to) }"
        >
          <span>{{ l.icon }}</span><span>{{ l.label }}</span>
        </router-link>
      </nav>
      <div class="px-4 py-3 text-xs text-white/60">{{ user }}</div>
    </aside>

    <!-- Main -->
    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex items-center gap-3 border-b bg-white px-4 py-3">
        <button class="rounded p-1 hover:bg-gray-100" @click="sidebar = !sidebar">☰</button>
        <div class="font-medium">{{ title }}</div>
        <div class="ml-auto">
          <a href="/app" class="text-sm text-gray-500 hover:text-gray-900">Desk →</a>
        </div>
      </header>
      <main class="min-h-0 flex-1 overflow-y-auto p-4">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const sidebar = ref(true)
const logo = '/assets/azzir_fleet/frontend/logo.svg'
const user = window.frappe?.boot?.user || ''
const links = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/quotations', label: 'Quotations', icon: '📝' },
  { to: '/invoices', label: 'Sales Invoices', icon: '🧾' },
  { to: '/delivery-notes', label: 'Delivery Notes', icon: '🚚' },
  { to: '/customers', label: 'Customers', icon: '👥' },
  { to: '/stock', label: 'See All Warehouses', icon: '📦' },
]
const title = computed(() => route.name || 'Sales')
const isActive = (to) => route.path.startsWith(to)
</script>
