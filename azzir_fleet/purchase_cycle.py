# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Purchase cycle — buy for another (internal) company.

Mirror of the sell-from-sister flow, for buying. A Purchase Order (and the
Purchase Receipt / Purchase Invoice it becomes) can carry, PER ROW, a Target
Company + Target Warehouse. They are only meaningful when the target company is a
DIFFERENT internal company than the one doing the buying — a same-company target
needs nothing here, ERPNext receives straight into the row's warehouse.

When the stock-moving document is submitted (a Purchase Receipt, or a Purchase
Invoice with Update Stock), for every row whose Target Company differs from the
buying company we automatically, inside the same transaction:

  1. create + submit a Delivery Note in the BUYING company that ships the just-
     received stock (from the row's warehouse) to an internal Customer that
     represents the target company, at cost (valuation rate); and
  2. create + submit the linked inter-company Purchase Receipt in the TARGET
     company, receiving the stock into the row's Target Warehouse.

Rows are grouped by target company, so buying for two different companies on one
document produces one transfer chain each.
"""

import frappe
from frappe import _
from frappe.utils import flt

from azzir_fleet.intercompany_sale import (
	_company_cost_center,
	_force_cost_center,
	_internal_customer,
	_internal_supplier,
)


def _linked_source_row(r):
	"""The source item row a PR/PI row was mapped from, so the target fields carry
	PO -> PR -> PI even though ERPNext's mapper doesn't copy custom fields."""
	if r.get("purchase_order_item"):
		dt, name = "Purchase Order Item", r.purchase_order_item
	elif r.get("pr_detail"):
		dt, name = "Purchase Receipt Item", r.pr_detail
	elif r.get("po_detail"):
		dt, name = "Purchase Order Item", r.po_detail
	else:
		return None
	if not frappe.get_meta(dt).has_field("azzir_row_to_target"):
		return None
	return frappe.db.get_value(
		dt, name, ["azzir_row_to_target", "azzir_target_company", "azzir_target_warehouse"], as_dict=True
	)


def default_target_rows(doc, method=None):
	"""PO / PR / PI validate: carry the per-row target fields from the linked source
	document row (PO -> PR -> PI), since ERPNext's mapper doesn't copy custom fields.
	The trigger is per row (azzir_row_to_target) — there is no header default."""
	for r in doc.get("items") or []:
		if r.get("azzir_row_to_target"):
			continue  # already set on this row
		src = _linked_source_row(r)
		if src and src.get("azzir_row_to_target"):
			r.azzir_row_to_target = 1
			r.azzir_target_company = src.get("azzir_target_company")
			r.azzir_target_warehouse = src.get("azzir_target_warehouse")


def process_target_transfer(doc, method=None):
	"""PR on_submit (and PI on_submit when Update Stock): for each row marked 'Buy For
	Target Company' whose target is a different internal company, ship the received
	stock there. Rows not marked are normal purchase lines."""
	# A Purchase Invoice only moves stock when it updates stock itself.
	if doc.doctype == "Purchase Invoice" and not doc.get("update_stock"):
		return
	if doc.get("azzir_target_done"):
		return

	source_company = doc.company
	groups = {}
	for r in doc.get("items") or []:
		if not r.get("azzir_row_to_target"):
			continue  # normal purchase line
		tc = r.get("azzir_target_company")
		if not tc:
			frappe.throw(_("Row #{0}: set a Target Company (or untick 'Buy For Target Company').").format(r.idx))
		if tc == source_company:
			continue  # same company — normal ERPNext receipt, nothing to transfer
		if not r.get("item_code") or flt(r.get("qty")) <= 0:
			continue
		if not frappe.get_cached_value("Item", r.item_code, "is_stock_item"):
			continue
		tw = r.get("azzir_target_warehouse")
		if not tw:
			frappe.throw(_("Row #{0}: set a Target Warehouse in {1}.").format(r.idx, frappe.bold(tc)))
		if frappe.get_cached_value("Warehouse", tw, "company") != tc:
			frappe.throw(
				_("Row #{0}: Target Warehouse {1} does not belong to {2}.").format(
					r.idx, frappe.bold(tw), frappe.bold(tc)
				)
			)
		groups.setdefault(tc, []).append((r, tw))

	if not groups:
		return

	# ERPNext inter-company needs an Unrealized Profit/Loss account on every company.
	for co in [source_company, *groups]:
		if not frappe.db.get_value("Company", co, "unrealized_profit_loss_account"):
			frappe.throw(
				_(
					"Set the Unrealized Profit / Loss Account on company {0} "
					"(Company → Accounts) — it is required for inter-company transfers."
				).format(frappe.bold(co))
			)
	ic_price_list = frappe.db.get_value("Price List", {"enabled": 1, "selling": 1, "buying": 1}, "name")
	if not ic_price_list:
		frappe.throw(
			_(
				"Inter-company transfers need a Price List with BOTH 'Buying' and 'Selling' "
				"enabled. Tick both on a Price List (e.g. Standard Selling) and retry."
			)
		)

	refs = []
	prev_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		for target_company, rows in groups.items():
			dn, pr = _build_target_transfer(doc, source_company, target_company, rows, ic_price_list)
			refs.append("{0}: DN {1} / PR {2}".format(target_company, dn, pr))
	finally:
		frappe.set_user(prev_user)

	doc.db_set("azzir_target_done", 1)
	doc.db_set("azzir_target_refs", "\n".join(refs))


def _build_target_transfer(doc, source_company, target_company, rows, ic_price_list):
	"""Ship `rows` (each (item row, target warehouse)) from the buying company to the
	target company via a Delivery Note + inter-company Purchase Receipt. Returns the
	(delivery note, purchase receipt) names."""
	internal_customer = _internal_customer(target_company, source_company)
	if not internal_customer:
		frappe.throw(
			_(
				"No internal Customer represents {0} for company {1}. Create a Customer with "
				"'Is Internal Customer', Represents Company {0}, and {1} under Allowed To Transact With."
			).format(frappe.bold(target_company), frappe.bold(source_company))
		)
	internal_supplier = _internal_supplier(source_company)
	if not internal_supplier:
		frappe.throw(
			_(
				"No internal Supplier represents {0} (needed in {1}). Create a Supplier with "
				"'Is Internal Supplier' and Represents Company {0}."
			).format(frappe.bold(source_company), frappe.bold(target_company))
		)
	source_cc = _company_cost_center(source_company)
	target_cc = _company_cost_center(target_company)

	# 1) Delivery Note in the buying company — ships the received stock out at cost.
	dn = frappe.new_doc("Delivery Note")
	dn.company = source_company
	dn.customer = internal_customer
	dn.selling_price_list = ic_price_list
	dn.ignore_pricing_rule = 1
	target_whs = []
	for r, tw in rows:
		rate = flt(r.get("valuation_rate")) or flt(r.get("rate"))
		dn.append(
			"items",
			{
				"item_code": r.item_code,
				"qty": r.qty,
				"uom": r.get("uom"),
				"rate": rate,
				"price_list_rate": rate,
				"warehouse": r.get("warehouse"),
				"cost_center": source_cc,
			},
		)
		target_whs.append(tw)
	_force_cost_center(dn, source_cc)
	dn.flags.ignore_permissions = True
	dn.insert()
	dn.submit()

	# 2) Inter-company Purchase Receipt in the target company — receives into each
	#    row's target warehouse.
	from erpnext.stock.doctype.delivery_note.delivery_note import make_inter_company_purchase_receipt

	pr = make_inter_company_purchase_receipt(dn.name)
	pr.company = target_company
	for i, pri in enumerate(pr.get("items") or []):
		if i < len(target_whs):
			pri.warehouse = target_whs[i]
	_force_cost_center(pr, target_cc)
	# Already priced at cost (the DN rate) — don't let the receiving company's
	# intercompany discount reduce it again.
	pr.flags.azzir_intercompany_priced = True
	pr.flags.ignore_permissions = True
	pr.insert()
	pr.submit()

	return (dn.name, pr.name)
