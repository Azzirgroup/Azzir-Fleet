# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Monthly Budget Report — see each Monthly Budget's accounts with LIVE actuals
(pulled from the General Ledger for the budget's period), the remaining balance
and the % used. Filter by company, year, a single month (e.g. last month) or one
account. Over-budget lines are flagged."""

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
	if filters.get("month"):
		budget_filters["month"] = filters.month

	budgets = frappe.get_all(
		"Monthly Budget",
		filters=budget_filters,
		fields=["name", "company", "month", "year", "from_date", "to_date"],
	)
	budgets.sort(key=lambda b: (b.year or 0, MONTHS.index(b.month) if b.month in MONTHS else 0))

	rows = []
	for b in budgets:
		accounts = frappe.get_all(
			"Monthly Budget Account",
			filters={"parent": b.name},
			fields=["account", "amount"],
			order_by="idx",
		)
		for a in accounts:
			if filters.get("account") and a.account != filters.account:
				continue
			budgeted = flt(a.amount)
			actual = _gl_actual(a.account, b.company, b.from_date, b.to_date)
			balance = budgeted - actual
			pct = (actual / budgeted * 100) if budgeted else 0.0
			rows.append(
				{
					"budget": b.name,
					"period": "%s %s" % (b.month, b.year),
					"account": a.account,
					"budgeted": budgeted,
					"actual": actual,
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
	by_period = {}
	for r in rows:
		p = by_period.setdefault(r["period"], {"budgeted": 0.0, "actual": 0.0})
		p["budgeted"] += flt(r["budgeted"])
		p["actual"] += flt(r["actual"])
	labels = list(by_period.keys())
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Budgeted"), "values": [by_period[p]["budgeted"] for p in labels]},
				{"name": _("Actual"), "values": [by_period[p]["actual"] for p in labels]},
			],
		},
		"type": "bar",
	}


def get_columns():
	return [
		{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 120},
		{"label": _("Budget"), "fieldname": "budget", "fieldtype": "Link", "options": "Monthly Budget", "width": 150},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 240},
		{"label": _("Budgeted"), "fieldname": "budgeted", "fieldtype": "Currency", "width": 130},
		{"label": _("Actual"), "fieldname": "actual", "fieldtype": "Currency", "width": 130},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 130},
		{"label": _("% Used"), "fieldname": "pct_used", "fieldtype": "Percent", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
	]
