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
          :class="{
            'cursor-pointer hover:bg-blue-50': canPick(r),
            'opacity-50 cursor-not-allowed': selectable && !r.is_group && r.selectable === false,
          }"
          :title="selectable && !r.is_group && r.selectable === false ? 'Not in your cost center — view only' : ''"
          @click="pick(r)"
        >
          <span :class="{ 'font-semibold': r.is_group }">
            {{ r.is_group ? '📁' : '•' }} {{ r.warehouse }}
            <span v-if="selectable && !r.is_group && r.selectable === false" class="ml-1 text-xs text-gray-400">🔒</span>
          </span>
          <span :class="{ 'font-semibold': r.is_group }">
            {{ num(r.qty) }}
            <span v-if="r.incoming" class="ml-1 font-normal text-gray-400">(+{{ num(r.incoming) }} incoming)</span>
          </span>
        </div>
      </template>
      <div class="flex items-center justify-between border-t-2 border-black py-2 font-bold">
        <span>Total</span>
        <span>{{ num(total) }}<span v-if="totalIncoming" class="ml-1 font-normal text-gray-400">(+{{ num(totalIncoming) }} incoming)</span></span>
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
const totalIncoming = computed(() => rows.value.filter((r) => !r.parent).reduce((s, r) => s + Number(r.incoming || 0), 0))

async function load() {
  if (!props.itemCode) { rows.value = []; return }
  loading.value = true
  try { rows.value = (await stockTree(props.itemCode)) || [] }
  finally { loading.value = false }
}
function canPick(r) { return props.selectable && !r.is_group && r.selectable !== false }
function pick(r) { if (canPick(r)) emit('select', r.warehouse) }
watch(() => props.itemCode, load)
onMounted(load)
</script>
