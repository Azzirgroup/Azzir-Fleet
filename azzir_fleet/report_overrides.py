# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Adds a "Description" column (right after Item Name) to the standard ERPNext
Stock Balance report, visible to everyone by default -- without touching
erpnext's own report file, which `bench update` would otherwise overwrite.

Done by monkey-patching erpnext.stock.report.stock_balance.stock_balance.execute
in memory, applied once per worker via the boot_session hook."""

import frappe
from frappe.utils import strip_html

_patched = False


def ensure_patched(bootinfo=None):
	"""Idempotent -- the actual patch only ever runs once per worker process."""
	global _patched
	if _patched:
		return
	_patched = True

	import erpnext.stock.report.stock_balance.stock_balance as stock_balance

	original_execute = stock_balance.execute

	def execute(filters=None):
		columns, data = original_execute(filters)

		idx = next((i for i, c in enumerate(columns) if c.get("fieldname") == "item_name"), None)
		if idx is None:
			return columns, data

		columns.insert(
			idx + 1,
			{
				"label": frappe._("Description"),
				"fieldname": "azzir_description",
				"fieldtype": "Small Text",
				"width": 200,
			},
		)

		item_codes = {row.get("item_code") for row in data if row.get("item_code")}
		descriptions = (
			frappe._dict(
				frappe.get_all(
					"Item",
					filters={"name": ["in", list(item_codes)]},
					fields=["name", "description"],
					as_list=True,
				)
			)
			if item_codes
			else {}
		)
		for row in data:
			row["azzir_description"] = strip_html(descriptions.get(row.get("item_code")) or "")

		return columns, data

	stock_balance.execute = execute
