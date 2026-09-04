# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Extend the whatsapp_integration app from azzir_fleet.

Same manual send flow the WhatsApp client already offers (the user picks the
number/sender exactly as before), but the message carries an **Approve link** that
opens the document in ERPNext so a manager can approve it there — instead of just
sending the document on its own. Nothing in the whatsapp_integration app is
modified; we only add a caption and delegate to its existing sender.
"""

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_url


def _approve_message(doctype: str, docname: str, note: str | None = None) -> str:
	"""The WhatsApp caption: an optional note + a link that opens the doc in ERPNext."""
	slug = doctype.lower().replace(" ", "-")
	link = "{0}/app/{1}/{2}".format(get_url(), slug, quote(docname))
	lines = []
	if note and note.strip():
		lines.append(note.strip())
	lines.append(_("Please review and APPROVE {0} {1}.").format(doctype, docname))
	lines.append(_("Open in ERPNext to approve:"))
	lines.append(link)
	return "\n".join(lines)


@frappe.whitelist()
def send_with_approve(doctype: str, docname: str, phone_number: str,
                      sender: str | None = None, note: str | None = None) -> dict:
	"""Send the document over WhatsApp (via the whatsapp_integration app) with an
	Approve link appended. Number/sender are supplied by the caller, the same way
	the WhatsApp client resolves them today."""
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")

	try:
		from whatsapp_integration.api.whatsapp.whatsapp import send_document_via_whatsapp
	except Exception:
		frappe.throw(_("The WhatsApp Integration app is not installed on this site."))

	message = _approve_message(doctype, docname, note)
	return send_document_via_whatsapp(doctype, docname, phone_number, message=message, sender=sender)
