<template>
  <RecordList title="Sales Invoices" doctype="Sales Invoice" :columns="cols" :tabs="tabs" new-route="/invoices/new" view-base="/invoices" search-field="customer_name" part-number />
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
// Split the list into normal invoices and credit notes (returns).
const tabs = [
  { label: 'Invoices', filters: { is_return: 0 } },
  { label: 'Credit Notes', filters: { is_return: 1 } },
]
</script>
