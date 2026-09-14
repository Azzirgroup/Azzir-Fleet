<template>
  <div>
    <RecordList ref="list" title="Customers" doctype="Customer" :columns="cols" search-field="customer_name" editable @edit="(r) => (editing = r.name)" />
    <p class="mt-2 text-xs text-gray-400">Tip: click a customer to edit their details.</p>
    <CustomerDialog v-if="editing" :name="editing" @close="editing = null" @saved="onSaved" />
  </div>
</template>
<script setup>
import { ref } from 'vue'
import RecordList from '@/components/RecordList.vue'
import CustomerDialog from '@/components/CustomerDialog.vue'
const cols = [
  { field: 'name', label: 'ID' },
  { field: 'customer_name', label: 'Name' },
  { field: 'customer_group', label: 'Group' },
  { field: 'territory', label: 'Territory' },
]
const editing = ref(null)
const list = ref(null)
function onSaved() { editing.value = null; list.value?.load?.() }
</script>
