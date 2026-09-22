# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Backfill azzir_delivery_status / azzir_per_delivered on existing Sales Invoices.

Post-model-sync patches run BEFORE fixtures create the custom-field columns, so we
ensure the fields exist first, then backfill. (after_migrate also backfills, covering
sites where this patch was already logged as run before the fix.)"""

import frappe


def execute():
	from azzir_fleet.delivery_status import backfill
	from azzir_fleet.setup import CUSTOM_FIELDS

	if not frappe.db.has_column("Sales Invoice", "azzir_per_delivered"):
		from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

		flds = [
			f for f in CUSTOM_FIELDS.get("Sales Invoice", [])
			if f["fieldname"] in ("azzir_delivery_status", "azzir_per_delivered")
		]
		if flds:
			create_custom_fields({"Sales Invoice": flds}, ignore_validate=True)

	backfill()
