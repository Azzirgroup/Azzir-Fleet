# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Warn before creating a duplicate draft off a mapped-doc "Create > X" button (e.g.
Sales Invoice -> Delivery Note, Purchase Invoice -> Purchase Receipt): if an unsubmitted
draft already exists referencing this exact source, offer to open it instead of
silently letting another one pile up."""

import frappe


@frappe.whitelist()
def find_draft_target(child_doctype: str, link_field: str, source_name: str) -> str | None:
	"""A DRAFT (docstatus=0) parent document whose `child_doctype` child table already
	references `source_name` via `link_field`. Child table rows carry their own
	docstatus mirroring the parent's, so this needs no join."""
	if not child_doctype or not link_field or not source_name:
		return None
	return frappe.db.get_value(child_doctype, {link_field: source_name, "docstatus": 0}, "parent")
