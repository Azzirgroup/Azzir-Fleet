<template>
  <div class="mx-auto max-w-4xl">
    <div class="mb-3 flex items-center gap-2">
      <h2 class="text-lg font-semibold">{{ existing ? `${doctype} ${name}` : `New ${doctype}` }}</h2>
      <span v-if="existing" class="rounded-full bg-gray-100 px-2 py-0.5 text-xs">{{ doc.status || (doc.docstatus === 1 ? 'Submitted' : 'Draft') }}</span>
      <div class="ml-auto flex gap-2">
        <button v-if="!existing" :disabled="busy" class="rounded-md border px-3 py-1.5 text-sm" @click="save(false)">Save Draft</button>
        <button v-if="!existing" :disabled="busy" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white" @click="save(true)">Save &amp; Submit</button>
        <button v-if="existing && doc.docstatus === 0" :disabled="busy" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white" @click="submitExisting">Submit</button>
      </div>
    </div>

    <div v-if="msg" class="mb-3 rounded-md px-3 py-2 text-sm" :class="err ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'">{{ msg }}</div>

    <!-- Header -->
    <div class="mb-4 grid grid-cols-1 gap-3 rounded-lg border bg-white p-4 md:grid-cols-2">
      <div>
        <label class="mb-1 block text-xs text-gray-500">Customer</label>
        <div v-if="existing" class="rounded-md border bg-gray-50 px-3 py-2 text-sm">{{ doc.customer_name || doc.party_name || doc.customer }}</div>
        <div v-else class="relative">
          <input v-model="custQ" placeholder="Search customer…" class="w-full rounded-md border px-3 py-2 text-sm" @input="searchCust" @focus="searchCust" />
          <div v-if="custResults.length" class="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-md border bg-white shadow">
            <div v-for="c in custResults" :key="c.name" class="cursor-pointer px-3 py-2 text-sm hover:bg-gray-50" @click="pickCust(c)">
              <div class="font-medium">{{ c.customer_name }}</div><div class="text-xs text-gray-500">{{ c.name }}</div>
            </div>
          </div>
        </div>
      </div>
      <div>
        <label class="mb-1 block text-xs text-gray-500">Company</label>
        <div class="rounded-md border bg-gray-50 px-3 py-2 text-sm">{{ doc.company || defaults.company }}</div>
      </div>
    </div>

    <!-- Items -->
    <div class="rounded-lg border bg-white">
      <div class="flex items-center border-b px-3 py-2">
        <div class="text-sm font-medium text-gray-600">Items</div>
        <button v-if="!existing" class="ml-auto rounded-md border px-2 py-1 text-xs" @click="addRow">+ Add item</button>
      </div>
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-left text-gray-500">
          <tr>
            <th class="px-3 py-2">Item</th><th class="px-3 py-2 w-20">Qty</th>
            <th class="px-3 py-2 w-28">Rate</th><th class="px-3 py-2 w-40">Warehouse</th>
            <th class="px-3 py-2 w-28 text-right">Amount</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="i" class="border-t align-top">
            <td class="px-3 py-2">
              <template v-if="existing">{{ row.item_code }}</template>
              <div v-else class="relative">
                <input v-model="row._q" :placeholder="row.item_code || 'Search item…'" class="w-full rounded border px-2 py-1" @input="searchItem(i)" />
                <div v-if="row._results && row._results.length" class="absolute z-10 mt-1 max-h-48 w-72 overflow-y-auto rounded-md border bg-white shadow">
                  <div v-for="it in row._results" :key="it.name" class="cursor-pointer px-2 py-1.5 text-xs hover:bg-gray-50" @click="pickItem(i, it)">
                    <div class="font-medium">{{ it.name }}</div><div class="text-gray-500">{{ it.item_name }}</div>
                  </div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2"><input v-if="!existing" v-model.number="row.qty" type="number" class="w-16 rounded border px-2 py-1" /><span v-else>{{ row.qty }}</span></td>
            <td class="px-3 py-2"><input v-if="!existing" v-model.number="row.rate" type="number" class="w-24 rounded border px-2 py-1" /><span v-else>{{ fmt(row.rate) }}</span></td>
            <td class="px-3 py-2">
              <template v-if="existing">{{ row.warehouse }}</template>
              <div v-else class="flex items-center gap-1">
                <input v-model="row.warehouse" placeholder="—" class="w-28 rounded border px-2 py-1" />
                <button v-if="row.item_code" class="rounded border px-1.5 py-1 text-xs" title="See all warehouses" @click="openStock(i)">📦</button>
              </div>
            </td>
            <td class="px-3 py-2 text-right">{{ fmt((row.qty || 0) * (row.rate || 0)) }}</td>
            <td class="px-2 py-2"><button v-if="!existing" class="text-gray-400 hover:text-red-500" @click="rows.splice(i, 1)">✕</button></td>
          </tr>
          <tr v-if="!rows.length"><td colspan="6" class="px-3 py-6 text-center text-gray-400">No items.</td></tr>
        </tbody>
        <tfoot>
          <tr class="border-t"><td colspan="4"></td><td class="px-3 py-2 text-right font-semibold">Total</td><td class="px-3 py-2 text-right font-semibold">{{ fmt(total) }}</td></tr>
        </tfoot>
      </table>
    </div>

    <!-- Stock modal -->
    <div v-if="stockRow !== null" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="stockRow = null">
      <div class="w-full max-w-lg rounded-lg bg-white p-4 shadow-xl">
        <div class="mb-2 flex items-center"><div class="font-semibold">Available stock — {{ rows[stockRow]?.item_code }}</div><button class="ml-auto text-gray-400" @click="stockRow = null">✕</button></div>
        <p class="mb-2 text-xs text-gray-500">Click a warehouse to set it on the row.</p>
        <StockTree :item-code="rows[stockRow]?.item_code" selectable @select="setWarehouse" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getList, getDoc, insertDoc, submitDoc, salesDefaults, fmt } from '@/utils/api.js'
import StockTree from '@/components/StockTree.vue'

const props = defineProps({ doctype: String, name: String })
const router = useRouter()

const existing = computed(() => !!props.name)
const doc = ref({})
const rows = ref([])
const defaults = ref({})
const busy = ref(false)
const msg = ref('')
const err = ref(false)

const custQ = ref('')
const custResults = ref([])
const customer = ref('')
const stockRow = ref(null)

const total = computed(() => rows.value.reduce((s, r) => s + (Number(r.qty) || 0) * (Number(r.rate) || 0), 0))

onMounted(async () => {
  defaults.value = await salesDefaults().catch(() => ({}))
  if (existing.value) {
    doc.value = await getDoc(props.doctype, props.name)
    rows.value = (doc.value.items || []).map((r) => ({ ...r }))
  } else {
    addRow()
  }
})

function addRow() { rows.value.push({ item_code: '', qty: 1, rate: 0, warehouse: '', _q: '', _results: [] }) }

let ct = null
function searchCust() {
  clearTimeout(ct)
  ct = setTimeout(async () => {
    if (!custQ.value) { custResults.value = []; return }
    custResults.value = await getList('Customer', { fields: ['name', 'customer_name'], filters: { customer_name: ['like', `%${custQ.value}%`] }, limit: 15 }).catch(() => [])
  }, 250)
}
function pickCust(c) { customer.value = c.name; custQ.value = c.customer_name; custResults.value = [] }

const its = {}
function searchItem(i) {
  clearTimeout(its[i])
  its[i] = setTimeout(async () => {
    const q = rows.value[i]._q
    if (!q) { rows.value[i]._results = []; return }
    rows.value[i]._results = await getList('Item', { fields: ['name', 'item_name'], filters: { disabled: 0, item_name: ['like', `%${q}%`] }, limit: 15 }).catch(() => [])
  }, 250)
}
function pickItem(i, it) { rows.value[i].item_code = it.name; rows.value[i]._q = it.name; rows.value[i]._results = [] }

function openStock(i) { stockRow.value = i }
function setWarehouse(wh) { if (stockRow.value !== null) rows.value[stockRow.value].warehouse = wh; stockRow.value = null }

async function save(submit) {
  msg.value = ''
  if (!customer.value) { err.value = true; msg.value = 'Pick a customer.'; return }
  const items = rows.value.filter((r) => r.item_code).map((r) => ({ item_code: r.item_code, qty: r.qty || 1, rate: r.rate || 0, warehouse: r.warehouse || undefined }))
  if (!items.length) { err.value = true; msg.value = 'Add at least one item.'; return }
  const d = { doctype: props.doctype, company: defaults.value.company, items }
  if (props.doctype === 'Quotation') { d.quotation_to = 'Customer'; d.party_name = customer.value }
  else d.customer = customer.value
  busy.value = true
  try {
    let saved = await insertDoc(d)
    if (submit) saved = await submitDoc(saved)
    err.value = false; msg.value = 'Saved.'
    const base = { Quotation: '/quotations', 'Sales Invoice': '/invoices', 'Delivery Note': '/delivery-notes' }[props.doctype]
    router.push(`${base}/${encodeURIComponent(saved.name)}`)
  } catch (e) {
    err.value = true; msg.value = e?.messages?.join(', ') || e?.message || 'Could not save.'
  } finally { busy.value = false }
}

async function submitExisting() {
  busy.value = true; msg.value = ''
  try { doc.value = await submitDoc(doc.value); err.value = false; msg.value = 'Submitted.' }
  catch (e) { err.value = true; msg.value = e?.messages?.join(', ') || 'Could not submit.' }
  finally { busy.value = false }
}
</script>
