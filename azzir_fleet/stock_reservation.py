# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Soft stock reservation for Sales Invoices.

Other OPEN invoices hold ("reserve") their stock so it can't be sold twice:
  - draft invoices (docstatus 0)                      -> full qty
  - submitted, no stock update, not yet delivered     -> qty - delivered_qty
  (submitted invoices that already moved stock via update_stock reduced the Bin
  qty, so they're not counted again.)

On submit, an invoice is blocked if on-hand minus everyone else's reservation is
less than it needs. Holders of the override role bypass the check.
"""

import frappe
from frappe import _
from frappe.utils import flt

from azzir_fleet.qty_limits import OVERRIDE_ROLE


def _has_override_role() -> bool:
	"""True only if the current user is EXPLICITLY assigned the override role.

	We can't use frappe.get_roles() here: for Administrator it returns every role
	in the system, so admin would always bypass the reservation. Checking the
	User's Has Role rows means only people you actually grant the role can force
	past a reservation.
	"""
	return bool(
		frappe.get_all(
			"Has Role",
			filters={"parent": frappe.session.user, "parenttype": "User", "role": OVERRIDE_ROLE},
			limit=1,
		)
	)


def check_stock_reservation(doc, method=None):
	if _has_override_role():
		return

	# Sum this invoice's need per (item, warehouse).
	needed = {}
	for row in doc.get("items") or []:
		code, wh = row.get("item_code"), row.get("warehouse")
		if not code or not wh:
			continue
		if not frappe.get_cached_value("Item", code, "is_stock_item"):
			continue
		needed[(code, wh)] = needed.get((code, wh), 0) + flt(row.qty)

	for (code, wh), qty in needed.items():
		actual = flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": wh}, "actual_qty"))
		reserved = _reserved_by_others(code, wh, doc.name)
		available = actual - reserved
		if flt(qty) > available + 1e-9:
			frappe.throw(
				_(
					"Item {0} in {1}: {2} on hand, {3} already reserved by other invoices — "
					"only {4} available, but this invoice needs {5}. The stock has already been "
					"reserved and is not enough to submit."
				).format(frappe.bold(code), wh, actual, reserved, available, qty),
				title=_("Stock Already Reserved"),
			)


def _reserved_by_others(code: str, wh: str, current_name: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(case
			when si.docstatus = 0 then sii.qty
			when si.docstatus = 1 and si.update_stock = 0
				then greatest(sii.qty - ifnull(sii.delivered_qty, 0), 0)
			else 0 end)
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where sii.item_code = %(code)s and sii.warehouse = %(wh)s
		  and si.name != %(cur)s and si.docstatus in (0, 1)
		""",
		{"code": code, "wh": wh, "cur": current_name or ""},
	)
	return flt(rows[0][0]) if rows and rows[0][0] else 0.0
