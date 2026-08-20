# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Monthly Budget Comparison Report — ONE row per month with the TOTAL budgeted
and the TOTAL actual for that month (actuals pulled live from the General
Ledger), the balance and % used, plus a Budgeted-vs-Actual bar chart.
Filter by company and year."""

import frappe
from frappe import _
from frappe.utils import flt

MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	rows = get_rows(filters)
	chart = get_chart(rows)
	return columns, rows, None, chart


def get_rows(filters):
	budget_filters = {"docstatus": ["<", 2]}
	if filters.get("company"):
		budget_filters["company"] = filters.company
	if filters.get("year"):
		budget_filters["year"] = filters.year

	budgets = frappe.get_all(
		"Monthly Budget",
		filters=budget_filters,
		fields=["name", "company", "month", "year", "from_date", "to_date"],
	)

	# Aggregate per (year, month) — sum across budgets that share a month.
	agg = {}
	for b in budgets:
		accounts = frappe.get_all(
			"Monthly Budget Account", filters={"parent": b.name}, fields=["account", "amount"]
		)
		budgeted = sum(flt(a.amount) for a in accounts)
		actual = sum(_gl_actual(a.account, b.company, b.from_date, b.to_date) for a in accounts)
		d = agg.setdefault((b.year, b.month), {"budgeted": 0.0, "actual": 0.0})
		d["budgeted"] += budgeted
		d["actual"] += actual

	rows = []
	for (year, month) in sorted(
		agg.keys(), key=lambda k: (k[0] or 0, MONTHS.index(k[1]) if k[1] in MONTHS else 0)
	):
		d = agg[(year, month)]
		budgeted, actual = d["budgeted"], d["actual"]
		balance = budgeted - actual
		pct = (actual / budgeted * 100) if budgeted else 0.0
		rows.append(
			{
				"period": "%s %s" % (month, year),
				"total_budgeted": budgeted,
				"total_actual": actual,
				"balance": balance,
				"pct_used": pct,
				"status": _("Over Budget") if actual > budgeted else _("Within Budget"),
			}
		)
	return rows


def _gl_actual(account, company, from_date, to_date):
	"""Net movement (debit - credit) on the account for the budget period."""
	if not (account and from_date and to_date):
		return 0.0
	res = frappe.db.sql(
		"""
		select coalesce(sum(debit - credit), 0)
		from `tabGL Entry`
		where account = %(acc)s and company = %(co)s
		  and posting_date between %(s)s and %(e)s
		  and is_cancelled = 0
		""",
		{"acc": account, "co": company, "s": from_date, "e": to_date},
	)
	return flt(res[0][0]) if res else 0.0


def get_chart(rows):
	if not rows:
		return None
	labels = [r["period"] for r in rows]
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Total Budgeted"), "values": [flt(r["total_budgeted"]) for r in rows]},
				{"name": _("Total Actual"), "values": [flt(r["total_actual"]) for r in rows]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": False},
	}


def get_columns():
	return [
		{"label": _("Month"), "fieldname": "period", "fieldtype": "Data", "width": 140},
		{"label": _("Total Budgeted"), "fieldname": "total_budgeted", "fieldtype": "Currency", "width": 160},
		{"label": _("Total Actual"), "fieldname": "total_actual", "fieldtype": "Currency", "width": 160},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 150},
		{"label": _("% Used"), "fieldname": "pct_used", "fieldtype": "Percent", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
	]
