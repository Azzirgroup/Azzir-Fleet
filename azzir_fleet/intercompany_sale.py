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


@frappe.whitelist()
def resolve_all_warehouses(item_code: str | None = None, group: str | None = None,
                           company: str | None = None) -> dict:
	"""Resolve a sales row's warehouse from the chosen "All Warehouses" group, following:
	  our group  ->  our own leaf with stock (use it, no sister)
	             ->  else sister GROUP with the SAME branch  ->  its child leaf with the
	                 most stock (the sister supply)  ->  back to OUR leaf: match the sister
	                 leaf's branch, else its name, else any leaf under our group.
	The returned `warehouse` is ALWAYS our own company's leaf (never the sister's — you
	can't put another company's warehouse on our document); the sister only supplies.
	Returns {warehouse, from_sister, supply_company, supply_warehouse} (empty if unusable)."""
	from azzir_fleet.item_codes import code_owner

	if not group or not company:
		return {}
	item = code_owner(item_code) or item_code
	grp = frappe.db.get_value(
		"Warehouse", group, ["lft", "rgt", "azzir_branch", "is_group"], as_dict=True
	)
	if not grp or grp.lft is None:
		return {}

	# Our own leaves under the picked group (for the map-back step).
	our_leaves = frappe.db.sql(
		"""select name, azzir_branch, warehouse_name from `tabWarehouse`
		   where company = %(co)s and is_group = 0 and disabled = 0
		     and lft >= %(l)s and rgt <= %(r)s order by name""",
		{"co": company, "l": grp.lft, "r": grp.rgt}, as_dict=True,
	)

	# 1) Prefer our OWN stock under this group — no sister needed.
	if item:
		own = _best_leaf_with_stock(item, company=company, lft=grp.lft, rgt=grp.rgt)
		if own:
			return {"warehouse": own.warehouse, "from_sister": 0}

	# 2) Sister GROUP(s) with the same branch as our group -> their child with most stock.
	sister_leaf = None
	if item and grp.azzir_branch:
		best_qty = -1.0
		for sg in frappe.get_all(
			"Warehouse",
			filters={"is_group": 1, "disabled": 0, "company": ["!=", company],
			         "azzir_branch": grp.azzir_branch},
			fields=["name", "lft", "rgt"],
		):
			cand = _best_leaf_with_stock(item, lft=sg.lft, rgt=sg.rgt, exclude_company=company)
			if cand and flt(cand.qty) > best_qty:
				best_qty, sister_leaf = flt(cand.qty), cand

	# 3) Map the sister leaf back to OUR leaf: by branch, else by name, else any of ours.
	our = None
	if sister_leaf and our_leaves:
		if sister_leaf.azzir_branch:
			our = next((l for l in our_leaves if l.azzir_branch == sister_leaf.azzir_branch), None)
		if not our:
			sn = (sister_leaf.warehouse_name or "").strip().lower()
			our = next((l for l in our_leaves if (l.warehouse_name or "").strip().lower() == sn), None)
	if not our and our_leaves:
		our = our_leaves[0]
	if not our:
		return {}

	if sister_leaf:
		return {
			"warehouse": our.name, "from_sister": 1,
			"supply_company": sister_leaf.company, "supply_warehouse": sister_leaf.warehouse,
		}
	return {"warehouse": our.name, "from_sister": 0}


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
	"""Sales Invoice before_submit: for each item row marked 'Buy From Sister Company',
	create one intercompany transfer (rows from the same sister share a transfer;
	different sisters get separate transfers). Rows not marked are normal lines."""
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
