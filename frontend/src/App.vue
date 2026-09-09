<template>
  <div class="flex h-screen w-screen overflow-hidden bg-gray-50 text-gray-900">
    <!-- Mobile backdrop shown when the drawer is open -->
    <div v-if="sidebar" class="fixed inset-0 z-30 bg-black/40 md:hidden" @click="sidebar = false"></div>
    <!-- Sidebar: static column on desktop, a slide-in drawer on mobile -->
    <aside
      class="azzir-brand fixed inset-y-0 left-0 z-40 flex w-56 shrink-0 flex-col text-white transition-transform md:static md:z-auto md:translate-x-0"
      :class="sidebar ? 'translate-x-0' : '-translate-x-full'"
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
          @click="closeOnMobile"
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
          <!-- 'Sales Portal' users are confined to this app; the desk would just
               302 them back here, so don't offer the link at all. -->
          <a
            v-if="!portalOnly"
            href="/app"
            class="text-sm text-gray-500 hover:text-gray-900"
            >Desk →</a
          >
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
// Open by default on desktop; closed on phones (it's an overlay drawer there).
const sidebar = ref(typeof window !== 'undefined' ? window.innerWidth >= 768 : true)
// Tapping a link on a phone closes the drawer so you land on the page.
function closeOnMobile() { if (typeof window !== 'undefined' && window.innerWidth < 768) sidebar.value = false }
const logo = '/assets/azzir_fleet/frontend/logo.svg'
// www/sales.py's boot dict is emitted by the sales.html template as TOP-LEVEL
// globals (window.user, window.portal_only, …), not as window.frappe.boot — the
// desk-style path is kept only as a fallback.
const user = window.user || window.frappe?.boot?.user || ''
const portalOnly = window.portal_only ?? window.frappe?.boot?.portal_only ?? false
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
