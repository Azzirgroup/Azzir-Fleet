# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})

	conditions, params = get_conditions(filters)
	data = get_data(conditions, params)
	columns = get_columns()
	chart = get_chart(data)

	return columns, data, None, chart


def get_conditions(filters):
	conditions = ["si.docstatus = 1"]
	params = {}

	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		params["company"] = filters.company

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
		params["customer"] = filters.customer

	if filters.get("cost_center"):
		conditions.append("sii.cost_center = %(cost_center)s")
		params["cost_center"] = filters.cost_center

	if filters.get("item_group"):
		conditions.append("sii.item_group = %(item_group)s")
		params["item_group"] = filters.item_group

	return conditions, params


def get_data(conditions, params):
	"""Invoice-level rows: Cost Center, Invoice Number, Date, Customer Name."""
	query = f"""
		SELECT
			si.name AS invoice_no,
			si.posting_date AS posting_date,
			si.customer AS customer,
			si.customer_name AS customer_name,
			COALESCE(sii.cost_center, si.cost_center, 'Undefined') AS cost_center,
			SUM(sii.qty) AS qty,
			SUM(sii.base_net_amount) AS amount
		FROM `tabSales Invoice` si
		LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {" AND ".join(conditions)}
		GROUP BY si.name, cost_center
		ORDER BY si.posting_date DESC
	"""
	return frappe.db.sql(query, params, as_dict=True)


def get_columns():
	return [
		{"fieldname": "cost_center", "label": _("Cost Center"), "fieldtype": "Link", "options": "Cost Center", "width": 150},
		{"fieldname": "invoice_no", "label": _("Invoice Number"), "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
		{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 200},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "qty", "label": _("Qty"), "fieldtype": "Float", "width": 100},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 130},
	]


def get_chart(data):
	if not data:
		return None

	# Aggregate amount by date for the chart
	totals_by_date = {}
	for row in data:
		d = str(row.get("posting_date"))
		totals_by_date[d] = totals_by_date.get(d, 0) + (row.get("amount") or 0)

	sorted_dates = sorted(totals_by_date.keys())
	labels = sorted_dates
	values = [totals_by_date[d] for d in sorted_dates]

	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Sales Amount"), "values": values}],
		},
		"type": "line",
	}