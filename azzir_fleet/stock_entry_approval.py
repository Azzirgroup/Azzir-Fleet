# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Maker-checker on Stock Entry: whoever creates the draft cannot submit it.

The person who first created the Stock Entry (doc.owner) is blocked from
submitting it — a second person must submit. On an amendment the amender becomes
the new owner, so the rule keeps holding. Administrator and holders of the
`Azzir Stock Override` role bypass it so nobody gets stuck.
"""

import frappe
from frappe import _

OVERRIDE_ROLE = "Azzir Stock Override"


def block_self_submit(doc, method=None):
	user = frappe.session.user
	if user == "Administrator" or OVERRIDE_ROLE in frappe.get_roles():
		return
	if user == doc.owner:
		frappe.throw(
			_(
				"You created this Stock Entry, so you cannot submit it. "
				"It must be submitted by someone else."
			),
			title=_("Separation of Duties"),
		)
