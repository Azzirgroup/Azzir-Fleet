<template>
  <div ref="root" class="relative">
    <input
      :value="open ? query : label"
      :placeholder="placeholder"
      class="w-full rounded-md border px-3 py-2 text-sm"
      @focus="onFocus"
      @input="onInput"
    />
    <div v-if="open" class="absolute z-30 mt-1 max-h-60 w-full min-w-[14rem] overflow-y-auto rounded-md border bg-white shadow-lg">
      <div v-if="loading" class="px-3 py-2 text-sm text-gray-400">Loading…</div>
      <div v-else-if="!options.length" class="px-3 py-2 text-sm text-gray-400">No results.</div>
      <div
        v-for="o in options"
        :key="o.name"
        class="cursor-pointer px-3 py-2 text-sm hover:bg-blue-50"
        @mousedown.prevent="pick(o)"
      >
        <div class="font-medium">{{ o[display] || o.name }}</div>
        <div v-if="o[display] && o[display] !== o.name" class="text-xs text-gray-500">{{ o.name }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { getList } from '@/utils/api.js'

const props = defineProps({
  modelValue: String,
  doctype: String,
  display: { type: String, default: 'name' },
  filters: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: 'Select…' },
})
const emit = defineEmits(['update:modelValue'])

const root = ref(null)
const open = ref(false)
const loading = ref(false)
const query = ref('')
const options = ref([])
const label = ref('')
let timer = null

async function fetch(q) {
  loading.value = true
  try {
    const filters = { ...props.filters }
    if (q) filters[props.display] = ['like', `%${q}%`]
    options.value = await getList(props.doctype, {
      fields: props.display === 'name' ? ['name'] : ['name', props.display],
      filters,
      order_by: `${props.display} asc`,
      limit: 25,
    })
  } catch (e) {
    options.value = []
  } finally {
    loading.value = false
  }
}

function onFocus() {
  open.value = true
  query.value = ''
  fetch('') // show the full list immediately on click
}
function onInput(e) {
  query.value = e.target.value
  open.value = true
  clearTimeout(timer)
  timer = setTimeout(() => fetch(query.value), 200)
}
function pick(o) {
  emit('update:modelValue', o.name)
  label.value = o[props.display] || o.name
  open.value = false
}
function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}

// keep the displayed label in sync if the value is set externally
watch(
  () => props.modelValue,
  (v) => { if (!v) label.value = '' },
  { immediate: true },
)

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>
