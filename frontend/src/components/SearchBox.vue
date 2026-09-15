<template>
  <div ref="root" class="relative">
    <input
      v-model="text"
      :placeholder="placeholder"
      class="w-full rounded-md border px-3 py-1.5 text-sm"
      @focus="onFocus"
      @input="onInput"
      @keyup.enter="onEnter"
    />
    <div
      v-if="open && (loading || suggestions.length)"
      class="absolute z-30 mt-1 max-h-64 w-full min-w-[16rem] overflow-y-auto rounded-md border bg-white shadow-lg"
    >
      <div v-if="loading" class="px-3 py-2 text-sm text-gray-400">Searching…</div>
      <div
        v-for="(s, i) in suggestions"
        :key="i"
        class="cursor-pointer px-3 py-2 text-sm hover:bg-blue-50"
        @mousedown.prevent="pick(s)"
      >
        <div class="font-medium">{{ s.label }}</div>
        <div v-if="s.sub" class="truncate text-xs text-gray-500">{{ s.sub }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

// A search input with a live suggestions dropdown. Unlike Combo it keeps free
// text: you can type a partial and press Enter, OR pick a suggestion. `fetcher`
// is an async (txt) => [{ value, label, sub }].
const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Search…' },
  fetcher: { type: Function, required: true },
})
const emit = defineEmits(['update:modelValue', 'search'])

const root = ref(null)
const text = ref(props.modelValue || '')
const suggestions = ref([])
const open = ref(false)
const loading = ref(false)
let timer = null

watch(() => props.modelValue, (v) => { if ((v || '') !== text.value) text.value = v || '' })
watch(text, (v) => emit('update:modelValue', v))

async function run(q) {
  loading.value = true
  try { suggestions.value = (await props.fetcher(q)) || [] }
  catch (e) { suggestions.value = [] }
  finally { loading.value = false }
}
function onFocus() { open.value = true; run(text.value) }
function onInput() { open.value = true; clearTimeout(timer); timer = setTimeout(() => run(text.value), 250) }
function onEnter() { open.value = false; emit('search') }
function pick(s) {
  text.value = s.value
  open.value = false
  emit('update:modelValue', s.value)
  emit('search')
}
function onDocClick(e) { if (root.value && !root.value.contains(e.target)) open.value = false }

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>
