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
def supply_warehouses(company: str | None = None, item_codes: list | str | None = None,
                      txt: str | None = None) -> list:
	"""Warehouses in the supply (sister) company that actually HOLD stock of the
	given item(s), with the total on-hand qty across those items. Used to fill the
	Supply Company Warehouse picker (sales frontend) with only stocked warehouses.
	Returns [{name, qty}] ordered by qty desc."""
	item_codes = frappe.parse_json(item_codes) if isinstance(item_codes, str) else (item_codes or [])
	item_codes = [c for c in item_codes if c]
	if not company:
		return []
	conds = ["b.actual_qty > 0", "w.company = %(co)s", "w.is_group = 0", "w.disabled = 0"]
	vals = {"co": company}
	if item_codes:
		conds.append("b.item_code in %(items)s")
		vals["items"] = tuple(item_codes)
	if txt:
		conds.append("b.warehouse like %(t)s")
		vals["t"] = "%%%s%%" % txt
	rows = frappe.db.sql(
		"select b.warehouse, sum(b.actual_qty) qty from `tabBin` b "
		"join `tabWarehouse` w on w.name = b.warehouse where "
		+ " and ".join(conds)
		+ " group by b.warehouse having qty > 0 order by qty desc limit 25",
		vals,
		as_dict=True,
	)
	return [
		{"name": r.warehouse, "qty": flt(r.qty), "label": "%s — %g in stock" % (r.warehouse, flt(r.qty))}
		for r in rows
	]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def supply_warehouse_link_query(doctype: str, txt: str, searchfield: str, start: int,
                                page_len: int, filters: dict | str | None) -> list:
	"""Desk link-field query for Supply Company Warehouse: only warehouses in the
	supply company that hold stock of the doc's items, showing the qty."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	rows = supply_warehouses(filters.get("company"), filters.get("item_codes"), txt)
	return [[r["name"], _("{0} in stock").format(r["qty"])] for r in rows]


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
	"""Sales Invoice validate: default each row's sister company/warehouse from the
	header, then point each stock row at the landing warehouse for ITS sister company
	(rows can be sourced from different sisters). Stock is transferred in at submit."""
	if not doc.get("azzir_buy_from_sister"):
		return
	default_company = doc.get("azzir_supply_company")
	default_wh = doc.get("azzir_supply_warehouse")
	landing_cache = {}
	for r in doc.get("items") or []:
		if not r.get("azzir_row_from_sister"):
			continue  # normal line — keep its own warehouse
		if not r.get("item_code") or not frappe.get_cached_value("Item", r.item_code, "is_stock_item"):
			continue
		# Default the row's source from the header when the row doesn't set its own.
		if not r.get("azzir_supply_company"):
			r.azzir_supply_company = default_company
		if not r.get("azzir_supply_warehouse") and r.get("azzir_supply_company") == default_company:
			r.azzir_supply_warehouse = default_wh
		sister = r.get("azzir_supply_company")
		if not sister:
			continue  # mandatory_depends_on on the header will prompt
		if sister not in landing_cache:
			lw = _landing_warehouse(doc.company, sister)
			if not lw:
				frappe.throw(
					_(
						"Configure a landing warehouse in {0} for sister company {1}: on a {0} "
						"warehouse tick 'Receives Sister Company Stock' and set its Sister Company to {1}."
					).format(frappe.bold(doc.company), frappe.bold(sister))
				)
			landing_cache[sister] = lw
		# The corporate row sells from the landing warehouse for its sister.
		r.warehouse = landing_cache[sister]


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


def _settlement(company: str) -> tuple:
	"""A (Mode of Payment, cash/bank Account) to auto-settle intercompany invoices
	in `company`. Returns (None, None) when the company has neither configured — in
	that case we leave the invoice outstanding rather than block the sale."""
	account = (
		frappe.get_cached_value("Company", company, "default_cash_account")
		or frappe.get_cached_value("Company", company, "default_bank_account")
		or frappe.db.get_value(
			"Account", {"company": company, "account_type": "Cash", "is_group": 0, "disabled": 0}, "name"
		)
		or frappe.db.get_value(
			"Account", {"company": company, "account_type": "Bank", "is_group": 0, "disabled": 0}, "name"
		)
	)
	mop = "Cash" if frappe.db.exists("Mode of Payment", "Cash") else frappe.db.get_value(
		"Mode of Payment", {"enabled": 1}, "name"
	)
	return (mop, account) if (mop and account) else (None, None)


def _mark_si_paid(si, company: str) -> None:
	"""Mark a (just-inserted, draft) Sales Invoice fully paid via its POS payment,
	so it submits as Paid (outstanding 0). No-op if the company has no cash account."""
	mop, account = _settlement(company)
	total = flt(si.rounded_total) or flt(si.grand_total)
	if not (mop and account) or total <= 0:
		return
	si.is_pos = 1
	si.flags.ignore_pos_profile = True
	si.set("payments", [])
	si.append("payments", {"mode_of_payment": mop, "amount": total, "account": account})
	si.flags.ignore_permissions = True
	si.save()


def _mark_pi_paid(pi, company: str) -> None:
	"""Mark a (just-inserted, draft) Purchase Invoice paid (Is Paid), so it submits
	as Paid (outstanding 0). No-op if the company has no cash account."""
	mop, account = _settlement(company)
	total = flt(pi.rounded_total) or flt(pi.grand_total)
	if not (mop and account) or total <= 0:
		return
	pi.is_paid = 1
	pi.mode_of_payment = mop
	pi.cash_bank_account = account
	pi.paid_amount = total
	pi.base_paid_amount = total * flt(pi.conversion_rate or 1)
	pi.flags.ignore_permissions = True
	pi.save()


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
	"""Sales Invoice before_submit: for each sister company sourced on the item
	rows, create one intercompany transfer (rows from the same sister share a
	transfer; different sisters get separate transfers)."""
	if not doc.get("azzir_buy_from_sister"):
		return
	# Idempotent: already built for this invoice.
	if doc.get("azzir_intercompany_done"):
		return

	corporate = doc.company

	# Group the SISTER-flagged stock rows by their sister company (defaulting to the
	# header). Rows not marked 'From Sister' are normal lines and left untouched.
	groups = {}
	for r in doc.get("items") or []:
		if not r.get("azzir_row_from_sister"):
			continue
		if not r.get("item_code") or flt(r.get("qty")) <= 0:
			continue
		if not frappe.get_cached_value("Item", r.item_code, "is_stock_item"):
			continue
		sister = r.get("azzir_supply_company") or doc.get("azzir_supply_company")
		if not sister:
			frappe.throw(_("Row #{0}: choose a Supply Company.").format(r.idx))
		if sister == corporate:
			frappe.throw(_("Row #{0}: the supply company must be a different (sister) company.").format(r.idx))
		wh = r.get("azzir_supply_warehouse") or doc.get("azzir_supply_warehouse")
		if not wh:
			frappe.throw(_("Row #{0}: choose a Supply Warehouse.").format(r.idx))
		groups.setdefault(sister, []).append((r, wh))
	if not groups:
		return  # header ticked but no row marked 'From Sister' — nothing to transfer

	# ERPNext requires an Unrealized Profit / Loss Account on every company involved.
	for co in [corporate, *groups]:
		if not frappe.db.get_value("Company", co, "unrealized_profit_loss_account"):
			frappe.throw(
				_(
					"Set the Unrealized Profit / Loss Account on company {0} "
					"(Company → Accounts) — it is required for intercompany transfers."
				).format(frappe.bold(co))
			)

	# ERPNext inter-company needs a Price List enabled for BOTH buying and selling.
	ic_price_list = frappe.db.get_value("Price List", {"enabled": 1, "selling": 1, "buying": 1}, "name")
	if not ic_price_list:
		frappe.throw(
			_(
				"Intercompany transfers need a Price List with BOTH 'Buying' and 'Selling' "
				"enabled. Tick both on a Price List (e.g. Standard Selling) and retry."
			)
		)

	factor = 1 - flt(frappe.db.get_value("Company", corporate, "azzir_intercompany_discount")) / 100.0
	corporate_cc = _company_cost_center(corporate)

	# Build everything as Administrator so the submitting user's own Cost Center
	# User Permission can't force a wrong-company cost center onto these docs.
	refs = []
	_prev_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		for sister, rows in groups.items():
			names = _build_one_transfer(doc, corporate, sister, rows, ic_price_list, factor, corporate_cc)
			refs.append("{0}: DN {1} / SI {2} / PI {3}".format(sister, *names))
			# Keep the single link fields populated with the first (or only) transfer.
			if not doc.get("azzir_intercompany_purchase_invoice"):
				doc.azzir_intercompany_delivery_note = names[0]
				doc.azzir_intercompany_sister_invoice = names[1]
				doc.azzir_intercompany_purchase_invoice = names[2]
	finally:
		frappe.set_user(_prev_user)

	doc.azzir_intercompany_done = 1
	doc.azzir_intercompany_refs = "\n".join(refs)


def _build_one_transfer(doc, corporate, sister, rows, ic_price_list, factor, corporate_cc):
	"""Create the DN + sister SI + corporate PI for one sister company. `rows` is a
	list of (corporate item row, sister supply warehouse). Returns (dn, si, pi)."""
	landing = _landing_warehouse(corporate, sister)
	if not landing:
		frappe.throw(
			_(
				"No warehouse in {0} is set to receive {1} stock. On a {0} warehouse tick "
				"'Receives Sister Company Stock' and set its Sister Company to {1}."
			).format(frappe.bold(corporate), frappe.bold(sister))
		)
	internal_customer = _internal_customer(corporate, sister)
	if not internal_customer:
		frappe.throw(
			_("No internal Customer represents {0} for company {1} (Is Internal Customer).").format(
				frappe.bold(corporate), frappe.bold(sister)
			)
		)
	internal_supplier = _internal_supplier(sister)
	if not internal_supplier:
		frappe.throw(
			_("No internal Supplier represents {0} in {1} (Is Internal Supplier).").format(
				frappe.bold(sister), frappe.bold(corporate)
			)
		)
	sister_cc = _company_cost_center(sister)

	# 1) Sister Delivery Note — stock leaves each row's sister warehouse.
	dn = frappe.new_doc("Delivery Note")
	dn.company = sister
	dn.customer = internal_customer
	dn.selling_price_list = ic_price_list
	dn.ignore_pricing_rule = 1
	for r, wh in rows:
		transfer_rate = flt(r.rate) * factor
		dn.append(
			"items",
			{
				"item_code": r.item_code,
				"qty": r.qty,
				"uom": r.get("uom"),
				"rate": transfer_rate,
				"price_list_rate": transfer_rate,
				"warehouse": wh,
				"cost_center": sister_cc,
			},
		)
	_force_cost_center(dn, sister_cc)
	dn.flags.ignore_permissions = True
	dn.insert()
	dn.submit()

	# Stamp each corporate item row with its sister Delivery Note (per row).
	for r, _wh in rows:
		if r.meta.has_field("azzir_sister_delivery_note"):
			r.azzir_sister_delivery_note = dn.name

	# 2) Sister Sales Invoice from that Delivery Note (sister earns the discounted price).
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice as _dn_to_si

	sister_si = _dn_to_si(dn.name)
	_force_cost_center(sister_si, sister_cc)
	sister_si.flags.ignore_permissions = True
	sister_si.insert()
	# Come in already paid (the sister has received the money from the corporate).
	_mark_si_paid(sister_si, sister)
	sister_si.submit()

	# 3) Corporate Purchase Invoice (update stock into the sister's landing warehouse).
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_inter_company_purchase_invoice

	pi = make_inter_company_purchase_invoice(sister_si.name)
	pi.update_stock = 1
	pi.set_warehouse = landing
	for r in pi.get("items") or []:
		r.warehouse = landing
	_force_cost_center(pi, corporate_cc)
	pi.flags.azzir_intercompany_priced = True
	pi.flags.ignore_permissions = True
	pi.insert()
	# Come in already paid (the corporate has paid the sister for the stock).
	_mark_pi_paid(pi, corporate)
	pi.submit()

	return (dn.name, sister_si.name, pi.name)
