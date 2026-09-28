# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Auto-send an approval request on WhatsApp when a sales document is sent for approval.

When a Quotation / Sales Invoice / Delivery Note moves INTO a pending-approval workflow
state (the below-cost "Request Approval" action) — whether that happens on the desk or on
the /sales portal — every Employee flagged "Receives Approval Requests (WhatsApp)" (Active,
with a Mobile number) is WhatsApped the document (PDF) plus an Approve link. No button to
click: it fires on the state transition itself.

The send runs in the background (enqueue) so it never blocks or fails the approval, and it
reuses the existing approve-message + the whatsapp_integration sender (nothing in that app
is modified).
"""

import re

import frappe
from frappe import _

APPROVAL_DOCTYPES = ("Quotation", "Sales Invoice", "Delivery Note")


def _is_pending(doc) -> bool:
	"""A draft document sitting in a workflow state whose name contains 'pending'."""
	return getattr(doc, "docstatus", 0) == 0 and bool(
		re.search("pending", (doc.get("workflow_state") or ""), re.I)
	)


def notify_pending_approval(doc, method=None):
	"""on_update hook: when the document has just transitioned INTO a pending-approval
	state, queue the WhatsApp approval requests. Only on the transition (previous state
	not pending) so we don't resend on every later save."""
	if doc.doctype not in APPROVAL_DOCTYPES or not _is_pending(doc):
		return
	before = doc.get_doc_before_save()
	prev = (before.get("workflow_state") if before else "") or ""
	if re.search("pending", prev, re.I):
		return  # was already pending — nothing new to notify
	frappe.enqueue(
		"azzir_fleet.approval_notify.send_approval_requests",
		queue="short",
		enqueue_after_commit=True,
		doctype=doc.doctype,
		docname=doc.name,
	)


def approval_recipients() -> list:
	"""Active employees flagged to receive approval requests, with a Mobile number.
	Returns [{employee, employee_name, phone}]."""
	if not frappe.get_meta("Employee").has_field("azzir_approval_recipient"):
		return []
	out = []
	for r in frappe.get_all(
		"Employee",
		filters={"azzir_approval_recipient": 1, "status": "Active"},
		fields=["name", "employee_name", "cell_number"],
	):
		phone = (r.cell_number or "").strip()
		if phone:
			out.append({"employee": r.name, "employee_name": r.employee_name or r.name, "phone": phone})
	return out


def _default_sender():
	"""The default WhatsApp sender configured in the whatsapp_integration app, if any."""
	try:
		from whatsapp_integration.api.whatsapp.whatsapp import get_whatsapp_senders

		senders = get_whatsapp_senders() or []
	except Exception:
		return None
	if not senders:
		return None
	chosen = next((s for s in senders if s.get("is_default")), senders[0])
	return chosen.get("value") or chosen.get("name")


def send_approval_requests(doctype: str, docname: str) -> None:
	"""Background: WhatsApp the document + approve link to every approval recipient."""
	recipients = approval_recipients()
	if not recipients:
		return
	try:
		from azzir_fleet.whatsapp_approve import _approve_message
		from whatsapp_integration.api.whatsapp.whatsapp import send_document_via_whatsapp
	except Exception:
		return

	sender = _default_sender()
	note = _("This {0} needs your approval.").format(doctype)
	message = _approve_message(doctype, docname, note)

	sent, failed = [], []
	for r in recipients:
		try:
			send_document_via_whatsapp(doctype, docname, r["phone"], message=message, sender=sender)
			sent.append(r["employee_name"])
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Approval WhatsApp to {r['employee_name']} ({r['phone']}) failed for {doctype} {docname}",
			)
			failed.append(r["employee_name"])

	# Leave a trail on the document so it's clear who was notified.
	if sent or failed:
		try:
			doc = frappe.get_doc(doctype, docname)
			parts = []
			if sent:
				parts.append(_("Approval request sent on WhatsApp to: {0}").format(", ".join(sent)))
			if failed:
				parts.append(_("Failed to WhatsApp: {0}").format(", ".join(failed)))
			doc.add_comment("Comment", "<br>".join(parts))
		except Exception:
			pass
