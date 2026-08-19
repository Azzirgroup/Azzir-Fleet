# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Sales Commission Center — the Commission Plan holds the CONFIG only
(company + BRANCH + period, per-month targets, expense/break-even pool, dynamic
tiers, and the branch's sales people). The actual commission is computed by the
Commission Report month-by-month, with unmet targets carried to the next month.

One active plan per branch+period: overlapping plans for the same branch are
blocked so a branch cannot have two live plans at once.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate


class CommissionPlan(Document):
	def validate(self):
		self._check_period()
		self._check_branch_overlap()

	def _check_period(self):
		if self.period_start and self.period_end and getdate(self.period_end) < getdate(self.period_start):
			frappe.throw(_("Period End cannot be before Period Start."))

	def _check_branch_overlap(self):
		"""A branch cannot have two plans whose periods overlap (i.e. while an
		existing plan for that branch is not yet over)."""
		if not (self.branch and self.period_start and self.period_end):
			return
		clash = frappe.db.sql(
			"""
			select name from `tabCommission Plan`
			where name != %(name)s and branch = %(branch)s
			  and period_start <= %(end)s and period_end >= %(start)s
			limit 1
			""",
			{"name": self.name or "new", "branch": self.branch,
			 "start": self.period_start, "end": self.period_end},
		)
		if clash:
			frappe.throw(
				_("Branch {0} already has Commission Plan {1} covering an overlapping period. "
				  "Finish or adjust it before creating another.").format(
					frappe.bold(self.branch), frappe.bold(clash[0][0])
				),
				title=_("Overlapping Plan"),
			)


def _months_in(start, end):
	"""List of (month_start, month_end) windows clipped to [start, end]."""
	start, end = getdate(start), getdate(end)
	months, cur = [], get_first_day(start)
	while cur <= end:
		months.append((max(cur, start), min(get_last_day(cur), end)))
		cur = add_months(cur, 1)
	return months


def compute_commission(plan, start=None, end=None):
	"""Per-member, per-month commission rows for a Commission Plan. Each month a
	member's effective target = monthly target + any shortfall carried from the
	previous month (when carry-over is enabled). Tiers and expense split (per
	month) are dynamic."""
	start = start or plan.period_start
	end = end or plan.period_end
	members = plan.members or []
	tiers = sorted(plan.tiers or [], key=lambda t: flt(t.threshold_pct))
	carry = cint(plan.get("carry_over"))
	pool = flt(plan.expense_pool)
	count = len(members) or 1

	carried = {m.name: 0.0 for m in members}  # shortfall carried into the month
	rows = []
	for (m_start, m_end) in _months_in(start, end):
		month_sales = {
			m.name: _member_sales(m.sales_person, plan.company, m_start, m_end) for m in members
		}
		total_sales = sum(month_sales.values())
		total_eff_target = sum(flt(m.target_amount) + (carried[m.name] if carry else 0.0) for m in members)

		for m in members:
			base_tgt = flt(m.target_amount)
			carried_in = carried[m.name] if carry else 0.0
			eff_tgt = base_tgt + carried_in
			s = flt(month_sales[m.name])
			pct_reached = (s / eff_tgt * 100) if eff_tgt else 0.0

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
				exp = (pool * eff_tgt / total_eff_target) if total_eff_target else 0.0

			shortfall = max(eff_tgt - s, 0.0)
			rows.append(
				{
					"month": m_start.strftime("%b %Y"),
					"branch": plan.branch,
					"sales_person": m.sales_person,
					"monthly_target": base_tgt,
					"carried_in": carried_in,
					"effective_target": eff_tgt,
					"actual_sales": s,
					"pct_reached": pct_reached,
					"commission_pct": pct,
					"gross_commission": gross,
					"expense_share": exp,
					"net_commission": gross - exp,
					"carried_out": shortfall if carry else 0.0,
				}
			)
			if carry:
				carried[m.name] = shortfall
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
