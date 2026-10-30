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
def sister_default_for_item(item_code: str | None = None) -> dict:
	"""Default sister source for a line when 'From sister' is ticked, from Azzir Fleet
	Settings: the Default Company, and the leaf warehouse UNDER the Default (group)
	Warehouse — nested groups included — that holds the MOST stock of the item.
	Returns {supply_company, supply_warehouse, qty}; supply_warehouse is None when no
	child warehouse under the group has any stock. {} when nothing is configured."""
	if not item_code:
		return {}
	company = frappe.db.get_single_value("Azzir Fleet Settings", "azzir_default_company")
	group_wh = frappe.db.get_single_value("Azzir Fleet Settings", "azzir_default_warehouse")
	if not company or not group_wh:
		return {}
	bounds = frappe.db.get_value("Warehouse", group_wh, ["lft", "rgt"])
	if not bounds or bounds[0] is None:
		return {}
	lft, rgt = bounds
	# Best (most stock) LEAF warehouse anywhere under the group, in the default company.
	row = frappe.db.sql(
		"""select b.warehouse, sum(b.actual_qty) qty
		   from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		   where b.item_code = %(item)s and b.actual_qty > 0
		     and w.company = %(co)s and w.is_group = 0 and w.disabled = 0
		     and w.lft >= %(lft)s and w.rgt <= %(rgt)s
		   group by b.warehouse having qty > 0 order by qty desc limit 1""",
		{"item": item_code, "co": company, "lft": lft, "rgt": rgt},
		as_dict=True,
	)
	if not row:
		return {"supply_company": company, "supply_warehouse": None, "qty": 0}
	return {"supply_company": company, "supply_warehouse": row[0].warehouse, "qty": flt(row[0].qty)}


@frappe.whitelist()
def company_group_warehouses(txt: str | None = None, company: str | None = None) -> list:
	"""GROUP warehouses of `company` — the choices for the sales "All Warehouses" picker.
	The user picks one of their own company's groups; resolve_all_warehouses() then finds
	the concrete leaf (ours, or a branch-matched sister that holds the stock)."""
	if not company:
		return []
	conds = ["w.is_group = 1", "w.disabled = 0", "w.company = %(co)s"]
	vals = {"co": company}
	if txt:
		conds.append("(w.name like %(t)s or w.warehouse_name like %(t)s)")
		vals["t"] = "%%%s%%" % txt
	rows = frappe.db.sql(
		"select w.name, w.warehouse_name from `tabWarehouse` w where "
		+ " and ".join(conds) + " order by w.name limit 25",
		vals,
		as_dict=True,
	)
	return [{"name": r.name, "warehouse_name": r.warehouse_name} for r in rows]


def _best_leaf_with_stock(item, *, company=None, lft=None, rgt=None, branch=None, exclude_company=None):
	"""Leaf warehouse (most stock of `item`) under the given filters. Returns a row with
	warehouse/company/azzir_branch/warehouse_name/qty, or None."""
	conds = ["b.item_code = %(it)s", "b.actual_qty > 0", "w.is_group = 0", "w.disabled = 0"]
	vals = {"it": item}
	if company:
		conds.append("w.company = %(co)s"); vals["co"] = company
	if exclude_company:
		conds.append("w.company != %(xco)s"); vals["xco"] = exclude_company
	if lft is not None:
		conds.append("w.lft >= %(l)s and w.rgt <= %(r)s"); vals["l"], vals["r"] = lft, rgt
	if branch:
		conds.append("w.azzir_branch = %(br)s"); vals["br"] = branch
	rows = frappe.db.sql(
		"""select b.warehouse, w.company, w.azzir_branch, w.warehouse_name, sum(b.actual_qty) qty
		   from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		   where """ + " and ".join(conds) +
		" group by b.warehouse having qty > 0 order by qty desc limit 1",
		vals, as_dict=True,
	)
	return rows[0] if rows else None


def _sister_landings(company: str) -> dict:
	"""Sisters of `company` as {sister_company: landing_leaf}, derived from the landing
	warehouses configured IN `company` (a leaf tagged 'Receives Sister Company Stock' with
	its Sister Company). This is the reliable source of the sister relationship — it does
	not depend on branches being aligned across companies."""
	out = {}
	for w in frappe.get_all(
		"Warehouse",
		filters={"company": company, "azzir_is_sister_landing": 1, "is_group": 0, "disabled": 0},
		fields=["name", "azzir_sister_company"],
	):
		if w.azzir_sister_company and w.azzir_sister_company not in out:
			out[w.azzir_sister_company] = w.name
	return out


@frappe.whitelist()
def resolve_all_warehouses(item_code: str | None = None, group: str | None = None,
                           company: str | None = None) -> dict:
	"""Resolve a sales row's warehouse from the chosen "All Warehouses" pick:
	  1. our OWN stock (under the picked group if given, else anywhere in our company) -> use it;
	  2. else a SISTER company (identified by our landing-warehouse config, NOT branches) with
	     the most stock of the item -> From sister, supply = that sister leaf, and the row
	     warehouse = OUR landing warehouse for that sister (a warehouse we're allowed to use).
	     A branch that matches the picked group is preferred when present, but not required.
	The returned `warehouse` is ALWAYS one of our own company's warehouses (the landing);
	the sister only supplies. Returns {warehouse, from_sister, supply_company,
	supply_warehouse} (empty if nothing usable)."""
	from azzir_fleet.item_codes import code_owner

	if not company:
		return {}
	item = code_owner(item_code) or item_code
	grp = None
	if group:
		grp = frappe.db.get_value("Warehouse", group, ["lft", "rgt", "azzir_branch"], as_dict=True)

	# 1) Prefer our OWN stock (scoped to the picked group when one is given).
	if item:
		if grp and grp.lft is not None:
			own = _best_leaf_with_stock(item, company=company, lft=grp.lft, rgt=grp.rgt)
		else:
			own = _best_leaf_with_stock(item, company=company)
		if own:
			return {"warehouse": own.warehouse, "from_sister": 0}
	if not item:
		return {}

	# 2) Sister companies come from our landing config. For each, find its leaf with the most
	#    stock of the item — preferring a leaf under a group sharing the picked branch.
	landings = _sister_landings(company)
	if not landings:
		return {}
	branch = grp.azzir_branch if grp else None
	best = None
	for sister, landing in landings.items():
		cand = None
		if branch:
			for sg in frappe.get_all(
				"Warehouse",
				filters={"company": sister, "is_group": 1, "disabled": 0, "azzir_branch": branch},
				fields=["lft", "rgt"],
			):
				c = _best_leaf_with_stock(item, company=sister, lft=sg.lft, rgt=sg.rgt)
				if c and (cand is None or flt(c.qty) > flt(cand.qty)):
					cand = c
		if not cand:
			cand = _best_leaf_with_stock(item, company=sister)
		if cand and (best is None or flt(cand.qty) > flt(best["qty"])):
			best = {"sister": sister, "leaf": cand.warehouse, "qty": flt(cand.qty), "landing": landing}

	if not best:
		return {}
	return {
		"warehouse": best["landing"],  # our landing warehouse (permitted + set_landing agrees)
		"from_sister": 1,
		"supply_company": best["sister"],
		"supply_warehouse": best["leaf"],
	}


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
	"""The corporate LEAF warehouse configured to receive this sister's stock. Stock
	can't post to a group node, so if the only tagged landing is a Group we raise a
	clear message instead of ERPNext's cryptic 'Group node not allowed' error."""
	base = {
		"company": corporate_company,
		"azzir_is_sister_landing": 1,
		"azzir_sister_company": sister_company,
		"disabled": 0,
	}
	leaf = frappe.db.get_value("Warehouse", {**base, "is_group": 0}, "name")
	if leaf:
		return leaf
	grp = frappe.db.get_value("Warehouse", {**base, "is_group": 1}, "name")
	if grp:
		frappe.throw(
			_(
				"The landing warehouse {0} (for sister company {1}) is a Group — stock can't "
				"be received into a group node. Untick 'Is Group' on it, or tag a non-group "
				"(leaf) warehouse as 'Receives Sister Company Stock' for {1} instead."
			).format(frappe.bold(grp), frappe.bold(sister_company))
		)
	return None


def set_landing_warehouse(doc, method=None):
	"""Validate: for each item row marked 'Buy From Sister Company', point the row at
	the landing warehouse for ITS sister company (rows can be sourced from different
	sisters). Stock is transferred in at submit. Driven entirely per row — there is
	no header toggle.

	A Quotation posts no stock and creates no sister transfer, so it needs no landing
	warehouse — skip it entirely (the row keeps whatever warehouse was chosen, e.g. the
	'All Warehouses' pick). The landing requirement only applies where stock moves
	(Sales Invoice).

	Zero-config: if no warehouse in the selling company is tagged to receive this sister's
	stock, we DON'T block — the row keeps its own resolved warehouse (the 'All Warehouses'
	pick), and the transfer lands there. A tagged landing warehouse still wins when set."""
	if doc.doctype == "Quotation":
		return
	landing_cache = {}
	for r in doc.get("items") or []:
		if not r.get("azzir_row_from_sister"):
			continue  # normal line — keep its own warehouse
		if not r.get("item_code") or not frappe.get_cached_value("Item", r.item_code, "is_stock_item"):
			continue
		sister = r.get("azzir_supply_company")
		if not sister:
			continue  # process_sister_purchase throws for this at submit
		if sister not in landing_cache:
			landing_cache[sister] = _landing_warehouse(doc.company, sister)
		# A tagged landing warehouse wins; otherwise keep the row's own warehouse
		# (zero-config fallback — the sister stock lands in the row's resolved warehouse).
		if landing_cache[sister]:
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
	def _usable(acc):
		# An account with balance_must_be = Debit/Credit rejects a settlement posting
		# in the wrong direction (e.g. "Petty Cash must always be Debit" when we credit
		# it to pay a bill). Skip such accounts so the sale isn't blocked.
		return bool(acc) and not frappe.db.get_value("Account", acc, "balance_must_be")

	account = None
	for cand in (
		frappe.get_cached_value("Company", company, "default_cash_account"),
		frappe.get_cached_value("Company", company, "default_bank_account"),
	):
		if _usable(cand):
			account = cand
			break
	if not account:
		for acc in frappe.get_all(
			"Account",
			filters={"company": company, "account_type": ["in", ["Cash", "Bank"]], "is_group": 0, "disabled": 0},
			pluck="name",
		):
			if _usable(acc):
				account = acc
				break
	mop = "Cash" if frappe.db.exists("Mode of Payment", "Cash") else frappe.db.get_value(
		"Mode of Payment", {"enabled": 1}, "name"
	)
	# No unconstrained cash/bank account -> leave the internal invoice outstanding
	# (a normal intercompany receivable/payable) instead of failing the whole sale.
	return (mop, account) if (mop and account) else (None, None)


def _mark_si_paid(si, company: str) -> None:
	"""Mark a (just-inserted, draft) Sales Invoice fully paid via its POS payment,
	so it submits as Paid (outstanding 0). No-op if the company has no cash account.
	Also used for a RETURN Sales Invoice (negative total) -- a negative POS payment
	correctly nets its outstanding to 0, so only an exact-zero total is skipped."""
	mop, account = _settlement(company)
	total = flt(si.rounded_total) or flt(si.grand_total)
	if not (mop and account) or total == 0:
		return
	si.is_pos = 1
	si.flags.ignore_pos_profile = True
	si.set("payments", [])
	si.append("payments", {"mode_of_payment": mop, "amount": total, "account": account})
	si.flags.ignore_permissions = True
	si.save()


def _mark_pi_paid(pi, company: str) -> None:
	"""Mark a (just-inserted, draft) Purchase Invoice paid (Is Paid), so it submits
	as Paid (outstanding 0). No-op if the company has no cash account. Also used for
	a RETURN Purchase Invoice (negative total) -- only an exact-zero total is skipped."""
	mop, account = _settlement(company)
	total = flt(pi.rounded_total) or flt(pi.grand_total)
	if not (mop and account) or total == 0:
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
	"""Sales Invoice before_submit: for each item row marked 'Buy From Sister Company',
	create one intercompany transfer (rows from the same sister share a transfer;
	different sisters get separate transfers). Rows not marked are normal lines.

	A RETURN (Credit Note) against a sister-sourced sale does NOT reverse anything
	here -- a Credit Note has no physical stock to send back yet (update_stock=0;
	the actual return happens via a separate return Delivery Note). See
	process_sister_return_delivery() for where that reversal actually runs."""
	if doc.is_return:
		return

	# Idempotent: already built for this invoice.
	if doc.get("azzir_intercompany_done"):
		return

	corporate = doc.company

	# Group the sister-flagged stock rows by their sister company.
	groups = {}
	for r in doc.get("items") or []:
		if not r.get("azzir_row_from_sister"):
			continue
		if not r.get("item_code") or flt(r.get("qty")) <= 0:
			continue
		if not frappe.get_cached_value("Item", r.item_code, "is_stock_item"):
			continue
		sister = r.get("azzir_supply_company")
		if not sister:
			frappe.throw(_("Row #{0}: choose a Supply Company.").format(r.idx))
		if sister == corporate:
			frappe.throw(_("Row #{0}: the supply company must be a different (sister) company.").format(r.idx))
		wh = r.get("azzir_supply_warehouse")
		if not wh:
			frappe.throw(_("Row #{0}: choose a Supply Warehouse.").format(r.idx))
		groups.setdefault(sister, []).append((r, wh))
	if not groups:
		return  # no row marked 'Buy From Sister Company' — nothing to transfer

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
	# Tagged landing warehouse (controlled); when none is set we fall back per row to the
	# corporate row's OWN warehouse (the 'All Warehouses' pick) — zero-config.
	landing = _landing_warehouse(corporate, sister)
	receiving = []  # per-row corporate warehouse the transferred stock lands in
	for r, _wh in rows:
		wh = landing or r.get("warehouse")
		if not wh:
			frappe.throw(
				_(
					"No receiving warehouse for {1} stock in {0}: either set a warehouse on the "
					"line, or on a {0} warehouse tick 'Receives Sister Company Stock' for {1}."
				).format(frappe.bold(corporate), frappe.bold(sister))
			)
		receiving.append(wh)
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
	if dn.meta.has_field("azzir_apply_vat"):
		dn.azzir_apply_vat = 0  # intercompany transfer — no VAT
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
	if sister_si.meta.has_field("azzir_apply_vat"):
		sister_si.azzir_apply_vat = 0  # intercompany transfer — no VAT
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
	# Intercompany transfer — no VAT on the corporate Purchase Invoice either.
	pi.set("taxes", [])
	if pi.meta.has_field("taxes_and_charges"):
		pi.taxes_and_charges = None
	pi.set_warehouse = landing or receiving[0]
	pi_items = pi.get("items") or []
	for idx, pir in enumerate(pi_items):
		pir.warehouse = landing or (receiving[idx] if idx < len(receiving) else receiving[-1])
	_force_cost_center(pi, corporate_cc)
	pi.flags.azzir_intercompany_priced = True
	pi.flags.ignore_permissions = True
	pi.insert()
	# Come in already paid (the corporate has paid the sister for the stock).
	_mark_pi_paid(pi, corporate)
	pi.submit()

	return (dn.name, sister_si.name, pi.name)


def process_sister_return_delivery(doc, method=None):
	"""Delivery Note on_submit: when a RETURN delivery note (reversing a customer's
	original delivery) is submitted, the physical stock is now ACTUALLY back in our
	landing warehouse -- only at this point can the matching sister transfer be
	reversed: stock sent back to the sister, both sides refunded, and a true-up for
	any valuation drift. This deliberately runs here rather than on the Credit
	Note's own submit, since a Credit Note (update_stock=0) never has physical stock
	to send back -- that only exists once this return delivery actually posts.

	A plain return (never sister-sourced, or nothing recorded to trace it to a
	completed transfer) is left alone -- it returns exactly like an ordinary
	delivery always has, with no extra documents created."""
	if not doc.is_return or not doc.return_against:
		return
	if doc.get("azzir_intercompany_return_done"):
		return

	# Trace back: this return's original Delivery Note -> the Sales Invoice(s) it
	# was created from (against_sales_invoice, set by ERPNext's own SI->DN mapper)
	# -> whichever of THOSE rows were sister-sourced.
	orig_rows = frappe.db.sql(
		"select item_code, against_sales_invoice from `tabDelivery Note Item` where parent=%s",
		(doc.return_against,),
		as_dict=True,
	)
	si_names = {r.against_sales_invoice for r in orig_rows if r.against_sales_invoice}
	if not si_names:
		return  # this delivery was never made from a Sales Invoice -- nothing to trace

	sister_dn_by_item = {}
	for si_name in si_names:
		rows = frappe.db.sql(
			"select item_code, azzir_row_from_sister, azzir_sister_delivery_note "
			"from `tabSales Invoice Item` where parent=%s",
			(si_name,),
			as_dict=True,
		)
		for r in rows:
			if r.azzir_row_from_sister and r.azzir_sister_delivery_note:
				sister_dn_by_item[r.item_code] = r.azzir_sister_delivery_note

	if not sister_dn_by_item:
		return  # the original sale wasn't sister-sourced -- an ordinary return

	# Group the returned qty by the sister Delivery Note it should reverse against --
	# everything sourced from the same original transfer reverses together.
	groups: dict[str, dict[str, float]] = {}
	for row in doc.get("items") or []:
		dn_name = sister_dn_by_item.get(row.item_code)
		if not dn_name:
			continue
		qty = abs(flt(row.qty))
		if qty <= 0:
			continue
		groups.setdefault(dn_name, {})
		groups[dn_name][row.item_code] = groups[dn_name].get(row.item_code, 0) + qty

	if not groups:
		return

	refs = []
	_prev_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		for dn_name, item_qtys in groups.items():
			result = _reverse_one_transfer(dn_name, item_qtys)
			if result is None:
				# The original transfer never fully completed (e.g. the sister's own
				# invoice was left as a draft) -- nothing to auto-reverse. Don't block
				# the return itself; it just proceeds as an ordinary return, flagged
				# here for manual follow-up on the sister company's side.
				refs.append(
					"DN {0}: could NOT auto-reverse -- the original sister transfer "
					"never fully completed. Stock was returned normally; the sister "
					"company's side needs manual review.".format(dn_name)
				)
				continue
			ret_dn, ret_si, ret_pi, true_up_je = result
			line = "reverses DN {0}: return DN {1} / return SI {2} / return PI {3}".format(
				dn_name, ret_dn, ret_si, ret_pi
			)
			if true_up_je:
				line += " / valuation true-up JE {0}".format(true_up_je)
			refs.append(line)
	finally:
		frappe.set_user(_prev_user)

	refs_text = "\n".join(refs)

	if doc.meta.has_field("azzir_intercompany_return_done"):
		doc.db_set("azzir_intercompany_return_done", 1, update_modified=False)
		doc.db_set("azzir_intercompany_return_refs", refs_text, update_modified=False)

	# Best-effort: also mirror onto the matching Credit Note, for visibility where
	# users already look for this.
	for si_name in si_names:
		credit_note = frappe.db.get_value(
			"Sales Invoice", {"is_return": 1, "return_against": si_name}, "name"
		)
		if credit_note:
			frappe.db.set_value(
				"Sales Invoice",
				credit_note,
				{"azzir_intercompany_return_done": 1, "azzir_intercompany_return_refs": refs_text},
			)


def _reverse_one_transfer(dn_name: str, item_qtys: dict) -> tuple | None:
	"""Reverse the given quantities of one original sister transfer: a return
	Delivery Note (stock back into the sister's supply warehouse), the matching
	return Sales Invoice / Credit Note in the sister (against their original SI),
	and the matching return Purchase Invoice in the corporate company (against its
	original PI, reversing stock out of the landing warehouse). Returns (dn, si, pi,
	true_up_je) names of the new documents, or None if the original transfer never
	fully completed (its sister invoice was never submitted, or no Purchase Invoice
	was ever created for it) -- there's nothing to auto-reverse in that case; the
	caller lets the return proceed as an ordinary one instead of blocking on it."""
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	sister_si_name = frappe.db.get_value("Sales Invoice Item", {"delivery_note": dn_name}, "parent")
	if not sister_si_name or frappe.db.get_value("Sales Invoice", sister_si_name, "docstatus") != 1:
		return None
	corporate_pi_name = frappe.db.get_value(
		"Purchase Invoice", {"inter_company_invoice_reference": sister_si_name, "docstatus": 1}, "name"
	)
	if not corporate_pi_name:
		return None

	sister_company = frappe.db.get_value("Delivery Note", dn_name, "company")
	corporate_company = frappe.db.get_value("Purchase Invoice", corporate_pi_name, "company")

	# 1) Return Delivery Note -- stock goes back into the sister's supply warehouse.
	dn_return = make_return_doc("Delivery Note", dn_name)
	_trim_to_returned_qty(dn_return, item_qtys)
	dn_return.flags.ignore_permissions = True
	dn_return.insert()
	dn_return.submit()

	# 2) Return Sales Invoice / Credit Note in the sister, against their original SI.
	si_return = make_return_doc("Sales Invoice", sister_si_name)
	_trim_to_returned_qty(si_return, item_qtys)
	si_return.flags.ignore_permissions = True
	si_return.insert()
	_mark_si_paid(si_return, sister_company)  # refund the sister's cash/bank
	si_return.submit()

	# 3) Return Purchase Invoice in the corporate company, against its original PI --
	#    reverses stock out of the landing warehouse and the amount paid to the sister.
	#    NOTE: ERPNext ALWAYS revalues a stock-updating return at the warehouse's
	#    current moving-average/FIFO cost (hardcoded for every return, for correct
	#    COGS) -- this return's amount can differ from the original transfer price
	#    if other stock has moved through that warehouse since. _true_up_return_
	#    valuation_gap() below corrects for that against the Unrealized P/L account.
	pi_return = make_return_doc("Purchase Invoice", corporate_pi_name)
	_trim_to_returned_qty(pi_return, item_qtys)
	pi_return.flags.ignore_permissions = True
	pi_return.insert()
	_mark_pi_paid(pi_return, corporate_company)  # refund the corporate's cash/bank
	pi_return.submit()
	pi_return.reload()
	# A stock-updating return's `rate` gets recalculated across several internal
	# passes (insert, the settlement save, submit); outstanding_amount can be left
	# over from an earlier pass even though it's genuinely fully settled -- the
	# Payment Ledger / GL Entries are the source of truth and already net to zero.
	# Force the cached field back in line rather than leave a cosmetically "unpaid"
	# document that the ledger itself doesn't agree with.
	if pi_return.is_paid and flt(pi_return.outstanding_amount) != 0:
		pi_return.db_set("outstanding_amount", 0, update_modified=False)

	true_up_je = _true_up_return_valuation_gap(pi_return, si_return, corporate_company)

	return (dn_return.name, si_return.name, pi_return.name, true_up_je)


def _true_up_return_valuation_gap(pi_return, si_return, corporate_company: str) -> str | None:
	"""A stock-updating Purchase Invoice return is ALWAYS revalued by ERPNext at the
	warehouse's current moving-average/FIFO cost (hardcoded for every return, for
	correct COGS) -- it can't be pinned to the original intercompany transfer price.
	The sister's credit note (Delivery Note / Sales Invoice side) has no such
	revaluation and DOES settle at the original transfer price. True up the gap
	between the two with a Journal Entry in the corporate company, against its
	Unrealized Profit / Loss account (the same account every intercompany transfer
	already requires -- exactly what it's for), so the two companies' books net to
	zero after a return regardless of valuation drift. Returns the Journal Entry
	name, or None if there was nothing material to true up."""
	intended = abs(flt(si_return.grand_total))
	actual = abs(flt(pi_return.grand_total))
	gap = flt(intended - actual, 2)
	if abs(gap) < 0.01:
		return None

	mop, account = _settlement(corporate_company)
	if not account:
		return None  # no cash/bank account configured -- nothing to true up against
	unrealized = frappe.get_cached_value("Company", corporate_company, "unrealized_profit_loss_account")
	cc = _company_cost_center(corporate_company)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = corporate_company
	je.posting_date = frappe.utils.nowdate()
	je.user_remark = _(
		"True-up for return of sister-sourced stock ({0}): the stock-valuation-based "
		"refund ({1}) differs from the original transfer-price refund ({2}) the sister "
		"actually credited back."
	).format(pi_return.name, actual, intended)

	cash_row = {"account": account, "cost_center": cc}
	pl_row = {"account": unrealized, "cost_center": cc}
	if gap > 0:
		# Corporate's own books under-recognized the cash refund -- bring it up to
		# the full amount the sister actually credited back.
		cash_row["debit_in_account_currency"] = gap
		pl_row["credit_in_account_currency"] = gap
	else:
		# Corporate's valuation-based refund OVER-recognized cash vs. what the
		# sister actually sent back -- bring it back down.
		cash_row["credit_in_account_currency"] = -gap
		pl_row["debit_in_account_currency"] = -gap

	je.append("accounts", cash_row)
	je.append("accounts", pl_row)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


def process_sister_sale_cancel_predelete(doc, method=None):
	"""Sales Invoice before_cancel: when a sister-sourced sale is being CANCELLED
	(voided as a mistake, as opposed to returned via a Credit Note), cancel any
	submitted customer Delivery Note(s) made from it FIRST. Frappe blocks cancelling
	an invoice while a submitted Delivery Note still references it, and that check
	runs AFTER on_cancel hooks fire -- clearing the Delivery Note here, in
	before_cancel, lets a single "Cancel" on the Sales Invoice undo the whole sale in
	one step instead of forcing the user to cancel the Delivery Note separately first.

	Only acts on sister-sourced sales (azzir_intercompany_done) -- an ordinary sale's
	Delivery Note is left exactly as Frappe already requires (cancel it yourself)."""
	if not doc.get("azzir_intercompany_done"):
		return
	dn_names = frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_invoice": doc.name},
		pluck="parent",
		distinct=True,
	)
	for dn_name in dn_names:
		if frappe.db.get_value("Delivery Note", dn_name, "docstatus") == 1:
			dn = frappe.get_doc("Delivery Note", dn_name)
			dn.flags.ignore_permissions = True
			dn.cancel()


def process_sister_sale_cancel(doc, method=None):
	"""Sales Invoice on_cancel: when a sister-sourced sale is cancelled (voided, not
	returned), automatically cancel the whole chain it created -- the corporate
	Purchase Invoice, the sister's own Sales Invoice, and the sister Delivery Note --
	undoing the transfer as if it had never happened. Covers BOTH real-world cases:
	stock that was already delivered to the customer (its Delivery Note was cancelled
	just above, in before_cancel) and stock still sitting, undelivered, in the
	landing warehouse (nothing else to cancel first) -- either way it all goes back
	to the sister. Idempotent and safe to re-run; anything already cancelled is
	skipped."""
	if not doc.get("azzir_intercompany_done"):
		return
	if doc.get("azzir_intercompany_cancel_done"):
		return

	sister_dns = {
		r.azzir_sister_delivery_note
		for r in doc.get("items") or []
		if r.get("azzir_row_from_sister") and r.get("azzir_sister_delivery_note")
	}
	if not sister_dns:
		return

	refs = []
	_prev_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		for dn_name in sister_dns:
			result = _cancel_one_transfer(dn_name)
			if result is None:
				refs.append(
					"DN {0}: nothing left to cancel (already cancelled, or the original "
					"transfer never fully completed).".format(dn_name)
				)
				continue
			sister_si_name, corporate_pi_name = result
			refs.append(
				"cancelled sister DN {0}: sister SI {1} / corporate PI {2}".format(
					dn_name, sister_si_name, corporate_pi_name
				)
			)
	finally:
		frappe.set_user(_prev_user)

	refs_text = "\n".join(refs)
	if doc.meta.has_field("azzir_intercompany_cancel_done"):
		doc.db_set("azzir_intercompany_cancel_done", 1, update_modified=False)
		doc.db_set("azzir_intercompany_cancel_refs", refs_text, update_modified=False)


def _cancel_one_transfer(dn_name: str) -> tuple | None:
	"""Cancel one completed sister transfer's chain -- the corporate Purchase
	Invoice, then the sister Sales Invoice, then the sister Delivery Note -- in that
	strict reverse order, the only order Frappe's own link-dependency checks allow
	(each step is still referenced by the one before it until it's gone). Skips
	anything already cancelled. Returns (sister_si, corporate_pi) names, or None if
	there was nothing submitted left to cancel."""
	sister_si_name = frappe.db.get_value("Sales Invoice Item", {"delivery_note": dn_name}, "parent")
	corporate_pi_name = (
		frappe.db.get_value(
			"Purchase Invoice",
			{"inter_company_invoice_reference": sister_si_name, "docstatus": 1},
			"name",
		)
		if sister_si_name
		else None
	)

	cancelled_anything = False

	if corporate_pi_name:
		pi = frappe.get_doc("Purchase Invoice", corporate_pi_name)
		pi.flags.ignore_permissions = True
		pi.cancel()
		cancelled_anything = True

	if sister_si_name and frappe.db.get_value("Sales Invoice", sister_si_name, "docstatus") == 1:
		sister_si = frappe.get_doc("Sales Invoice", sister_si_name)
		sister_si.flags.ignore_permissions = True
		sister_si.cancel()
		cancelled_anything = True

	if frappe.db.get_value("Delivery Note", dn_name, "docstatus") == 1:
		dn = frappe.get_doc("Delivery Note", dn_name)
		dn.flags.ignore_permissions = True
		dn.cancel()
		cancelled_anything = True

	if not cancelled_anything:
		return None
	return (sister_si_name or "-", corporate_pi_name or "-")


def _trim_to_returned_qty(return_doc, item_qtys: dict) -> None:
	"""make_return_doc mirrors EVERY row of the source document, negated at its full
	original quantity. Keep only the rows actually being returned, and scale each
	down to the quantity actually returned (a partial return may cover less than the
	original transfer did)."""
	kept = []
	for row in return_doc.items:
		wanted = item_qtys.get(row.item_code)
		if not wanted:
			continue
		row.qty = -wanted  # row.qty mirrors the source negated; wanted is already positive
		# Purchase Invoice Item requires received_qty == qty + rejected_qty; both are
		# mirrored from the source's full (untrimmed) quantity. Reset them so
		# validate_accepted_rejected_qty's own auto-fill sets received_qty = qty.
		if row.meta.has_field("received_qty"):
			row.received_qty = 0
		if row.meta.has_field("rejected_qty"):
			row.rejected_qty = 0
		kept.append(row)
	return_doc.items = kept

	# The source doc was auto-settled (_mark_si_paid / _mark_pi_paid), so
	# make_return_doc also mirrors ITS full-amount payment/paid-amount fields --
	# stale now that items are trimmed to a (possibly partial) returned amount.
	# Clear them here so insert()'s own validation doesn't choke on the mismatch;
	# _mark_si_paid / _mark_pi_paid re-settle correctly right after, against the
	# freshly recalculated (trimmed) total.
	if return_doc.meta.has_field("payments"):
		return_doc.set("payments", [])
		if return_doc.meta.has_field("is_pos"):
			return_doc.is_pos = 0
	if return_doc.meta.has_field("is_paid"):
		return_doc.is_paid = 0
		return_doc.paid_amount = 0
		return_doc.base_paid_amount = 0
