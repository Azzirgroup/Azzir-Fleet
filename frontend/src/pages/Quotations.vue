<template>
  <RecordList title="Quotations" doctype="Quotation" :columns="cols" new-route="/quotations/new" view-base="/quotations" search-field="party_name" />
</template>
<script setup>
import RecordList from '@/components/RecordList.vue'
const cols = [
  { field: 'name', label: 'ID' },
  { field: 'party_name', label: 'Customer' },
  { field: 'transaction_date', label: 'Date' },
  { field: 'grand_total', label: 'Total', type: 'currency' },
  { field: 'status', label: 'Status', type: 'status' },
]
</script>
