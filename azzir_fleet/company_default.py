# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Per-user default Company.

The User form carries an `azzir_company` field. Whatever it is set to becomes
that user's default Company, which ERPNext then auto-fills on every new document
whose company field defaults from the Company user-default — Quotation, Sales
Invoice, etc. — on the desk AND on the /sales portal (sales_api.get_defaults reads
the same user default)."""

import frappe


def sync_user_company(doc, method=None):
	"""User on_update: mirror azzir_company into the user's Company default.

	We write the *lowercase* "company" default (not "Company"): the capitalised key
	is a user-permission key that ERPNext's get_user_default("Company") only honours
	via its scrubbed "company" fallback, so writing "company" is what actually drives
	the company field on new documents."""
	if not frappe.get_meta("User").has_field("azzir_company"):
		return
	# Only act when the field itself was set/changed, so we never clobber a company
	# default that was configured elsewhere on users who don't use this field.
	if not doc.has_value_changed("azzir_company"):
		return
	company = (doc.get("azzir_company") or "").strip()
	current = frappe.defaults.get_user_default("company", doc.name)
	if company:
		if current != company:
			frappe.defaults.set_user_default("company", company, doc.name)
	elif current:
		# Field cleared — drop the per-user default so it falls back to the global one.
		frappe.defaults.clear_user_default("company", doc.name)
