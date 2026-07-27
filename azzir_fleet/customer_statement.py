# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Customer Statement — statement of account for a single customer.

Self-contained (does NOT rely on the query-report framework, which is broken on
Frappe 17-dev). Powers the `customer-statement` desk page. A customer is a
receivable, so balance = debit - credit (positive = customer owes us).
"""

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_statement(company: str, customer: str, from_date: str = "", to_date: str = "") -> dict:
	currency = None
	if company:
		currency = frappe.get_cached_value("Company", company, "default_currency")
	if not currency:
		currency = frappe.db.get_default("currency")

	data = []
	if customer:
		# Opening balance: net of everything strictly before From Date.
		opening = 0.0
		if from_date:
			conds = ["party_type = 'Customer'", "party = %(customer)s", "is_cancelled = 0", "posting_date < %(from_date)s"]
			vals = {"customer": customer, "from_date": from_date}
			if company:
				conds.append("company = %(company)s")
				vals["company"] = company
			row = frappe.db.sql(
				"select sum(debit) - sum(credit) as bal from `tabGL Entry` where "
				+ " and ".join(conds),
				vals,
				as_dict=True,
			)
			opening = flt(row[0].bal) if row and row[0].bal else 0.0

		# Movements within the period.
		conds = ["party_type = 'Customer'", "party = %(customer)s", "is_cancelled = 0"]
		vals = {"customer": customer}
		if company:
			conds.append("company = %(company)s")
			vals["company"] = company
		if from_date:
			conds.append("posting_date >= %(from_date)s")
			vals["from_date"] = from_date
		if to_date:
			conds.append("posting_date <= %(to_date)s")
			vals["to_date"] = to_date

		entries = frappe.db.sql(
			"""
			select posting_date, voucher_type, voucher_no, against, remarks, debit, credit
			from `tabGL Entry`
			where {conds}
			order by posting_date asc, creation asc
			""".format(conds=" and ".join(conds)),
			vals,
			as_dict=True,
		)

		balance = opening
		total_debit = 0.0
		total_credit = 0.0

		data.append({"posting_date": from_date, "voucher_type": _("Opening Balance"), "balance": opening})
		for e in entries:
			balance += flt(e.debit) - flt(e.credit)
			total_debit += flt(e.debit)
			total_credit += flt(e.credit)
			data.append(
				{
					"posting_date": e.posting_date,
					"voucher_type": e.voucher_type,
					"voucher_no": e.voucher_no,
					"against": e.against,
					"remarks": e.remarks,
					"debit": flt(e.debit),
					"credit": flt(e.credit),
					"balance": balance,
				}
			)
		data.append(
			{
				"posting_date": to_date,
				"voucher_type": _("Closing Balance"),
				"debit": total_debit,
				"credit": total_credit,
				"balance": balance,
			}
		)

	return {
		"data": data,
		"currency": currency,
		"customer_name": frappe.db.get_value("Customer", customer, "customer_name") if customer else "",
		"company": company,
	}
