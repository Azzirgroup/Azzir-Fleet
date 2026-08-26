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

export const getDoc = (doctype, name) =>
  call('frappe.client.get', { doctype, name })

export const insertDoc = (doc) => call('frappe.client.insert', { doc })

export const submitDoc = (doc) => call('frappe.client.submit', { doc })

// azzir_fleet backend helpers
export const stockTree = (item_code, groups_only = 0) =>
  call('azzir_fleet.stock_info.get_stock_tree', { item_code, exclude_invoice: '', groups_only })

export const salesDefaults = () => call('azzir_fleet.sales_api.get_defaults')
export const dashboardStats = () => call('azzir_fleet.sales_api.dashboard_stats')

export const fmt = (n, currency) => {
  const v = Number(n || 0)
  const s = v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return currency ? `${currency} ${s}` : s
}
