# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Backfill azzir_delivery_status / azzir_per_delivered on existing Sales Invoices
so the new fields are populated the moment the app is deployed."""

import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.has_column("Sales Invoice", "azzir_per_delivered"):
		return

	# One aggregate query: delivered vs total qty of STOCK items per submitted invoice.
	rows = frappe.db.sql(
		"""
		select si.name, si.update_stock,
			sum(case when it.is_stock_item = 1 then sii.qty else 0 end) as total,
			sum(case when it.is_stock_item = 1
				then least(ifnull(sii.delivered_qty, 0), sii.qty) else 0 end) as delivered
		from `tabSales Invoice` si
		join `tabSales Invoice Item` sii on sii.parent = si.name
		join `tabItem` it on it.name = sii.item_code
		where si.docstatus < 2
		group by si.name
		""",
		as_dict=True,
	)

	for i, r in enumerate(rows):
		total = flt(r.total)
		if r.update_stock or total <= 0:
			per = 100.0
		else:
			per = min(100.0, flt(r.delivered) / total * 100.0)
		status = "Fully Delivered" if per >= 100 else ("Partly Delivered" if per > 0 else "Not Delivered")
		frappe.db.set_value(
			"Sales Invoice", r.name,
			{"azzir_per_delivered": per, "azzir_delivery_status": status},
			update_modified=False,
		)
		if i % 500 == 0:
			frappe.db.commit()
	frappe.db.commit()
