<template>
  <div>
    <div class="mb-3 flex items-center gap-2">
      <h2 class="text-lg font-semibold">{{ title }}</h2>
      <SearchBox v-model="q" placeholder="Search…" :fetcher="suggestMain" class="ml-2 w-56" @search="load" />
      <SearchBox
        v-if="partNumber"
        v-model="pn"
        placeholder="Part number…"
        :fetcher="suggestPart"
        class="w-52"
        @search="load"
      />
      <button class="rounded-md border px-3 py-1.5 text-sm" @click="load">Refresh</button>
      <button
        v-if="isSalesDoctype && mayCreate"
        class="azzir-brand ml-auto rounded-md px-3 py-1.5 text-sm text-white"
        @click="showDialog = true"
      >
        + New
      </button>
    </div>
    <div
      v-if="isSalesDoctype && mayCreate === false"
      class="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700"
    >
      You don't have permission to create {{ title }}. Please ask your manager for access.
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
import { getList, salesList, itemMultiSearch, canCreateDoc, fmt } from '@/utils/api.js'
import DocDialog from '@/components/DocDialog.vue'
import SearchBox from '@/components/SearchBox.vue'

const props = defineProps({
  title: String,
  doctype: String,
  columns: Array,
  filters: { type: Object, default: () => ({}) },
  newRoute: String,
  viewBase: String,
  searchField: { type: String, default: 'name' },
  editable: { type: Boolean, default: false },
  partNumber: { type: Boolean, default: false },
})
const emit = defineEmits(['edit'])

const router = useRouter()
const route = useRoute()
const rows = ref([])
const loading = ref(false)
const q = ref('')
const pn = ref('')
const showDialog = ref(false)
// This list is one of the creatable sales doctypes (drives salesList vs getList).
const isSalesDoctype = computed(() =>
  ['Quotation', 'Sales Invoice', 'Delivery Note'].includes(props.doctype),
)
// Whether THIS user may create it — null until checked, then true/false. Gates the
// New button; false shows a "ask your manager" note (e.g. Delivery Note).
const mayCreate = ref(null)

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
    const fetchList = isSalesDoctype.value ? salesList : getList
    const opts = { fields: props.columns.map((c) => c.field), filters, limit: 100 }
    // Part-number narrowing is server-side and only on the sales-list path.
    if (isSalesDoctype.value && props.partNumber && pn.value) opts.part_number = pn.value
    rows.value = await fetchList(props.doctype, opts)
  } finally {
    loading.value = false
  }
}
function open(r) {
  if (props.viewBase) router.push(`${props.viewBase}/${encodeURIComponent(r.name)}`)
  else if (props.editable) emit('edit', r)
}

// Suggestions for the main search box: distinct values of the searched field
// (e.g. customer names) among the records this user can see.
async function suggestMain(txt) {
  const val = (txt || '').trim()
  const filters = { ...props.filters }
  if (val) filters[props.searchField] = ['like', `%${val}%`]
  const fetchList = isSalesDoctype.value ? salesList : getList
  const rows = await fetchList(props.doctype, {
    fields: ['name', props.searchField],
    filters,
    limit: 8,
  }).catch(() => [])
  const seen = new Set()
  const out = []
  for (const r of rows) {
    const v = r[props.searchField]
    if (v && !seen.has(v)) { seen.add(v); out.push({ value: v, label: v, sub: r.name }) }
  }
  return out
}

// Suggestions for the part-number box: matching items (code / name / description
// / old code), same resolver the list filter uses.
async function suggestPart(txt) {
  const rows = await itemMultiSearch(txt, 0, 8).catch(() => [])
  return rows.map((r) => ({
    value: r.item_code,
    label: r.item_code,
    sub: [r.item_name, r.description].filter(Boolean).join(' — '),
  }))
}
onMounted(async () => {
  if (isSalesDoctype.value) {
    mayCreate.value = await canCreateDoc(props.doctype).catch(() => false)
    if (route.query.new && mayCreate.value) showDialog.value = true
  }
  load()
})
defineExpose({ load })
</script>
