<template>
  <div class="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/40 p-4" @click.self="$emit('close')">
    <div class="my-6 w-full max-w-lg rounded-xl bg-white shadow-xl">
      <div class="flex items-center gap-2 border-b px-4 py-3">
        <h3 class="font-semibold">Add multiple items</h3>
        <button class="ml-auto rounded-md p-1 text-gray-400 hover:text-gray-700" @click="$emit('close')">✕</button>
      </div>
      <div class="px-4 py-3">
        <input
          ref="box" v-model="q" @input="onInput"
          placeholder="Search by code, part no., name or description…"
          class="mb-3 w-full rounded-md border px-3 py-2 text-sm"
        />
        <div class="max-h-80 overflow-y-auto rounded-md border">
          <div v-if="loading" class="px-3 py-4 text-center text-sm text-gray-400">Searching…</div>
          <div v-else-if="!results.length" class="px-3 py-4 text-center text-sm text-gray-400">No items.</div>
          <label
            v-for="r in results" :key="r.item_code"
            class="flex cursor-pointer items-start gap-2 border-b px-3 py-2 last:border-0 hover:bg-blue-50"
          >
            <input type="checkbox" class="mt-1" :checked="picked.has(r.item_code)" @change="toggle(r.item_code)" />
            <div class="min-w-0">
              <div class="font-medium">{{ r.item_code }}</div>
              <div class="truncate text-xs text-gray-500">
                {{ r.item_name }}<span v-if="r.description"> — {{ r.description }}</span>
              </div>
            </div>
          </label>
        </div>
      </div>
      <div class="flex items-center gap-2 border-t px-4 py-3">
        <span class="text-sm text-gray-500">{{ picked.size }} selected</span>
        <button class="ml-auto rounded-md border px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button :disabled="!picked.size" class="azzir-brand rounded-md px-3 py-1.5 text-sm text-white disabled:opacity-50" @click="add">
          Add {{ picked.size || '' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { itemMultiSearch } from '@/utils/api.js'

const emit = defineEmits(['close', 'add'])
const q = ref('')
const results = ref([])
const loading = ref(false)
const picked = ref(new Set()) // item codes ticked
const box = ref(null)
let timer = null

async function search() {
  loading.value = true
  try { results.value = await itemMultiSearch(q.value).catch(() => []) }
  finally { loading.value = false }
}
function onInput() { clearTimeout(timer); timer = setTimeout(search, 250) }
// Replace the Set so Vue re-renders the checkboxes.
function toggle(code) {
  const s = new Set(picked.value)
  s.has(code) ? s.delete(code) : s.add(code)
  picked.value = s
}
function add() { if (picked.value.size) emit('add', [...picked.value]) }

onMounted(() => { search(); box.value?.focus() })
</script>
