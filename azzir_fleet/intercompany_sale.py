# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Sell sister-company stock from a corporate company (e.g. HCL sells HPL/HUL stock).

Flow, all driven by data (no company names hardcoded):

* A Cost Center marked "Corporate" (azzir_is_corporate) makes its assigned users
  eligible. Such a user sees a "Buy stock from sister company" checkbox on the
  Sales Invoice, plus Supply Company + Supply Company Warehouse.
* Each corporate warehouse is tagged as the landing warehouse for one sister
  company (azzir_is_sister_landing + azzir_sister_company).
* When that Sales Invoice is submitted, BEFORE it posts we automatically create &
  submit, inside the same transaction (so any failure rolls everything back):
    1. a Delivery Note in the SUPPLY company (stock leaves the chosen sister
       warehouse), at the transfer price = market x (1 - intercompany discount);
    2. a Sales Invoice in the supply company from that Delivery Note (sister earns
       e.g. 70%);
    3. the linked Purchase Invoice in the corporate company (update stock) that
       receives into the landing warehouse at the same transfer price.
  The corporate Sales Invoice's own rows are pointed at the landing warehouse, so
  the corporate company then sells to the real customer at the full market rate
  and keeps the margin (e.g. 30%).
"""

import frappe
from frappe import _
from frappe.utils import flt


def corporate_cost_centers(user: str | None = None) -> set:
	"""Cost centers assigned to the user (User Permission) that are flagged
	Corporate."""
	user = user or frappe.session.user
	if not frappe.get_meta("Cost Center").has_field("azzir_is_corporate"):
		return set()
	ccs = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Cost Center"},
		pluck="for_value",
	)
	if not ccs:
		return set()
	return set(
		frappe.get_all(
			"Cost Center",
			filters={"name": ["in", ccs], "azzir_is_corporate": 1},
			pluck="name",
		)
	)


@frappe.whitelist()
def user_can_buy_from_sister() -> bool:
	"""Whether the current user may use the sister-company purchase feature
	(they hold at least one Corporate cost center). Administrator / System Manager
	always may, so they can configure and test."""
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return True
	return bool(corporate_cost_centers())


def _internal_customer(represents_company: str, selling_company: str) -> str | None:
	"""The internal Customer that represents `represents_company` (the corporate
	company) and may transact with `selling_company` (the sister)."""
	rows = frappe.get_all(
		"Customer",
		filters={"is_internal_customer": 1, "represents_company": represents_company},
		pluck="name",
	)
	for c in rows:
		allowed = frappe.get_all(
			"Allowed To Transact With", filters={"parent": c, "company": selling_company}, limit=1
		)
		if allowed:
			return c
	return rows[0] if rows else None


def _internal_supplier(represents_company: str) -> str | None:
	"""The internal Supplier that represents `represents_company` (the sister)."""
	return frappe.db.get_value(
		"Supplier", {"is_internal_supplier": 1, "represents_company": represents_company}, "name"
	)


def _landing_warehouse(corporate_company: str, sister_company: str) -> str | None:
	"""The corporate warehouse configured to receive this sister's stock."""
	return frappe.db.get_value(
		"Warehouse",
		{
			"company": corporate_company,
			"azzir_is_sister_landing": 1,
			"azzir_sister_company": sister_company,
			"disabled": 0,
		},
		"name",
	)


def set_landing_warehouse(doc, method=None):
	"""Sales Invoice validate: for a buy-from-sister invoice, point the stock rows
	at the corporate landing warehouse (same company as the invoice), so the doc is
	consistent from draft. The stock itself is transferred in at submit."""
	if not doc.get("azzir_buy_from_sister"):
		return
	sister = doc.get("azzir_supply_company")
	if not sister:
		return  # mandatory_depends_on will prompt for it
	landing = _landing_warehouse(doc.company, sister)
	if not landing:
		frappe.throw(
			_(
				"Configure a landing warehouse in {0} for sister company {1}: on a {0} "
				"warehouse tick 'Receives Sister Company Stock' and set its Sister Company to {1}."
			).format(frappe.bold(doc.company), frappe.bold(sister))
		)
	for r in doc.get("items") or []:
		if r.get("item_code") and frappe.get_cached_value("Item", r.item_code, "is_stock_item"):
			r.warehouse = landing


def _company_cost_center(company: str) -> str | None:
	"""A non-group cost center that belongs to `company` (its default, else any
	leaf). Used so auto-created intercompany docs never inherit a cost center from
	another company (e.g. the user's Corporate cost center)."""
	cc = frappe.get_cached_value("Company", company, "cost_center")
	if cc and not frappe.get_cached_value("Cost Center", cc, "is_group"):
		return cc
	return frappe.db.get_value(
		"Cost Center", {"company": company, "is_group": 0, "disabled": 0}, "name"
	)


def _force_cost_center(target, cost_center: str | None) -> None:
	"""Set the cost center on every item (and tax) row so nothing inherits a
	cost center from a different company."""
	if not cost_center:
		return
	for r in target.get("items") or []:
		r.cost_center = cost_center
	for t in target.get("taxes") or []:
		if hasattr(t, "cost_center"):
			t.cost_center = cost_center


def process_sister_purchase(doc, method=None):
	"""Sales Invoice before_submit: orchestrate the intercompany transfer so the
	corporate company holds the sister's stock (at a discount) before it sells."""
	if not doc.get("azzir_buy_from_sister"):
		return
	# Idempotent: if we already built the chain for this invoice, do nothing.
	if doc.get("azzir_intercompany_purchase_invoice"):
		return

	corporate = doc.company
	sister = doc.get("azzir_supply_company")
	supply_wh = doc.get("azzir_supply_warehouse")
	if not sister or not supply_wh:
		frappe.throw(_("Select the Supply Company and the Supply Company Warehouse."))
	if sister == corporate:
		frappe.throw(_("The supply company must be a different (sister) company."))

	landing = _landing_warehouse(corporate, sister)
	if not landing:
		frappe.throw(
			_(
				"No warehouse in {0} is set to receive {1} stock. On a {0} warehouse, tick "
				"'Receives sister company stock' and set its Sister Company to {1}."
			).format(frappe.bold(corporate), frappe.bold(sister))
		)

	internal_customer = _internal_customer(corporate, sister)
	if not internal_customer:
		frappe.throw(
			_("No internal Customer represents {0} for company {1}. Create one (Is Internal Customer).").format(
				frappe.bold(corporate), frappe.bold(sister)
			)
		)
	internal_supplier = _internal_supplier(sister)
	if not internal_supplier:
		frappe.throw(
			_("No internal Supplier represents {0}. Create one in {1} (Is Internal Supplier).").format(
				frappe.bold(sister), frappe.bold(corporate)
			)
		)

	# ERPNext inter-company transactions require a price list enabled for BOTH
	# buying and selling (so the same list serves the sister SI and the corporate PI).
	ic_price_list = frappe.db.get_value(
		"Price List", {"enabled": 1, "selling": 1, "buying": 1}, "name"
	)
	if not ic_price_list:
		frappe.throw(
			_(
				"Intercompany transfers need a Price List with BOTH 'Buying' and 'Selling' "
				"enabled. Tick both on a Price List (e.g. Standard Selling) and retry."
			)
		)

	disc = flt(frappe.db.get_value("Company", corporate, "azzir_intercompany_discount"))
	factor = 1 - disc / 100.0

	lines = [r for r in (doc.get("items") or []) if r.get("item_code") and flt(r.get("qty")) > 0]
	if not lines:
		frappe.throw(_("Add at least one item before buying from a sister company."))

	sister_cc = _company_cost_center(sister)
	corporate_cc = _company_cost_center(corporate)

	# Build the intercompany documents as Administrator. The submitting user is
	# restricted (User Permission) to their own Corporate cost center, and ERPNext
	# would otherwise force THAT cost center onto the sister/corporate docs — which
	# belong to other companies — and reject them. Administrator has no such
	# restriction, so each doc keeps its own company's cost center.
	_prev_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		_build_intercompany_docs(doc, sister, supply_wh, landing, internal_customer,
		                         ic_price_list, factor, sister_cc, corporate_cc, lines)
	finally:
		frappe.set_user(_prev_user)

	# Point the corporate invoice's own rows at the landing warehouse, so it sells
	# (to the real customer, at full market rate) from the stock we just received.
	for r in lines:
		r.warehouse = landing


def _build_intercompany_docs(doc, sister, supply_wh, landing, internal_customer,
                             ic_price_list, factor, sister_cc, corporate_cc, lines):
	# 1) Sister Delivery Note — stock leaves the chosen sister warehouse.
	dn = frappe.new_doc("Delivery Note")
	dn.company = sister
	dn.customer = internal_customer
	dn.selling_price_list = ic_price_list
	dn.ignore_pricing_rule = 1
	dn.set_warehouse = supply_wh
	for r in lines:
		transfer_rate = flt(r.rate) * factor
		dn.append(
			"items",
			{
				"item_code": r.item_code,
				"qty": r.qty,
				"uom": r.get("uom"),
				"rate": transfer_rate,
				"price_list_rate": transfer_rate,
				"warehouse": supply_wh,
				"cost_center": sister_cc,
			},
		)
	_force_cost_center(dn, sister_cc)
	dn.flags.ignore_permissions = True
	dn.insert()
	dn.submit()

	# 2) Sister Sales Invoice from that Delivery Note (sister earns the 70%).
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice as _dn_to_si

	sister_si = _dn_to_si(dn.name)
	_force_cost_center(sister_si, sister_cc)
	sister_si.flags.ignore_permissions = True
	sister_si.insert()
	sister_si.submit()

	# 3) Corporate Purchase Invoice, linked to the sister SI, receiving stock into
	#    the landing warehouse at the same (already discounted) transfer price.
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
		make_inter_company_purchase_invoice,
	)

	pi = make_inter_company_purchase_invoice(sister_si.name)
	pi.update_stock = 1
	pi.set_warehouse = landing
	for r in pi.get("items") or []:
		r.warehouse = landing
	_force_cost_center(pi, corporate_cc)
	# Already priced at the transfer rate — don't let the receipt hook discount again.
	pi.flags.azzir_intercompany_priced = True
	pi.flags.ignore_permissions = True
	pi.insert()
	pi.submit()

	# Record the links on the corporate invoice (idempotency + audit trail).
	doc.azzir_intercompany_delivery_note = dn.name
	doc.azzir_intercompany_sister_invoice = sister_si.name
	doc.azzir_intercompany_purchase_invoice = pi.name
