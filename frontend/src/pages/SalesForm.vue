<template>
  <div class="mx-auto max-w-4xl">
    <div class="mb-3 flex items-center gap-2">
      <button class="rounded p-1 text-gray-500 hover:bg-gray-100" @click="$router.back()">←</button>
      <h2 class="text-lg font-semibold">{{ doctype }} {{ name }}</h2>
      <span class="rounded-full px-2 py-0.5 text-xs" :class="statusClass">{{ statusText }}</span>
      <div class="ml-auto flex flex-wrap gap-2">
        <button class="rounded-md border px-3 py-1.5 text-sm" @click="printDoc">🖨 Print</button>
        <!-- Draft actions -->
        <template v-if="doc.docstatus === 0">
          <button class="rounded-md border px-3 py-1.5 text-sm" @click="editing = true">Edit</button>
          <button :disabled="busy" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white" @click="submitDraft">Submit</button>
        </template>
        <!-- Submitted: create next in the flow -->
        <template v-else-if="doc.docstatus === 1">
          <button v-for="a in nextActions" :key="a.target" :disabled="busy" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white" @click="createNext(a.target)">
            + {{ a.label }}
          </button>
        </template>
      </div>
    </div>

    <div v-if="msg" class="mb-3 rounded-md px-3 py-2 text-sm" :class="err ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'">{{ msg }}</div>

    <div v-if="loading" class="py-10 text-center text-gray-400">Loading…</div>
    <template v-else>
      <div class="mb-4 grid grid-cols-2 gap-4 rounded-lg border bg-white p-4 text-sm md:grid-cols-4">
        <div><div class="text-xs text-gray-500">Customer</div><div class="font-medium">{{ doc.customer_name || doc.party_name || doc.customer }}</div></div>
        <div><div class="text-xs text-gray-500">Date</div><div>{{ doc.transaction_date || doc.posting_date }}</div></div>
        <div><div class="text-xs text-gray-500">Company</div><div>{{ doc.company }}</div></div>
        <div><div class="text-xs text-gray-500">Grand Total</div><div class="font-semibold">{{ fmt(doc.grand_total, doc.currency) }}</div></div>
      </div>

      <div class="overflow-x-auto rounded-lg border bg-white">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-500">
            <tr><th class="px-3 py-2">Item</th><th class="px-3 py-2">Qty</th><th class="px-3 py-2">Rate</th><th class="px-3 py-2">Warehouse</th><th class="px-3 py-2 text-right">Amount</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in doc.items || []" :key="r.name" class="border-t">
              <td class="px-3 py-2"><div class="font-medium">{{ r.item_code }}</div><div class="text-xs text-gray-500">{{ r.item_name }}</div></td>
              <td class="px-3 py-2">{{ r.qty }}</td>
              <td class="px-3 py-2">{{ fmt(r.rate) }}</td>
              <td class="px-3 py-2">{{ r.warehouse || '—' }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(r.amount) }}</td>
            </tr>
          </tbody>
          <tfoot><tr class="border-t"><td colspan="4" class="px-3 py-2 text-right font-semibold">Grand Total</td><td class="px-3 py-2 text-right font-semibold">{{ fmt(doc.grand_total, doc.currency) }}</td></tr></tfoot>
        </table>
      </div>
    </template>

    <DocDialog v-if="editing" :doctype="doctype" :edit="doc" @close="editing = false" @saved="onEdited" />
    <DocDialog v-if="createTarget" :doctype="createTarget" :initial="createInitial" @close="createTarget = null" @saved="onNextSaved" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDoc, submitDoc, makeNext, fmt } from '@/utils/api.js'
import DocDialog from '@/components/DocDialog.vue'

const props = defineProps({ doctype: String, name: String })
const router = useRouter()

const doc = ref({})
const loading = ref(true)
const busy = ref(false)
const editing = ref(false)
const createTarget = ref(null)
const createInitial = ref(null)
const msg = ref('')
const err = ref(false)

const statusText = computed(() => doc.value.status || (doc.value.docstatus === 1 ? 'Submitted' : doc.value.docstatus === 2 ? 'Cancelled' : 'Draft'))
const statusClass = computed(() => doc.value.docstatus === 1 ? 'bg-green-100 text-green-700' : doc.value.docstatus === 2 ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600')

const SPA_ROUTE = { Quotation: '/quotations', 'Sales Invoice': '/invoices', 'Delivery Note': '/delivery-notes' }
const nextActions = computed(() => {
  if (props.doctype === 'Quotation') return [{ target: 'Sales Invoice', label: 'Sales Invoice' }]
  if (props.doctype === 'Sales Invoice') return [{ target: 'Delivery Note', label: 'Delivery Note' }, { target: 'Payment Entry', label: 'Payment Entry' }]
  return []
})

async function load() {
  loading.value = true
  try { doc.value = await getDoc(props.doctype, props.name) }
  finally { loading.value = false }
}
onMounted(load)

async function submitDraft() {
  busy.value = true; msg.value = ''
  try { doc.value = await submitDoc(doc.value); err.value = false; msg.value = 'Submitted.' }
  catch (e) { err.value = true; msg.value = e?.messages?.join(', ') || 'Could not submit.' }
  finally { busy.value = false }
}
function onEdited() { editing.value = false; load() }

async function createNext(target) {
  busy.value = true; msg.value = ''
  try {
    const r = await makeNext(props.doctype, props.name, target)
    err.value = false
    if (r.mode === 'open') {
      // Payment Entry: created straight away, open it in the desk.
      window.open(`/app/${r.doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(r.name)}`, '_blank')
      msg.value = `${r.doctype} created — opened in a new tab.`
    } else {
      // Sales Invoice / Delivery Note: review the prefilled form, then save.
      createTarget.value = r.doctype
      createInitial.value = r.data
    }
  } catch (e) {
    err.value = true; msg.value = e?.messages?.join(', ') || e?.message || `Could not create ${target}.`
  } finally { busy.value = false }
}

function printDoc() {
  // Opens the desk print view, which renders the doctype's default print format.
  const url = `/printview?doctype=${encodeURIComponent(props.doctype)}&name=${encodeURIComponent(props.name)}&trigger_print=1`
  window.open(url, '_blank')
}

function onNextSaved(saved) {
  const target = createTarget.value
  createTarget.value = null
  const route = SPA_ROUTE[target]
  if (route && saved?.name) router.push(`${route}/${encodeURIComponent(saved.name)}`)
}
</script>
