# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Delivery progress on a Sales Invoice: azzir_per_delivered + azzir_delivery_status.

For a stock sale, delivery happens either at the invoice (Update Stock on) or via
linked Delivery Notes. We compute the % of the invoice's STOCK items that has been
delivered and a matching status. Recomputed when the invoice is saved and whenever a
Delivery Note against it is submitted or cancelled.
"""

import frappe
from frappe.utils import flt


def _status(per: float) -> str:
	if per >= 100:
		return "Fully Delivered"
	if per > 0:
		return "Partly Delivered"
	return "Not Delivered"


def _percent(doc) -> float:
	"""% delivered across the invoice's STOCK items. Non-stock/service-only invoices
	have nothing to deliver, so they read as fully delivered (100)."""
	total = 0.0
	delivered = 0.0
	for row in doc.get("items") or []:
		code = row.get("item_code")
		if not code or not frappe.get_cached_value("Item", code, "is_stock_item"):
			continue
		qty = flt(row.get("qty"))
		total += qty
		if doc.get("update_stock"):
			delivered += qty  # stock moved at invoice time -> delivered
		else:
			delivered += min(flt(row.get("delivered_qty")), qty)
	if total <= 0:
		return 100.0
	return min(100.0, delivered / total * 100.0)


def apply(doc, method=None):
	"""Set the two fields on a Sales Invoice doc (validate hook)."""
	if not doc.meta.has_field("azzir_per_delivered"):
		return
	per = _percent(doc)
	doc.azzir_per_delivered = per
	doc.azzir_delivery_status = _status(per)


def backfill(only_empty: bool = False):
	"""Populate azzir_delivery_status / azzir_per_delivered on existing invoices, in
	one aggregate query (delivered vs total qty of STOCK items). `only_empty` skips
	invoices that already have a status — cheap to run on every migrate."""
	if not frappe.db.has_column("Sales Invoice", "azzir_per_delivered"):
		return
	where = "si.docstatus < 2"
	if only_empty:
		where += " and (si.azzir_delivery_status is null or si.azzir_delivery_status = '')"
	rows = frappe.db.sql(
		f"""
		select si.name, si.update_stock,
			sum(case when it.is_stock_item = 1 then sii.qty else 0 end) as total,
			sum(case when it.is_stock_item = 1
				then least(ifnull(sii.delivered_qty, 0), sii.qty) else 0 end) as delivered
		from `tabSales Invoice` si
		join `tabSales Invoice Item` sii on sii.parent = si.name
		join `tabItem` it on it.name = sii.item_code
		where {where}
		group by si.name
		""",
		as_dict=True,
	)
	for i, r in enumerate(rows):
		total = flt(r.total)
		per = 100.0 if (r.update_stock or total <= 0) else min(100.0, flt(r.delivered) / total * 100.0)
		frappe.db.set_value(
			"Sales Invoice", r.name,
			{"azzir_per_delivered": per, "azzir_delivery_status": _status(per)},
			update_modified=False,
		)
		if i % 500 == 0:
			frappe.db.commit()
	frappe.db.commit()


def refresh_from_delivery_note(dn, method=None):
	"""Delivery Note on_submit / on_cancel: recompute the linked Sales Invoices, since
	their line delivered_qty just changed (ERPNext updates it before this hook)."""
	names = {
		row.get("against_sales_invoice")
		for row in (dn.get("items") or [])
		if row.get("against_sales_invoice")
	}
	for name in names:
		if not name or not frappe.db.exists("Sales Invoice", name):
			continue
		doc = frappe.get_doc("Sales Invoice", name)
		if not doc.meta.has_field("azzir_per_delivered"):
			return
		per = _percent(doc)
		frappe.db.set_value(
			"Sales Invoice", name,
			{"azzir_per_delivered": per, "azzir_delivery_status": _status(per)},
			update_modified=False,
		)
