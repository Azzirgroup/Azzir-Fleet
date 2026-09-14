<template>
  <div class="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/40 p-4" @click.self="$emit('close')">
    <div class="my-6 w-full max-w-lg rounded-xl bg-white shadow-xl">
      <div class="flex items-center gap-2 border-b px-4 py-3">
        <h3 class="font-semibold">Edit Customer</h3>
        <div class="ml-auto flex gap-2">
          <button :disabled="busy" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white" @click="save">Save</button>
          <button class="rounded-md p-1 text-gray-400 hover:text-gray-700" @click="$emit('close')">✕</button>
        </div>
      </div>
      <div class="px-4 py-3">
        <div v-if="msg" class="mb-3 rounded-md px-3 py-2 text-sm" :class="err ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'">{{ msg }}</div>
        <div v-if="loading" class="py-8 text-center text-sm text-gray-400">Loading…</div>
        <div v-else class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div class="md:col-span-2">
            <label class="mb-1 block text-xs text-gray-500">Customer Name</label>
            <input v-model="f.customer_name" class="w-full rounded-md border px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Type</label>
            <select v-model="f.customer_type" class="w-full rounded-md border px-3 py-2 text-sm">
              <option>Company</option><option>Individual</option><option>Partnership</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Tax ID</label>
            <input v-model="f.tax_id" class="w-full rounded-md border px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Customer Group</label>
            <Combo v-model="f.customer_group" doctype="Customer Group" display="name" placeholder="Select group" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Territory</label>
            <Combo v-model="f.territory" doctype="Territory" display="name" placeholder="Select territory" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Mobile</label>
            <input v-model="f.mobile_no" class="w-full rounded-md border px-3 py-2 text-sm" placeholder="e.g. 255…" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-gray-500">Email</label>
            <input v-model="f.email_id" type="email" class="w-full rounded-md border px-3 py-2 text-sm" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCustomer, saveCustomer } from '@/utils/api.js'
import Combo from '@/components/Combo.vue'

const props = defineProps({ name: String })
const emit = defineEmits(['close', 'saved'])

const f = ref({ customer_name: '', customer_type: 'Company', customer_group: '', territory: '', tax_id: '', mobile_no: '', email_id: '' })
const loading = ref(true)
const busy = ref(false)
const msg = ref('')
const err = ref(false)

onMounted(async () => {
  try {
    const d = await getCustomer(props.name)
    f.value = { ...f.value, ...d }
  } finally { loading.value = false }
})

async function save() {
  busy.value = true; msg.value = ''
  try {
    await saveCustomer(props.name, { ...f.value })
    err.value = false; emit('saved')
  } catch (e) {
    err.value = true; msg.value = e?.messages?.join(', ') || e?.message || 'Could not save.'
  } finally { busy.value = false }
}
</script>
