<template>
  <RecordList title="Delivery Notes" doctype="Delivery Note" :columns="cols" new-route="/delivery-notes/new" view-base="/delivery-notes" search-field="customer_name" />
</template>
<script setup>
import RecordList from '@/components/RecordList.vue'
const cols = [
  { field: 'name', label: 'ID' },
  { field: 'customer_name', label: 'Customer' },
  { field: 'posting_date', label: 'Date' },
  { field: 'grand_total', label: 'Total', type: 'currency' },
  { field: 'status', label: 'Status', type: 'status' },
]
</script>
