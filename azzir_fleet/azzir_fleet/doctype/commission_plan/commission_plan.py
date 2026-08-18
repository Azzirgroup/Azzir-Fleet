# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Sales Commission Center — the Commission Plan holds the CONFIG only
(company + period, overall target, expense/break-even pool, dynamic tiers, and
the sales people with their targets). The actual commission is computed by the
Commission Report (pick a plan + date range + optionally one sales person), so
nothing is stored on the plan.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CommissionPlan(Document):
	pass


def compute_commission(plan, start=None, end=None):
	"""Return per-member commission rows for a Commission Plan over a date range
	(defaults to the plan's own period). Tiers and expense split are dynamic."""
	start = start or plan.period_start
	end = end or plan.period_end
	members = plan.members or []

	sales = {m.name: _member_sales(m.sales_person, plan.company, start, end) for m in members}
	total_target = sum(flt(m.target_amount) for m in members)
	total_sales = sum(sales.values())
	count = len(members) or 1
	pool = flt(plan.expense_pool)
	tiers = sorted(plan.tiers or [], key=lambda t: flt(t.threshold_pct))

	rows = []
	for m in members:
		s, tgt = flt(sales[m.name]), flt(m.target_amount)
		pct_reached = (s / tgt * 100) if tgt else 0.0

		pct = 0.0
		for t in tiers:
			if pct_reached >= flt(t.threshold_pct):
				pct = flt(t.commission_pct)
		gross = s * pct / 100.0

		if plan.distribute_expense_by == "Equally":
			exp = pool / count
		elif plan.distribute_expense_by == "By Sales":
			exp = (pool * s / total_sales) if total_sales else 0.0
		else:  # By Target
			exp = (pool * tgt / total_target) if total_target else 0.0

		rows.append(
			{
				"sales_person": m.sales_person,
				"target": tgt,
				"actual_sales": s,
				"pct_reached": pct_reached,
				"commission_pct": pct,
				"gross_commission": gross,
				"expense_share": exp,
				"net_commission": gross - exp,
			}
		)
	return rows


def _member_sales(sales_person, company, start, end):
	"""A sales person's sales for the period = their Sales Team allocation on
	submitted Sales Invoices (falls back to net_total x allocated %)."""
	if not (sales_person and company and start and end):
		return 0.0
	res = frappe.db.sql(
		"""
		select coalesce(nullif(st.allocated_amount, 0),
		                si.base_net_total * st.allocated_percentage / 100) as amt
		from `tabSales Team` st
		join `tabSales Invoice` si on si.name = st.parent
		where st.sales_person = %(sp)s and si.docstatus = 1 and si.company = %(co)s
		  and si.posting_date between %(s)s and %(e)s
		""",
		{"sp": sales_person, "co": company, "s": start, "e": end},
	)
	return sum(flt(r[0]) for r in res) if res else 0.0
