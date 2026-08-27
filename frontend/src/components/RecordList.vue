<template>
  <div>
    <div class="mb-3 flex items-center gap-2">
      <h2 class="text-lg font-semibold">{{ title }}</h2>
      <input
        v-model="q"
        placeholder="Search…"
        class="ml-2 w-56 rounded-md border px-3 py-1.5 text-sm"
        @keyup.enter="load"
      />
      <button class="rounded-md border px-3 py-1.5 text-sm" @click="load">Refresh</button>
      <button
        v-if="canCreate"
        class="azzir-brand ml-auto rounded-md px-3 py-1.5 text-sm text-white"
        @click="showDialog = true"
      >
        + New
      </button>
    </div>

    <DocDialog
      v-if="showDialog"
      :doctype="doctype"
      @close="showDialog = false"
      @saved="onSaved"
    />

    <div class="overflow-x-auto rounded-lg border bg-white">
      <table class="min-w-full text-sm">
        <thead class="bg-gray-50 text-left text-gray-500">
          <tr>
            <th v-for="c in columns" :key="c.field" class="px-3 py-2 font-medium">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td :colspan="columns.length" class="px-3 py-6 text-center text-gray-400">Loading…</td></tr>
          <tr v-else-if="!rows.length"><td :colspan="columns.length" class="px-3 py-6 text-center text-gray-400">No records.</td></tr>
          <tr
            v-for="r in rows"
            :key="r.name"
            class="cursor-pointer border-t hover:bg-gray-50"
            @click="open(r)"
          >
            <td v-for="c in columns" :key="c.field" class="px-3 py-2">
              <span v-if="c.type === 'currency'">{{ fmt(r[c.field]) }}</span>
              <span v-else-if="c.type === 'status'" class="rounded-full bg-gray-100 px-2 py-0.5 text-xs">{{ r[c.field] }}</span>
              <span v-else>{{ r[c.field] }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getList, salesList, fmt } from '@/utils/api.js'
import DocDialog from '@/components/DocDialog.vue'

const props = defineProps({
  title: String,
  doctype: String,
  columns: Array,
  filters: { type: Object, default: () => ({}) },
  newRoute: String,
  viewBase: String,
  searchField: { type: String, default: 'name' },
})

const router = useRouter()
const route = useRoute()
const rows = ref([])
const loading = ref(false)
const q = ref('')
const showDialog = ref(false)
const canCreate = computed(() =>
  ['Quotation', 'Sales Invoice', 'Delivery Note'].includes(props.doctype),
)

function onSaved(doc) {
  showDialog.value = false
  if (props.viewBase && doc?.name) router.push(`${props.viewBase}/${encodeURIComponent(doc.name)}`)
  else load()
}

async function load() {
  loading.value = true
  try {
    const filters = { ...props.filters }
    if (q.value) filters[props.searchField] = ['like', `%${q.value}%`]
    const fetchList = canCreate.value ? salesList : getList
    rows.value = await fetchList(props.doctype, {
      fields: props.columns.map((c) => c.field),
      filters,
      limit: 100,
    })
  } finally {
    loading.value = false
  }
}
function open(r) {
  if (props.viewBase) router.push(`${props.viewBase}/${encodeURIComponent(r.name)}`)
}
onMounted(() => {
  if (route.query.new && canCreate.value) showDialog.value = true
  load()
})
</script>
