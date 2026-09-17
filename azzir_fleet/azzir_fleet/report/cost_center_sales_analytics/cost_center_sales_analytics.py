# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_days


def execute(filters=None):
	filters = frappe._dict(filters or {})

	conditions, params = get_conditions(filters)
	periods = get_periods(filters)

	invoice_rows = get_invoice_rows(conditions, params)

	columns = get_columns(periods)
	data = get_pivoted_data(invoice_rows, periods)
	chart = get_chart(data, periods)

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


def get_invoice_rows(conditions, params):
	"""Pull invoice-level rows directly from Sales Invoice / Sales Invoice Item,
	referencing the invoice name and its posting (invoice) date."""
	query = f"""
		SELECT
			si.name AS invoice,
			si.posting_date AS posting_date,
			si.customer AS customer,
			COALESCE(sii.cost_center, si.cost_center, 'Undefined') AS cost_center,
			SUM(sii.base_net_amount) AS amount
		FROM `tabSales Invoice` si
		LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {" AND ".join(conditions)}
		GROUP BY si.name, cost_center
		ORDER BY si.posting_date
	"""
	return frappe.db.sql(query, params, as_dict=True)


def get_periods(filters):
	"""Build the list of period buckets (label + start/end date) between
	from_date and to_date, based on the selected range."""
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None

	if not from_date or not to_date:
		# fallback: last 12 months up to today
		to_date = getdate()
		from_date = add_days(to_date, -365)

	range_type = filters.get("range") or "Monthly"
	periods = []
	current = from_date

	while current <= to_date:
		if range_type == "Weekly":
			period_end = min(add_days(current, 6), to_date)
			label = current.strftime("%d %b %Y")
		elif range_type == "Quarterly":
			quarter = (current.month - 1) // 3 + 1
			label = f"Q{quarter} {current.year}"
			# move to end of quarter
			end_month = quarter * 3
			period_end = getdate(f"{current.year}-{end_month:02d}-01")
			period_end = _last_day_of_month(period_end)
			period_end = min(period_end, to_date)
		elif range_type == "Yearly":
			label = str(current.year)
			period_end = min(getdate(f"{current.year}-12-31"), to_date)
		else:  # Monthly
			label = current.strftime("%b %Y")
			period_end = _last_day_of_month(current)
			period_end = min(period_end, to_date)

		periods.append({
			"key": f"period_{len(periods)}",
			"label": label,
			"start": current,
			"end": period_end,
		})
		current = add_days(period_end, 1)

	return periods


def _last_day_of_month(date):
	next_month = date.replace(day=28) + frappe.utils.datetime.timedelta(days=4)
	return next_month - frappe.utils.datetime.timedelta(days=next_month.day)


def get_columns(periods):
	columns = [
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 200},
		{"fieldname": "cost_center", "label": _("Cost Center"), "fieldtype": "Link", "options": "Cost Center", "width": 150},
	]
	for p in periods:
		columns.append({
			"fieldname": p["key"],
			"label": p["label"],
			"fieldtype": "Currency",
			"width": 120,
		})
	columns.append({"fieldname": "total", "label": _("Total"), "fieldtype": "Currency", "width": 130})
	return columns


def get_pivoted_data(invoice_rows, periods):
	"""Pivot invoice rows into one row per (customer, cost_center) with a
	column per period."""
	pivot = {}

	for row in invoice_rows:
		key = (row.customer, row.cost_center)
		if key not in pivot:
			pivot[key] = {"customer": row.customer, "cost_center": row.cost_center, "total": 0}
			for p in periods:
				pivot[key][p["key"]] = 0

		posting_date = getdate(row.posting_date)
		for p in periods:
			if p["start"] <= posting_date <= p["end"]:
				pivot[key][p["key"]] += row.amount or 0
				pivot[key]["total"] += row.amount or 0
				break

	data = list(pivot.values())
	data.sort(key=lambda r: r["total"], reverse=True)
	return data


def get_chart(data, periods):
	if not data or not periods:
		return None

	labels = [p["label"] for p in periods]
	# Sum each period across all customers/cost centers for the chart
	totals = []
	for p in periods:
		totals.append(sum(row.get(p["key"], 0) for row in data))

	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Sales Amount"), "values": totals}],
		},
		"type": "line",
	}