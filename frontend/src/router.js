import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/quotations', name: 'Quotations', component: () => import('@/pages/Quotations.vue') },
  { path: '/quotations/:name', name: 'QuotationView', component: () => import('@/pages/SalesForm.vue'), props: (r) => ({ doctype: 'Quotation', name: r.params.name }) },
  { path: '/invoices', name: 'Invoices', component: () => import('@/pages/Invoices.vue') },
  { path: '/invoices/:name', name: 'InvoiceView', component: () => import('@/pages/SalesForm.vue'), props: (r) => ({ doctype: 'Sales Invoice', name: r.params.name }) },
  { path: '/delivery-notes', name: 'DeliveryNotes', component: () => import('@/pages/DeliveryNotes.vue') },
  { path: '/delivery-notes/:name', name: 'DeliveryNoteView', component: () => import('@/pages/SalesForm.vue'), props: (r) => ({ doctype: 'Delivery Note', name: r.params.name }) },
  { path: '/customers', name: 'Customers', component: () => import('@/pages/Customers.vue') },
  { path: '/stock', name: 'Stock', component: () => import('@/pages/Stock.vue') },
]

const router = createRouter({ history: createWebHistory('/sales'), routes })
export default router
