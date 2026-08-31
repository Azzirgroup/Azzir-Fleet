import { call } from 'frappe-ui'

export const getList = (doctype, opts = {}) =>
  call('frappe.client.get_list', {
    doctype,
    fields: opts.fields || ['name'],
    filters: opts.filters || {},
    order_by: opts.order_by || 'modified desc',
    limit_page_length: opts.limit || 50,
    limit_start: opts.start || 0,
  })

export const getCount = (doctype, filters = {}) =>
  call('frappe.client.get_count', { doctype, filters })

// Sales lists are scoped server-side: a salesperson only sees the documents they
// created; holders of an overseer role see all. Same shape as getList.
export const salesList = (doctype, opts = {}) =>
  call('azzir_fleet.sales_api.sales_list', {
    doctype,
    fields: opts.fields || ['name'],
    filters: opts.filters || {},
    order_by: opts.order_by || 'modified desc',
    limit_page_length: opts.limit || 100,
    limit_start: opts.start || 0,
  })

export const getDoc = (doctype, name) =>
  call('frappe.client.get', { doctype, name })

export const insertDoc = (doc) => call('frappe.client.insert', { doc })

export const submitDoc = (doc) => call('frappe.client.submit', { doc })

// azzir_fleet backend helpers
export const stockTree = (item_code, groups_only = 0) =>
  call('azzir_fleet.stock_info.get_stock_tree', { item_code, exclude_invoice: '', groups_only })

export const salesDefaults = () => call('azzir_fleet.sales_api.get_defaults')
export const userCanBuySister = () => call('azzir_fleet.intercompany_sale.user_can_buy_from_sister')
export const dashboardStats = () => call('azzir_fleet.sales_api.dashboard_stats')
export const itemDetails = (item_code, customer, company, price_list, qty = 1) =>
  call('azzir_fleet.sales_api.item_details', { item_code, customer, company, price_list, qty })
export const makeNext = (source_doctype, source_name, target) =>
  call('azzir_fleet.sales_api.make_next', { source_doctype, source_name, target })
export const saveDoc = (doc) => call('frappe.client.save', { doc })

export const fmt = (n, currency) => {
  const v = Number(n || 0)
  const s = v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return currency ? `${currency} ${s}` : s
}
