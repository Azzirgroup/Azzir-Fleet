<template>
  <div>
    <div v-if="loading" class="py-4 text-center text-gray-400">Loading stock…</div>
    <div v-else-if="!rows.length" class="py-4 text-center text-gray-400">No stock in any warehouse.</div>
    <div v-else class="max-h-96 overflow-y-auto text-sm">
      <template v-for="(grp, co) in grouped" :key="co">
        <div v-if="co" class="mt-2 border-b-2 border-black bg-gray-50 px-2 py-1 font-bold">🏢 {{ co }}</div>
        <div
          v-for="r in grp"
          :key="r.warehouse"
          class="flex items-center justify-between border-b border-gray-100 py-1.5"
          :style="{ paddingLeft: (r.depth || 0) * 20 + 4 + 'px' }"
          :class="{ 'cursor-pointer hover:bg-blue-50': selectable && !r.is_group }"
          @click="pick(r)"
        >
          <span :class="{ 'font-semibold': r.is_group }">{{ r.is_group ? '📁' : '•' }} {{ r.warehouse }}</span>
          <span :class="{ 'font-semibold': r.is_group }">{{ num(r.qty) }}</span>
        </div>
      </template>
      <div class="flex items-center justify-between border-t-2 border-black py-2 font-bold">
        <span>Total</span><span>{{ num(total) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { stockTree } from '@/utils/api.js'

const props = defineProps({
  itemCode: String,
  selectable: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])

const rows = ref([])
const loading = ref(false)

const num = (n) => Number(n || 0).toLocaleString()
const grouped = computed(() => {
  const g = {}
  for (const r of rows.value) (g[r.company || ''] = g[r.company || ''] || []).push(r)
  return g
})
const total = computed(() => rows.value.filter((r) => !r.parent).reduce((s, r) => s + Number(r.qty || 0), 0))

async function load() {
  if (!props.itemCode) { rows.value = []; return }
  loading.value = true
  try { rows.value = (await stockTree(props.itemCode)) || [] }
  finally { loading.value = false }
}
function pick(r) { if (props.selectable && !r.is_group) emit('select', r.warehouse) }
watch(() => props.itemCode, load)
onMounted(load)
</script>
