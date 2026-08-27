<template>
  <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4" @click.self="close">
    <div class="my-6 w-full max-w-3xl rounded-xl bg-white shadow-xl">
      <div class="flex items-center gap-2 border-b px-4 py-3">
        <h3 class="font-semibold">{{ edit ? `Edit ${doctype} ${edit.name}` : `New ${doctype}` }}</h3>
        <div class="ml-auto flex gap-2">
          <button :disabled="busy" class="rounded-md border px-3 py-1.5 text-sm" @click="save(false)">Save Draft</button>
          <button :disabled="busy" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white" @click="save(true)">Save &amp; Submit</button>
          <button class="rounded-md p-1 text-gray-400 hover:text-gray-700" @click="close">✕</button>
        </div>
      </div>

      <div class="px-4 py-3">
        <div v-if="msg" class="mb-3 rounded-md px-3 py-2 text-sm" :class="err ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'">{{ msg }}</div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs text-gray-500">Company</label>
            <Combo v-model="company" doctype="Company" display="name" placeholder="Select company" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Customer</label>
            <Combo v-model="customer" doctype="Customer" display="customer_name" placeholder="Select customer" query-method="azzir_fleet.sales_api.list_customers" :query-args="{ company }" />
          </div>
        </div>

        <div class="rounded-lg border">
          <div class="flex items-center border-b px-3 py-2">
            <div class="text-sm font-medium text-gray-600">Items</div>
            <button class="ml-auto rounded-md border px-2 py-1 text-xs" @click="addRow">+ Add item</button>
          </div>
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 text-left text-gray-500">
              <tr><th class="px-3 py-2">Item</th><th class="px-2 py-2 w-16">Qty</th><th class="px-2 py-2 w-24">Rate</th><th class="px-2 py-2 w-44">Warehouse</th><th class="px-2 py-2 w-24 text-right">Amount</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in rows" :key="i" class="border-t align-top">
                <td class="px-2 py-2 w-64"><Combo v-model="row.item_code" doctype="Item" display="item_name" placeholder="Select item" :filters="{ disabled: 0 }" @update:model-value="(v) => onItem(i, v)" /></td>
                <td class="px-2 py-2"><input v-model.number="row.qty" type="number" class="w-14 rounded border px-2 py-1" /></td>
                <td class="px-2 py-2"><input v-model.number="row.rate" type="number" class="w-20 rounded border px-2 py-1" /></td>
                <td class="px-2 py-2">
                  <div class="flex items-center gap-1">
                    <input v-model="row.warehouse" placeholder="—" class="w-28 rounded border px-2 py-1" />
                    <button v-if="row.item_code" class="rounded border px-1.5 py-1 text-xs" title="See all warehouses" @click="stockRow = i">📦</button>
                  </div>
                </td>
                <td class="px-2 py-2 text-right">{{ fmt((row.qty || 0) * (row.rate || 0)) }}</td>
                <td class="px-2 py-2"><button class="text-gray-400 hover:text-red-500" @click="rows.splice(i, 1)">✕</button></td>
              </tr>
              <tr v-if="!rows.length"><td colspan="6" class="px-3 py-6 text-center text-gray-400">No items.</td></tr>
            </tbody>
            <tfoot><tr class="border-t"><td colspan="4"></td><td class="px-3 py-2 text-right font-semibold">Total</td><td class="px-3 py-2 text-right font-semibold">{{ fmt(total) }}</td></tr></tfoot>
          </table>
        </div>
      </div>
    </div>

    <!-- Stock modal -->
    <div v-if="stockRow !== null" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4" @click.self="stockRow = null">
      <div class="w-full max-w-lg rounded-lg bg-white p-4 shadow-xl">
        <div class="mb-2 flex items-center"><div class="font-semibold">Available stock — {{ rows[stockRow]?.item_code }}</div><button class="ml-auto text-gray-400" @click="stockRow = null">✕</button></div>
        <p class="mb-2 text-xs text-gray-500">Click a warehouse to set it on the row.</p>
        <StockTree :item-code="rows[stockRow]?.item_code" selectable @select="setWarehouse" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { insertDoc, submitDoc, saveDoc, itemDetails, salesDefaults, fmt } from '@/utils/api.js'
import Combo from '@/components/Combo.vue'
import StockTree from '@/components/StockTree.vue'

const props = defineProps({
  doctype: String,
  edit: { type: Object, default: null },
  initial: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const defaults = ref({})
const company = ref('')
const customer = ref('')
const base = ref(null) // full existing doc when editing
const rows = ref([])
const busy = ref(false)
const msg = ref('')
const err = ref(false)
const stockRow = ref(null)

const total = computed(() => rows.value.reduce((s, r) => s + (Number(r.qty) || 0) * (Number(r.rate) || 0), 0))

// Changing the company clears the picked customer (it may not belong to the new one).
watch(company, (n, o) => { if (o) customer.value = '' })

onMounted(async () => {
  defaults.value = await salesDefaults().catch(() => ({}))
  company.value = props.edit?.company || props.initial?.company || defaults.value.company || ''
  if (props.edit) {
    base.value = props.edit
    customer.value = props.edit.party_name || props.edit.customer || ''
    rows.value = (props.edit.items || []).map((r) => ({ item_code: r.item_code, qty: r.qty, rate: r.rate, warehouse: r.warehouse || '' }))
    if (!rows.value.length) addRow()
  } else if (props.initial) {
    customer.value = props.initial.customer || ''
    rows.value = (props.initial.items || []).map((r) => ({ item_code: r.item_code, qty: r.qty || 1, rate: r.rate || 0, warehouse: r.warehouse || '' }))
    if (!rows.value.length) addRow()
  } else {
    addRow()
  }
})
function addRow() { rows.value.push({ item_code: '', qty: 1, rate: 0, warehouse: '' }) }
function setWarehouse(wh) { if (stockRow.value !== null) rows.value[stockRow.value].warehouse = wh; stockRow.value = null }
function close() { emit('close') }

// Auto-fetch the price when an item is chosen (like ERPNext).
async function onItem(i, item_code) {
  if (!item_code) return
  const d = await itemDetails(item_code, customer.value, defaults.value.company, defaults.value.selling_price_list, rows.value[i].qty || 1).catch(() => ({}))
  if (d && d.rate && !rows.value[i].rate) rows.value[i].rate = d.rate
}

async function save(submit) {
  msg.value = ''
  if (!customer.value) { err.value = true; msg.value = 'Pick a customer.'; return }
  const items = rows.value.filter((r) => r.item_code).map((r) => ({ item_code: r.item_code, qty: r.qty || 1, rate: r.rate || 0, warehouse: r.warehouse || undefined }))
  if (!items.length) { err.value = true; msg.value = 'Add at least one item.'; return }
  busy.value = true
  try {
    let saved
    if (base.value) {
      const d = { ...base.value, company: company.value, items }
      saved = await saveDoc(d)
      if (submit) saved = await submitDoc(saved)
    } else {
      const d = { doctype: props.doctype, company: company.value, items }
      if (props.doctype === 'Quotation') { d.quotation_to = 'Customer'; d.party_name = customer.value }
      else d.customer = customer.value
      saved = await insertDoc(d)
      if (submit) saved = await submitDoc(saved)
    }
    emit('saved', saved)
  } catch (e) {
    err.value = true; msg.value = e?.messages?.join(', ') || e?.message || 'Could not save.'
  } finally { busy.value = false }
}
</script>
