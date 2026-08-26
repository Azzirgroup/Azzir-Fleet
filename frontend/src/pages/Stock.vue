<template>
  <div class="mx-auto max-w-2xl">
    <h2 class="mb-3 text-lg font-semibold">See All Warehouses</h2>
    <div class="mb-4">
      <label class="mb-1 block text-xs text-gray-500">Item</label>
      <Combo v-model="selected" doctype="Item" display="item_name" :filters="{ disabled: 0 }" placeholder="Click to choose an item" />
    </div>

    <div class="rounded-lg border bg-white p-3">
      <div class="mb-2 text-sm font-medium text-gray-600">
        Available stock by warehouse <span v-if="selected" class="text-gray-900">— {{ selected }}</span>
      </div>
      <StockTree v-if="selected" :item-code="selected" />
      <div v-else class="py-6 text-center text-sm text-gray-400">Choose an item above.</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Combo from '@/components/Combo.vue'
import StockTree from '@/components/StockTree.vue'

const selected = ref('')
</script>
