<template>
  <div>
    <h2 class="mb-4 text-lg font-semibold">Sales Dashboard</h2>
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div v-for="k in kpis" :key="k.label" class="rounded-lg border bg-white p-4">
        <div class="text-xs uppercase tracking-wide text-gray-500">{{ k.label }}</div>
        <div class="mt-1 text-2xl font-semibold" :style="{ color: k.color }">{{ k.value }}</div>
      </div>
    </div>

    <h3 class="mb-2 mt-6 text-sm font-semibold text-gray-600">Quick actions</h3>
    <div class="flex flex-wrap gap-2">
      <router-link to="/quotations?new=1" class="azzir-brand rounded-md px-3 py-2 text-sm text-white">+ Quotation</router-link>
      <router-link to="/invoices?new=1" class="azzir-brand rounded-md px-3 py-2 text-sm text-white">+ Sales Invoice</router-link>
      <router-link to="/delivery-notes?new=1" class="azzir-brand rounded-md px-3 py-2 text-sm text-white">+ Delivery Note</router-link>
      <router-link to="/stock" class="rounded-md border px-3 py-2 text-sm">See All Warehouses</router-link>
    </div>

    <h3 class="mb-2 mt-6 text-sm font-semibold text-gray-600">Recent quotations</h3>
    <div class="overflow-x-auto rounded-lg border bg-white">
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-left text-gray-500">
          <tr><th class="px-3 py-2">ID</th><th class="px-3 py-2">Customer</th><th class="px-3 py-2">Total</th><th class="px-3 py-2">Status</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in recent" :key="r.name" class="cursor-pointer border-t hover:bg-gray-50" @click="$router.push(`/quotations/${encodeURIComponent(r.name)}`)">
            <td class="px-3 py-2">{{ r.name }}</td>
            <td class="px-3 py-2">{{ r.party_name }}</td>
            <td class="px-3 py-2">{{ fmt(r.grand_total) }}</td>
            <td class="px-3 py-2">{{ r.status }}</td>
          </tr>
          <tr v-if="!recent.length"><td colspan="4" class="px-3 py-6 text-center text-gray-400">No quotations yet.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { dashboardStats, getList, fmt } from '@/utils/api.js'

const kpis = ref([])
const recent = ref([])

onMounted(async () => {
  try {
    const s = await dashboardStats()
    kpis.value = [
      { label: 'Open Quotations', value: s.open_quotations ?? 0, color: '#5E64FF' },
      { label: 'Unpaid Invoices', value: s.unpaid_invoices ?? 0, color: '#FF5858' },
      { label: 'Draft Invoices', value: s.draft_invoices ?? 0, color: '#FFB868' },
      { label: 'This Month Sales', value: fmt(s.month_sales), color: '#29CD42' },
    ]
  } catch (e) {
    kpis.value = []
  }
  try {
    recent.value = await getList('Quotation', {
      fields: ['name', 'party_name', 'grand_total', 'status'],
      order_by: 'modified desc',
      limit: 8,
    })
  } catch (e) { recent.value = [] }
})
</script>
