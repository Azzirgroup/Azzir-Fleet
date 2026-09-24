# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Backend for the Azzir Sales frappe-ui frontend (/sales)."""

import frappe
from frappe.utils import flt, getdate, get_first_day, get_last_day, nowdate


SALES_DOCTYPES = {"Quotation", "Sales Invoice", "Delivery Note"}
# Owner-scoping is OPT-IN: give a user this role and they only ever see the
# Quotations / Sales Invoices / Delivery Notes they created themselves — on the
# desk (list views, reports, opening a doc by URL) and in the /sales portal.
# Users without it keep whatever their normal role permissions allow.
OWN_ONLY_ROLE = "Document Creator"
# These override the role — a system/sales overseer still sees everyone's sales
# even if "Document Creator" was also assigned to them.
SEE_ALL_ROLES = {"Azzir Sales Overseer", "System Manager"}


def _own_only(user: str | None = None) -> bool:
	"""True when this user is restricted to the sales documents they created."""
	roles = set(frappe.get_roles(user) if user else frappe.get_roles())
	if roles & SEE_ALL_ROLES:
		return False
	return OWN_ONLY_ROLE in roles


def _can_see_all(user: str | None = None) -> bool:
	"""Everyone except a 'Document Creator' sees the whole sales pipeline."""
	return not _own_only(user)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Desk list views / reports: a 'Document Creator' sees only the documents
	they created; everyone else is left to the standard role permissions. Same
	rule as the /sales portal, now on the desk too."""
	user = user or frappe.session.user
	if not _own_only(user):
		return ""
	return "`owner` = {user}".format(user=frappe.db.escape(user))


def has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Block a 'Document Creator' from opening someone else's sales document by
	URL. Returning True defers to Frappe's standard role permissions."""
	user = user or frappe.session.user
	if not _own_only(user):
		return True
	return (doc.owner == user) if getattr(doc, "owner", None) else True


@frappe.whitelist()
def get_defaults() -> dict:
	"""Company / currency / price list the Sales forms post against."""
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	return {
		"company": company,
		"currency": currency,
		"selling_price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list"),
		"user": frappe.session.user,
		"can_see_all": _can_see_all(),
	}


def _part_number_parents(doctype: str, txt: str) -> list:
	"""Names of sales docs whose line items carry a part number matching `txt` —
	resolved the same way the backend item search does: current code, an old/alias
	code, or a separator-insensitive partial ('1003402' finds '100-3402'). Powers
	the frontend 'Part Number' list filter."""
	from azzir_fleet.alias import _norm, _norm_sql, fuzzy_item_matches

	txt = (txt or "").strip()
	if not txt:
		return []
	child_dt = doctype + " Item"
	parents: set = set()
	# 1) resolve the text to current item codes (handles old codes too), then the
	#    lines that use them.
	codes = {m["item"] for m in fuzzy_item_matches(txt, limit=500) if m.get("item")}
	if codes:
		parents |= set(
			frappe.get_all(child_dt, filters={"item_code": ["in", list(codes)]}, pluck="parent")
		)
	# 2) direct separator-insensitive partial match on the code stored on the line.
	n = _norm(txt)
	if n:
		parents |= set(
			frappe.db.sql_list(
				f"select distinct parent from `tab{child_dt}` where {_norm_sql('item_code')} like %(n)s",
				{"n": f"%{n}%"},
			)
		)
	return list(parents)


@frappe.whitelist()
def sales_list(doctype: str, fields: list | str | None = None, filters: dict | str | None = None,
               order_by: str = "modified desc", limit_page_length: int = 100, limit_start: int = 0,
               part_number: str | None = None) -> list:
	"""List sales documents. A 'Document Creator' only sees the ones THEY created;
	everyone else sees all they have permission to. Enforced on the server, not
	just hidden in the UI. When `part_number` is given, the list is narrowed to
	documents that contain a matching line item (by code / old code / partial)."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	fields = frappe.parse_json(fields) if isinstance(fields, str) else (fields or ["name"])
	if _own_only():
		filters["owner"] = frappe.session.user
	if part_number and part_number.strip():
		parents = _part_number_parents(doctype, part_number)
		if not parents:
			return []
		filters["name"] = ["in", parents]
	return frappe.get_list(
		doctype, fields=fields, filters=filters, order_by=order_by,
		limit_page_length=limit_page_length, limit_start=limit_start,
	)


@frappe.whitelist()
def dashboard_stats() -> dict:
	"""KPI counts for the Sales dashboard."""
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	start, end = get_first_day(nowdate()), get_last_day(nowdate())
	mine = _own_only()
	owner = frappe.session.user

	def cnt(dt, f):
		return frappe.db.count(dt, {**f, "owner": owner} if mine else f)

	ms = frappe.db.sql(
		"""select coalesce(sum(base_grand_total), 0) from `tabSales Invoice`
		   where docstatus = 1 and company = %(c)s and posting_date between %(s)s and %(e)s
		   {owner}""".format(owner="and owner = %(o)s" if mine else ""),
		{"c": company, "s": start, "e": end, "o": owner},
	)[0][0]
	return {
		"open_quotations": cnt("Quotation", {"status": "Open"}),
		"unpaid_invoices": cnt("Sales Invoice", {"status": "Unpaid"}),
		"draft_invoices": cnt("Sales Invoice", {"docstatus": 0}),
		"month_sales": flt(ms),
	}


@frappe.whitelist()
def list_customers(company: str | None = None, txt: str | None = None) -> list:
	"""Customers for the sales forms. If the Customer doctype has a 'company'
	field, narrow to that company; otherwise show ALL customers (customers are
	not company-scoped in stock ERPNext, so filtering by company would wrongly
	hide everyone). Always returns data as long as customers exist."""
	like = "%%%s%%" % (txt or "")
	conds = "(c.name like %(t)s or c.customer_name like %(t)s) and c.disabled = 0"
	vals = {"t": like}
	if company and frappe.get_meta("Customer").has_field("company"):
		conds += " and c.company = %(co)s"
		vals["co"] = company
	return frappe.db.sql(
		"select c.name, c.customer_name from `tabCustomer` c where "
		+ conds
		+ " order by c.customer_name limit 25",
		vals,
		as_dict=True,
	)


@frappe.whitelist()
def get_customer(name: str) -> dict:
	"""A customer's editable details for the /sales portal edit form."""
	if not has_app_permission():
		frappe.throw(frappe._("Not allowed."))
	c = frappe.get_doc("Customer", name)
	return {
		"name": c.name,
		"customer_name": c.customer_name,
		"customer_type": c.customer_type,
		"customer_group": c.customer_group,
		"territory": c.territory,
		"tax_id": c.get("tax_id"),
		"mobile_no": c.get("mobile_no"),
		"email_id": c.get("email_id"),
	}


@frappe.whitelist()
def save_customer(name: str, data) -> dict:
	"""Update a customer's basic details (and its primary contact's phone/email) from
	the /sales portal, so a sales officer can complete incomplete customers."""
	if not has_app_permission():
		frappe.throw(frappe._("Not allowed."))
	data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
	c = frappe.get_doc("Customer", name)
	for f in ("customer_name", "customer_type", "customer_group", "territory", "tax_id"):
		if data.get(f) is not None:
			c.set(f, data.get(f))
	c.flags.ignore_permissions = True
	c.save()

	mobile = (data.get("mobile_no") or "").strip()
	email = (data.get("email_id") or "").strip()
	if mobile or email:
		_save_primary_contact(c, mobile, email)

	frappe.db.commit()
	return {"name": c.name}


def _save_primary_contact(customer, mobile: str, email: str) -> None:
	"""Set the phone/email on the customer's primary Contact (creating one if none)."""
	cname = customer.get("customer_primary_contact")
	if cname and frappe.db.exists("Contact", cname):
		contact = frappe.get_doc("Contact", cname)
	else:
		contact = frappe.new_doc("Contact")
		contact.first_name = customer.customer_name or customer.name
		contact.append("links", {"link_doctype": "Customer", "link_name": customer.name})

	if mobile:
		if not any((r.phone or "") == mobile for r in contact.get("phone_nos") or []):
			contact.append("phone_nos", {"phone": mobile})
		for r in contact.phone_nos:
			r.is_primary_mobile_no = 1 if (r.phone or "") == mobile else 0
	if email:
		if not any((r.email_id or "") == email for r in contact.get("email_ids") or []):
			contact.append("email_ids", {"email_id": email})
		for r in contact.email_ids:
			r.is_primary = 1 if (r.email_id or "") == email else 0

	contact.flags.ignore_permissions = True
	contact.save()
	# Reflect on the Customer immediately (mobile_no/email_id are read-only fetches that
	# otherwise only refresh on the next customer save).
	updates: dict = {}
	if not customer.get("customer_primary_contact"):
		updates["customer_primary_contact"] = contact.name
	if mobile:
		updates["mobile_no"] = mobile
	if email:
		updates["email_id"] = email
	if updates:
		frappe.db.set_value("Customer", customer.name, updates)


@frappe.whitelist()
def item_details(item_code: str, customer: str | None = None, company: str | None = None,
                 price_list: str | None = None, qty: float = 1) -> dict:
	"""Rate + description for an item, the same way ERPNext auto-fills a sales row
	(price list rate, pricing rules, UOM)."""
	from erpnext.stock.get_item_details import get_item_details

	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	price_list = price_list or frappe.db.get_single_value("Selling Settings", "selling_price_list")
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	ctx = frappe._dict({
		"item_code": item_code, "company": company, "customer": customer,
		"selling_price_list": price_list, "price_list": price_list,
		"currency": currency, "price_list_currency": currency,
		"conversion_rate": 1, "plc_conversion_rate": 1, "qty": qty or 1,
		"doctype": "Sales Invoice", "transaction_type": "selling",
		"is_pos": 0, "is_return": 0, "ignore_pricing_rule": 0, "update_stock": 0,
	})
	try:
		out = get_item_details(ctx)
	except Exception:
		return {}
	from azzir_fleet.below_cost import _buying_rate

	return {
		"rate": out.get("price_list_rate") or out.get("rate") or 0,
		# The undiscounted list price, shown alongside the (editable) rate so the
		# seller sees what the price list says vs. what they're charging.
		"price_list_rate": out.get("price_list_rate") or 0,
		# Buying/cost price — lets the form warn (and switch the submit button to
		# "Send for Approval") the moment a rate is typed below this.
		"buying_rate": _buying_rate(item_code),
		"item_name": out.get("item_name"),
		"description": out.get("description"),
		"uom": out.get("stock_uom") or out.get("uom"),
	}


@frappe.whitelist()
def make_next(source_doctype: str, source_name: str, target: str) -> dict:
	"""Next document in the sales flow using ERPNext's own mappers. Sales Invoice /
	Delivery Note come back as PREFILLED data for review (the user confirms items /
	warehouses, then saves) — exactly how the desk opens a mapped doc. Payment Entry
	is inserted straight away and opened.
	Quotation -> Sales Invoice -> (Delivery Note / Payment Entry)."""
	if target == "Payment Entry" and source_doctype == "Sales Invoice":
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		doc = get_payment_entry("Sales Invoice", source_name)
		doc.insert(ignore_permissions=True)
		return {"mode": "open", "doctype": doc.doctype, "name": doc.name}

	if target == "Sales Invoice" and source_doctype == "Quotation":
		from azzir_fleet.quotation import make_sales_invoice
		doc = make_sales_invoice(source_name)
	elif target == "Delivery Note" and source_doctype == "Sales Invoice":
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
		doc = make_delivery_note(source_name)
	else:
		frappe.throw(frappe._("Cannot create {0} from {1}.").format(target, source_doctype))

	return {
		"mode": "form",
		"doctype": target,
		"data": {
			"customer": doc.get("customer") or doc.get("party_name"),
			# Carry the (possibly edited) customer name forward so the next document
			# keeps it instead of resetting to the customer master's name.
			"customer_name": doc.get("customer_name"),
			# Link back to the source Quotation (Sales Invoice only) so the invoice
			# inherits its approval requirement (below_cost.flag_below_cost).
			"azzir_source_quotation": (
				source_name if source_doctype == "Quotation" and target == "Sales Invoice" else None
			),
			"azzir_apply_vat": doc.get("azzir_apply_vat"),
			"items": [
				{
					"item_code": r.item_code,
					"qty": r.qty,
					"rate": r.rate,
					"warehouse": r.get("warehouse"),
					# Carry the PER-ROW buy-from-sister choice so the transfer still runs
					# when this Sales Invoice is submitted (was previously dropped here).
					"azzir_row_from_sister": r.get("azzir_row_from_sister"),
					"azzir_supply_company": r.get("azzir_supply_company"),
					"azzir_supply_warehouse": r.get("azzir_supply_warehouse"),
				}
				for r in (doc.get("items") or [])
			],
		},
	}


@frappe.whitelist()
def submit_sales_doc(doctype: str, name: str) -> dict:
	"""Submit a sales document, honouring an active Workflow. When a workflow is
	live on the doctype (e.g. the below-cost approval), we apply the correct workflow
	ACTION instead of a raw submit: a below-cost doc (azzir_below_cost = 1) routes to
	'Request Approval' and waits for a manager; a normal doc takes 'Submit' straight
	through. With no active workflow it's a plain submit (unchanged behaviour)."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("submit")

	from frappe.model.workflow import get_workflow_name, get_transitions, apply_workflow

	wf = get_workflow_name(doctype)
	if not wf:
		doc.submit()
		return {"name": doc.name, "docstatus": doc.docstatus, "workflow_state": None,
		        "below_cost": int(doc.get("azzir_below_cost") or 0), "message": frappe._("Submitted.")}

	# Available transitions already reflect the below-cost condition + the user's role.
	actions = [t.get("action") for t in (get_transitions(doc) or [])]
	if not actions:
		frappe.throw(frappe._(
			"You are not allowed to submit this document under the current approval "
			"workflow. It may need a manager's approval."))
	# Prefer a straight Submit; otherwise the approval route; otherwise whatever's offered.
	action = "Submit" if "Submit" in actions else ("Request Approval" if "Request Approval" in actions else actions[0])
	apply_workflow(doc, action)
	held = doc.docstatus == 0
	return {
		"name": doc.name,
		"docstatus": doc.docstatus,
		"workflow_state": doc.get("workflow_state"),
		"below_cost": int(doc.get("azzir_below_cost") or 0),
		"message": (frappe._("Sent for approval — this sale is below buying price.")
		            if held else frappe._("Submitted.")),
	}


@frappe.whitelist()
def workflow_actions(doctype: str, name: str) -> dict:
	"""The workflow actions the CURRENT user may take on this document right now.
	Drives the view page's buttons: an approver sees 'Approve'/'Reject', the creator
	of a below-cost doc awaiting approval sees nothing (self-approval is blocked). With
	no active workflow, a draft simply offers 'Submit'."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	doc = frappe.get_doc(doctype, name)
	from frappe.model.workflow import get_workflow_name, get_transitions

	if not get_workflow_name(doctype):
		can_submit = doc.docstatus == 0 and doc.has_permission("submit")
		return {"workflow": False, "state": None,
		        "actions": ([{"action": "Submit"}] if can_submit else [])}

	trans = get_transitions(doc) or []
	# get_transitions does NOT apply the self-approval rule (Frappe only enforces it
	# when the action is actually taken), so mirror it here — otherwise the creator of
	# a below-cost doc would see an "Approve" button that errors on click. A user is
	# offered a transition only if: they're Administrator, the transition allows self
	# approval, or they aren't the document's owner.
	user = frappe.session.user
	owner = doc.get("owner")
	def _offerable(t):
		return user == "Administrator" or t.get("allow_self_approval") or user != owner
	return {"workflow": True, "state": doc.get("workflow_state"),
	        "actions": [{"action": t.get("action")} for t in trans if _offerable(t)]}


@frappe.whitelist()
def apply_workflow_action(doctype: str, name: str, action: str) -> dict:
	"""Apply one workflow action (Approve / Reject / Submit / Request Approval). Role
	and self-approval rules are enforced by Frappe's workflow engine."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	doc = frappe.get_doc(doctype, name)
	from frappe.model.workflow import get_workflow_name, apply_workflow

	if get_workflow_name(doctype):
		apply_workflow(doc, action)
	elif action == "Submit":
		doc.check_permission("submit")
		doc.submit()
	else:
		frappe.throw(frappe._("Action {0} is not available.").format(action))
	return {"name": doc.name, "docstatus": doc.docstatus, "workflow_state": doc.get("workflow_state")}


def has_app_permission() -> bool:
	"""Who may open the /sales app: sales roles, accounts, or a manager."""
	roles = set(frappe.get_roles())
	allowed = {"Sales User", "Sales Manager", "Accounts User", "Accounts Manager", "System Manager", "Sales Portal"}
	return bool(roles & allowed)


@frappe.whitelist()
def can_create(doctype: str) -> bool:
	"""Whether the current user may CREATE `doctype`. Drives the /sales frontend so
	the 'New' / 'create next' buttons only show when the user actually has the
	permission (e.g. Delivery Note is gated for users without stock/delivery rights)."""
	return bool(frappe.has_permission(doctype, "create"))


@frappe.whitelist()
def action_perms(doctype: str, name: str) -> dict:
	"""What the current user may do to this sales document RIGHT NOW, using ERPNext's
	own role permissions — drives the Edit / Cancel / Amend buttons on the view page."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	doc = frappe.get_doc(doctype, name)
	ds = doc.docstatus
	return {
		"docstatus": ds,
		"can_write": ds == 0 and bool(frappe.has_permission(doctype, "write", doc=doc)),
		"can_submit": ds == 0 and bool(frappe.has_permission(doctype, "submit", doc=doc)),
		"can_cancel": ds == 1 and bool(frappe.has_permission(doctype, "cancel", doc=doc)),
		"can_amend": ds == 2 and bool(frappe.has_permission(doctype, "amend", doc=doc)),
	}


@frappe.whitelist()
def cancel_sales_doc(doctype: str, name: str) -> dict:
	"""Cancel a submitted sales document. ERPNext's cancel-permission check runs
	inside doc.cancel()."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	doc = frappe.get_doc(doctype, name)
	doc.cancel()
	return {"name": doc.name, "docstatus": doc.docstatus, "message": frappe._("Cancelled.")}


@frappe.whitelist()
def amend_sales_doc(doctype: str, name: str) -> dict:
	"""Amend a cancelled sales document: create a fresh DRAFT copy linked to it
	(amended_from), which the user can then edit and re-submit. Permission is enforced
	by has_permission('amend') + the insert's create check."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	src = frappe.get_doc(doctype, name)
	if src.docstatus != 2:
		frappe.throw(frappe._("Only a cancelled document can be amended."))
	if not frappe.has_permission(doctype, "amend", doc=src):
		frappe.throw(frappe._("You are not allowed to amend this {0}.").format(doctype), frappe.PermissionError)
	amended = frappe.copy_doc(src)
	amended.amended_from = name
	amended.docstatus = 0
	# Reset the workflow state so the amended DRAFT starts at the workflow's first
	# (draft) state, not the cancelled doc's 'Approved' state (which would be an
	# invalid Draft->Approved transition on insert).
	from frappe.model.workflow import get_workflow_name

	wf = get_workflow_name(doctype)
	if wf:
		wfd = frappe.get_cached_doc("Workflow", wf)
		draft_state = next((s.state for s in wfd.states if str(s.doc_status) == "0"), None)
		if wfd.workflow_state_field and draft_state:
			amended.set(wfd.workflow_state_field, draft_state)
	amended.insert()
	return {"name": amended.name, "message": frappe._("Draft amendment created.")}
