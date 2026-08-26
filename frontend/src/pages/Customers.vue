<template>
  <RecordList title="Customers" doctype="Customer" :columns="cols" search-field="customer_name" />
</template>
<script setup>
import RecordList from '@/components/RecordList.vue'
const cols = [
  { field: 'name', label: 'ID' },
  { field: 'customer_name', label: 'Name' },
  { field: 'customer_group', label: 'Group' },
  { field: 'territory', label: 'Territory' },
]
</script>
